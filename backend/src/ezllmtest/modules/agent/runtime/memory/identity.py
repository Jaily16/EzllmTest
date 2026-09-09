"""可信 scope 和线程身份：纯计算，不访问 Redis 或项目文件。"""
from __future__ import annotations
import hashlib
import json
import re
from ezllmtest.modules.agent.domain.contracts import TrustedProjectScope
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
def derive_agent_scope_hash(
    scope: TrustedProjectScope,
    graph_version: str,
) -> str:
    """将可信项目、操作者及 scope 版本规范化后派生隔离标识，不读取项目文件或 Redis。"""
    if not graph_version or len(graph_version) > 128:
        raise ValueError("graph_version is invalid")
    canonical = json.dumps(
        {
            "graph_version": graph_version,
            "scope": scope.model_dump(mode="json"),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

def derive_storage_thread_id(scope_hash: str, external_thread_id: str) -> str:
    """把线程标识绑定到可信 scope，防止不同项目使用相同 thread ID 访问同一记录。"""
    if not _HEX_64.fullmatch(scope_hash):
        raise ValueError("scope_hash must be a lowercase SHA-256 digest")
    if not external_thread_id or len(external_thread_id) > 128:
        raise ValueError("external_thread_id is invalid")
    return hashlib.sha256(
        f"{scope_hash}\0{external_thread_id}".encode("utf-8")
    ).hexdigest()
