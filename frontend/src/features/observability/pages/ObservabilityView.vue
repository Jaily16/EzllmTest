<template>
  <main class="observability-page" tabindex="-1">
    <header class="topbar">
      <router-link class="brand" to="/" aria-label="返回 EzllmTest 项目入口">
        <img :src="workbenchLogo" width="42" height="42" alt="" aria-hidden="true" />
        <span>EzllmTest</span>
      </router-link>
      <div class="topbar__title">
        <span>本地工具</span>
        <strong>中文观测后台</strong>
      </div>
      <router-link class="topbar__link" to="/">返回项目入口</router-link>
    </header>

    <div class="observability-content ez-content ez-content--wide">
      <section class="hero" aria-labelledby="observability-title">
        <div>
          <p class="eyebrow">仅限本机 · 安全元数据</p>
          <h1 id="observability-title">Agent 运行观测</h1>
          <p>
            查看本地依赖健康、指标、Trace
            与安全日志。这里不展示项目正文、模型提示词、推理内容、工具参数或凭据。
          </p>
        </div>
        <div class="refresh-panel">
          <label>
            <span>时间窗口</span>
            <select :value="selectedWindow" @change="handleWindowChange">
              <option value="15m">15 分钟</option>
              <option value="1h">1 小时</option>
              <option value="6h">6 小时</option>
              <option value="24h">24 小时</option>
              <option value="7d">7 天</option>
            </select>
          </label>
          <el-button :loading="refreshing" @click="refreshNow">立即刷新</el-button>
          <small>每 10 秒自动刷新 · 最近 {{ lastUpdatedLabel }}</small>
        </div>
      </section>

      <el-alert
        v-if="error"
        class="degraded-alert"
        type="warning"
        :closable="false"
        :title="error"
        show-icon
      />

      <FeedbackState
        v-if="loading && !overview"
        kind="loading"
        title="正在读取本地观测数据"
        description="只执行本机只读请求，不会创建 Agent 运行或调用模型。"
        skeleton="cards"
      />

      <template v-else-if="overview">
        <section class="panel" aria-labelledby="health-title">
          <div class="section-heading">
            <div>
              <p class="eyebrow">依赖状态</p>
              <h2 id="health-title">本地运行健康</h2>
            </div>
            <span>{{ formatTime(overview.generated_at_ms) }}</span>
          </div>
          <div class="health-grid">
            <article v-for="item in healthItems" :key="item.key" class="health-card">
              <span class="status-dot" :data-status="item.status" aria-hidden="true"></span>
              <div>
                <strong>{{ item.label }}</strong>
                <p>{{ item.status === "ok" ? "正常" : "暂不可用" }}</p>
              </div>
              <el-tag :type="item.status === 'ok' ? 'success' : 'danger'" size="small">
                {{ item.status === "ok" ? "OK" : "不可用" }}
              </el-tag>
            </article>
          </div>
        </section>

        <section class="panel" aria-labelledby="metrics-title">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Agent 指标</p>
              <h2 id="metrics-title">当前窗口摘要</h2>
            </div>
          </div>
          <dl class="metric-grid">
            <div v-for="item in metricCards" :key="item.label" class="metric-card">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
              <span>{{ item.hint }}</span>
            </div>
          </dl>

          <div class="metrics-layout">
            <article class="chart-card" aria-labelledby="activity-chart-title">
              <div class="chart-heading">
                <h3 id="activity-chart-title">命令与调用趋势</h3>
                <ul class="chart-legend" aria-label="图例">
                  <li><span class="legend-mark legend-mark--commands"></span>命令</li>
                  <li><span class="legend-mark legend-mark--models"></span>模型调用</li>
                  <li><span class="legend-mark legend-mark--tools"></span>工具调用</li>
                </ul>
              </div>
              <svg
                class="activity-chart"
                viewBox="0 0 720 180"
                role="img"
                aria-labelledby="activity-chart-title activity-chart-description"
              >
                <desc id="activity-chart-description">
                  当前时间窗口内命令、模型调用和工具调用的十二段趋势。下方表格提供同等数据。
                </desc>
                <line v-for="y in [20, 65, 110, 155]" :key="y" x1="24" :y1="y" x2="696" :y2="y" />
                <polyline class="chart-line chart-line--commands" :points="seriesPaths.commands" />
                <polyline class="chart-line chart-line--models" :points="seriesPaths.model_calls" />
                <polyline class="chart-line chart-line--tools" :points="seriesPaths.tool_calls" />
              </svg>
              <details class="data-equivalent">
                <summary>查看图表数据表</summary>
                <div class="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>时间</th>
                        <th>命令</th>
                        <th>模型调用</th>
                        <th>工具调用</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="point in overview.metrics.series" :key="point.started_at_ms">
                        <td>{{ formatShortTime(point.started_at_ms) }}</td>
                        <td>{{ formatNumber(point.commands) }}</td>
                        <td>{{ formatNumber(point.model_calls) }}</td>
                        <td>{{ formatNumber(point.tool_calls) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </details>
            </article>

            <article class="latency-card" aria-labelledby="latency-title">
              <h3 id="latency-title">延迟分位数</h3>
              <div class="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>阶段</th>
                      <th>p50</th>
                      <th>p95</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in latencyRows" :key="row.label">
                      <td>{{ row.label }}</td>
                      <td>{{ formatDuration(row.p50) }}</td>
                      <td>{{ formatDuration(row.p95) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </article>
          </div>
        </section>

        <div class="observability-grid">
          <section class="panel" aria-labelledby="traces-title">
            <div class="section-heading section-heading--controls">
              <div>
                <p class="eyebrow">调用链</p>
                <h2 id="traces-title">Trace 列表</h2>
              </div>
              <label class="compact-filter">
                <span>状态</span>
                <select :value="traceStatus" @change="handleTraceStatusChange">
                  <option value="all">全部</option>
                  <option value="ok">正常</option>
                  <option value="error">错误</option>
                </select>
              </label>
            </div>
            <ul v-if="traces.length" class="record-list">
              <li v-for="trace in traces" :key="trace.trace_id">
                <button
                  class="record-button"
                  type="button"
                  :aria-current="trace.trace_id === selectedTraceId ? 'true' : undefined"
                  @click="selectTrace(trace.trace_id)"
                >
                  <span>
                    <strong>{{ shortenId(trace.trace_id) }}</strong>
                    <small>{{ trace.services.join(" · ") || "未知服务" }}</small>
                  </span>
                  <span class="record-meta">
                    <el-tag :type="trace.status === 'ok' ? 'success' : 'danger'" size="small">
                      {{ trace.status === "ok" ? "正常" : "错误" }}
                    </el-tag>
                    <small
                      >{{ formatDuration(trace.duration_ms) }} · {{ trace.span_count }} spans</small
                    >
                    <small>{{ formatTime(trace.ended_at_ms) }}</small>
                  </span>
                </button>
              </li>
            </ul>
            <p v-else class="empty-copy">当前窗口暂无 Trace。</p>
          </section>

          <section class="panel" aria-labelledby="logs-title">
            <div class="section-heading section-heading--controls">
              <div>
                <p class="eyebrow">安全事件</p>
                <h2 id="logs-title">本地日志</h2>
              </div>
              <label class="compact-filter">
                <span>级别</span>
                <select :value="logLevel" @change="handleLogLevelChange">
                  <option value="all">全部</option>
                  <option value="info">信息</option>
                  <option value="warning">警告</option>
                  <option value="error">错误</option>
                </select>
              </label>
            </div>
            <ol v-if="logs.length" class="log-list">
              <li v-for="entry in logs" :key="entry.cursor">
                <div class="log-title">
                  <el-tag :type="logTagType(entry.level)" size="small">{{
                    logLevelLabel(entry.level)
                  }}</el-tag>
                  <strong>{{ entry.event }}</strong>
                  <time :datetime="isoTime(entry.observed_at_ms)">{{
                    formatTime(entry.observed_at_ms)
                  }}</time>
                </div>
                <p>{{ entry.service }}</p>
                <dl v-if="Object.keys(entry.fields).length" class="safe-fields">
                  <div v-for="(value, key) in entry.fields" :key="key">
                    <dt>{{ key }}</dt>
                    <dd>{{ value }}</dd>
                  </div>
                </dl>
              </li>
            </ol>
            <p v-else class="empty-copy">当前窗口暂无安全日志。</p>
          </section>
        </div>

        <section
          v-if="selectedTrace"
          class="panel trace-detail"
          aria-labelledby="trace-detail-title"
        >
          <div class="section-heading">
            <div>
              <p class="eyebrow">层级详情</p>
              <h2 id="trace-detail-title">Trace {{ shortenId(selectedTrace.trace_id) }}</h2>
            </div>
            <div class="trace-actions">
              <el-button @click="copyText(selectedTrace.trace_id, 'Trace ID')"
                >复制完整 ID</el-button
              >
              <el-button @click="clearTrace">关闭详情</el-button>
            </div>
          </div>
          <ol class="span-list">
            <li
              v-for="span in traceSpans"
              :key="span.span_id"
              :style="{ '--span-depth': String(span.depth) }"
            >
              <div class="span-heading">
                <span>
                  <strong>{{ span.name }}</strong>
                  <small>{{ span.service }} · {{ shortenId(span.span_id) }}</small>
                </span>
                <span class="span-meta">
                  <el-tag :type="span.status === 'error' ? 'danger' : 'success'" size="small">
                    {{ span.status === "error" ? "错误" : "正常" }}
                  </el-tag>
                  {{ formatDuration(span.duration_ms) }}
                </span>
              </div>
              <dl v-if="Object.keys(span.attributes).length" class="safe-fields">
                <div v-for="(value, key) in span.attributes" :key="key">
                  <dt>{{ key }}</dt>
                  <dd>{{ value }}</dd>
                </div>
              </dl>
            </li>
          </ol>
        </section>

        <section class="panel retention-panel" aria-labelledby="retention-title">
          <div>
            <p class="eyebrow">数据边界</p>
            <h2 id="retention-title">保留与导出状态</h2>
          </div>
          <dl>
            <div>
              <dt>保留时间</dt>
              <dd>{{ capabilities?.retention_days ?? 7 }} 天</dd>
            </div>
            <div>
              <dt>总行数上限</dt>
              <dd>{{ formatNumber(capabilities?.maximum_rows ?? 100000) }}</dd>
            </div>
            <div>
              <dt>当前行数</dt>
              <dd>{{ formatNumber(storageTotal) }}</dd>
            </div>
            <div>
              <dt>内容策略</dt>
              <dd>仅安全元数据</dd>
            </div>
            <div>
              <dt>最近导出</dt>
              <dd>{{ deliveryLabel }}</dd>
            </div>
          </dl>
        </section>
      </template>
    </div>
  </main>
</template>

<script lang="ts" setup>
// 只展示观测服务已脱敏的摘要和用户选择的详情，图表计算不访问项目正文。

import { computed, getCurrentInstance } from "vue";
import { ElMessage } from "@/shared/ui/messages";
import FeedbackState from "@/shared/components/FeedbackState.vue";
import workbenchLogo from "@/shared/assets/brand/ezlogo-workbench-v2.png";
import { useObservability } from "@/features/observability/composables/useObservability";
import type {
  LogLevel,
  ObservabilitySpan,
  ObservabilityWindow,
  TraceStatus,
} from "@/features/observability/types";

type TagType = "success" | "warning" | "danger" | "info" | "primary";
type SeriesKey = "commands" | "model_calls" | "tool_calls";
interface SpanWithDepth extends ObservabilitySpan {
  depth: number;
}

const instance = getCurrentInstance();
const observabilityApiUrl = String(
  instance?.appContext.config.globalProperties.$observabilityApiUrl || "http://127.0.0.1:8140",
);
const agentApiUrl = String(
  instance?.appContext.config.globalProperties.$agentApiUrl || "http://127.0.0.1:8231",
);

const {
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
  refreshNow,
} = useObservability(observabilityApiUrl, agentApiUrl);

const healthNames: Array<{ key: string; label: string }> = [
  { key: "observability-api", label: "观测服务" },
  { key: "frontend", label: "前端" },
  { key: "legacy-api", label: "Legacy API" },
  { key: "agent-api", label: "Agent API" },
  { key: "worker", label: "Worker" },
  { key: "mysql", label: "MySQL" },
  { key: "redis", label: "Redis" },
];

/**
 * 派生用于界面展示或请求判断的健康状态条目。
 */
const healthItems = computed(() =>
  healthNames.map((item) => ({
    ...item,
    status: overview.value?.health[item.key] === "ok" ? ("ok" as const) : ("unavailable" as const),
  })),
);

/**
 * 派生用于界面展示或请求判断的指标卡片。
 */
const metricCards = computed(() => {
  const metrics = overview.value?.metrics;
  if (!metrics) return [];
  return [
    { label: "活跃运行", value: formatNumber(metrics.active_runs), hint: "当前 gauge" },
    {
      label: "已处理命令",
      value: formatNumber(metrics.commands),
      hint: `${formatNumber(metrics.commands_per_minute, 2)} / 分钟`,
    },
    {
      label: "模型调用",
      value: formatNumber(metrics.model_calls),
      hint: `错误率 ${formatPercent(metrics.model_error_rate)}`,
    },
    {
      label: "工具调用",
      value: formatNumber(metrics.tool_calls),
      hint: `错误率 ${formatPercent(metrics.tool_error_rate)}`,
    },
    { label: "输入 Token", value: formatNumber(metrics.input_tokens), hint: "当前窗口" },
    { label: "输出 Token", value: formatNumber(metrics.output_tokens), hint: "当前窗口" },
  ];
});

/**
 * 派生用于界面展示或请求判断的延迟 rows。
 */
const latencyRows = computed(() => {
  const latency = overview.value?.metrics.latency_ms;
  if (!latency) return [];
  return [
    { label: "Graph 节点", ...latency.graph },
    { label: "模型", ...latency.model },
    { label: "工具", ...latency.tool },
    { label: "SSE 首包", ...latency.sse_ttfe },
  ];
});

/**
 * 派生用于界面展示或请求判断的序列 max。
 */
const seriesMax = computed(() => {
  const points = overview.value?.metrics.series ?? [];
  return Math.max(
    1,
    ...points.flatMap((point) => [point.commands, point.model_calls, point.tool_calls]),
  );
});

/** 把窗口内聚合值映射到折线坐标，空序列使用页面定义的回退。 */
const pointsFor = (key: SeriesKey): string => {
  const points = overview.value?.metrics.series ?? [];
  if (!points.length) return "";
  return points
    .map((point, index) => {
      const x = 24 + (index * 672) / Math.max(1, points.length - 1);
      const y = 155 - (point[key] / seriesMax.value) * 135;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
};

/**
 * 派生用于界面展示或请求判断的序列 paths。
 */
const seriesPaths = computed(() => ({
  commands: pointsFor("commands"),
  model_calls: pointsFor("model_calls"),
  tool_calls: pointsFor("tool_calls"),
}));

/** 按父 span 关系生成展示层级，限制深度并检测循环，不修改原始观测记录。 */
const traceSpans = computed<SpanWithDepth[]>(() => {
  const spans = selectedTrace.value?.spans ?? [];
  const byId = new Map(spans.map((span) => [span.span_id, span]));
  /**
   * 沿父 span 关系计算缩进层级，用于呈现 Trace 层次。
   * @param span 沿用当前 TypeScript 类型约束的输入。
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   */
  const depthOf = (span: ObservabilitySpan): number => {
    let depth = 0;
    let parentId = span.parent_span_id;
    const visited = new Set<string>([span.span_id]);
    while (parentId && byId.has(parentId) && !visited.has(parentId) && depth < 8) {
      visited.add(parentId);
      depth += 1;
      parentId = byId.get(parentId)?.parent_span_id ?? null;
    }
    return depth;
  };
  return spans.map((span) => ({ ...span, depth: depthOf(span) }));
});

/**
 * 派生用于界面展示或请求判断的浏览器存储 total。
 */
const storageTotal = computed(() => {
  const storage = overview.value?.storage;
  return storage ? storage.spans + storage.metrics + storage.logs : 0;
});

/**
 * 派生用于界面展示或请求判断的传输标签。
 */
const deliveryLabel = computed(() => {
  if (!delivery.value) return "Agent 状态暂不可用";
  return delivery.value.status === "ok"
    ? `正常 · 已导出 ${delivery.value.exported_batches} 批`
    : `降级 · 失败 ${delivery.value.failed_batches} 批，丢弃 ${delivery.value.dropped_batches} 批`;
});

/** 将界面窗口选择交给观测状态层校验并刷新。 */
const handleWindowChange = (event: Event): void => {
  setWindow((event.target as HTMLSelectElement).value as ObservabilityWindow);
};

/** 更新 Trace 列表状态过滤，不改动原观测记录。 */
const handleTraceStatusChange = (event: Event): void => {
  setTraceStatus((event.target as HTMLSelectElement).value as TraceStatus | "all");
};

/** 更新脱敏日志级别过滤，不改变日志采集等级。 */
const handleLogLevelChange = (event: Event): void => {
  setLogLevel((event.target as HTMLSelectElement).value as LogLevel | "all");
};

/** 格式化聚合计数供展示，不重算后端统计。 */
const formatNumber = (value: number, maximumFractionDigits = 0): string =>
  new Intl.NumberFormat("zh-CN", { maximumFractionDigits }).format(value);

/** 把统计比例转换为百分比显示。 */
const formatPercent = (value: number): string =>
  new Intl.NumberFormat("zh-CN", { style: "percent", maximumFractionDigits: 1 }).format(value);

/** 把聚合耗时转换为易读单位，保留无数据情形的展示。 */
const formatDuration = (value: number | null): string =>
  value === null ? "暂无样本" : `${formatNumber(value, value < 10 ? 2 : 1)} ms`;

/** 显示完整观测时间，避免原始时间戳直接进入主要列表。 */
const formatTime = (value: number): string => new Date(value).toLocaleString("zh-CN");
/** 为趋势横轴提供简短时间标签。 */
const formatShortTime = (value: number): string =>
  new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
/** 为时间元素提供机器可读时间，展示文本另行格式化。 */
const isoTime = (value: number): string => new Date(value).toISOString();
/** 缩短列表中的标识展示，完整标识仍用于详情查询。 */
const shortenId = (value: string): string =>
  value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;

/** 按日志级别选择视觉标签，不参与安全过滤。 */
const logTagType = (level: LogLevel): TagType =>
  ({ info: "info", warning: "warning", error: "danger" })[level] as TagType;
/** 将日志级别映射为中文展示标签。 */
const logLevelLabel = (level: LogLevel): string =>
  ({ info: "信息", warning: "警告", error: "错误" })[level];

/** 通过剪贴板复制用户选择的展示字段，权限失败时反馈提示。 */
const copyText = async (value: string, label: string): Promise<void> => {
  try {
    await navigator.clipboard.writeText(value);
    ElMessage({ message: `${label} 已复制`, type: "success" });
  } catch {
    ElMessage({ message: `无法访问剪贴板，请手动复制${label}`, type: "warning" });
  }
};
</script>

<style scoped>
.observability-page {
  min-height: 100vh;
  min-height: 100dvh;
  color: var(--ez-color-text-primary);
  background: var(--ez-color-canvas);
}

.topbar {
  position: sticky;
  top: 0;
  z-index: var(--ez-z-sticky);
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  min-height: var(--ez-shell-header-height);
  gap: var(--ez-space-4);
  padding: var(--ez-space-2) var(--ez-page-gutter);
  background: color-mix(in srgb, var(--ez-color-surface) 94%, transparent);
  border-bottom: 1px solid var(--ez-color-border);
  backdrop-filter: blur(12px);
}

.brand,
.topbar__link {
  color: inherit;
  text-decoration: none;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--ez-space-2);
  font-family: var(--ez-font-brand);
  font-size: var(--ez-font-size-20);
}

.brand img {
  object-fit: contain;
}

.topbar__title {
  display: grid;
  min-width: 0;
}

.topbar__title span,
.topbar__link {
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
}

.topbar__title strong {
  overflow-wrap: anywhere;
}

.topbar__link {
  min-height: var(--ez-touch-target);
  padding: var(--ez-space-3);
}

.observability-content {
  display: grid;
  gap: var(--ez-space-6);
  padding-block: var(--ez-space-6) var(--ez-space-12);
}

.hero,
.panel {
  min-width: 0;
  padding: var(--ez-space-6);
  background: var(--ez-color-surface);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-large);
  box-shadow: var(--ez-shadow-small);
}

.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ez-space-6);
  background: linear-gradient(135deg, var(--ez-color-brand-50), var(--ez-color-surface));
  border-color: var(--ez-color-brand-100);
}

h1,
h2,
h3,
p {
  overflow-wrap: anywhere;
}

h1 {
  margin: var(--ez-space-1) 0 var(--ez-space-2);
  font-size: clamp(var(--ez-font-size-24), 4vw, var(--ez-font-size-32));
}

h2,
h3,
p {
  margin-top: 0;
}

h2 {
  margin-bottom: 0;
  font-size: var(--ez-font-size-20);
}

h3 {
  margin-bottom: var(--ez-space-3);
  font-size: var(--ez-font-size-16);
}

.hero p:not(.eyebrow) {
  max-width: var(--ez-reading-measure);
  margin-bottom: 0;
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
}

.eyebrow {
  margin-bottom: var(--ez-space-1);
  color: var(--ez-color-brand-700);
  font-size: var(--ez-font-size-12);
  font-weight: 700;
  letter-spacing: 0.06em;
}

.refresh-panel {
  display: grid;
  min-width: 210px;
  gap: var(--ez-space-2);
}

.refresh-panel label,
.compact-filter {
  display: grid;
  gap: var(--ez-space-1);
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-12);
}

select {
  min-height: var(--ez-control-height);
  padding: 0 var(--ez-space-3);
  color: var(--ez-color-text-primary);
  background: var(--ez-color-surface);
  border: 1px solid var(--ez-color-border-strong);
  border-radius: var(--ez-radius-small);
  font: inherit;
}

.refresh-panel small,
.section-heading > span,
.record-list small,
.span-heading small {
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
}

.degraded-alert {
  position: sticky;
  top: calc(var(--ez-shell-header-height) + var(--ez-space-2));
  z-index: var(--ez-z-raised);
}

.section-heading,
.chart-heading,
.span-heading,
.log-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ez-space-3);
}

