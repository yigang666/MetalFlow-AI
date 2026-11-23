"""Create the sandbox runtime login before applying migrations."""

import os

from psycopg import Error, sql
from sqlalchemy import create_engine, text

ROLE_NAME = "metaflow_app"


def main():
    password = os.environ["DATABASE_APP_PASSWORD"]
    if len(password) < 16:
        raise ValueError("DATABASE_APP_PASSWORD must contain at least 16 characters")

    engine = create_engine(os.environ["DATABASE_ADMIN_URL"], hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(173951, 1)"))
        role = connection.execute(
            text(
                """
                SELECT r.rolsuper, r.rolcreaterole, r.rolcreatedb, r.rolreplication, r.rolbypassrls,
                       EXISTS (SELECT 1 FROM pg_auth_members WHERE member = r.oid) AS has_memberships
                FROM pg_roles AS r
                WHERE r.rolname = :role
                """
            ),
            {"role": ROLE_NAME},
        ).one_or_none()
        if role is not None and any(role):
            raise RuntimeError(
                "The pre-existing metaflow_app role has unsafe privileges"
            )

        # PostgreSQL role DDL requires a literal rather than a bind parameter.
        operation = "CREATE" if role is None else "ALTER"
        statement = sql.SQL(
            operation + " ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
            "NOREPLICATION NOBYPASSRLS PASSWORD {}"
        ).format(sql.Identifier(ROLE_NAME), sql.Literal(password))
        driver = connection.connection.driver_connection
        if driver is None:
            raise RuntimeError("No active connection for sandbox role provisioning")
        try:
            with driver.cursor() as cursor:
                cursor.execute(statement)
        except Error:
            raise RuntimeError("Could not provision the sandbox runtime role") from None

        connection.execute(
            text("REVOKE CREATE ON SCHEMA public FROM PUBLIC, metaflow_app")
        )
    engine.dispose()


if __name__ == "__main__":
    main()
