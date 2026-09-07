import axios, { type AxiosRequestConfig } from "axios";

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

interface ObservabilityEnvelope<T> {
  schema_version: "iteration6-observability-v1";
  status: string;
  data: T;
}

interface AgentEnvelope<T> {
  status: string;
  data: T;
}

/**
 * 处理normalized，并保持现有输入输出约定。
 */
const normalized = (baseUrl: string): string => baseUrl.replace(/\/$/, "");

/**
 * 处理请求，并保持现有输入输出约定。
 *
 * @param baseUrl 沿用当前 TypeScript 类型约束的输入。
 * @param path 沿用当前 TypeScript 类型约束的输入。
 * @param config 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
 */
const request = async <T>(
  baseUrl: string,
  path: string,
  config: AxiosRequestConfig = {},
): Promise<T> => {
  const response = await axios.request<ObservabilityEnvelope<T>>({
    url: `${normalized(baseUrl)}${path}`,
    method: "GET",
    ...config,
  });
  if (
    response.status >= 400 ||
    response.data?.schema_version !== "iteration6-observability-v1" ||
    response.data?.status !== "success"
  ) {
    throw new Error("本地观测服务暂时无法完成请求");
  }
  return response.data.data;
};

/**
 * 加载观测能力清单，并保持现有状态与错误处理语义。
 */
export const loadObservabilityCapabilities = (baseUrl: string) =>
  request<ObservabilityCapabilities>(baseUrl, "/observability/v1/capabilities");

/**
 * 加载观测总览，并保持现有状态与错误处理语义。
 */
export const loadObservabilityOverview = (baseUrl: string, window: ObservabilityWindow) =>
  request<ObservabilityOverview>(baseUrl, "/observability/v1/overview", {
    params: { window },
  });

/**
 * 处理list观测 Trace，并保持现有输入输出约定。
 */
export const listObservabilityTraces = (
  baseUrl: string,
  window: ObservabilityWindow,
  status: TraceStatus | "all",
) =>
  request<{ items: TraceSummary[]; next: number | null }>(baseUrl, "/observability/v1/traces", {
    params: { window, status: status === "all" ? undefined : status, limit: 50 },
  });

/**
 * 加载观测 Trace，并保持现有状态与错误处理语义。
 */
export const loadObservabilityTrace = (baseUrl: string, traceId: string) =>
  request<TraceDetail>(baseUrl, `/observability/v1/traces/${encodeURIComponent(traceId)}`);

/**
 * 处理list观测日志，并保持现有输入输出约定。
 */
export const listObservabilityLogs = (
  baseUrl: string,
  window: ObservabilityWindow,
  level: LogLevel | "all",
) =>
  request<{ items: SafeLogEntry[]; next: number | null }>(baseUrl, "/observability/v1/logs", {
    params: { window, level: level === "all" ? undefined : level, limit: 50 },
  });

/**
 * 加载telemetry传输，并保持现有状态与错误处理语义。
 *
 * @param agentBaseUrl 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
 */
export const loadTelemetryDelivery = async (agentBaseUrl: string): Promise<TelemetryDelivery> => {
  const response = await axios.get<AgentEnvelope<{ telemetry?: { delivery?: TelemetryDelivery } }>>(
    `${normalized(agentBaseUrl)}/health`,
  );
  const delivery = response.data?.data?.telemetry?.delivery;
  if (response.status >= 400 || response.data?.status !== "success" || !delivery) {
    throw new Error("Agent 遥测状态暂不可用");
  }
  return delivery;
};
