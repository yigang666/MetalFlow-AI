"""Parser and duplicate-matching checks using synthetic Excel workbooks."""

from io import BytesIO
from xml.etree.ElementTree import fromstring
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.crm_import import (
    COLUMNS,
    DOCUMENT_REL_NS,
    MAX_DATA_ROWS,
    MAX_XML_BYTES,
    PACKAGE_REL_NS,
    SPREADSHEET_NS,
    ImportInputError,
    _classify_rows,
    _identity_keys,
    _read_rows,
    parse_workbook,
)


def make_xlsx(
    rows: list[tuple[str | int, ...]],
    *,
    columns: tuple[str, ...] = COLUMNS,
    sheet_name: str = "Customers",
) -> bytes:
    """Build a portable synthetic workbook without third-party writers."""
    sheet_rows = []
    for row_number, fields in enumerate([columns, *rows], 1):
        cells = []
        for column_index, value in enumerate(fields):
            reference = f"{chr(65 + column_index)}{row_number}"
            if isinstance(value, str):
                cells.append(
                    f'<c r="{reference}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
                )
            else:
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    content_types = """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
        <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
        <Default Extension="xml" ContentType="application/xml"/>
        <Override PartName="/xl/workbook.xml"
                  ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
        <Override PartName="/xl/worksheets/sheet1.xml"
                  ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
    </Types>"""
    root_relationships = f"""<Relationships xmlns="{PACKAGE_REL_NS}">
        <Relationship Id="rId1" Type="{DOCUMENT_REL_NS}/officeDocument" Target="xl/workbook.xml"/>
    </Relationships>"""
    workbook = f"""<workbook xmlns="{SPREADSHEET_NS}" xmlns:r="{DOCUMENT_REL_NS}">
        <sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>
    </workbook>"""
    workbook_relations = f"""<Relationships xmlns="{PACKAGE_REL_NS}">
        <Relationship Id="rId1" Type="{DOCUMENT_REL_NS}/worksheet" Target="worksheets/sheet1.xml"/>
    </Relationships>"""
    worksheet = f"""<worksheet xmlns="{SPREADSHEET_NS}">
        <sheetData>{"".join(sheet_rows)}</sheetData>
    </worksheet>"""

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_relationships)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_relations)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return output.getvalue()


def replace_members(payload: bytes, replacements: dict[str, str]) -> bytes:
    output = BytesIO()
    with (
        ZipFile(BytesIO(payload)) as original,
        ZipFile(output, "w", ZIP_DEFLATED) as modified,
    ):
        for path in original.namelist():
            if path not in replacements:
                modified.writestr(path, original.read(path))
        for path, content in replacements.items():
            modified.writestr(path, content)
    return output.getvalue()


def test_parse_text_fields_and_preserve_phone_zeroes():
    workbook = make_xlsx(
        [(" 样本客户 ", "CN", "https://customer.example.test", "联系人", "", "00123")]
    )
    [row] = parse_workbook(workbook)
    assert row.errors == ()
    assert row.fields["name"] == "样本客户"
    assert row.fields["phone"] == "00123"


def test_file_level_template_validation():
    with pytest.raises(ImportInputError, match="Customers worksheet"):
        parse_workbook(make_xlsx([("Acme",)], sheet_name="Clients"))
    with pytest.raises(ImportInputError, match="exact Customers header"):
        parse_workbook(make_xlsx([("Acme",)], columns=("name", "website")))
    with pytest.raises(ImportInputError, match="needs a header and at least one"):
        parse_workbook(make_xlsx([]))


def test_row_errors_do_not_invalidate_the_workbook():
    first, second = parse_workbook(
        make_xlsx(
            [
                ("", "CN", "javascript:example", "", "invalid", 123),
                ("Valid customer",),
            ]
        )
    )
    assert first.number == 2
    assert set(first.errors) >= {
        "name is required",
        "contact_name is required when contact details are supplied",
        "email must have a valid address format",
        "phone must be an Excel text cell",
        "website must be an HTTP or HTTPS URL",
    }
    assert not second.errors


def test_duplicate_suggestions_cover_existing_and_workbook_rows():
    first, second, third = parse_workbook(
        make_xlsx(
            [
                ("  ACME Metals", "", "https://www.acme.example.test"),
                ("Other name", "", "http://acme.example.test/order"),
                ("A distinct customer",),
            ]
        )
    )
    assert ("name", "acme metals") in _identity_keys(first.fields)
    match_id = "71c1285a-dd0b-4673-8f98-51fa06911e68"
    results = _classify_rows(
        [first, second, third],
        {("website", "acme.example.test"): {match_id: "Previous customer"}},
    )
    assert [row["status"] for row in results] == ["duplicate", "duplicate", "ready"]
    assert results[0]["matches"] == [{"id": match_id, "name": "Previous customer"}]
    assert results[1]["errors"] == ["Possible duplicate of workbook row 2"]