.section-heading {
  margin-bottom: var(--ez-space-4);
}

.section-heading--controls {
  align-items: end;
}

.health-grid,
.metric-grid {
  display: grid;
  gap: var(--ez-space-3);
}

.health-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--ez-space-3);
  padding: var(--ez-space-3);
  background: var(--ez-color-surface-subtle);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
}

.health-card p {
  margin: var(--ez-space-1) 0 0;
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
}

.status-dot {
  width: 10px;
  height: 10px;
  background: var(--ez-color-danger);
  border-radius: 50%;
}

.status-dot[data-status="ok"] {
  background: var(--ez-color-success);
}

.metric-grid {
  margin: 0;
}

.metric-card {
  display: grid;
  align-content: start;
  gap: var(--ez-space-1);
  min-width: 0;
  padding: var(--ez-space-4);
  background: var(--ez-color-surface-subtle);
  border-radius: var(--ez-radius-medium);
}

.metric-card dt,
.metric-card span {
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
}

.metric-card dd {
  min-width: 0;
  margin: 0;
  font-size: var(--ez-font-size-24);
  font-weight: 700;
  overflow-wrap: anywhere;
}

.metrics-layout,
.observability-grid {
  display: grid;
  gap: var(--ez-space-4);
  margin-top: var(--ez-space-6);
}

