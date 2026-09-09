// 观测页快照与刷新生命周期；摘要、日志和可选详情分开加载，隐藏页面停止轮询。
import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  loadObservabilityCapabilities,
  loadObservabilityOverview,
  loadObservabilityTrace,
  loadTelemetryDelivery,
  listObservabilityLogs,
  listObservabilityTraces,
} from "@/features/observability/api/observability";
import type {
  LogLevel,
  ObservabilityCapabilities,
  ObservabilityOverview,
  ObservabilityWindow,
  SafeLogEntry,
  TelemetryDelivery,
  TraceDetail,
  TraceStatus,
  TraceSummary,
} from "@/features/observability/types";

const WINDOWS: readonly ObservabilityWindow[] = ["15m", "1h", "6h", "24h", "7d"];
const TRACE_ID_PATTERN = /^[0-9a-f]{32}$/;

export interface ObservabilityState {
  capabilities: Ref<ObservabilityCapabilities | null>;
  overview: Ref<ObservabilityOverview | null>;
  traces: Ref<TraceSummary[]>;
  logs: Ref<SafeLogEntry[]>;
  selectedTrace: Ref<TraceDetail | null>;
  selectedTraceId: Ref<string>;
  selectedWindow: Ref<ObservabilityWindow>;
  traceStatus: Ref<TraceStatus | "all">;
  logLevel: Ref<LogLevel | "all">;
  delivery: Ref<TelemetryDelivery | null>;
  loading: Ref<boolean>;
  refreshing: Ref<boolean>;
  error: Ref<string>;
  lastUpdatedLabel: Readonly<Ref<string>>;
  setWindow: (value: ObservabilityWindow) => void;
  setTraceStatus: (value: TraceStatus | "all") => void;
  setLogLevel: (value: LogLevel | "all") => void;
  selectTrace: (traceId: string) => Promise<void>;
  clearTrace: () => void;
  refreshNow: () => Promise<void>;
}

/** 仅接受单个字符串查询参数，数组或其他类型不作为选择值。 */
const queryValue = (value: unknown): string => (typeof value === "string" ? value : "");

/** 只接受支持的观测时间窗口，未知值回退到一小时。 */
const initialWindow = (value: unknown): ObservabilityWindow => {
  const candidate = queryValue(value) as ObservabilityWindow;
  return WINDOWS.includes(candidate) ? candidate : "1h";
};