def test_unsupported_archive_and_expansion_limits():
    workbook = make_xlsx([("Acme",)])
    with pytest.raises(ImportInputError, match="Unable to read"):
        parse_workbook(b"invalid archive")
    oversized = replace_members(workbook, {"large.xml": "x" * (MAX_XML_BYTES + 1)})
    with pytest.raises(ImportInputError, match="unsupported entry"):
        parse_workbook(oversized)
    traversal = replace_members(workbook, {"../external.xml": "unused"})
    with pytest.raises(ImportInputError, match="unsupported entry"):
        parse_workbook(traversal)
    with pytest.raises(ImportInputError, match="500 data rows"):
        parse_workbook(make_xlsx([("Acme",)] * (MAX_DATA_ROWS + 1)))


def test_reject_formula_external_relationship_and_dtd():
    workbook = make_xlsx([("Acme",)])
    sheet_path = "xl/worksheets/sheet1.xml"
    with ZipFile(BytesIO(workbook)) as archive:
        sheet = archive.read(sheet_path).decode()
    formula = sheet.replace(
        '<c r="A2" t="inlineStr">', '<c r="A2" t="inlineStr"><f>1+1</f>'
    )
    with pytest.raises(ImportInputError, match="formulas"):
        parse_workbook(replace_members(workbook, {sheet_path: formula}))
    assert formula != sheet
    with pytest.raises(ImportInputError, match="Unable to read"):
        parse_workbook(
            replace_members(
                workbook,
                {sheet_path: '<!DOCTYPE worksheet [<!ENTITY test "text">]>' + sheet},
            )
        )
    relationship = f"""<Relationships xmlns="{PACKAGE_REL_NS}">
        <Relationship Id="rId1" Type="{DOCUMENT_REL_NS}/worksheet"
                      Target="https://example.test/sheet.xml" TargetMode="External"/>
    </Relationships>"""
    with pytest.raises(ImportInputError, match="external links"):
        parse_workbook(
            replace_members(workbook, {"xl/_rels/workbook.xml.rels": relationship})
        )


def test_reject_unexpected_multiletter_column():
    workbook = make_xlsx([("Acme",)])
    sheet_path = "xl/worksheets/sheet1.xml"
    with ZipFile(BytesIO(workbook)) as archive:
        sheet = archive.read(sheet_path).decode()
    sheet = sheet.replace('r="A2"', 'r="AB2"')
    with pytest.raises(ImportInputError, match="unexpected columns"):
        parse_workbook(replace_members(workbook, {sheet_path: sheet}))


def test_read_rich_shared_strings_used_by_excel():
    base = make_xlsx([("Acme",)])
    sheet_path = "xl/worksheets/sheet1.xml"
    rel_path = "xl/_rels/workbook.xml.rels"
    with ZipFile(BytesIO(base)) as archive:
        sheet = archive.read(sheet_path).decode()
        relations = archive.read(rel_path).decode()
    relations = relations.replace(
        "</Relationships>",
        f"""
        <Relationship Id="rId2" Type="{DOCUMENT_REL_NS}/sharedStrings" Target="/xl/sharedStrings.xml"/>
    </Relationships>
    """,
    )
    shared_strings = f"""
        <sst xmlns="{SPREADSHEET_NS}">
            <si><r><t>Acme</t></r><r><t xml:space="preserve"> Metals</t></r></si>
        </sst>
    """.strip()
    sheet = sheet.replace(
        '<c r="A2" t="inlineStr"><is><t>Acme</t></is></c>',
        '<c r="A2" t="s"><v>0</v></c>',
    )
    workbook = replace_members(
        base,
        {
            sheet_path: sheet,
            rel_path: relations,
            "xl/sharedStrings.xml": shared_strings,
        },
    )
    [row] = parse_workbook(workbook)
    assert row.fields["name"] == "Acme Metals"


def test_repeated_oversized_shared_string_is_bounded_before_trimming():
    class OversizedString(str):
        def strip(self, chars=None):
            pytest.fail("Oversized cell passed to str.strip without bounding")

    with ZipFile(BytesIO(make_xlsx([("Acme", "", "URL")] * 10))) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode()
    for row in range(2, 12):
        for column, value in (("A", "Acme"), ("C", "URL")):
            reference = f"{column}{row}"
            sheet = sheet.replace(
                f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>',
                f'<c r="{reference}" t="s"><v>0</v></c>',
            )
    rows = _read_rows(fromstring(sheet), [OversizedString("A" * 4096)])
    assert len(rows) == 10
    for row in rows:
        assert row.fields["name"] == "A" * 200
        assert row.fields["website"] is None
        assert row.errors == (
            "name exceeds 200 characters",
            "website exceeds 500 characters",
        )


@pytest.mark.parametrize(
    ("url", "valid"),
    [
        ("https://linkedin.com/in/sandbox", True),
        ("https://uk.linkedin.com/in/sandbox", True),
        ("http://linkedin.com/in/sandbox", False),
        ("https://linkedin.com.example.test/in/sandbox", False),
        ("https://example.test@linkedin.com/in/sandbox", False),
        ("https://uk..linkedin.com/in/sandbox", False),
    ],
)
def test_linkedin_url_requires_https_and_linkedin_domain(url, valid):
    [row] = parse_workbook(make_xlsx([("Acme", "", "", "Contact", "", "", url)]))
    if valid:
        assert row.errors == ()
    else:
        assert row.errors == ("linkedin_url must be an HTTPS LinkedIn URL",)
