"""Read an untrusted XLSX upload and import explicitly reviewed Sandbox customers."""

import hashlib
import json
import posixpath
import re
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from xml.etree.ElementTree import Element, ParseError
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile
from zlib import error as CompressionError

from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]
from defusedxml.ElementTree import fromstring  # type: ignore[import-untyped]
from sqlalchemy import text
from sqlalchemy.orm import Session

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_UNPACKED_BYTES = 16 * 1024 * 1024
MAX_XML_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 128
MAX_DATA_ROWS = 500
MAX_MATCHES_PER_ROW = 20
COLUMNS = (
    "name",
    "country",
    "website",
    "contact_name",
    "email",
    "phone",
    "linkedin_url",
)
LIMITS = (200, 100, 500, 200, 254, 50, 500)
COLUMN_LIMITS = dict(zip("ABCDEFG", LIMITS, strict=True))
SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOCUMENT_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_REF = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,6})")
EMAIL = re.compile(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+")
PHONE = re.compile(r"[0-9+() .\-]+")
LINKEDIN_HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)*linkedin\.com")
IdentityKey = tuple[str, str]


class ImportInputError(ValueError):
    """Report an invalid workbook without including its contents in the error."""


@dataclass(frozen=True)
class CustomerRow:
    number: int
    fields: dict[str, str | None]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class Cell:
    value: str = ""
    is_text: bool = True
    oversized: bool = False


def _tag(name: str) -> str:
    return f"{{{SPREADSHEET_NS}}}{name}"


def _parse_xml(archive: ZipFile, path: str) -> Element:
    with archive.open(path) as member:
        content = member.read(MAX_XML_BYTES + 1)
    if len(content) > MAX_XML_BYTES:
        raise ImportInputError("Workbook XML exceeds the permitted size")
    return fromstring(
        content, forbid_dtd=True, forbid_entities=True, forbid_external=True
    )


def _archive_entries(archive: ZipFile) -> set[str]:
    entries = archive.infolist()
    names = {entry.filename for entry in entries}
    if len(entries) > MAX_ENTRIES or len(names) != len(entries):
        raise ImportInputError("Workbook archive has invalid or excessive entries")
    if sum(entry.file_size for entry in entries) > MAX_UNPACKED_BYTES:
        raise ImportInputError("Workbook archive expands beyond the permitted size")
    for entry in entries:
        relative_name = entry.filename.rstrip("/")
        if (
            entry.file_size > MAX_XML_BYTES
            or entry.flag_bits & 1
            or entry.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
            or "\\" in relative_name
            or relative_name.startswith("/")
            or any(part in {"", ".", ".."} for part in relative_name.split("/"))
        ):
            raise ImportInputError("Workbook archive contains an unsupported entry")
        if "externallinks" in relative_name.lower().split("/"):
            raise ImportInputError("Workbook external links are forbidden")
        if relative_name.lower().endswith("vbaproject.bin"):
            raise ImportInputError("Workbook macros are forbidden")
    return names


def _relationship_maps(archive: ZipFile, names: set[str]) -> dict[str, tuple[str, str]]:
    workbook_relationships = {}
    for path in sorted(name for name in names if name.endswith(".rels")):
        relationships = _parse_xml(archive, path)
        if relationships.tag != f"{{{PACKAGE_REL_NS}}}Relationships":
            raise ImportInputError("Invalid workbook relationships")
        for relationship in relationships:
            if relationship.get("TargetMode", "Internal") != "Internal":
                raise ImportInputError("Workbook external links are forbidden")
            if path != "xl/_rels/workbook.xml.rels":
                continue
            relation_id = relationship.get("Id", "")
            target = relationship.get("Target", "")
            relation_type = relationship.get("Type", "")
            if not relation_id or not target or relation_id in workbook_relationships:
                raise ImportInputError("Invalid workbook relationships")
            resolved = (
                posixpath.normpath(target.lstrip("/"))
                if target.startswith("/")
                else posixpath.normpath(posixpath.join("xl", target))
            )
            workbook_relationships[relation_id] = (relation_type, resolved)
    return workbook_relationships


def _visible_text(element: Element) -> str:
    return "".join(
        node.text or ""
        for node in (
            element.findall(_tag("t")) + element.findall(f"{_tag('r')}/{_tag('t')}")
        )
    )


