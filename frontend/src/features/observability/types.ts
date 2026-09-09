// 观测查询返回的摘要与详情 DTO；这些类型不授予 ingestion 写入权限。
export type ObservabilityWindow = "15m" | "1h" | "6h" | "24h" | "7d";

export type HealthStatus = "ok" | "unavailable";

export type TraceStatus = "ok" | "error";

export type LogLevel = "info" | "warning" | "error";

export type SafeScalar = boolean | number | string;

export interface ObservabilityCapabilities {
  windows: ObservabilityWindow[];
  default_window: ObservabilityWindow;
  maximum_page_size: number;
  retention_days: number;
  maximum_rows: number;
  row_limits: {
    spans: number;
    metrics: number;
    logs: number;
  };
  content_policy: "metadata_only";
}

export interface ObservabilitySeriesPoint {
  started_at_ms: number;
  commands: number;
  model_calls: number;
  tool_calls: number;
}

export interface LatencyPercentiles {
  p50: number | null;
  p95: number | null;
}

export interface ObservabilityMetrics {
  active_runs: number;
  commands: number;
  commands_per_minute: number;
  model_calls: number;
  tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  model_error_rate: number;
  tool_error_rate: number;
  latency_ms: {
    graph: LatencyPercentiles;
    model: LatencyPercentiles;
    tool: LatencyPercentiles;
    sse_ttfe: LatencyPercentiles;
  };
  series: ObservabilitySeriesPoint[];
}

export interface ObservabilityOverview {
  generated_at_ms: number;
  window: ObservabilityWindow;
  health: Record<string, HealthStatus>;
  storage: {
    spans: number;
    metrics: number;
    logs: number;
  };
  metrics: ObservabilityMetrics;
}

export interface TraceSummary {
  cursor: number;
  trace_id: string;
  started_at_ms: number;
  ended_at_ms: number;
  duration_ms: number;
  span_count: number;
  status: TraceStatus;
  services: string[];
}

export interface ObservabilitySpan {
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  service: string;
  name: string;
  started_at_ms: number;
  ended_at_ms: number;
  duration_ms: number;
  status: "unset" | TraceStatus;
  attributes: Record<string, SafeScalar>;
}

export interface TraceDetail {
  trace_id: string;
  status: TraceStatus;
  started_at_ms: number;
  ended_at_ms: number;
  spans: ObservabilitySpan[];
}

export interface SafeLogEntry {
  cursor: number;
  observed_at_ms: number;
  level: LogLevel;
  service: string;
  event: string;
  fields: Record<string, SafeScalar>;
}

export interface TelemetryDelivery {
  exported_batches: number;
  failed_batches: number;
  dropped_batches: number;
  status: "ok" | "degraded";
}
