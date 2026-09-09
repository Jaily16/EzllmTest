# 在本地 SQLite 保存已校验的脱敏记录，执行七天和十万行的保留上限。
"""Bounded, local SQLite storage for sanitized observability records."""

from __future__ import annotations
from ezllmtest.modules.observability.ports.storage import ObservabilityStorageError

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from ezllmtest.platform.telemetry.contracts import LogRecord, MetricRecord, SpanRecord
from ezllmtest.modules.observability.schemas.query import OBSERVABILITY_SCHEMA_VERSION


_EXPECTED_COLUMNS = {
    "observability_metadata": ("key", "value"),
    "spans": (
        "id",
        "trace_id",
        "span_id",
        "parent_span_id",
        "service",
        "name",
        "started_at_ms",
        "ended_at_ms",
        "duration_ms",
        "status",
        "attributes_json",
    ),
    "metric_points": (
        "id",
        "observed_at_ms",
        "start_time_ms",
        "service",
        "name",
        "kind",
        "value",
        "count",
        "total",
        "minimum",
        "maximum",
        "bounds_json",
        "bucket_counts_json",
        "labels_json",
    ),
    "log_entries": (
        "id",
        "observed_at_ms",
        "level",
        "service",
        "event",
        "fields_json",
    ),
}




def _stored_json(value: str) -> Any:
    """将已校验的观测结构序列化为稳定 JSON；这里只处理观测白名单内容，不是任意业务脱敏器。"""
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        raise ObservabilityStorageError(
            "observability_storage:read_failed"
        ) from None


