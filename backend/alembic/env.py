"""Run transactional migrations with the dedicated database administrator URL."""

import os

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

if context.is_offline_mode():
    raise RuntimeError("Phase 1 migrations require a live PostgreSQL sandbox")

engine = create_engine(os.environ["DATABASE_ADMIN_URL"], poolclass=NullPool)
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