.chart-card,
.latency-card {
  min-width: 0;
  padding: var(--ez-space-4);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
}

.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ez-space-3);
  margin: 0;
  padding: 0;
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-12);
  list-style: none;
}

.legend-mark {
  display: inline-block;
  width: 18px;
  height: 3px;
  margin-right: var(--ez-space-1);
  vertical-align: middle;
  background: var(--ez-color-brand-600);
}

.legend-mark--models {
  background: var(--ez-color-info);
}

.legend-mark--tools {
  background: var(--ez-color-warning);
}

.activity-chart {
  display: block;
  width: 100%;
  min-height: 180px;
  margin-top: var(--ez-space-2);
}

.activity-chart line {
  stroke: var(--ez-color-border);
  stroke-width: 1;
}

.chart-line {
  fill: none;
  stroke: var(--ez-color-brand-600);
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 3;
}

.chart-line--models {
  stroke: var(--ez-color-info);
  stroke-dasharray: 8 4;
}

.chart-line--tools {
  stroke: var(--ez-color-warning);
  stroke-dasharray: 2 5;
}

.data-equivalent {
  margin-top: var(--ez-space-3);
}

.data-equivalent summary {
  min-height: var(--ez-touch-target);
  padding: var(--ez-space-3) 0;
  color: var(--ez-color-brand-700);
  cursor: pointer;
}

