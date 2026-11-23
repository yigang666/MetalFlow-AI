"""Local Sandbox SaaS foundation API."""

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

engine = create_engine(
    os.environ["DATABASE_URL"], pool_pre_ping=True, hide_parameters=True
)
app = FastAPI(title="MetalFlow AI Sandbox")
api = "/api/v1"
bearer = HTTPBearer(auto_error=False)
crm_staff = ("crm:read", "crm:write")
crm_managers = (*crm_staff, "crm:assign", "crm:import")
permissions_by_role = {
    "owner": ("users:read", "audit:read", *crm_managers),
    "admin": ("users:read", *crm_managers),
    "auditor": ("audit:read",),
    "sales": crm_staff,
}


class LoginRequest(BaseModel):
    tenant_id: UUID
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256, repr=False)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserView(BaseModel):
    id: UUID
    email: str
    role: str
    active: bool


class MeView(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    role: str
    permissions: tuple[str, ...]


class TenantView(BaseModel):
    id: UUID
    name: str


class AuditView(BaseModel):
    id: UUID
    actor_id: UUID | None
    action: str
    outcome: str
    occurred_at: datetime
    resource_id: UUID | None
    details: dict[str, str] | None


class UserPage(BaseModel):
    items: list[UserView]


class AuditPage(BaseModel):
    items: list[AuditView]


@dataclass(frozen=True)
class Identity:
    tenant_id: UUID
    id: UUID
    email: str
    role: str
    token_hash: str

    @property
    def permissions(self):
        return permissions_by_role.get(self.role, ())


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, _exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})


def unauthorized():
    return HTTPException(
        401, "Invalid credentials or session", headers={"WWW-Authenticate": "Bearer"}
    )


def transaction():
    with Session(engine) as connection, connection.begin():
        yield connection


def set_tenant(connection, tenant_id):
    connection.execute(
        text("SELECT set_config('metaflow.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def password_matches(password: str, stored: str) -> bool:
    # Unknown users take the same scrypt path as known users.
    algorithm, salt_hex, hash_hex = stored.split("$")
    computed = hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt_hex),
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )
    return algorithm == "scrypt" and hmac.compare_digest(
        computed, bytes.fromhex(hash_hex)
    )


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


Connection = Annotated[Session, Depends(transaction, scope="function")]