def _json(value: Any) -> str:
    """将值编码为稳定 JSON 文本。"""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class ObservabilityStore:
    SPAN_SHARE = 50
    METRIC_SHARE = 30

    def __init__(self, path: Path, *, retention_days: int, max_rows: int) -> None:
        """记录 SQLite 路径、保留期和容量配置并建立锁，构造实例不会开始服务生命周期。"""
        if not path.is_absolute() or retention_days < 1 or max_rows < 100:
            raise ObservabilityStorageError("observability_storage:invalid_settings")
        self.path = path
        self.retention_days = retention_days
        self.max_rows = max_rows
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    @property
    def span_limit(self) -> int:
        """返回 span 记录的容量约束，供写入前的批次和保留策略使用。"""
        return self.max_rows * self.SPAN_SHARE // 100

    @property
    def metric_limit(self) -> int:
        """返回指标记录容量约束，不代表产品负载能力。"""
        return self.max_rows * self.METRIC_SHARE // 100

    @property
    def log_limit(self) -> int:
        """返回脱敏日志记录容量约束，避免本地观测无限增长。"""
        return self.max_rows - self.span_limit - self.metric_limit

    def open(self) -> None:
        """打开本地观测 SQLite 并初始化所需结构；应只由观测进程生命周期显式调用。"""
        with self._lock:
            if self._connection is not None:
                return
            connection: sqlite3.Connection | None = None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(
                    self.path,
                    timeout=3.0,
                    check_same_thread=False,
                )
                connection.row_factory = sqlite3.Row
                existing = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                    if not str(row[0]).startswith("sqlite_")
                }
                if existing and existing != set(_EXPECTED_COLUMNS):
                    raise ObservabilityStorageError(
                        "observability_storage:unrecognized_database"
                    )
                if existing:
                    for table, expected_columns in _EXPECTED_COLUMNS.items():
                        actual_columns = tuple(
                            str(row[1])
                            for row in connection.execute(f"PRAGMA table_info({table})")
                        )
                        if actual_columns != expected_columns:
                            raise ObservabilityStorageError(
                                "observability_storage:unrecognized_database"
                            )
                    version = connection.execute(
                        "SELECT value FROM observability_metadata WHERE key='schema_version'"
                    ).fetchone()
                    if version is None:
                        raise ObservabilityStorageError(
                            "observability_storage:missing_schema_version"
                        )
                    if version[0] != OBSERVABILITY_SCHEMA_VERSION:
                        raise ObservabilityStorageError(
                            "observability_storage:unsupported_schema_version"
                        )
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=NORMAL")
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA busy_timeout=3000")
                if not existing:
                    self._create_schema(connection)
                    connection.execute(
                        "INSERT INTO observability_metadata(key, value) VALUES('schema_version', ?)",
                        (OBSERVABILITY_SCHEMA_VERSION,),
                    )
                    connection.commit()
                self._connection = connection
                connection = None
            except ObservabilityStorageError:
                if connection is not None:
                    connection.close()
                raise
            except (OSError, sqlite3.Error):
                if connection is not None:
                    connection.close()
                raise ObservabilityStorageError(
                    "observability_storage:unavailable"
                ) from None

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        """创建观测专用表和索引，不操作项目 MySQL schema。"""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS observability_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS spans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                span_id TEXT NOT NULL UNIQUE,
                parent_span_id TEXT,
                service TEXT NOT NULL,
                name TEXT NOT NULL,
                started_at_ms INTEGER NOT NULL,
                ended_at_ms INTEGER NOT NULL,
                duration_ms REAL NOT NULL,
                status TEXT NOT NULL,
                attributes_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS spans_time_idx ON spans(ended_at_ms DESC, id DESC);
            CREATE INDEX IF NOT EXISTS spans_trace_idx ON spans(trace_id, started_at_ms, id);
            CREATE INDEX IF NOT EXISTS spans_status_idx ON spans(status, ended_at_ms DESC);
            CREATE TABLE IF NOT EXISTS metric_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at_ms INTEGER NOT NULL,
                start_time_ms INTEGER NOT NULL,
                service TEXT NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                value REAL,
                count INTEGER,
                total REAL,
                minimum REAL,
                maximum REAL,
                bounds_json TEXT NOT NULL,
                bucket_counts_json TEXT NOT NULL,
                labels_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS metrics_time_idx ON metric_points(observed_at_ms DESC, id DESC);
            CREATE INDEX IF NOT EXISTS metrics_name_idx ON metric_points(name, observed_at_ms DESC);
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at_ms INTEGER NOT NULL,
                level TEXT NOT NULL,
                service TEXT NOT NULL,
                event TEXT NOT NULL,
                fields_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS logs_time_idx ON log_entries(observed_at_ms DESC, id DESC);
            CREATE INDEX IF NOT EXISTS logs_level_idx ON log_entries(level, observed_at_ms DESC);
            """
        )

    def close(self) -> None:
        """关闭本实例 SQLite 连接，生命周期结束后不再接受查询或写入。"""
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def ready(self) -> bool:
        """检查本实例是否已具备可用连接，不能代替产品数据库或普通 worker 的就绪状态。"""
        with self._lock:
            try:
                return bool(
                    self._require().execute("SELECT 1").fetchone()[0] == 1
                )
            except (ObservabilityStorageError, sqlite3.Error):
                return False

    def _require(self) -> sqlite3.Connection:
        """要求观测连接已打开，未进入生命周期时明确失败而不隐式初始化。"""
        if self._connection is None:
            raise ObservabilityStorageError("observability_storage:not_open")
        return self._connection

    def insert_spans(self, records: Iterable[SpanRecord]) -> int:
        """将通过共享 wire schema 校验的脱敏 span 批次交给本地写入流程。"""
        rows = [
            (
                item.trace_id,
                item.span_id,
                item.parent_span_id,
                item.service,
                item.name,
                item.started_at_ms,
                item.ended_at_ms,
                item.duration_ms,
                item.status,
                _json(item.attributes),
            )
            for item in records
        ]
        return self._insert(
            """
            INSERT OR IGNORE INTO spans(
                trace_id, span_id, parent_span_id, service, name,
                started_at_ms, ended_at_ms, duration_ms, status, attributes_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def insert_metrics(self, records: Iterable[MetricRecord]) -> int:
        """保存允许的指标记录，不接收任意业务字段或高基数标签。"""
        rows = [
            (
                item.observed_at_ms,
                item.start_time_ms,
                item.service,
                item.name,
                item.kind,
                item.value,
                item.count,
                item.total,
                item.minimum,
                item.maximum,
                _json(item.bounds),
                _json(item.bucket_counts),
                _json(item.labels),
            )
            for item in records
        ]
        return self._insert(
            """
            INSERT INTO metric_points(
                observed_at_ms, start_time_ms, service, name, kind, value,
                count, total, minimum, maximum, bounds_json,
                bucket_counts_json, labels_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def insert_logs(self, records: Iterable[LogRecord]) -> int:
        """保存允许事件与字段组成的脱敏日志，不持久化异常正文或自由文本载荷。"""
        rows = [
            (
                item.observed_at_ms,
                item.level,
                item.service,
                item.event,
                _json(item.fields),
            )
            for item in records
        ]
        return self._insert(
            """
            INSERT INTO log_entries(observed_at_ms, level, service, event, fields_json)
            VALUES(?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _insert(self, statement: str, rows: list[tuple[Any, ...]]) -> int:
        """在本地连接和锁的约束下写入批次，并保持事务与清理边界。"""
        if not rows:
            return 0
        with self._lock:
            try:
                connection = self._require()
                before = connection.total_changes
                with connection:
                    connection.executemany(statement, rows)
                return connection.total_changes - before
            except (sqlite3.Error, ObservabilityStorageError):
                raise ObservabilityStorageError(
                    "observability_storage:write_failed"
                ) from None

    def cleanup(self, *, now_ms: int | None = None) -> dict[str, int]:
        """执行既定保留期和行数上限策略，仅作用于本地观测记录。"""
        current = int(time.time() * 1_000) if now_ms is None else now_ms
        cutoff = current - self.retention_days * 86_400_000
        with self._lock:
            try:
                connection = self._require()
                with connection:
                    connection.execute(
                        """
                        DELETE FROM spans WHERE trace_id IN (
                            SELECT trace_id FROM spans GROUP BY trace_id
                            HAVING MAX(ended_at_ms) < ?
                        )
                        """,
                        (cutoff,),
                    )
                    connection.execute(
                        "DELETE FROM metric_points WHERE observed_at_ms < ?",
                        (cutoff,),
                    )
                    connection.execute(
                        "DELETE FROM log_entries WHERE observed_at_ms < ?",
                        (cutoff,),
                    )
                    self._trim_traces(connection)
                    self._trim_rows(connection, "metric_points", self.metric_limit)
                    self._trim_rows(connection, "log_entries", self.log_limit)
                return self.counts()
            except (sqlite3.Error, ObservabilityStorageError):
                raise ObservabilityStorageError(
                    "observability_storage:cleanup_failed"
                ) from None

    def _trim_traces(self, connection: sqlite3.Connection) -> None:
        """按观测保留策略裁剪 trace/span 历史，不能把观测清理扩展为项目数据删除。"""
        count = int(connection.execute("SELECT COUNT(*) FROM spans").fetchone()[0])
        overflow = count - self.span_limit
        if overflow <= 0:
            return
        traces = connection.execute(
            """
            SELECT trace_id, COUNT(*) AS span_count
            FROM spans GROUP BY trace_id
            ORDER BY MAX(ended_at_ms), trace_id
            """
        ).fetchall()
        selected: list[str] = []
        removed = 0
        for row in traces:
            selected.append(str(row[0]))
            removed += int(row[1])
            if removed >= overflow:
                break
        for start in range(0, len(selected), 200):
            batch = selected[start : start + 200]
            placeholders = ",".join("?" for _ in batch)
            connection.execute(
                f"DELETE FROM spans WHERE trace_id IN ({placeholders})", batch
            )

    @staticmethod
    def _trim_rows(
        connection: sqlite3.Connection, table: str, limit: int
    ) -> None:
        """对指定观测表保留有界记录，表选择来自实现白名单而非用户 SQL。"""
        if table not in {"metric_points", "log_entries"}:
            raise ObservabilityStorageError("observability_storage:invalid_table")
        count = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        overflow = count - limit
        if overflow > 0:
            connection.execute(
                f"""
                DELETE FROM {table} WHERE id IN (
                    SELECT id FROM {table} ORDER BY observed_at_ms, id LIMIT ?
                )
                """,
                (overflow,),
            )

    def counts(self) -> dict[str, int]:
        """返回观测表计数供状态展示，不读取业务数据库。"""
        with self._lock:
            try:
                connection = self._require()
                return {
                    "spans": int(
                        connection.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
                    ),
                    "metrics": int(
                        connection.execute(
                            "SELECT COUNT(*) FROM metric_points"
                        ).fetchone()[0]
                    ),
                    "logs": int(
                        connection.execute(
                            "SELECT COUNT(*) FROM log_entries"
                        ).fetchone()[0]
                    ),
                }
            except (sqlite3.Error, ObservabilityStorageError):
                raise ObservabilityStorageError(
                    "observability_storage:read_failed"
                ) from None

    def trace_summaries(
        self, *, since_ms: int, status: str | None, limit: int, before: int | None
    ) -> list[dict[str, Any]]:
        """按时间和筛选条件返回 trace 摘要，详情通过独立查询获取。"""
        parameters: list[Any] = [since_ms, status, status, before, before, limit]
        query = """
            SELECT MIN(id) AS cursor, trace_id, MIN(started_at_ms) AS started_at_ms,
                   MAX(ended_at_ms) AS ended_at_ms, COUNT(*) AS span_count,
                   SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS error_count,
                   GROUP_CONCAT(DISTINCT service) AS services
            FROM spans
            GROUP BY trace_id
            HAVING MAX(ended_at_ms) >= ?
               AND (? IS NULL OR
                    CASE WHEN SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) > 0
                         THEN 'error' ELSE 'ok' END = ?)
               AND (? IS NULL OR MIN(id) < ?)
            ORDER BY ended_at_ms DESC, cursor DESC LIMIT ?
        """
        with self._lock:
            try:
                rows = self._require().execute(query, parameters).fetchall()
            except (sqlite3.Error, ObservabilityStorageError):
                raise ObservabilityStorageError(
                    "observability_storage:read_failed"
                ) from None
        return [
            {
                "cursor": int(row["cursor"]),
                "trace_id": str(row["trace_id"]),
                "started_at_ms": int(row["started_at_ms"]),
                "ended_at_ms": int(row["ended_at_ms"]),
                "duration_ms": max(0, int(row["ended_at_ms"]) - int(row["started_at_ms"])),
                "span_count": int(row["span_count"]),
                "status": "error" if int(row["error_count"]) else "ok",
                "services": sorted(str(row["services"] or "").split(",")),
            }
            for row in rows
        ]

    def trace_detail(self, trace_id: str) -> dict[str, Any] | None:
        """读取指定 trace 的观测结构；该接口不重放原始模型或工具调用。"""
        with self._lock:
            try:
                rows = self._require().execute(
                    """
                    SELECT trace_id, span_id, parent_span_id, service, name,
                           started_at_ms, ended_at_ms, duration_ms, status,
                           attributes_json
                    FROM spans WHERE trace_id=? ORDER BY started_at_ms, id
                    """,
                    (trace_id,),
                ).fetchall()
            except (sqlite3.Error, ObservabilityStorageError):
                raise ObservabilityStorageError(
                    "observability_storage:read_failed"
                ) from None
        if not rows:
            return None
        spans = [
            {
                "trace_id": str(row["trace_id"]),
                "span_id": str(row["span_id"]),
                "parent_span_id": row["parent_span_id"],
                "service": str(row["service"]),
                "name": str(row["name"]),
                "started_at_ms": int(row["started_at_ms"]),
                "ended_at_ms": int(row["ended_at_ms"]),
                "duration_ms": float(row["duration_ms"]),
                "status": str(row["status"]),
                "attributes": _stored_json(row["attributes_json"]),
            }
            for row in rows
        ]
        return {
            "trace_id": trace_id,
            "status": "error" if any(item["status"] == "error" for item in spans) else "ok",
            "started_at_ms": min(item["started_at_ms"] for item in spans),
            "ended_at_ms": max(item["ended_at_ms"] for item in spans),
            "spans": spans,
        }

    def logs(
        self,
        *,
        since_ms: int,
        level: str | None,
        service: str | None,
        limit: int,
        before: int | None,
    ) -> list[dict[str, Any]]:
        """在有界筛选窗口内读取脱敏日志，禁止任意 SQL 或自由字段查询。"""
        clauses = ["observed_at_ms >= ?"]
        parameters: list[Any] = [since_ms]
        if level is not None:
            clauses.append("level = ?")
            parameters.append(level)
        if service is not None:
            clauses.append("service = ?")
            parameters.append(service)
        if before is not None:
            clauses.append("id < ?")
            parameters.append(before)
        parameters.append(limit)
        query = f"""
            SELECT id, observed_at_ms, level, service, event, fields_json
            FROM log_entries WHERE {' AND '.join(clauses)}
            ORDER BY observed_at_ms DESC, id DESC LIMIT ?
        """
        with self._lock:
            try:
                rows = self._require().execute(query, parameters).fetchall()
            except (sqlite3.Error, ObservabilityStorageError):
                raise ObservabilityStorageError(
                    "observability_storage:read_failed"
                ) from None
        return [
            {
                "cursor": int(row["id"]),
                "observed_at_ms": int(row["observed_at_ms"]),
                "level": str(row["level"]),
                "service": str(row["service"]),
                "event": str(row["event"]),
                "fields": _stored_json(row["fields_json"]),
            }
            for row in rows
        ]

    def metrics_since(self, since_ms: int) -> list[dict[str, Any]]:
        """读取窗口内指标供纯聚合函数计算，不访问外部监控服务。"""
        with self._lock:
            try:
                rows = self._require().execute(
                    """
                    SELECT observed_at_ms, start_time_ms, service, name, kind,
                           value, count, total, minimum, maximum, bounds_json,
                           bucket_counts_json, labels_json
                    FROM metric_points WHERE observed_at_ms >= ?
                    ORDER BY observed_at_ms, id
                    """,
                    (since_ms,),
                ).fetchall()
            except (sqlite3.Error, ObservabilityStorageError):
                raise ObservabilityStorageError(
                    "observability_storage:read_failed"
                ) from None
        return [
            {
                "observed_at_ms": int(row["observed_at_ms"]),
                "start_time_ms": int(row["start_time_ms"]),
                "service": str(row["service"]),
                "name": str(row["name"]),
                "kind": str(row["kind"]),
                "value": row["value"],
                "count": row["count"],
                "total": row["total"],
                "minimum": row["minimum"],
                "maximum": row["maximum"],
                "bounds": _stored_json(row["bounds_json"]),
                "bucket_counts": _stored_json(row["bucket_counts_json"]),
                "labels": _stored_json(row["labels_json"]),
            }
            for row in rows
        ]
