#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
project="metalflow-verify-$(openssl rand -hex 6)"
env_file=$(mktemp)

compose() {
  env -u DATABASE_ADMIN_PASSWORD -u DATABASE_APP_PASSWORD -u SANDBOX_PASSWORD \
    docker compose --project-name "$project" --env-file "$env_file" \
    -f compose.yaml -f scripts/phase1-test.compose.yaml "$@"
}

cleanup() {
  status=$?
  if (( status != 0 )); then
    compose ps --all || true
    compose logs --tail 60 || true
  fi
  compose down --timeout 10 || status=1
  rm -f -- "$env_file"
  exit "$status"
}
trap cleanup EXIT

generate_secret() {
  local secret
  secret=$(openssl rand -hex 24)
  printf '%s=%s\n' "$1" "$secret"
}

generate_secret DATABASE_ADMIN_PASSWORD > "$env_file"
generate_secret DATABASE_APP_PASSWORD >> "$env_file"
generate_secret SANDBOX_PASSWORD >> "$env_file"

echo "Starting isolated MetalFlow Sandbox: $project"
compose up --build --wait --wait-timeout 120
compose run --rm --no-deps --build tests

echo "Rolling back schema on the disposable database"
compose stop frontend backend
compose run --rm --no-deps migrate python -m alembic downgrade base
compose exec -T db psql -U metaflow_admin -d metaflow -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
    IF to_regclass('public.tenants') IS NOT NULL OR
       to_regclass('public.users') IS NOT NULL OR
       to_regclass('public.sessions') IS NOT NULL OR
       to_regclass('public.audit_logs') IS NOT NULL OR
       to_regclass('public.customers') IS NOT NULL OR
       to_regclass('public.customer_contacts') IS NOT NULL OR
       to_regclass('public.follow_up_tasks') IS NOT NULL OR
       to_regclass('public.crm_import_batches') IS NOT NULL THEN
        RAISE EXCEPTION 'Application relations remain after downgrade';
    END IF;
END
$$;
SQL

echo "Reapplying migrations and starting the stack again"
compose run --rm --no-deps migrate
compose up --wait --wait-timeout 120
compose run --rm --no-deps tests
