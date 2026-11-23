"""CRM acceptance against disposable PostgreSQL and two seeded tenants."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4, uuid5

import pytest
from crm_workbook import workbook
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_foundation import API, TENANT_A, TENANT_B, auth, set_scope

pytest_plugins = ("test_foundation",)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def create(client, headers, name, owner_id=None):
    result = client.post(
        f"{API}/customers",
        headers=headers,
        json={"name": name, "country": "SG", "owner_id": owner_id},
    )
    assert result.status_code == 201, result.text
    return result.json()["id"]


def import_request(client, auth_headers, payload, mode="preview", confirm=None):
    params = [("mode", mode)]
    if confirm is not None:
        params.append(("confirm_row", str(confirm)))
    return client.post(
        f"{API}/customers/import",
        params=params,
        headers={**auth_headers, "content-type": XLSX},
        content=payload,
    )


def test_customer_contact_follow_up_and_assignment(runtime):
    client, _ = runtime
    owner = auth(client)
    sales = auth(client, account="sales")
    tenant_b = auth(client, TENANT_B)
    title = f"Railway Metals {uuid4()}"
    customer_id = create(client, owner, title)
    url = f"{API}/customers/{customer_id}"
    assert client.get(f"{url}/360", headers=sales).status_code == 404
    assert client.get(f"{url}/360", headers=tenant_b).status_code == 404
    assert (
        client.patch(
            f"{url}/owner",
            headers=owner,
            json={
                "owner_id": str(uuid5(TENANT_B, "sales@example.test")),
            },
        ).status_code
        == 422
    )
    owner_choices = client.get(f"{API}/customers/owners", headers=owner).json()["items"]
    assert {item["email"] for item in owner_choices} == {
        "owner@example.test",
        "admin@example.test",
        "sales@example.test",
    }
    sales_id = str(uuid5(TENANT_A, "sales@example.test"))
    assert (
        client.patch(
            f"{url}/owner",
            headers=owner,
            json={
                "owner_id": sales_id,
            },
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"{url}/owner",
            headers=sales,
            json={
                "owner_id": sales_id,
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{url}/contacts",
            headers=tenant_b,
            json={
                "name": "Wrong tenant",
            },
        ).status_code
        == 404
    )
    contact = client.post(
        f"{url}/contacts",
        headers=sales,
        json={
            "name": "Lin",
            "email": "lin@example.test",
            "phone": "001234",
        },
    )
    assert contact.status_code == 201, contact.text
    task = client.post(
        f"{url}/follow-ups",
        headers=sales,
        json={
            "title": "Confirm specifications",
            "due_date": "2026-12-01",
        },
    )
    assert task.status_code == 201, task.text
    task_url = f"{url}/follow-ups/{task.json()['id']}"
    completed = client.patch(task_url, headers=sales, json={"completed": True})
    assert completed.status_code == 200 and completed.json()["completed_at"]
    assert (
        client.patch(task_url, headers=sales, json={"completed": True}).json()
        == completed.json()
    )
    result = client.get(f"{url}/360", headers=sales)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["customer"]["name"] == title
    assert body["owner"]["id"] == sales_id
    assert body["contacts"] == [contact.json()]
    assert body["follow_ups"] == [completed.json()]
    assert (
        client.patch(
            f"{url}/owner",
            headers=owner,
            json={
                "owner_id": str(uuid5(TENANT_A, "owner@example.test")),
            },
        ).status_code
        == 200
    )
    assert client.get(f"{url}/360", headers=sales).status_code == 404
    assert customer_id not in {
        item["id"]
        for item in client.get(f"{API}/customers", headers=sales).json()["items"]
    }
    entries = client.get(f"{API}/audit-logs", headers=owner).json()["items"]
    assert {
        "crm:customer:create",
        "crm:customer:assign",
        "crm:contact:create",
        "crm:follow-up:create",
        "crm:follow-up:complete",
    } <= {item["action"] for item in entries}
    assert any(
        item["resource_id"] == customer_id
        and item["action"] == "crm:customer:assign"
        and item["details"]
        == {
            "previous_owner_id": str(uuid5(TENANT_A, "owner@example.test")),
            "new_owner_id": sales_id,
        }
        for item in entries
    )


def test_crm_role_requirements_and_upload_limits(runtime):
    client, _ = runtime
    owner = auth(client)
    sales = auth(client, account="sales")
    auditor = auth(client, account="auditor")
    assert client.get(f"{API}/customers").status_code == 401
    assert client.get(f"{API}/customers", headers=auditor).status_code == 403
    assert client.get(f"{API}/customers/owners", headers=sales).status_code == 403
    assert (
        client.post(
            f"{API}/customers", headers=sales, json={"name": "Forbidden"}
        ).status_code
        == 403
    )
    assert import_request(client, sales, b"not workbook").status_code == 403
    assert import_request(client, owner, b"bad ZIP").status_code == 422
    assert (
        import_request(client, owner, b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
    )
    assert (
        client.post(
            f"{API}/customers/import", headers=owner, content=b"text"
        ).status_code
        == 415
    )


def test_excel_preview_duplicate_confirmation_and_replay(runtime):
    client, _ = runtime
    owner = auth(client)
    tenant_b = auth(client, TENANT_B)
    tag = uuid4().hex
    candidate = f"Existing {tag}"
    original = create(client, owner, candidate)
    brand = f"Workbook {tag}"
    unique_phone = f"00{int(tag[:10], 16)}"
    data = workbook(
        (brand, "SG", "", "Lee", f"lee-{tag}@example.test", unique_phone, ""),
        (candidate, "SG", "", "", "", "", ""),
        ("", "SG", "", "", "", "", ""),
    )
    preview = import_request(client, owner, data)
    assert preview.status_code == 200, preview.text
    by_row = {row["row"]: row for row in preview.json()["rows"]}
    assert by_row[2]["status"] == "ready"
    assert by_row[3]["status"] == "duplicate"
    assert by_row[3]["matches"] == [{"id": original, "name": candidate}]
    assert by_row[4]["status"] == "invalid"
    assert all(
        item["name"] != brand
        for item in client.get(f"{API}/customers", headers=owner).json()["items"]
    )
    other = import_request(client, tenant_b, data)
    assert other.status_code == 200, other.text
    assert other.json()["rows"][1]["status"] == "ready"
    commit = import_request(client, owner, data, "commit", confirm=3)
    assert commit.status_code == 200, commit.text
    assert [(row["row"], row["status"]) for row in commit.json()["rows"]] == [
        (2, "created"),
        (3, "created"),
        (4, "invalid"),
    ]
    replay = import_request(client, owner, data, "commit", confirm=3)
    assert replay.status_code == 200 and replay.json()["replayed"]
    assert replay.json()["rows"] == commit.json()["rows"]
    # Use raw scoped DB access to avoid depending on list pagination.
    _, engine = runtime
    with engine.begin() as connection:
        set_scope(connection, TENANT_A)
        set_crm_scope(connection, TENANT_A, "owner")
        records = (
            connection.execute(
                text(
                    "SELECT id, name FROM customers WHERE name IN (:candidate,:brand)"
                ),
                {"candidate": candidate, "brand": brand},
            )
            .mappings()
            .all()
        )
    assert sum(row["name"] == candidate for row in records) == 2
    assert sum(row["name"] == brand for row in records) == 1
    imported_id = next(row["id"] for row in records if row["name"] == brand)
    assert (
        client.get(f"{API}/customers/{imported_id}/360", headers=owner).json()[
            "contacts"
        ][0]["phone"]
        == unique_phone
    )


def test_concurrent_import_retry_creates_one_customer(runtime):
    client, _ = runtime
    owner = auth(client)
    title = f"Concurrent {uuid4()}"
    data = workbook((title, "", "", "", "", "", ""))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: import_request(client, owner, data, "commit"), range(2))
        )
    assert all(response.status_code == 200 for response in results)
    assert sorted(response.json()["replayed"] for response in results) == [False, True]
    assert all(
        response.json()["rows"][0]["status"] == "created" for response in results
    )


def set_crm_scope(connection, tenant, role):
    connection.execute(
        text("""
            SELECT set_config('metaflow.crm_actor', :actor, true),
                   set_config('metaflow.crm_role', :role, true)
        """),
        {"actor": str(uuid5(tenant, f"{role}@example.test")), "role": role},
    )


def test_crm_rls_without_scope_and_cross_tenant_writes(runtime):
    client, engine = runtime
    owner = auth(client)
    customer_id = create(client, owner, f"RLS {uuid4()}")
    tenant_b = auth(client, TENANT_B)
    other_id = create(client, tenant_b, f"RLS B {uuid4()}")
    with engine.connect() as connection:
        set_scope(connection, TENANT_A)
        assert (
            connection.execute(text("SELECT count(*) FROM customers")).scalar_one() == 0
        )
        set_crm_scope(connection, TENANT_A, "sales")
        assert (
            connection.execute(
                text("SELECT 1 FROM customers WHERE id = :id"),
                {
                    "id": customer_id,
                },
            ).scalar_one_or_none()
            is None
        )
        set_crm_scope(connection, TENANT_A, "owner")
        assert (
            connection.execute(
                text("SELECT 1 FROM customers WHERE id = :id"),
                {
                    "id": customer_id,
                },
            ).scalar_one()
            == 1
        )
        with pytest.raises(DBAPIError) as blocked:
            connection.execute(
                text("""
                    INSERT INTO customer_contacts (id, tenant_id, customer_id, name)
                    VALUES (:id, :tenant, :customer, 'Wrong tenant')
                """),
                {"id": uuid4(), "tenant": TENANT_B, "customer": other_id},
            )
        assert blocked.value.orig.sqlstate == "42501"
        connection.rollback()
        assert (
            connection.execute(text("SELECT count(*) FROM customers")).scalar_one() == 0
        )
