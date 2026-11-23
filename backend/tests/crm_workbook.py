"""Synthetic OOXML spreadsheet fixture and Sandbox template generator."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

COLUMNS = (
    "name",
    "country",
    "website",
    "contact_name",
    "email",
    "phone",
    "linkedin_url",
)
SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
PACKAGE = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def workbook(*rows: tuple[str, ...]) -> bytes:
    cells_by_row = []
    for row_number, row in enumerate((COLUMNS, *rows), start=1):
        if len(row) != len(COLUMNS):
            raise ValueError("Each fixture row must have seven cells")
        cells = [
            f'<c r="{col}{row_number}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
            for col, value in zip("ABCDEFG", row)
        ]
        cells_by_row.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            f'<Relationships xmlns="{PACKAGE}"><Relationship Id="rId1" Type="{OFFICE}/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{SHEET}" xmlns:r="{OFFICE}"><sheets>'
            '<sheet name="Customers" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{PACKAGE}"><Relationship Id="rId1" Type="{OFFICE}/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{SHEET}"><sheetData>{"".join(cells_by_row)}</sheetData></worksheet>',
        )
    return output.getvalue()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.output.open("xb") as destination:
        destination.write(
            workbook(
                (
                    "Sandbox Sample Metals",
                    "SG",
                    "https://sample.example.test",
                    "Demo Buyer",
                    "buyer@example.test",
                    "001234",
                    "",
                )
            )
        )
