#!/usr/bin/env bash
# Scan the working tree for secrets. Does not rewrite git history.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if ! command -v gitleaks >/dev/null 2>&1; then
  echo "Install gitleaks first: brew install gitleaks" >&2
  exit 1
fi
exec gitleaks detect --no-banner --source "$ROOT" --config "$ROOT/.gitleaks.toml"