def _cell_text(cell: Element, shared_strings: list[str]) -> tuple[str, bool]:
    if cell.find(_tag("f")) is not None:
        raise ImportInputError("Workbook formulas are forbidden")
    cell_type = cell.get("t", "n")
    if cell_type == "inlineStr":
        inline = cell.find(_tag("is"))
        return (_visible_text(inline) if inline is not None else "", True)
    scalar = cell.findtext(_tag("v"), "")
    if cell_type == "s":
        if len(scalar) > 7 or not scalar.isascii() or not scalar.isdigit():
            raise ImportInputError("Invalid shared string reference")
        index = int(scalar)
        if index >= len(shared_strings):
            raise ImportInputError("Invalid shared string reference")
        return shared_strings[index], True
    return scalar, cell_type == "str"


def _read_rows(worksheet: Element, shared_strings: list[str]) -> list[CustomerRow]:
    sheet_data = worksheet.find(_tag("sheetData"))
    if sheet_data is None:
        raise ImportInputError("The Customers worksheet is empty")
    result: list[CustomerRow] = []
    header_seen = False
    previous_row = 0
    for row in sheet_data.findall(_tag("row")):
        number_text = row.get("r", "")
        if (
            len(number_text) > 7
            or not number_text.isascii()
            or not number_text.isdigit()
        ):
            raise ImportInputError("Invalid worksheet row number")
        number = int(number_text)
        if number <= previous_row or number > 1_048_576:
            raise ImportInputError("Invalid worksheet row number")
        previous_row = number
        values: dict[str, Cell] = {}
        for cell in row.findall(_tag("c")):
            reference = CELL_REF.fullmatch(cell.get("r", ""))
            if (
                reference is None
                or int(reference[2]) != number
                or reference[1] in values
            ):
                raise ImportInputError("Invalid worksheet cell reference")
            column = reference[1]
            value, is_text = _cell_text(cell, shared_strings)
            limit = COLUMN_LIMITS.get(column)
            if limit is None:
                if value:
                    raise ImportInputError(
                        "The Customers worksheet has unexpected columns"
                    )
                values[column] = Cell()
                continue
            if len(value) > limit:
                preview = value[:limit] if column == "A" else ""
                values[column] = Cell(preview, is_text, oversized=True)
            else:
                values[column] = Cell(value, is_text)
        if not any(cell.oversized or cell.value.strip() for cell in values.values()):
            continue
        cells = [values.get(column, Cell()) for column in COLUMN_LIMITS]
        if not header_seen:
            if (
                number != 1
                or any(cell.oversized for cell in cells)
                or tuple(cell.value for cell in cells) != COLUMNS
            ):
                raise ImportInputError("Use the exact Customers header in row 1")
            header_seen = True
            continue
        if len(result) >= MAX_DATA_ROWS:
            raise ImportInputError("Workbook exceeds 500 data rows")
        result.append(_validate_row(number, cells))
    if not header_seen or not result:
        raise ImportInputError(
            "The Customers worksheet needs a header and at least one data row"
        )
    return result


