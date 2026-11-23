#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
project=metalflow-local
env_file=.env.sandbox

compose() {
  env -u DATABASE_ADMIN_PASSWORD -u DATABASE_APP_PASSWORD -u SANDBOX_PASSWORD \
    docker compose --project-name "$project" --env-file "$env_file" -f compose.yaml "$@"
}

case "${1:-}" in
  up)
    if [[ ! -f "$env_file" ]]; then
      umask 077
      generated=$(mktemp .env.sandbox.XXXXXX)
      trap 'rm -f -- "$generated"' EXIT
      admin_password=$(openssl rand -hex 24)
      app_password=$(openssl rand -hex 24)
      sandbox_password=$(openssl rand -hex 24)
      {
        printf 'DATABASE_ADMIN_PASSWORD=%s\n' "$admin_password"
        printf 'DATABASE_APP_PASSWORD=%s\n' "$app_password"
        printf 'SANDBOX_PASSWORD=%s\n' "$sandbox_password"
      } > "$generated"
      if ! ln -- "$generated" "$env_file" && [[ ! -f "$env_file" ]]; then
        exit 1
      fi
    fi
    compose up --build --wait --wait-timeout 120
    ;;
  down)
    compose down
    ;;
  status)
    compose ps --all
    ;;
  logs)
    compose logs --tail 100
    ;;
  password)
    sed -n 's/^SANDBOX_PASSWORD=//p' "$env_file"
    ;;
  *)
    printf 'Usage: %s {up|down|status|logs|password}\n' "$0" >&2
    exit 2
    ;;
esac
