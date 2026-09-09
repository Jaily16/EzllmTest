<template>
  <section v-if="visible" class="execution-panel" :aria-busy="running || undefined">
    <p class="ez-sr-only" role="status" aria-live="polite" aria-atomic="true">
      {{ executionAnnouncement }}
    </p>
    <header class="execution-panel__header">
      <div class="execution-panel__identity">
        <span class="execution-state" :data-state="executionState">
          {{ stateLabel }}
        </span>
        <div class="execution-panel__copy">
          <h3>{{ progress.label }}</h3>
          <p v-if="meta.model" class="model-meta">
            {{ meta.label || "模型执行" }} · {{ meta.model }}
          </p>
        </div>
      </div>
      <el-button
        v-if="running"
        type="danger"
        plain
        size="small"
        aria-label="取消当前模型生成"
        @click="$emit('cancel')"
      >
        取消生成
      </el-button>
    </header>

    <div class="execution-progress" aria-label="执行进度">
      <el-progress
        :percentage="progress.percent"
        :status="progressStatus"
        :stroke-width="10"
        striped
        :striped-flow="running"
      />
      <p v-if="progress.current !== null && progress.total !== null" class="chunk-count">
        当前分块：{{ progress.current }} / {{ progress.total }}
      </p>
    </div>

    <div v-if="statusFacts.length" class="execution-facts" aria-label="结果保留状态">
      <span
        v-for="fact in statusFacts"
        :key="fact.label"
        class="execution-fact"
        :data-tone="fact.tone"
      >
        {{ fact.label }}
      </span>
    </div>

    <el-collapse
      v-if="running || reasoningSections.length"
      v-model="openSections"
      class="reasoning-collapse"
    >
      <el-collapse-item name="thinking">
        <template #title>
          <span class="reasoning-title">模型推理 · 仅本次会话</span>
        </template>
        <div ref="thinkingContainer" class="reasoning-container">
          <p v-if="reasoningSections.length === 0" class="reasoning-placeholder">
            等待模型返回推理内容…
          </p>
          <section
            v-for="section in reasoningSections"
            :key="section.stage"
            class="reasoning-section"
          >
            <h4>{{ section.label }}</h4>
            <pre>{{ section.text }}</pre>
          </section>
        </div>
      </el-collapse-item>
    </el-collapse>

    <section v-if="usageReceived" class="usage" aria-label="Token 用量">
      <h4>Token 用量</h4>
      <div class="usage-grid">
        <div v-for="item in usageItems" :key="item.label" class="usage-item">
          <span>{{ item.label }}</span>
          <strong>{{ formatTokens(item.value) }}</strong>
        </div>
      </div>
    </section>

    <div v-if="error" class="terminal-state terminal-state--error" role="alert">
      <h4>失败</h4>
      <p>{{ error.message }}</p>
      <p>
        {{
          error.retryable ? "可安全重试，已接收的内容仍保留在页面中。" : "请检查输入或配置后再试。"
        }}
      </p>
    </div>
    <div v-else-if="cancelled" class="terminal-state terminal-state--cancelled" role="status">
      <h4>已取消</h4>
      <p>已接收的内容仍保留在页面中，本次未保存。</p>
    </div>
    <div v-else-if="completed" class="terminal-state terminal-state--completed" role="status">
      <h4>{{ successTitle || "已完成" }}</h4>
      <p v-if="fromCache">结果已从服务器缓存恢复，未发起新的模型生成。</p>
      <p v-else-if="saved">结果已保存，可在后续工作流中继续使用。</p>
      <p v-else-if="meta.persistence === 'session'">结果仅当前页面保留，刷新或离开后不可恢复。</p>
    </div>
  </section>
</template>

<script lang="ts" setup>
// 工作流通用展示与确认交互，明确区分缓存恢复、已保存结果及会话草稿。

/* global defineProps, defineEmits */
import { computed, nextTick, ref, watch } from "vue";
import type {
  LlmExecutionMeta,
  LlmProgress,
  LlmReasoningSection,
  LlmStreamError,
  LlmTokenUsage,
} from "@/shared/composables/useLlmStream";

type ExecutionState = "connecting" | "running" | "completed" | "cached" | "cancelled" | "failed";
type FactTone = "info" | "success" | "warning" | "danger";

const props = defineProps<{
  visible: boolean;
  running: boolean;
  completed: boolean;
  cancelled: boolean;
  saved: boolean;
  fromCache: boolean;
  progress: LlmProgress;
  meta: LlmExecutionMeta;
  reasoningSections: LlmReasoningSection[];
  usage: LlmTokenUsage;
  usageReceived: boolean;
  error: LlmStreamError | null;
  successTitle?: string;
}>();

