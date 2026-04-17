#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

API_BASE_URL="${API_BASE_URL:-}"
PASS=0
FAIL=0

# Prefer python3 (many images use it); fall back to python.
py_runner() {
  if command -v python3 >/dev/null 2>&1 && python3 -c "import pytest" >/dev/null 2>&1; then
    echo "python3"
  elif command -v python >/dev/null 2>&1 && python -c "import pytest" >/dev/null 2>&1; then
    echo "python"
  else
    echo ""
  fi
}

# Ensure the backend image is built from backend/Dockerfile (Python + requirements), not a stale/custom image.
ensure_backend_image_for_tests() {
  if docker compose run --rm --no-deps -T backend python -c "import pytest, asyncpg" >/dev/null 2>&1; then
    return 0
  fi
  yellow "Building backend image from backend/Dockerfile (required for API tests)..."
  docker compose build backend
}

green()  { printf "\033[32m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

banner() {
  echo ""
  echo "========================================"
  echo "  $1"
  echo "========================================"
  echo ""
}

# API tests default to in-process ASGI (API_INPROCESS=1): only PostgreSQL must be running.
ensure_postgres_for_api_tests() {
  command -v docker >/dev/null 2>&1 || return 0
  [ -f docker-compose.yml ] || return 0
  yellow "Starting PostgreSQL for API tests (in-process ASGI; no Uvicorn port needed)..."
  if ! docker compose up -d --wait db 2>/dev/null; then
    docker compose up -d db
  fi
}

# Legacy: real HTTP to a running backend (set API_INPROCESS=0).
ensure_http_api_stack_if_needed() {
  command -v docker >/dev/null 2>&1 || return 0
  [ -f docker-compose.yml ] || return 0
  if [ -n "${API_BASE_URL:-}" ]; then
    return 0
  fi
  local candidate
  for candidate in \
    "http://127.0.0.1:8001" "http://127.0.0.1:8000" \
    "http://localhost:8001" "http://localhost:8000"; do
    if http_get_ok "$candidate/api/v1/health"; then
      return 0
    fi
  done
  yellow "Starting PostgreSQL and backend (Docker Compose) for HTTP API tests..."
  if ! docker compose up -d --wait db backend 2>/dev/null; then
    docker compose up -d db backend
  fi
}

http_get_ok() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -sf --connect-timeout 2 --max-time 5 "$url" >/dev/null 2>&1 && return 0
  fi
  command -v python3 >/dev/null 2>&1 || return 1
  python3 -c "import urllib.request; urllib.request.urlopen('$url', timeout=5)" >/dev/null 2>&1
}

verify_http_api_reachable() {
  yellow "Waiting for live backend at $API_BASE_URL/api/v1/health ..."
  local i
  for i in $(seq 1 30); do
    if http_get_ok "$API_BASE_URL/api/v1/health"; then
      green "Backend health OK."
      return 0
    fi
    sleep 2
  done
  red "Backend not reachable at $API_BASE_URL"
  return 1
}

run_pytest() {
  local test_path="$1"
  shift

  # API tests always run in the backend container (Python + backend/requirements.txt).
  if [[ "$test_path" == API_tests ]] || [[ "$test_path" == API_tests/* ]]; then
    export API_INPROCESS="${API_INPROCESS:-1}"
    export API_BASE_URL="${API_BASE_URL:-http://test}"
    if ! command -v docker >/dev/null 2>&1; then
      red "API tests require Docker."
      return 127
    fi
    [ -f docker-compose.yml ] || {
      red "docker-compose.yml not found."
      return 127
    }
    ensure_backend_image_for_tests
    yellow "Running API tests in the backend container..."
    docker compose run --rm --no-deps -T -w /workspace \
      -e PYTHONPATH=/workspace/backend \
      -e API_INPROCESS="${API_INPROCESS:-1}" \
      -e API_BASE_URL="${API_BASE_URL:-http://test}" \
      backend python -m pytest -v --tb=short -o cache_dir=/tmp/pytest_cache \
      "$test_path" "$@"
    return $?
  fi

  local py
  py="$(py_runner)"
  if [ -n "$py" ]; then
    PYTHONPATH="${SCRIPT_DIR}/backend:${PYTHONPATH:-}" "$py" -m pytest "$test_path" -v --tb=short "$@"
    return $?
  fi

  if command -v docker >/dev/null 2>&1 && [ -f docker-compose.yml ]; then
    yellow "Host python has no pytest; running tests in the backend container..."
    docker compose run --rm --no-deps -T -w /workspace \
      -e PYTHONPATH=/workspace/backend \
      backend python -m pytest -v --tb=short -o cache_dir=/tmp/pytest_cache \
      "$test_path" "$@"
    return $?
  fi

  red "pytest is unavailable (install pytest on the host or use Docker)."
  return 127
}

run_unit_tests() {
  banner "Unit Tests"
  if [ -d "unit_tests" ]; then
    yellow "Running backend unit tests..."
    run_pytest unit_tests/backend/
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
      green "Unit tests passed."
      PASS=$((PASS + 1))
    else
      red "Unit tests failed (exit code $exit_code)."
      FAIL=$((FAIL + 1))
    fi
  else
    yellow "No unit_tests/ directory found. Skipping."
  fi
}

run_api_tests() {
  banner "API Tests"
  export API_INPROCESS="${API_INPROCESS:-1}"
  if [ "$API_INPROCESS" = "0" ] || [ "$API_INPROCESS" = "false" ]; then
    export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8001}"
    ensure_http_api_stack_if_needed
    verify_http_api_reachable
  else
    export API_BASE_URL="${API_BASE_URL:-http://test}"
    if [ -f .env ]; then
      set -a
      # shellcheck source=/dev/null
      . ./.env
      set +a
    fi
    ensure_postgres_for_api_tests
  fi

  if [ -d "API_tests" ]; then
    yellow "Running API tests (API_INPROCESS=$API_INPROCESS, API_BASE_URL=$API_BASE_URL) ..."
    API_BASE_URL="$API_BASE_URL" API_INPROCESS="$API_INPROCESS" run_pytest API_tests/
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
      green "API tests passed."
      PASS=$((PASS + 1))
    else
      red "API tests failed (exit code $exit_code)."
      FAIL=$((FAIL + 1))
    fi
  else
    yellow "No API_tests/ directory found. Skipping."
  fi
}

MODE="${1:-all}"

case "$MODE" in
  unit) run_unit_tests ;;
  api)  run_api_tests ;;
  all)  run_unit_tests; run_api_tests ;;
  *)    echo "Usage: $0 [unit|api|all]"; exit 1 ;;
esac

banner "Test Summary"
echo "Passed: $PASS"
if [ $FAIL -gt 0 ]; then
  red "Failed: $FAIL"
  exit 1
fi
green "All test suites passed."
exit 0
