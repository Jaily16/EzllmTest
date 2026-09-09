"""bootstrap 提供运行期 adapter 工厂，应用不构造 Redis/序列化实现。"""
from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class RuntimeAdapters:
    serializer: Any
    budget_ledger: Any
    checkpoint: Callable[..., Any]