.table-scroll {
  max-width: 100%;
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--ez-font-size-13);
}

th,
td {
  padding: var(--ez-space-2) var(--ez-space-3);
  text-align: left;
  white-space: nowrap;
  border-bottom: 1px solid var(--ez-color-border);
}

th {
  color: var(--ez-color-text-muted);
  font-weight: 600;
}

.record-list,
.log-list,
.span-list {
  display: grid;
  gap: var(--ez-space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.record-button {
  display: flex;
  width: 100%;
  min-height: var(--ez-touch-target);
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ez-space-3);
  padding: var(--ez-space-3);
  color: inherit;
  text-align: left;
  background: var(--ez-color-surface-subtle);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
  cursor: pointer;
}

.record-button[aria-current="true"] {
  border-color: var(--ez-color-brand-500);
  box-shadow: inset 3px 0 0 var(--ez-color-brand-500);
}

.record-button > span,
.record-meta {
  display: grid;
  min-width: 0;
  gap: var(--ez-space-1);
}

.record-button strong,
.record-button small {
  overflow-wrap: anywhere;
}

.record-meta {
  justify-items: end;
  text-align: right;
}

.log-list > li,
.span-list > li {
  min-width: 0;
  padding: var(--ez-space-3);
  background: var(--ez-color-surface-subtle);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
}

.log-title {
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
}

.log-title time {
  margin-left: auto;
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
}

.log-list > li > p {
  margin: var(--ez-space-2) 0 0;
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
}

.safe-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--ez-space-2);
  margin: var(--ez-space-3) 0 0;
}