def _url_host(value: str) -> str | None:
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return None
    if (
        parts.scheme not in {"https", "http"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or "\\" in value
        or any(character.isspace() or ord(character) < 32 for character in value)
        or port == 0
    ):
        return None
    host = parts.hostname.lower().rstrip(".")
    return host.removeprefix("www.") or None


def _validate_row(number: int, cells: list[Cell]) -> CustomerRow:
    errors = []
    fields = {}
    for field, limit, cell in zip(COLUMNS, LIMITS, cells, strict=True):
        value = cell.value.strip()
        fields[field] = value or None
        if value and not cell.is_text:
            errors.append(f"{field} must be an Excel text cell")
        if cell.oversized:
            errors.append(f"{field} exceeds {limit} characters")
    if not fields["name"]:
        errors.append("name is required")
    if (
        any(fields[field] for field in ("email", "phone", "linkedin_url"))
        and not fields["contact_name"]
    ):
        errors.append("contact_name is required when contact details are supplied")
    website = fields["website"]
    if website and not _url_host(website):
        errors.append("website must be an HTTP or HTTPS URL")
    linkedin = fields["linkedin_url"]
    if linkedin:
        parts = urlsplit(linkedin) if _url_host(linkedin) else None
        if (
            parts is None
            or parts.scheme != "https"
            or not LINKEDIN_HOST.fullmatch(parts.hostname or "")
        ):
            errors.append("linkedin_url must be an HTTPS LinkedIn URL")
    email = fields["email"]
    if email and not EMAIL.fullmatch(email):
        errors.append("email must have a valid address format")
    phone = fields["phone"]
    if phone and (
        not PHONE.fullmatch(phone) or not any(char.isdigit() for char in phone)
    ):
        errors.append("phone must contain digits and optional punctuation")
    return CustomerRow(number=number, fields=fields, errors=tuple(errors))


def parse_workbook(payload: bytes) -> list[CustomerRow]:
    """Parse standard XLSX cells without extracting files or resolving links."""
    if not payload or len(payload) > MAX_UPLOAD_BYTES:
        raise ImportInputError("Upload a nonempty XLSX workbook of at most 2 MiB")
    try:
        with ZipFile(BytesIO(payload)) as archive:
            names = _archive_entries(archive)
            relationships = _relationship_maps(archive, names)
            workbook = _parse_xml(archive, "xl/workbook.xml")
            if workbook.tag != _tag("workbook"):
                raise ImportInputError("Invalid workbook document")
            sheets = [
                sheet
                for sheet in workbook.findall(f"{_tag('sheets')}/{_tag('sheet')}")
                if sheet.get("name") == "Customers"
            ]
            if len(sheets) != 1:
                raise ImportInputError("Workbook must contain one Customers worksheet")
            sheet_relation, worksheet_path = relationships[
                sheets[0].attrib[f"{{{DOCUMENT_REL_NS}}}id"]
            ]
            if not sheet_relation.endswith(
                "/worksheet"
            ) or not worksheet_path.startswith("xl/worksheets/"):
                raise ImportInputError("Invalid Customers worksheet relationship")
            shared_strings = None
            for relation_type, path in relationships.values():
                if relation_type.endswith("/sharedStrings"):
                    if shared_strings is not None or not path.startswith("xl/"):
                        raise ImportInputError("Invalid shared string relationship")
                    shared_strings = [
                        _visible_text(item)
                        for item in _parse_xml(archive, path).findall(_tag("si"))
                    ]
            worksheet = _parse_xml(archive, worksheet_path)
            if worksheet.tag != _tag("worksheet"):
                raise ImportInputError("Invalid Customers worksheet")
            return _read_rows(worksheet, shared_strings or [])
    except ImportInputError:
        raise
    except (
        BadZipFile,
        CompressionError,
        DefusedXmlException,
        KeyError,
        NotImplementedError,
        OSError,
        OverflowError,
        ParseError,
        RuntimeError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise ImportInputError("Unable to read the XLSX workbook") from exc


def _identity_keys(fields: dict[str, str | None]) -> set[IdentityKey]:
    keys = set()
    if name := fields.get("name"):
        keys.add(("name", " ".join(name.casefold().split())))
    if (website := fields.get("website")) and (host := _url_host(website)):
        keys.add(("website", host))
    if email := fields.get("email"):
        keys.add(("email", email.strip().casefold()))
    phone = fields.get("phone") or ""
    if digits := "".join(char for char in phone if char.isascii() and char.isdigit()):
        keys.add(("phone", digits))
    if (url := fields.get("linkedin_url")) and (linkedin_host := _url_host(url)):
        keys.add(
            ("linkedin_url", linkedin_host + urlsplit(url).path.rstrip("/").casefold())
        )
    return keys


def lock_crm_tenant(session: Session, tenant_id: UUID) -> None:
    """Serialize suggestion-sensitive writes on one tenant for the current transaction."""
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": f"metalflow.crm:{tenant_id}"},
    )


def _existing_matches(
    session: Session, tenant_id: UUID, wanted_keys: set[IdentityKey]
) -> dict[IdentityKey, dict[str, str]]:
    matches: dict[IdentityKey, dict[str, str]] = defaultdict(dict)
    if not wanted_keys:
        return matches
    statements = (
        """
        SELECT c.id, c.name, c.name AS customer_name, c.website,
               NULL AS email, NULL AS phone, NULL AS linkedin_url
        FROM customers c WHERE c.tenant_id = :tenant_id
        ORDER BY c.id
        """,
        """
        SELECT c.id, NULL AS name, c.name AS customer_name, NULL AS website,
               cc.email, cc.phone, cc.linkedin_url
        FROM customer_contacts cc JOIN customers c
          ON c.tenant_id = cc.tenant_id AND c.id = cc.customer_id
        WHERE cc.tenant_id = :tenant_id
        ORDER BY c.id
        """,
    )
    for statement in statements:
        for row in session.execute(
            text(statement), {"tenant_id": tenant_id}
        ).mappings():
            fields = {
                field: row[field]
                for field in ("name", "website", "email", "phone", "linkedin_url")
            }
            for key in _identity_keys(fields) & wanted_keys:
                candidates = matches[key]
                if len(candidates) < MAX_MATCHES_PER_ROW:
                    candidates[str(row["id"])] = row["customer_name"]
    return matches


def _classify_rows(
    rows: list[CustomerRow], existing: dict[IdentityKey, dict[str, str]]
) -> list[dict]:
    source_rows: dict[IdentityKey, int] = {}
    results = []
    for row in rows:
        errors = list(row.errors)
        candidates: dict[str, str] = {}
        status = "invalid" if errors else "ready"
        if not errors:
            keys = _identity_keys(row.fields)
            previous_rows = sorted(
                {source_rows[key] for key in keys if key in source_rows}
            )
            for key in keys:
                source_rows.setdefault(key, row.number)
                candidates.update(existing.get(key, {}))
            if previous_rows:
                errors.append(
                    "Possible duplicate of workbook row "
                    + ", ".join(map(str, previous_rows))
                )
            if candidates or previous_rows:
                status = "duplicate"
        results.append(
            {
                "row": row.number,
                "name": (row.fields["name"] or "")[: LIMITS[0]],
                "status": status,
                "matches": [
                    {"id": candidate, "name": candidates[candidate]}
                    for candidate in sorted(candidates)[:MAX_MATCHES_PER_ROW]
                ],
                "errors": errors,
            }
        )
    return results


def _insert_customer(
    session: Session, tenant_id: UUID, actor_id: UUID, row: CustomerRow
) -> UUID:
    customer_id = uuid4()
    session.execute(
        text("""
            INSERT INTO customers (id, tenant_id, owner_id, name, country, website)
            VALUES (:customer_id, :tenant_id, :owner_id, :name, :country, :website)
        """),
        {
            "customer_id": customer_id,
            "tenant_id": tenant_id,
            "owner_id": actor_id,
            "name": row.fields["name"],
            "country": row.fields["country"],
            "website": row.fields["website"],
        },
    )
    if name := row.fields["contact_name"]:
        session.execute(
            text("""
                INSERT INTO customer_contacts (id, tenant_id, customer_id, name, email, phone, linkedin_url)
                VALUES (:id, :tenant_id, :customer_id, :name, :email, :phone, :linkedin_url)
            """),
            {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "customer_id": customer_id,
                "name": name,
                "email": row.fields["email"],
                "phone": row.fields["phone"],
                "linkedin_url": row.fields["linkedin_url"],
            },
        )
    return customer_id


def execute_import(
    session: Session,
    tenant_id: UUID,
    actor_id: UUID,
    payload: bytes,
    mode: str,
    confirm_rows: list[int],
) -> dict:
    """Return a preview or commit synthetically reviewed rows within the caller's transaction."""
    if mode not in {"preview", "commit"}:
        raise ImportInputError("Invalid import mode")
    if len(confirm_rows) > MAX_DATA_ROWS or (mode == "preview" and confirm_rows):
        raise ImportInputError("Invalid duplicate confirmations")
    rows = parse_workbook(payload)
    confirmed = set(confirm_rows)
    request_hash = hashlib.sha256(
        hashlib.sha256(payload).digest() + json.dumps(sorted(confirmed)).encode("ascii")
    ).hexdigest()
    batch = {"tenant_id": tenant_id, "request_hash": request_hash}
    if mode == "commit":
        lock_crm_tenant(session, tenant_id)
        existing = session.execute(
            text("""
                SELECT response FROM crm_import_batches
                WHERE tenant_id = :tenant_id AND request_hash = :request_hash
            """),
            batch,
        ).scalar_one_or_none()
        if existing is not None:
            return {**existing, "replayed": True}

    wanted_keys = {
        key for row in rows if not row.errors for key in _identity_keys(row.fields)
    }
    results = _classify_rows(rows, _existing_matches(session, tenant_id, wanted_keys))
    response = {"rows": results, "replayed": False}
    if mode == "preview":
        return response
    duplicate_rows = {
        result["row"] for result in results if result["status"] == "duplicate"
    }
    if not confirmed <= duplicate_rows:
        raise ImportInputError(
            "Confirm only rows marked possible duplicate in the current preview"
        )

    for row, result in zip(rows, results, strict=True):
        if result["status"] == "ready" or row.number in confirmed:
            customer_id = _insert_customer(session, tenant_id, actor_id, row)
            result["status"] = "created"
            result["customer_id"] = str(customer_id)

    session.execute(
        text("""
            INSERT INTO crm_import_batches (tenant_id, request_hash, response)
            VALUES (:tenant_id, :request_hash, CAST(:response AS jsonb))
        """),
        {**batch, "response": json.dumps(response, ensure_ascii=False)},
    )
    return response
