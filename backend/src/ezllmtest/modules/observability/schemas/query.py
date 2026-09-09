"""观测查询窗口与本地存储版本；不是生产者的共享 wire schema。"""
import time

OBSERVABILITY_SCHEMA_VERSION = "iteration6-observability-v1"



WINDOW_MILLISECONDS = {
    "15m": 15 * 60 * 1_000,
    "1h": 60 * 60 * 1_000,
    "6h": 6 * 60 * 60 * 1_000,
    "24h": 24 * 60 * 60 * 1_000,
    "7d": 7 * 24 * 60 * 60 * 1_000,
}



def window_start_ms(window: str, *, now_ms: int | None = None) -> int:
    """把受支持的查询窗口换算为开始时间；未知窗口不扩展为无限历史查询。"""
    duration = WINDOW_MILLISECONDS.get(window)
    if duration is None:
        raise ValueError("unsupported observability window")
    current = int(time.time() * 1_000) if now_ms is None else now_ms
    return max(0, current - duration)