.safe-fields div {
  min-width: 0;
  padding: var(--ez-space-2);
  background: var(--ez-color-surface);
  border-radius: var(--ez-radius-small);
}

.safe-fields dt {
  color: var(--ez-color-text-muted);
  font: var(--ez-font-size-12) var(--ez-font-code);
}

.safe-fields dd {
  min-width: 0;
  margin: var(--ez-space-1) 0 0;
  overflow-wrap: anywhere;
}

.trace-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ez-space-2);
}

.span-list > li {
  margin-left: calc(min(var(--span-depth), 4) * var(--ez-space-4));
  border-left: 3px solid var(--ez-color-brand-300);
}

.span-heading > span {
  display: grid;
  min-width: 0;
  gap: var(--ez-space-1);
}

.span-meta {
  justify-items: end;
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
  white-space: nowrap;
}

.retention-panel,
.retention-panel dl {
  display: grid;
  gap: var(--ez-space-4);
}

.retention-panel dl {
  margin: 0;
}

.retention-panel dl div {
  display: flex;
  justify-content: space-between;
  gap: var(--ez-space-3);
  padding-bottom: var(--ez-space-2);
  border-bottom: 1px solid var(--ez-color-border);
}

.retention-panel dt {
  color: var(--ez-color-text-muted);
}

