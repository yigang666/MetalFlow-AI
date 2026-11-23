"""Phase 1 acceptance against a disposable Postgres database with seeded fixtures."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4, uuid5

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

TENANT_A = UUID("11111111-1111-4111-8111-111111111111")
TENANT_B = UUID("22222222-2222-4222-8222-222222222222")
API = "/api/v1"


@pytest.fixture(scope="module")
def runtime():
    if os.getenv("METALFLOW_TEST_SANDBOX") != "1":
        pytest.fail("Use a disposable seeded database with METALFLOW_TEST_SANDBOX=1")
    from app.main import app, engine

    with TestClient(app) as client:
        yield client, engine


def login(client, tenant=TENANT_A, account="owner", password=None):
    return client.post(
        f"{API}/auth/login",
        json={
            "tenant_id": str(tenant),
            "email": f"{account}@example.test",
            "password": password
            if password is not None
            else os.environ["SANDBOX_PASSWORD"],
        },
    )


def auth(client, tenant=TENANT_A, account="owner"):
    response = login(client, tenant, account)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def set_scope(connection, tenant_id):
    connection.execute(
        text("SELECT set_config('metaflow.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def test_readiness_and_auth_required(runtime):
    client, _ = runtime
    assert client.get(f"{API}/health").status_code == 200
    for path in ("me", "tenant", "users", "audit-logs"):
        assert client.get(f"{API}/{path}").status_code == 401


def test_generic_invalid_credentials_and_disabled(runtime):
    client, _ = runtime
    wrong_password = login(client, password="wrong-password")
    for response in (
        wrong_password,
        login(client, account="missing"),
        login(client, account="disabled"),
        login(client, tenant=uuid4()),
    ):
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid credentials or session"}


def test_changes_apply_to_existing_sessions(runtime):
    admin_url = os.getenv("DATABASE_ADMIN_URL")
    if not admin_url:
        pytest.skip("Needs the administrator URL for the disposable database")

    client, _ = runtime
    headers = auth(client, TENANT_B, "admin")
    assert client.get(f"{API}/users", headers=headers).status_code == 200
    admin_engine = create_engine(admin_url, hide_parameters=True)
    account = {"tenant": TENANT_B, "id": uuid5(TENANT_B, "admin@example.test")}
    try:
        with admin_engine.begin() as connection:
            set_scope(connection, TENANT_B)
            connection.execute(
                text(
                    "UPDATE users SET role = 'sales' WHERE tenant_id = :tenant AND id = :id"
                ),
                account,
            )
        assert client.get(f"{API}/users", headers=headers).status_code == 403
        with admin_engine.begin() as connection:
            set_scope(connection, TENANT_B)
            connection.execute(
                text(
                    "UPDATE users SET active = false WHERE tenant_id = :tenant AND id = :id"
                ),
                account,
            )
        assert client.get(f"{API}/me", headers=headers).status_code == 401
    finally:
        with admin_engine.begin() as connection:
            set_scope(connection, TENANT_B)
            connection.execute(
                text(
                    "UPDATE users SET role = 'admin', active = true WHERE tenant_id = :tenant AND id = :id"
                ),
                account,
            )
        admin_engine.dispose()
        assert client.post(f"{API}/auth/logout", headers=headers).status_code == 204


def test_invalid_input_does_not_echo_password(runtime):
    client, _ = runtime
    sentinel = "must-not-appear-in-error"
    result = client.post(
        f"{API}/auth/login",
        json={
            "tenant_id": "invalid",
            "email": "owner@example.test",
            "password": sentinel * 30,
        },
    )
    assert result.status_code == 422
    assert sentinel not in result.text


@pytest.mark.parametrize(
    ("account", "users_status", "audit_status"),
    [
        ("owner", 200, 200),
        ("admin", 200, 403),
        ("sales", 403, 403),
        ("auditor", 403, 200),
    ],
)
def test_role_matrix(runtime, account, users_status, audit_status):
    client, _ = runtime
    headers = auth(client, account=account)
    profile = client.get(f"{API}/me", headers=headers)
    assert profile.status_code == 200
    assert profile.headers["cache-control"] == "no-store"
    assert profile.json()["role"] == account
    assert client.get(f"{API}/users", headers=headers).status_code == users_status
    assert client.get(f"{API}/audit-logs", headers=headers).status_code == audit_status


def test_bidirectional_tenant_isolation_and_scope_spoofing(runtime):
    client, _ = runtime
    for current, other in ((TENANT_A, TENANT_B), (TENANT_B, TENANT_A)):
        headers = {**auth(client, current), "X-Tenant-ID": str(other)}
        tenant = client.get(
            f"{API}/tenant", headers=headers, params={"tenant_id": str(other)}
        )
        assert tenant.status_code == 200 and tenant.json()["id"] == str(current)
        users = client.get(f"{API}/users", headers=headers).json()["items"]
        assert len(users) == 5
        for user in users:
            assert user["id"] == str(uuid5(current, user["email"]))
            assert "password_hash" not in user
        tampered = headers["Authorization"].replace(str(current), str(other), 1)
        assert (
            client.get(f"{API}/me", headers={"Authorization": tampered}).status_code
            == 401
        )


def test_pagination_validation(runtime):
    client, _ = runtime
    headers = auth(client)
    first = client.get(f"{API}/users", headers=headers, params={"limit": 2}).json()[
        "items"
    ]
    second = client.get(
        f"{API}/users", headers=headers, params={"limit": 2, "offset": 2}
    ).json()["items"]
    assert len(first) == len(second) == 2
    assert {item["id"] for item in first}.isdisjoint(item["id"] for item in second)
    assert client.get(f"{API}/users?limit=101", headers=headers).status_code == 422


def test_refresh_is_single_use_and_logout_revokes(runtime):
    client, _ = runtime
    old = auth(client)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: client.post(f"{API}/auth/refresh", headers=old), range(2)
            )
        )
    assert sorted(response.status_code for response in results) == [200, 401]
    fresh = next(
        response.json()["access_token"]
        for response in results
        if response.status_code == 200
    )
    new = {"Authorization": f"Bearer {fresh}"}
    assert client.get(f"{API}/me", headers=old).status_code == 401
    assert client.get(f"{API}/me", headers=new).status_code == 200
    assert client.post(f"{API}/auth/logout", headers=new).status_code == 204
    assert client.get(f"{API}/me", headers=new).status_code == 401


def test_denial_audit_is_visible_only_in_same_tenant(runtime):
    client, _ = runtime
    sales = auth(client, TENANT_A, "sales")
    assert client.get(f"{API}/users", headers=sales).status_code == 403
    tenant_a = client.get(
        f"{API}/audit-logs", headers=auth(client, TENANT_A, "auditor")
    )
    tenant_b = client.get(
        f"{API}/audit-logs", headers=auth(client, TENANT_B, "auditor")
    )
    actor = str(uuid5(TENANT_A, "sales@example.test"))
    assert any(
        item["actor_id"] == actor
        and item["action"] == "users:read"
        and item["outcome"] == "denied"
        for item in tenant_a.json()["items"]
    )
    assert all(item["actor_id"] != actor for item in tenant_b.json()["items"])


def test_rls_fails_closed_and_transaction_scope_resets(runtime):
    _, engine = runtime
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 0
        set_scope(connection, TENANT_A)
        ids = set(
            connection.execute(text("SELECT DISTINCT tenant_id FROM users")).scalars()
        )
        assert ids == {TENANT_A}
        connection.commit()
        assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 0
        set_scope(connection, TENANT_B)
        ids = set(
            connection.execute(text("SELECT DISTINCT tenant_id FROM users")).scalars()
        )
        assert ids == {TENANT_B}


def test_rls_rejects_cross_tenant_insert_and_audit_mutation(runtime):
    _, engine = runtime
    with engine.connect() as connection:
        set_scope(connection, TENANT_A)
        with pytest.raises(DBAPIError) as cross_tenant:
            connection.execute(
                text(
                    "INSERT INTO audit_logs (id, tenant_id, action, outcome) VALUES (:id, :t, 'test', 'test')"
                ),
                {"id": uuid4(), "t": TENANT_B},
            )
        assert cross_tenant.value.orig.sqlstate == "42501"
        connection.rollback()
        set_scope(connection, TENANT_A)
        with pytest.raises(DBAPIError) as mutation:
            connection.execute(
                text("DELETE FROM audit_logs WHERE tenant_id = :t"), {"t": TENANT_A}
            )
        assert mutation.value.orig.sqlstate == "42501"


def test_session_uses_digest_and_expired_session_is_rejected(runtime):
    client, engine = runtime
    headers = auth(client)
    token = headers["Authorization"].split(" ", 1)[1]
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    expired_token = f"{TENANT_A}." + "a" * 43
    expired_hash = hashlib.sha256(expired_token.encode("ascii")).hexdigest()
    with engine.begin() as connection:
        set_scope(connection, TENANT_A)
        hashes = set(
            connection.execute(text("SELECT token_hash FROM sessions")).scalars()
        )
        assert token_hash in hashes
        assert token not in hashes
        connection.execute(
            text("""
                INSERT INTO sessions (tenant_id, user_id, token_hash, expires_at)
                VALUES (:t, :u, :h, now() - interval '1 minute')
                ON CONFLICT DO NOTHING
            """),
            {
                "t": TENANT_A,
                "u": uuid5(TENANT_A, "owner@example.test"),
                "h": expired_hash,
            },
        )
    try:
        assert (
            client.get(
                f"{API}/me", headers={"Authorization": f"Bearer {expired_token}"}
            ).status_code
            == 401
        )
    finally:
        with engine.begin() as connection:
            set_scope(connection, TENANT_A)
            connection.execute(
                text("DELETE FROM sessions WHERE token_hash = :h"), {"h": expired_hash}
            )