defineEmits<{ (event: "cancel"): void }>();

const openSections = ref<string[]>([]);
const thinkingContainer = ref<HTMLElement | null>(null);
/**
 * 派生用于界面展示或请求判断的模型推理 length。
 */
const reasoningLength = computed(() =>
  props.reasoningSections.reduce((total, section) => total + section.text.length, 0),
);
/** 按错误、取消、缓存和完成的优先级展示执行阶段，避免把失败显示为完成。 */
const executionState = computed<ExecutionState>(() => {
  if (props.error) return "failed";
  if (props.cancelled) return "cancelled";
  if (props.completed && props.fromCache) return "cached";
  if (props.completed) return "completed";
  if (props.running) return "running";
  return "connecting";
});
/**
 * 派生用于界面展示或请求判断的状态标签。
 */
const stateLabel = computed(
  () =>
    ({
      connecting: "正在连接",
      running: "进行中",
      completed: "已完成",
      cached: "已完成",
      cancelled: "已取消",
      failed: "失败",
    })[executionState.value],
);
/** 根据完成、缓存或取消状态生成读屏播报；错误由错误区单独呈现，避免重复播报。 */
const executionAnnouncement = computed(() => {
  if (props.error) return "";
  if (executionState.value === "cached") return "模型任务已完成，结果已从缓存恢复";
  if (executionState.value === "completed") {
    return props.saved ? "模型任务已完成，结果已保存" : "模型任务已完成，结果仅当前页面保留";
  }
  if (executionState.value === "cancelled") return "模型任务已取消，本次未保存";
  if (executionState.value === "connecting") return "正在连接模型服务";
  if (props.progress.current !== null && props.progress.total !== null) {
    return `模型任务进行中，当前分块 ${props.progress.current} / ${props.progress.total}`;
  }
  return "模型任务进行中";
});
/** 只有完成且已保存才显示成功进度；错误和取消使用不同视觉状态。 */
const progressStatus = computed(() => {
  if (props.error) return "exception";
  if (props.cancelled) return "warning";
  if (props.completed && props.saved) return "success";
  return undefined;
});
/** 分别显示缓存恢复、长期保存和会话保留事实，失败或取消明确标为本次未保存。 */
const statusFacts = computed<Array<{ label: string; tone: FactTone }>>(() => {
  const facts: Array<{ label: string; tone: FactTone }> = [];
  if (props.completed && props.fromCache) {
    facts.push({ label: "已从缓存恢复", tone: "info" });
  }
  if (props.completed && props.saved) {
    facts.push({ label: "已保存", tone: "success" });
  } else if (props.completed && props.meta.persistence === "session") {
    facts.push({ label: "仅当前页面保留", tone: "warning" });
  }
  if (props.cancelled || props.error) {
    facts.push({ label: "本次未保存", tone: "danger" });
  }
  return facts;
});
/**
 * 派生用于界面展示或请求判断的用量条目。
 */
const usageItems = computed(() => [
  { label: "输入 Token", value: props.usage.input_tokens },
  { label: "思考 Token", value: props.usage.reasoning_tokens },
  { label: "正文 Token", value: props.usage.output_tokens },
  { label: "总 Token", value: props.usage.total_tokens },
]);
/** 按展示规则格式化 token 数，区分尚无计数与已知消耗。 */
const formatTokens = (value: number | null) =>
  value === null ? "厂商未返回" : value.toLocaleString();

/** 仅在推理区展开时等待渲染并滚动到底部，避免折叠内容抢占滚动。 */
watch(reasoningLength, async () => {
  if (!openSections.value.includes("thinking")) return;
  await nextTick();
  if (thinkingContainer.value) {
    thinkingContainer.value.scrollTop = thinkingContainer.value.scrollHeight;
  }
});
</script>

<style scoped>
.execution-panel {
  min-width: 0;
  margin-top: var(--ez-space-4);
  padding: var(--ez-space-4);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-large);
  background: var(--ez-color-surface);
  box-shadow: var(--ez-shadow-small);
}

.execution-panel__header,
.execution-panel__identity {
  display: flex;
  align-items: flex-start;
}

.execution-panel__header {
  justify-content: space-between;
  gap: var(--ez-space-4);
}

.execution-panel__identity {
  gap: var(--ez-space-3);
  min-width: 0;
}

.execution-panel__copy {
  min-width: 0;
}

