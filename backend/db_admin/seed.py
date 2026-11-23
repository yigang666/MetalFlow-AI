"""Create stable synthetic tenants and accounts in the sandbox."""

import os
from hashlib import scrypt
from secrets import token_bytes
from uuid import UUID, uuid5

from sqlalchemy import create_engine, text

TENANTS = {
    UUID("11111111-1111-4111-8111-111111111111"): "Sandbox Tenant A",
    UUID("22222222-2222-4222-8222-222222222222"): "Sandbox Tenant B",
}
ACCOUNTS = {
    "owner": "owner",
    "admin": "admin",
    "sales": "sales",
    "auditor": "auditor",
    "disabled": "sales",
}


def password_hash(password):
    salt = token_bytes(16)
    digest = scrypt(password, salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def main():
    password = os.environ["SANDBOX_PASSWORD"].encode("utf-8")
    if not 16 <= len(password) <= 128:
        raise ValueError("SANDBOX_PASSWORD must contain 16 to 128 UTF-8 bytes")

    engine = create_engine(os.environ["DATABASE_ADMIN_URL"], hide_parameters=True)
    with engine.begin() as connection:
        for tenant_id, name in TENANTS.items():
            connection.execute(
                text("SELECT set_config('metaflow.tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            connection.execute(
                text(
                    "INSERT INTO tenants (id, name) VALUES (:id, :name) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tenant_id, "name": name},
            )
            for account, role in ACCOUNTS.items():
                email = f"{account}@example.test"
                connection.execute(
                    text(
                        """
                        INSERT INTO users (id, tenant_id, email, role, active, password_hash)
                        VALUES (:id, :tenant_id, :email, :role, :active, :password_hash)
                        ON CONFLICT (tenant_id, email) DO NOTHING
                        """
                    ),
                    {
                        "id": uuid5(tenant_id, email),
                        "tenant_id": tenant_id,
                        "email": email,
                        "role": role,
                        "active": account != "disabled",
                        "password_hash": password_hash(password),
                    },
                )
    engine.dispose()


if __name__ == "__main__":
    main()
