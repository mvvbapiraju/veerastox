#!/usr/bin/env bash
set -euo pipefail

SUPPORTED_COMMANDS=(
  "veerastox-get-data"
  "veerastox-generate-signals"
  "veerastox-run-backtest"
  "veerastox-cleanup"
  "veerastox-beta-sp500"
  "veerastox-beta-nasdaq"
  "veerastox-beta-dji"
  "veerastox-beta-all"
  "veerastox-webapp"
)

is_supported_command() {
  local candidate="$1"
  local cmd
  for cmd in "${SUPPORTED_COMMANDS[@]}"; do
    if [[ "$cmd" == "$candidate" ]]; then
      return 0
    fi
  done
  return 1
}

print_usage() {
  cat <<'EOF'
Usage:
  ./init_project.sh [SUPPORTED_COMMAND [ARG ...]]

Runs project initialization:
  1) python3 -m pip install -r requirements.txt
  2) python3 -m pip install --no-deps -e .
  3) python3 -m compileall src scripts

If a supported command is provided, it runs after initialization.

Supported commands:
  - veerastox-get-data
  - veerastox-generate-signals
  - veerastox-run-backtest
  - veerastox-cleanup
  - veerastox-beta-sp500
  - veerastox-beta-nasdaq
  - veerastox-beta-dji
  - veerastox-beta-all
  - veerastox-webapp
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  print_usage
  exit 0
fi

post_cmd="${1:-}"
if [[ -n "$post_cmd" ]]; then
  if ! is_supported_command "$post_cmd"; then
    echo "Error: unsupported command '$post_cmd'" >&2
    echo >&2
    print_usage >&2
    exit 1
  fi
fi

python3 -m pip install -r requirements.txt
python3 -m pip install --no-deps -e .
python3 -m compileall src scripts

if [[ -n "$post_cmd" ]]; then
  shift
  "$post_cmd" "$@"
fi
