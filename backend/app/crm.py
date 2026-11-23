"""Tenant-scoped Sandbox CRM endpoints."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, HttpUrl, StringConstraints, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from .crm_import import ImportInputError, execute_import, lock_crm_tenant
from .main import (
    Connection,
    CurrentIdentity,
    Identity,
    Limit,
    Offset,
    audit,
    require_permission,
)

router = APIRouter(prefix="/api/v1/customers", tags=["CRM"])
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
ContactEmail = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    ),
]
Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
]
CustomerFields = "id, name, country, website, owner_id, created_at"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_XLSX = 2 * 1024 * 1024


class CustomerInput(BaseModel):
    name: ShortText
    country: ShortText | None = None
    website: HttpUrl | None = None
    owner_id: UUID | None = None

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value and (value.username or value.password):
            raise ValueError("URL credentials are not allowed")
        return value


class ContactInput(BaseModel):
    name: ShortText
    email: ContactEmail | None = None
    phone: Phone | None = None
    linkedin_url: HttpUrl | None = None

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value and (
            value.scheme != "https"
            or value.username
            or value.password
            or not (
                value.host == "linkedin.com"
                or (value.host and value.host.endswith(".linkedin.com"))
            )
        ):
            raise ValueError("Expected an HTTPS LinkedIn URL")
        return value


class TaskInput(BaseModel):
    title: ShortText
    due_date: date | None = None


class CompleteInput(BaseModel):
    completed: Literal[True]


class OwnerInput(BaseModel):
    owner_id: UUID


class CustomerView(BaseModel):
    id: UUID
    name: str
    country: str | None
    website: str | None
    owner_id: UUID
    created_at: datetime


class OwnerChoice(BaseModel):
    id: UUID
    email: str


class OwnerView(OwnerChoice):
    active: bool


class ContactView(BaseModel):
    id: UUID
    name: str
    email: str | None
    phone: str | None
    linkedin_url: str | None


class TaskView(BaseModel):
    id: UUID
    title: str
    due_date: date | None
    completed_at: datetime | None


class CustomerPage(BaseModel):
    items: list[CustomerView]


class OwnerPage(BaseModel):
    items: list[OwnerChoice]


class Customer360(BaseModel):
    customer: CustomerView
    owner: OwnerView
    contacts: list[ContactView]
    follow_ups: list[TaskView]


class ImportMatch(BaseModel):
    id: UUID
    name: str


class ImportRow(BaseModel):
    row: int
    name: str
    status: Literal["ready", "duplicate", "invalid", "created"]
    matches: list[ImportMatch]
    errors: list[str]
    customer_id: UUID | None = None


class ImportResult(BaseModel):
    rows: list[ImportRow]
    replayed: bool


@dataclass
class CRMContext:
    session: Session
    identity: Identity

    def params(self, **values: object) -> dict[str, object]:
        return {
            "tenant_id": self.identity.tenant_id,
            "actor": self.identity.id,
            "all_customers": self.identity.role in {"admin", "owner"},
            **values,
        }

    def permission(self, permission: str) -> None:
        require_permission(self.session, self.identity, permission)

    def lock_tenant(self) -> None:
        lock_crm_tenant(self.session, self.identity.tenant_id)

    def record(
        self,
        action: str,
        resource_id: UUID | None = None,
        details: dict[str, str] | None = None,
    ) -> None:
        audit(self.session, self.identity, action, "allowed", resource_id, details)

    def customer(self, customer_id: UUID) -> CustomerView:
        row = (
            self.session.execute(
                text(f"""
                SELECT {CustomerFields} FROM customers
                WHERE tenant_id = :tenant_id AND id = :id
                    AND (:all_customers OR owner_id = :actor)
            """),
                self.params(id=customer_id),
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise HTTPException(404, "Customer not found")
        return CustomerView.model_validate(dict(row))

    def ensure_owner(self, owner_id: UUID) -> None:
        owner = self.session.execute(
            text("""
                SELECT 1 FROM users
                WHERE tenant_id = :tenant_id AND id = :id AND active
                    AND role IN ('owner', 'admin', 'sales')
            """),
            self.params(id=owner_id),
        ).scalar_one_or_none()
        if owner is None:
            raise HTTPException(422, "Invalid customer owner")


def crm_context(identity: CurrentIdentity, connection: Connection) -> CRMContext:
    require_permission(connection, identity, "crm:read")
    connection.execute(
        text("""
            SELECT set_config('metaflow.crm_actor', :actor, true),
                   set_config('metaflow.crm_role', :role, true)
        """),
        {"actor": str(identity.id), "role": identity.role},
    )
    return CRMContext(connection, identity)


CRM = Annotated[CRMContext, Depends(crm_context)]


@router.get("", response_model=CustomerPage)
def list_customers(crm: CRM, limit: Limit = 50, offset: Offset = 0):
    rows = crm.session.execute(
        text(f"""
            SELECT {CustomerFields} FROM customers
            WHERE tenant_id = :tenant_id AND (:all_customers OR owner_id = :actor)
            ORDER BY lower(name), id LIMIT :limit OFFSET :offset
        """),
        crm.params(limit=limit, offset=offset),
    ).mappings()
    return {"items": [dict(row) for row in rows]}


@router.post("", status_code=201, response_model=CustomerView)
def create_customer(body: CustomerInput, crm: CRM):
    crm.permission("crm:assign")
    crm.lock_tenant()
    owner_id = body.owner_id or crm.identity.id
    crm.ensure_owner(owner_id)
    row = (
        crm.session.execute(
            text(f"""
            INSERT INTO customers (id, tenant_id, owner_id, name, country, website)
            VALUES (:id, :tenant_id, :owner_id, :name, :country, :website)
            RETURNING {CustomerFields}
        """),
            crm.params(
                id=uuid4(),
                owner_id=owner_id,
                name=body.name,
                country=body.country,
                website=str(body.website) if body.website else None,
            ),
        )
        .mappings()
        .one()
    )
    crm.record("crm:customer:create", row["id"])
    return dict(row)


@router.get("/owners", response_model=OwnerPage)
def list_owners(crm: CRM):
    crm.permission("crm:assign")
    rows = crm.session.execute(
        text("""
            SELECT id, email FROM users
            WHERE tenant_id = :tenant_id AND active AND role IN ('owner', 'admin', 'sales')
            ORDER BY email, id
        """),
        crm.params(),
    ).mappings()
    return {"items": [dict(row) for row in rows]}


@router.get("/{customer_id}/360", response_model=Customer360)
def customer_360(customer_id: UUID, crm: CRM):
    crm.lock_tenant()
    customer = crm.customer(customer_id)
    owner = (
        crm.session.execute(
            text(
                "SELECT id, email, active FROM users WHERE tenant_id = :tenant_id AND id = :id"
            ),
            crm.params(id=customer.owner_id),
        )
        .mappings()
        .one()
    )
    contacts = crm.session.execute(
        text("""
            SELECT id, name, email, phone, linkedin_url FROM customer_contacts
            WHERE tenant_id = :tenant_id AND customer_id = :id ORDER BY name, id
        """),
        crm.params(id=customer_id),
    ).mappings()
    tasks = crm.session.execute(
        text("""
            SELECT id, title, due_date, completed_at FROM follow_up_tasks
            WHERE tenant_id = :tenant_id AND customer_id = :id
            ORDER BY completed_at NULLS FIRST, due_date NULLS LAST, id
        """),
        crm.params(id=customer_id),
    ).mappings()
    return {
        "customer": customer,
        "owner": dict(owner),
        "contacts": [dict(row) for row in contacts],
        "follow_ups": [dict(row) for row in tasks],
    }


@router.patch("/{customer_id}/owner", response_model=CustomerView)
def assign_owner(customer_id: UUID, body: OwnerInput, crm: CRM):
    crm.permission("crm:assign")
    crm.lock_tenant()
    current = crm.customer(customer_id)
    if current.owner_id == body.owner_id:
        return current
    crm.ensure_owner(body.owner_id)
    row = (
        crm.session.execute(
            text(f"""
            UPDATE customers SET owner_id = :owner_id
            WHERE tenant_id = :tenant_id AND id = :id RETURNING {CustomerFields}
        """),
            crm.params(id=customer_id, owner_id=body.owner_id),
        )
        .mappings()
        .one()
    )
    crm.record(
        "crm:customer:assign",
        customer_id,
        {
            "previous_owner_id": str(current.owner_id),
            "new_owner_id": str(body.owner_id),
        },
    )
    return dict(row)


@router.post("/{customer_id}/contacts", status_code=201, response_model=ContactView)
def add_contact(customer_id: UUID, body: ContactInput, crm: CRM):
    crm.permission("crm:write")
    crm.lock_tenant()
    crm.customer(customer_id)
    row = (
        crm.session.execute(
            text("""
            INSERT INTO customer_contacts (id, tenant_id, customer_id, name, email, phone, linkedin_url)
            VALUES (:id, :tenant_id, :customer_id, :name, :email, :phone, :linkedin_url)
            RETURNING id, name, email, phone, linkedin_url
        """),
            crm.params(
                id=uuid4(),
                customer_id=customer_id,
                name=body.name,
                email=body.email,
                phone=body.phone,
                linkedin_url=str(body.linkedin_url) if body.linkedin_url else None,
            ),
        )
        .mappings()
        .one()
    )
    crm.record("crm:contact:create", row["id"], {"customer_id": str(customer_id)})
    return dict(row)


@router.post("/{customer_id}/follow-ups", status_code=201, response_model=TaskView)
def add_task(customer_id: UUID, body: TaskInput, crm: CRM):
    crm.permission("crm:write")
    crm.lock_tenant()
    crm.customer(customer_id)
    row = (
        crm.session.execute(
            text("""
            INSERT INTO follow_up_tasks (id, tenant_id, customer_id, title, due_date)
            VALUES (:id, :tenant_id, :customer_id, :title, :due_date)
            RETURNING id, title, due_date, completed_at
        """),
            crm.params(
                id=uuid4(),
                customer_id=customer_id,
                title=body.title,
                due_date=body.due_date,
            ),
        )
        .mappings()
        .one()
    )
    crm.record("crm:follow-up:create", row["id"], {"customer_id": str(customer_id)})
    return dict(row)


@router.patch("/{customer_id}/follow-ups/{task_id}", response_model=TaskView)
def complete_task(customer_id: UUID, task_id: UUID, _body: CompleteInput, crm: CRM):
    crm.permission("crm:write")
    crm.lock_tenant()
    crm.customer(customer_id)
    params = crm.params(id=task_id, customer_id=customer_id)
    row = (
        crm.session.execute(
            text("""
            SELECT id, title, due_date, completed_at FROM follow_up_tasks
            WHERE tenant_id = :tenant_id AND customer_id = :customer_id AND id = :id
        """),
            params,
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Follow-up not found")
    if row["completed_at"] is None:
        row = (
            crm.session.execute(
                text("""
                UPDATE follow_up_tasks SET completed_at = now()
                WHERE tenant_id = :tenant_id AND customer_id = :customer_id AND id = :id
                RETURNING id, title, due_date, completed_at
            """),
                params,
            )
            .mappings()
            .one()
        )
        crm.record("crm:follow-up:complete", task_id, {"customer_id": str(customer_id)})
    return dict(row)


def authorize_import(crm: CRM) -> CRMContext:
    crm.permission("crm:import")
    return crm


ImportCRM = Annotated[CRMContext, Depends(authorize_import)]


async def upload_bytes(request: Request, _crm: ImportCRM) -> bytes:
    media_type = (
        request.headers.get("content-type", "").partition(";")[0].strip().lower()
    )
    if media_type != XLSX:
        raise HTTPException(415, "Expected an XLSX workbook")
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > MAX_XLSX:
            raise HTTPException(413, "Workbook exceeds 2 MiB")
        payload.extend(chunk)
    return bytes(payload)


@router.post(
    "/import",
    response_model=ImportResult,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                XLSX: {"schema": {"type": "string", "format": "binary"}},
            },
        }
    },
)
def import_customers(
    crm: ImportCRM,
    payload: Annotated[bytes, Depends(upload_bytes)],
    mode: Literal["preview", "commit"] = "preview",
    confirm_row: Annotated[list[int] | None, Query(max_length=500)] = None,
):
    try:
        result = execute_import(
            crm.session,
            crm.identity.tenant_id,
            crm.identity.id,
            payload,
            mode,
            confirm_row or [],
        )
    except ImportInputError as exc:
        raise HTTPException(422, str(exc)) from None
    if mode == "commit" and not result["replayed"]:
        crm.record("crm:customer:import")
    return result
