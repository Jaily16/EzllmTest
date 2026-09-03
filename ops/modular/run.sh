#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
exec python3 -B "$REPO_ROOT/scripts/modular_runtime.py" --repo-root "$REPO_ROOT" "$@"