.execution-panel h3,
.execution-panel h4,
.execution-panel p {
  overflow-wrap: anywhere;
}

.execution-panel h3 {
  margin: 0;
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-16);
  line-height: var(--ez-line-height-tight);
}

.execution-state,
.execution-fact {
  display: inline-flex;
  align-items: center;
  min-height: var(--ez-space-6);
  border-radius: var(--ez-radius-pill);
  font-size: var(--ez-font-size-12);
  font-weight: 700;
  white-space: nowrap;
}

.execution-state {
  padding: var(--ez-space-1) var(--ez-space-2);
  background: var(--ez-color-info-bg);
  color: var(--ez-color-info);
}

.execution-state[data-state="running"] {
  background: var(--ez-color-brand-50);
  color: var(--ez-color-brand-700);
  animation: execution-pulse 1.8s var(--ez-motion-easing) infinite;
}

.execution-state[data-state="completed"],
.execution-state[data-state="cached"] {
  background: var(--ez-color-success-bg);
  color: var(--ez-color-success);
}

.execution-state[data-state="cancelled"] {
  background: var(--ez-color-warning-bg);
  color: var(--ez-color-warning);
}

.execution-state[data-state="failed"] {
  background: var(--ez-color-danger-bg);
  color: var(--ez-color-danger);
}

.model-meta,
.chunk-count {
  margin: var(--ez-space-1) 0 0;
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-13);
  line-height: var(--ez-line-height-body);
}

.execution-progress {
  margin-top: var(--ez-space-4);
}

.execution-facts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ez-space-2);
  margin-top: var(--ez-space-3);
}

.execution-fact {
  padding: var(--ez-space-1) var(--ez-space-2);
}

.execution-fact[data-tone="info"] {
  background: var(--ez-color-info-bg);
  color: var(--ez-color-info);
}

.execution-fact[data-tone="success"] {
  background: var(--ez-color-success-bg);
  color: var(--ez-color-success);
}

.execution-fact[data-tone="warning"] {
  background: var(--ez-color-warning-bg);
  color: var(--ez-color-warning);
}

.execution-fact[data-tone="danger"] {
  background: var(--ez-color-danger-bg);
  color: var(--ez-color-danger);
}

.reasoning-collapse,
.usage,
.terminal-state {
  margin-top: var(--ez-space-4);
}

.reasoning-title {
  color: var(--ez-color-text-secondary);
  font-weight: 700;
}

.reasoning-container {
  max-height: 300px;
  overflow-y: auto;
  padding: var(--ez-space-3);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-small);
  background: var(--ez-color-surface-subtle);
}

.reasoning-placeholder {
  margin: 0;
  color: var(--ez-color-text-muted);
}

.reasoning-section + .reasoning-section {
  margin-top: var(--ez-space-4);
  padding-top: var(--ez-space-4);
  border-top: 1px dashed var(--ez-color-border-strong);
}

.reasoning-section h4,
.usage h4,
.terminal-state h4 {
  margin: 0 0 var(--ez-space-2);
}

.reasoning-section h4 {
  color: var(--ez-color-brand-600);
  font-size: var(--ez-font-size-13);
}

pre {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--ez-color-text-secondary);
  font-family: var(--ez-font-body);
  line-height: var(--ez-line-height-body);
}

.usage h4 {
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-14);
}

.usage-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--ez-space-2);
}

.usage-item {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--ez-space-1);
  padding: var(--ez-space-3);
  border-radius: var(--ez-radius-small);
  background: var(--ez-color-surface-subtle);
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
}

.usage-item strong {
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-16);
  overflow-wrap: anywhere;
}

.terminal-state {
  padding: var(--ez-space-3) var(--ez-space-4);
  border-radius: var(--ez-radius-medium);
  background: var(--ez-color-success-bg);
  color: var(--ez-color-success);
}

.terminal-state--cancelled {
  background: var(--ez-color-warning-bg);
  color: var(--ez-color-warning);
}

.terminal-state--error {
  background: var(--ez-color-danger-bg);
  color: var(--ez-color-danger);
}

.terminal-state p {
  margin: var(--ez-space-1) 0 0;
  line-height: var(--ez-line-height-body);
}

@keyframes execution-pulse {
  50% {
    opacity: 0.72;
  }
}

@media (max-width: 720px) {
  .usage-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 480px) {
  .execution-panel__header {
    align-items: stretch;
    flex-direction: column;
  }

  .execution-panel__header > .el-button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .execution-state[data-state="running"] {
    animation: none;
  }
}
</style>
