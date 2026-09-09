// 封装脱敏观测查询及 Agent 投递健康接口，DTO 与页面响应式状态分别维护。
import type {
  ObservabilityWindow,
  TraceStatus,
  LogLevel,
  ObservabilityCapabilities,
  ObservabilityOverview,
  TraceSummary,
  TraceDetail,
  SafeLogEntry,
  TelemetryDelivery,
} from "@/features/observability/types";
import axios, { type AxiosRequestConfig } from "axios";

interface ObservabilityEnvelope<T> {
  schema_version: "iteration6-observability-v1";
  status: string;
  data: T;
}

interface AgentEnvelope<T> {
  status: string;
  data: T;
}

/** 移除公开端点末尾的一个斜杠，供观测接口路径拼接。 */
const normalized = (baseUrl: string): string => baseUrl.replace(/\/$/, "");

/**
 * 读取观测响应信封并统一拒绝失败状态，不把服务错误误当作有效查询数据。
 * @param baseUrl 沿用当前 TypeScript 类型约束的输入。
 * @param path 沿用当前 TypeScript 类型约束的输入。
 * @param config 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
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

/** 读取本地观测的可用能力及保留策略说明。 */
export const loadObservabilityCapabilities = (baseUrl: string) =>
  request<ObservabilityCapabilities>(baseUrl, "/observability/v1/capabilities");

/** 按指定时间窗口查询聚合统计。 */
export const loadObservabilityOverview = (baseUrl: string, window: ObservabilityWindow) =>
  request<ObservabilityOverview>(baseUrl, "/observability/v1/overview", {
    params: { window },
  });

/** 按窗口及状态查询脱敏 Trace 摘要列表，不请求每条 Trace 详情。 */
export const listObservabilityTraces = (
  baseUrl: string,
  window: ObservabilityWindow,
  status: TraceStatus | "all",
) =>
  request<{ items: TraceSummary[]; next: number | null }>(baseUrl, "/observability/v1/traces", {
    params: { window, status: status === "all" ? undefined : status, limit: 50 },
  });

/** 按显式选择的 Trace ID 查询详情，供用户打开详情时使用。 */
export const loadObservabilityTrace = (baseUrl: string, traceId: string) =>
  request<TraceDetail>(baseUrl, `/observability/v1/traces/${encodeURIComponent(traceId)}`);

/** 按时间窗口与日志级别查询服务端脱敏列表。 */
export const listObservabilityLogs = (
  baseUrl: string,
  window: ObservabilityWindow,
  level: LogLevel | "all",
) =>
  request<{ items: SafeLogEntry[]; next: number | null }>(baseUrl, "/observability/v1/logs", {
    params: { window, level: level === "all" ? undefined : level, limit: 50 },
  });

/**
 * 从 Agent 端读取遥测投递健康，不读取业务任务正文。
 * @param agentBaseUrl 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
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
