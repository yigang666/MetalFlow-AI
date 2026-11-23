"""Create customer, contact, follow-up, and import receipt tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_crm"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

TENANT = "nullif(current_setting('metaflow.tenant_id', true), '')::uuid"
ACTOR = "nullif(current_setting('metaflow.crm_actor', true), '')::uuid"
ROLE = "current_setting('metaflow.crm_role', true)"
CRM_TABLES = ("customers", "customer_contacts", "follow_up_tasks", "crm_import_batches")


def active_actor(table, roles):
    return f"""
        {table}.tenant_id = {TENANT}
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.tenant_id = {table}.tenant_id
                AND users.id = {ACTOR}
                AND users.active
                AND users.role = {ROLE}
                AND users.role IN ({roles})
        )
    """


def visible_parent(table):
    # This lookup uses the same customer SELECT policy, including ownership.
    return f"""
        {table}.tenant_id = {TENANT}
        AND EXISTS (
            SELECT 1 FROM customers
            WHERE customers.tenant_id = {table}.tenant_id
                AND customers.id = {table}.customer_id
        )
    """


def enable_policies():
    for table in CRM_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")

    managers = "'owner', 'admin'"
    crm_roles = "'owner', 'admin', 'sales'"
    customer_read = f"""
        {active_actor("customers", crm_roles)}
        AND ({ROLE} IN ({managers}) OR customers.owner_id = {ACTOR})
    """
    customer_manage = active_actor("customers", managers)
    eligible_owner = f"""
        {customer_manage}
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.tenant_id = customers.tenant_id
                AND users.id = customers.owner_id
                AND users.active
                AND users.role IN ({crm_roles})
        )
    """
    op.execute(
        f"CREATE POLICY customer_read ON customers FOR SELECT TO metaflow_app "
        f"USING ({customer_read})"
    )
    op.execute(
        f"CREATE POLICY customer_insert ON customers FOR INSERT TO metaflow_app "
        f"WITH CHECK ({eligible_owner})"
    )
    op.execute(
        f"CREATE POLICY customer_assign ON customers FOR UPDATE TO metaflow_app "
        f"USING ({customer_manage}) WITH CHECK ({eligible_owner})"
    )

    for table in ("customer_contacts", "follow_up_tasks", "crm_import_batches"):
        scope = (
            active_actor(table, managers)
            if table == "crm_import_batches"
            else visible_parent(table)
        )
        op.execute(
            f"CREATE POLICY crm_read ON {table} FOR SELECT TO metaflow_app USING ({scope})"
        )
        op.execute(
            f"CREATE POLICY crm_insert ON {table} FOR INSERT TO metaflow_app "
            f"WITH CHECK ({scope})"
        )
    task_scope = visible_parent("follow_up_tasks")
    op.execute(
        "CREATE POLICY task_complete ON follow_up_tasks FOR UPDATE TO metaflow_app "
        f"USING ({task_scope}) WITH CHECK ({task_scope})"
    )

    op.execute("GRANT SELECT, INSERT ON customers TO metaflow_app")
    op.execute("GRANT UPDATE (owner_id) ON customers TO metaflow_app")
    op.execute("GRANT SELECT, INSERT ON customer_contacts TO metaflow_app")
    op.execute("GRANT SELECT, INSERT ON follow_up_tasks TO metaflow_app")
    op.execute("GRANT UPDATE (completed_at) ON follow_up_tasks TO metaflow_app")
    op.execute("GRANT SELECT, INSERT ON crm_import_batches TO metaflow_app")


def upgrade():
    op.add_column("audit_logs", sa.Column("resource_id", sa.Uuid()))
    op.add_column("audit_logs", sa.Column("details", postgresql.JSONB()))
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("country", sa.Text()),
        sa.Column("website", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", "id", name="tenant_customer"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "owner_id"], ["users.tenant_id", "users.id"]
        ),
        sa.CheckConstraint("btrim(name) <> ''", name="customer_name_present"),
    )
    op.create_index(
        "customers_tenant_created", "customers", ["tenant_id", "created_at", "id"]
    )
    op.create_index("customers_tenant_owner", "customers", ["tenant_id", "owner_id"])
    op.create_table(
        "customer_contacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text()),
        sa.Column("phone", sa.Text()),
        sa.Column("linkedin_url", sa.Text()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"]
        ),
        sa.CheckConstraint("btrim(name) <> ''", name="contact_name_present"),
    )
    op.create_index(
        "contacts_customer", "customer_contacts", ["tenant_id", "customer_id", "id"]
    )
    op.create_table(
        "follow_up_tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"]
        ),
        sa.CheckConstraint("btrim(title) <> ''", name="follow_up_title_present"),
    )
    op.create_index(
        "follow_ups_customer", "follow_up_tasks", ["tenant_id", "customer_id", "id"]
    )
    op.create_table(
        "crm_import_batches",
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), primary_key=True
        ),
        sa.Column("request_hash", sa.Text(), primary_key=True),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'", name="crm_import_request_digest"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(response) = 'object'", name="crm_import_response_object"
        ),
    )
    enable_policies()


def downgrade():
    for table in reversed(CRM_TABLES):
        op.drop_table(table)
    op.drop_column("audit_logs", "details")
    op.drop_column("audit_logs", "resource_id")