/**
 * 组合观测摘要、脱敏日志和 Agent 投递健康；自动刷新保留上次有效结果，Trace 详情单独按选择加载。
 * @param observabilityBaseUrl 沿用当前 TypeScript 类型约束的输入。
 * @param agentBaseUrl 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
export const useObservability = (
  observabilityBaseUrl: string,
  agentBaseUrl: string,
): ObservabilityState => {
  const route = useRoute();
  const router = useRouter();
  const capabilities = ref<ObservabilityCapabilities | null>(null);
  const overview = ref<ObservabilityOverview | null>(null);
  const traces = ref<TraceSummary[]>([]);
  const logs = ref<SafeLogEntry[]>([]);
  const selectedTrace = ref<TraceDetail | null>(null);
  const initialTrace = queryValue(route.query.trace);
  const selectedTraceId = ref(TRACE_ID_PATTERN.test(initialTrace) ? initialTrace : "");
  const selectedWindow = ref<ObservabilityWindow>(initialWindow(route.query.window));
  const traceStatus = ref<TraceStatus | "all">("all");
  const logLevel = ref<LogLevel | "all">("all");
  const delivery = ref<TelemetryDelivery | null>(null);
  const loading = ref(true);
  const refreshing = ref(false);
  const error = ref("");
  const lastUpdatedAt = ref<number | null>(null);
  let intervalId: number | null = null;
  let mounted = false;

  /**
   * 派生用于界面展示或请求判断的last updated标签。
   */
  const lastUpdatedLabel = computed(() => {
    if (lastUpdatedAt.value === null) return "尚未刷新";
    return new Date(lastUpdatedAt.value).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  });

  /**
   * 没有选中 Trace 时清空详情；详情读取失败独立返回失败，不清空其他观测摘要。
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   */
  const loadSelectedTrace = async (): Promise<boolean> => {
    if (!selectedTraceId.value) {
      selectedTrace.value = null;
      return true;
    }
    try {
      selectedTrace.value = await loadObservabilityTrace(
        observabilityBaseUrl,
        selectedTraceId.value,
      );
      return true;
    } catch {
      selectedTrace.value = null;
      return false;
    }
  };

  /**
   * 并发读取摘要和列表，防止重复刷新；投递健康失败可降级，整体失败保留上次有效快照。
   * @param background 沿用当前 TypeScript 类型约束的输入。
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   */
  const loadSnapshot = async (background: boolean): Promise<void> => {
    if (refreshing.value) return;
    refreshing.value = true;
    if (!background && overview.value === null) loading.value = true;
    try {
      const capabilitiesRequest = capabilities.value
        ? Promise.resolve(capabilities.value)
        : loadObservabilityCapabilities(observabilityBaseUrl);
      const deliveryRequest = loadTelemetryDelivery(agentBaseUrl).catch(() => null);
      const [nextCapabilities, nextOverview, nextTraces, nextLogs, nextDelivery] =
        await Promise.all([
          capabilitiesRequest,
          loadObservabilityOverview(observabilityBaseUrl, selectedWindow.value),
          listObservabilityTraces(observabilityBaseUrl, selectedWindow.value, traceStatus.value),
          listObservabilityLogs(observabilityBaseUrl, selectedWindow.value, logLevel.value),
          deliveryRequest,
        ]);

      capabilities.value = nextCapabilities;
      overview.value = nextOverview;
      traces.value = nextTraces.items;
      logs.value = nextLogs.items;
      if (nextDelivery !== null) delivery.value = nextDelivery;
      const traceLoaded = await loadSelectedTrace();
      lastUpdatedAt.value = Date.now();
      error.value = traceLoaded ? "" : "无法读取所选 Trace，其他观测结果已更新。";
    } catch {
      error.value = overview.value
        ? "刷新失败，页面继续保留上一次有效结果。"
        : "本地观测服务暂不可用，请确认 8140 服务已就绪。";
    } finally {
      loading.value = false;
      refreshing.value = false;
    }
  };

  /** 将时间窗口和可选 Trace ID 写入观测页 URL，支持导航恢复。 */
  const replaceQuery = (traceId = selectedTraceId.value): void => {
    const query: Record<string, string> = { window: selectedWindow.value };
    if (traceId) query.trace = traceId;
    void router.replace({ path: "/observability", query });
  };

  /** 仅在支持的时间窗口发生变化时同步 URL 并刷新数据。 */
  const setWindow = (value: ObservabilityWindow): void => {
    if (!WINDOWS.includes(value) || value === selectedWindow.value) return;
    selectedWindow.value = value;
    replaceQuery();
    void loadSnapshot(false);
  };

  /** 更新 Trace 列表过滤条件并重新请求快照。 */
  const setTraceStatus = (value: TraceStatus | "all"): void => {
    traceStatus.value = value;
    void loadSnapshot(false);
  };

  /** 更新脱敏日志级别过滤条件并刷新快照。 */
  const setLogLevel = (value: LogLevel | "all"): void => {
    logLevel.value = value;
    void loadSnapshot(false);
  };

  /** 校验 Trace ID 后显式读取详情；失败保留列表并显示错误。 */
  const selectTrace = async (traceId: string): Promise<void> => {
    if (!TRACE_ID_PATTERN.test(traceId)) return;
    selectedTraceId.value = traceId;
    replaceQuery(traceId);
    try {
      selectedTrace.value = await loadObservabilityTrace(observabilityBaseUrl, traceId);
      error.value = "";
    } catch {
      error.value = "无法读取该 Trace，列表和其他观测结果仍然保留。";
    }
  };

  /** 清除详情选择及 URL 中的 Trace 参数，列表状态保持可用。 */
  const clearTrace = (): void => {
    selectedTraceId.value = "";
    selectedTrace.value = null;
    replaceQuery("");
  };

  /** 释放当前自动刷新定时器，避免卸载或隐藏后继续轮询。 */
  const stopTimer = (): void => {
    if (intervalId !== null) {
      window.clearInterval(intervalId);
      intervalId = null;
    }
  };

  /** 只在已挂载且页面可见时开启十秒刷新，并先释放旧定时器。 */
  const startTimer = (): void => {
    stopTimer();
    if (mounted && document.visibilityState === "visible") {
      intervalId = window.setInterval(() => void loadSnapshot(true), 10_000);
    }
  };

  /** 隐藏页面停止轮询；重新可见时立即刷新并恢复定时器。 */
  const handleVisibility = (): void => {
    if (document.visibilityState === "hidden") {
      stopTimer();
      return;
    }
    void loadSnapshot(true);
    startTimer();
  };

  watch(
    () => route.query.trace,
    (value) => {
      if (!mounted) return;
      const traceId = queryValue(value);
      if (traceId === selectedTraceId.value) return;
      if (!traceId) {
        selectedTraceId.value = "";
        selectedTrace.value = null;
      } else if (TRACE_ID_PATTERN.test(traceId)) {
        selectedTraceId.value = traceId;
        void loadSelectedTrace();
      }
    },
  );

  onMounted(() => {
    mounted = true;
    document.addEventListener("visibilitychange", handleVisibility);
    void loadSnapshot(false).finally(startTimer);
  });

  /**
   * 组件卸载时释放事件监听、定时器或流式连接。
   */
  onBeforeUnmount(() => {
    mounted = false;
    stopTimer();
    document.removeEventListener("visibilitychange", handleVisibility);
  });

  return {
    capabilities,
    overview,
    traces,
    logs,
    selectedTrace,
    selectedTraceId,
    selectedWindow,
    traceStatus,
    logLevel,
    delivery,
    loading,
    refreshing,
    error,
    lastUpdatedLabel,
    setWindow,
    setTraceStatus,
    setLogLevel,
    selectTrace,
    clearTrace,
    /** 触发前台刷新，复用并发抑制和上次有效快照保护。 */
    refreshNow: () => loadSnapshot(false),
  };
};