.retention-panel dd {
  margin: 0;
  text-align: right;
  overflow-wrap: anywhere;
}

.empty-copy {
  margin: 0;
  padding: var(--ez-space-6);
  color: var(--ez-color-text-muted);
  text-align: center;
  background: var(--ez-color-surface-subtle);
  border-radius: var(--ez-radius-medium);
}

@media (min-width: 680px) {
  .health-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .metric-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .retention-panel {
    grid-template-columns: minmax(180px, 0.5fr) minmax(0, 1.5fr);
  }
}

@media (min-width: 960px) {
  .health-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .metrics-layout {
    grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.7fr);
  }
  .observability-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 679px) {
  .topbar {
    grid-template-columns: auto minmax(0, 1fr);
  }
  .topbar__link {
    display: none;
  }
  .hero,
  .section-heading,
  .chart-heading,
  .span-heading,
  .record-button {
    flex-direction: column;
  }
  .refresh-panel {
    width: 100%;
  }
  .record-meta,
  .span-meta {
    justify-items: start;
    text-align: left;
  }
  .log-title time {
    width: 100%;
    margin-left: 0;
  }
  .span-list > li {
    margin-left: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    scroll-behavior: auto !important;
  }
}

@media (forced-colors: active) {
  .panel,
  .hero,
  .health-card,
  .metric-card,
  .record-button,
  .log-list > li,
  .span-list > li {
    border: 1px solid CanvasText;
  }
  .status-dot {
    border: 2px solid CanvasText;
  }
}
</style>
