"""Create tenant identity, session, and audit tables.

Revision ID: 0001_foundation
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


# A transaction-local GUC may revert to an empty string on pooled connections.
TENANT_SCOPE = "nullif(current_setting('metaflow.tenant_id', true), '')::uuid"


def upgrade():
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'sales', 'auditor')", name="valid_role"
        ),
        sa.CheckConstraint(
            "email = lower(email) AND email = btrim(email)", name="normalized_email"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="tenant_user"),
        sa.UniqueConstraint("tenant_id", "email", name="tenant_email"),
    )
    op.create_table(
        "sessions",
        sa.Column("tenant_id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.id"]
        ),
        sa.CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="valid_token_hash"),
    )
    op.create_index("sessions_expiration", "sessions", ["expires_at"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_id"], ["users.tenant_id", "users.id"]
        ),
    )
    op.create_index(
        "audit_logs_tenant_time", "audit_logs", ["tenant_id", "occurred_at", "id"]
    )

    for table in ("tenants", "users", "sessions", "audit_logs"):
        tenant_column = "id" if table == "tenants" else "tenant_id"
        scope = f"{tenant_column} = {TENANT_SCOPE}"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_scope ON {table} USING ({scope}) WITH CHECK ({scope})"
        )
        op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")

    op.execute("GRANT USAGE ON SCHEMA public TO metaflow_app")
    op.execute("GRANT SELECT ON tenants, users TO metaflow_app")
    op.execute("GRANT SELECT, INSERT, DELETE ON sessions TO metaflow_app")
    op.execute("GRANT SELECT, INSERT ON audit_logs TO metaflow_app")


def downgrade():
    op.execute("REVOKE USAGE ON SCHEMA public FROM metaflow_app")
    op.drop_index("audit_logs_tenant_time", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("sessions_expiration", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("tenants")
