import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  loadObservabilityCapabilities,
  loadObservabilityOverview,
  loadObservabilityTrace,
  loadTelemetryDelivery,
  listObservabilityLogs,
  listObservabilityTraces,
  type LogLevel,
  type ObservabilityCapabilities,
  type ObservabilityOverview,
  type ObservabilityWindow,
  type SafeLogEntry,
  type TelemetryDelivery,
  type TraceDetail,
  type TraceStatus,
  type TraceSummary,
} from "@/features/observability/state/observability";

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

/**
 * 处理查询值，并保持现有输入输出约定。
 */
const queryValue = (value: unknown): string => (typeof value === "string" ? value : "");

/**
 * 处理initial时间窗口，并保持现有输入输出约定。
 */
const initialWindow = (value: unknown): ObservabilityWindow => {
  const candidate = queryValue(value) as ObservabilityWindow;
  return WINDOWS.includes(candidate) ? candidate : "1h";
};

/**
 * 管理本地观测查询、窗口切换、自动刷新与 Trace 选择。
 *
 * @param observabilityBaseUrl 沿用当前 TypeScript 类型约束的输入。
 * @param agentBaseUrl 沿用当前 TypeScript 类型约束的输入。
 *
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
   * 加载已选 Trace，并保持现有状态与错误处理语义。
   *
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
   * 加载snapshot，并保持现有状态与错误处理语义。
   *
   * @param background 沿用当前 TypeScript 类型约束的输入。
   *
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

  /**
   * 处理replace查询，并保持现有输入输出约定。
   */
  const replaceQuery = (traceId = selectedTraceId.value): void => {
    const query: Record<string, string> = { window: selectedWindow.value };
    if (traceId) query.trace = traceId;
    void router.replace({ path: "/observability", query });
  };

  /**
   * 设置时间窗口，并保持现有状态与错误处理语义。
   */
  const setWindow = (value: ObservabilityWindow): void => {
    if (!WINDOWS.includes(value) || value === selectedWindow.value) return;
    selectedWindow.value = value;
    replaceQuery();
    void loadSnapshot(false);
  };

  /**
   * 设置Trace状态，并保持现有状态与错误处理语义。
   */
  const setTraceStatus = (value: TraceStatus | "all"): void => {
    traceStatus.value = value;
    void loadSnapshot(false);
  };

  /**
   * 设置日志级别，并保持现有状态与错误处理语义。
   */
  const setLogLevel = (value: LogLevel | "all"): void => {
    logLevel.value = value;
    void loadSnapshot(false);
  };

  /**
   * 选择指定 Trace，并同步 URL 查询参数与详情请求。
   */
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

  /**
   * 清除Trace，并保持现有状态与错误处理语义。
   */
  const clearTrace = (): void => {
    selectedTraceId.value = "";
    selectedTrace.value = null;
    replaceQuery("");
  };

  /**
   * 停止定时器，并保持现有状态与错误处理语义。
   */
  const stopTimer = (): void => {
    if (intervalId !== null) {
      window.clearInterval(intervalId);
      intervalId = null;
    }
  };

  /**
   * 启动定时器，并保持现有状态与错误处理语义。
   */
  const startTimer = (): void => {
    stopTimer();
    if (mounted && document.visibilityState === "visible") {
      intervalId = window.setInterval(() => void loadSnapshot(true), 10_000);
    }
  };

  /**
   * 根据页面可见状态暂停或恢复观测自动刷新。
   */
  const handleVisibility = (): void => {
    if (document.visibilityState === "hidden") {
      stopTimer();
      return;
    }
    void loadSnapshot(true);
    startTimer();
  };

  /**
   * 监听相关响应式状态变化，并同步执行既有更新逻辑。
   */
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

  /**
   * 组件挂载后执行既有初始化或恢复流程。
   */
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
    /**
     * 刷新now，并保持现有状态与错误处理语义。
     */
    refreshNow: () => loadSnapshot(false),
  };
};
