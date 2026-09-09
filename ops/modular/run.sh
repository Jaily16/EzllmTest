#!/usr/bin/env sh
# 使用当前环境 python3 调用可选 runner；保留 exec 的信号转交。此包装不代表 Linux 独立 token 共享已验证。
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
exec python3 -B "$REPO_ROOT/ops/modular_runtime.py" --repo-root "$REPO_ROOT" "$@"