def authorize_token(
    connection: Connection,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    response: Response,
):
    if (
        not credentials
        or len(credentials.credentials) != 80
        or not credentials.credentials.isascii()
    ):
        raise unauthorized()
    tenant_part, separator, _ = credentials.credentials.partition(".")
    if not separator:
        raise unauthorized()
    try:
        tenant_id = UUID(tenant_part)
    except ValueError:
        raise unauthorized() from None
    token_hash = digest(credentials.credentials)
    set_tenant(connection, tenant_id)
    row = (
        connection.execute(
            text("""
            SELECT u.id, u.email, u.role
            FROM sessions s
            JOIN users u ON u.tenant_id = s.tenant_id AND u.id = s.user_id
            JOIN tenants t ON t.id = s.tenant_id
            WHERE s.tenant_id = :tenant_id AND s.token_hash = :token_hash
                AND s.expires_at > now() AND u.active AND t.active
        """),
            {"tenant_id": tenant_id, "token_hash": token_hash},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise unauthorized()
    response.headers["Cache-Control"] = "no-store"
    return Identity(tenant_id=tenant_id, token_hash=token_hash, **row)


CurrentIdentity = Annotated[Identity, Depends(authorize_token)]


def audit(
    connection: Session,
    identity: Identity,
    action: str,
    outcome: str,
    resource_id: UUID | None = None,
    details: dict[str, str] | None = None,
):
    connection.execute(
        text("""
            INSERT INTO audit_logs (id, tenant_id, actor_id, action, outcome, occurred_at, resource_id, details)
            VALUES (:id, :tenant_id, :actor_id, :action, :outcome, now(), :resource_id, CAST(:details AS jsonb))
        """),
        {
            "id": uuid4(),
            "tenant_id": identity.tenant_id,
            "actor_id": identity.id,
            "action": action,
            "outcome": outcome,
            "resource_id": resource_id,
            "details": json.dumps(details) if details is not None else None,
        },
    )


def require_permission(connection, identity, permission):
    if permission not in identity.permissions:
        audit(connection, identity, permission, "denied")
        # Preserve the denial record before returning the HTTP error.
        connection.commit()
        raise HTTPException(403, "Permission denied")


def issue_token(connection, tenant_id, user_id):
    token = f"{tenant_id}.{secrets.token_urlsafe(32)}"
    connection.execute(
        text("""
            INSERT INTO sessions (tenant_id, user_id, token_hash, expires_at)
            VALUES (:tenant_id, :user_id, :token_hash, now() + interval '30 minutes')
        """),
        {"tenant_id": tenant_id, "user_id": user_id, "token_hash": digest(token)},
    )
    return TokenResponse(access_token=token)


def delete_session(connection, identity):
    return connection.execute(
        text("""
            DELETE FROM sessions
            WHERE tenant_id = :tenant_id AND token_hash = :token_hash
            RETURNING token_hash
        """),
        {"tenant_id": identity.tenant_id, "token_hash": identity.token_hash},
    ).scalar_one_or_none()


@app.get(f"{api}/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(
                text("""
                    SELECT 1 FROM tenants WHERE false
                    UNION ALL SELECT 1 FROM users WHERE false
                    UNION ALL SELECT 1 FROM sessions WHERE false
                    UNION ALL SELECT 1 FROM audit_logs WHERE false
                    UNION ALL SELECT 1 FROM customers WHERE false
                    UNION ALL SELECT 1 FROM customer_contacts WHERE false
                    UNION ALL SELECT 1 FROM follow_up_tasks WHERE false
                    UNION ALL SELECT 1 FROM crm_import_batches WHERE false
                """)
            )
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None
    return {"status": "ok"}


@app.post(f"{api}/auth/login", response_model=TokenResponse)
def login(credentials: LoginRequest, response: Response, connection: Connection):
    set_tenant(connection, credentials.tenant_id)
    row = (
        connection.execute(
            text("""
            SELECT u.id, u.email, u.role, u.active AND t.active AS active, u.password_hash
            FROM users u JOIN tenants t ON t.id = u.tenant_id
            WHERE u.tenant_id = :tenant_id AND u.email = :email
        """),
            {
                "tenant_id": credentials.tenant_id,
                "email": credentials.email.strip().lower(),
            },
        )
        .mappings()
        .one_or_none()
    )
    stored = row["password_hash"] if row else ("scrypt$" + "0" * 32 + "$" + "0" * 64)
    if (
        not password_matches(credentials.password, stored)
        or not row
        or not row["active"]
    ):
        raise unauthorized()
    identity = Identity(credentials.tenant_id, row["id"], row["email"], row["role"], "")
    audit(connection, identity, "auth:login", "allowed")
    response.headers["Cache-Control"] = "no-store"
    return issue_token(connection, identity.tenant_id, identity.id)


@app.post(f"{api}/auth/refresh", response_model=TokenResponse)
def refresh(identity: CurrentIdentity, connection: Connection):
    if delete_session(connection, identity) is None:
        raise unauthorized()
    audit(connection, identity, "auth:refresh", "allowed")
    return issue_token(connection, identity.tenant_id, identity.id)


@app.post(f"{api}/auth/logout", status_code=204)
def logout(identity: CurrentIdentity, connection: Connection):
    if delete_session(connection, identity) is None:
        raise unauthorized()
    audit(connection, identity, "auth:logout", "allowed")


@app.get(f"{api}/me", response_model=MeView)
def me(identity: CurrentIdentity):
    return {
        "id": identity.id,
        "tenant_id": identity.tenant_id,
        "email": identity.email,
        "role": identity.role,
        "permissions": identity.permissions,
    }


@app.get(f"{api}/tenant", response_model=TenantView)
def tenant(identity: CurrentIdentity, connection: Connection):
    return dict(
        connection.execute(
            text("SELECT id, name FROM tenants WHERE id = :tenant_id"),
            {"tenant_id": identity.tenant_id},
        )
        .mappings()
        .one()
    )


Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=10000)]


@app.get(f"{api}/users", response_model=UserPage)
def users(
    identity: CurrentIdentity,
    connection: Connection,
    limit: Limit = 50,
    offset: Offset = 0,
):
    require_permission(connection, identity, "users:read")
    rows = connection.execute(
        text("""
            SELECT id, email, role, active FROM users WHERE tenant_id = :tenant_id
            ORDER BY email, id LIMIT :limit OFFSET :offset
        """),
        {"tenant_id": identity.tenant_id, "limit": limit, "offset": offset},
    ).mappings()
    return {"items": [dict(row) for row in rows]}


@app.get(f"{api}/audit-logs", response_model=AuditPage)
def audit_logs(
    identity: CurrentIdentity,
    connection: Connection,
    limit: Limit = 50,
    offset: Offset = 0,
):
    require_permission(connection, identity, "audit:read")
    rows = connection.execute(
        text("""
            SELECT id, actor_id, action, outcome, occurred_at, resource_id, details FROM audit_logs
            WHERE tenant_id = :tenant_id ORDER BY occurred_at DESC, id DESC
            LIMIT :limit OFFSET :offset
        """),
        {"tenant_id": identity.tenant_id, "limit": limit, "offset": offset},
    ).mappings()
    return {"items": [dict(row) for row in rows]}


def install_crm() -> None:
    from app.crm import router

    app.include_router(router)


install_crm()
