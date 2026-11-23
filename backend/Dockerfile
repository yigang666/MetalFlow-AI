FROM python:3.13-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --disable-pip-version-check --no-cache-dir -r requirements.txt
RUN groupadd --system metaflow && useradd --system --no-create-home --gid metaflow metaflow

FROM base AS admin
COPY alembic.ini ./
COPY alembic ./alembic
COPY db_admin ./db_admin
USER metaflow

FROM base AS runtime
COPY app ./app
USER metaflow
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
COPY requirements-dev.txt ./
RUN pip install --disable-pip-version-check --no-cache-dir -r requirements-dev.txt
COPY ruff.toml ./
COPY tests ./tests
USER metaflow
CMD ["sh", "-ec", "ruff check --no-cache app tests && mypy --check-untyped-defs --cache-dir=/dev/null app && python -m pytest -p no:cacheprovider tests"]
