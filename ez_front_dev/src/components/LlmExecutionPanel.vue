<template>
  <el-card v-if="visible" class="execution-panel" shadow="never">
    <div class="progress-heading">
      <div>
        <div class="stage-label">{{ progress.label }}</div>
        <div v-if="meta.model" class="model-meta">{{ meta.label }} · {{ meta.model }}</div>
      </div>
      <el-button v-if="running" type="danger" plain size="small" @click="$emit('cancel')">
        取消生成
      </el-button>
    </div>
    <el-progress
      :percentage="progress.percent"
      :status="progressStatus"
      :stroke-width="12"
      striped
      :striped-flow="running"
    />
    <div v-if="progress.current !== null && progress.total !== null" class="chunk-count">
      当前分块：{{ progress.current }} / {{ progress.total }}
    </div>

    <el-collapse v-if="running || reasoningSections.length" v-model="openSections" class="thinking-collapse">
      <el-collapse-item name="thinking">
        <template #title>
          <span class="thinking-title">模型思考过程（仅当前会话展示）</span>
        </template>
        <div ref="thinkingContainer" class="thinking-container">
          <div v-if="reasoningSections.length === 0" class="thinking-placeholder">
            等待模型返回思考内容…
          </div>
          <section v-for="section in reasoningSections" :key="section.stage" class="thinking-section">
            <div class="thinking-stage">{{ section.label }}</div>
            <pre>{{ section.text }}</pre>
          </section>
        </div>
      </el-collapse-item>
    </el-collapse>

    <div v-if="usageReceived" class="usage-grid">
      <div v-for="item in usageItems" :key="item.label" class="usage-item">
        <span>{{ item.label }}</span>
        <strong>{{ formatTokens(item.value) }}</strong>
      </div>
    </div>
    <el-alert
      v-if="error" class="result-alert" type="error" :closable="false" show-icon
      :title="error.message" description="已接收的内容会保留在页面中，但本次结果未保存。"
    />
    <el-alert
      v-else-if="cancelled" class="result-alert" type="warning" :closable="false" show-icon
      title="生成已取消" description="已接收的内容会保留在页面中，本次结果未保存。"
    />
    <el-alert
      v-else-if="completed" class="result-alert" type="success" :closable="false" show-icon
      :title="successTitle || (fromCache ? '已读取数据库中保存的结果' : '大模型执行已完成')"
    />
  </el-card>
</template>

<script lang="ts" setup>
/* global defineProps, defineEmits */
import { computed, nextTick, ref, watch } from "vue";
import type { LlmProgress, LlmReasoningSection, LlmStreamError, LlmTokenUsage } from "@/composables/useLlmStream";

const props = defineProps<{
  visible: boolean;
  running: boolean;
  completed: boolean;
  cancelled: boolean;
  saved: boolean;
  fromCache: boolean;
  progress: LlmProgress;
  meta: { label: string; model: string };
  reasoningSections: LlmReasoningSection[];
  usage: LlmTokenUsage;
  usageReceived: boolean;
  error: LlmStreamError | null;
  successTitle?: string;
}>();

defineEmits<{ (event: "cancel"): void }>();

const openSections = ref<string[]>(["thinking"]);
const thinkingContainer = ref<HTMLElement | null>(null);
const reasoningLength = computed(() =>
  props.reasoningSections.reduce((total, section) => total + section.text.length, 0)
);
const progressStatus = computed(() => {
  if (props.error) return "exception";
  if (props.completed && props.saved) return "success";
  return undefined;
});
const usageItems = computed(() => [
  { label: "输入 Token", value: props.usage.input_tokens },
  { label: "思考 Token", value: props.usage.reasoning_tokens },
  { label: "正文 Token", value: props.usage.output_tokens },
  { label: "总 Token", value: props.usage.total_tokens },
]);
const formatTokens = (value: number | null) =>
  value === null ? "厂商未返回" : value.toLocaleString();

watch(reasoningLength, async () => {
  await nextTick();
  if (thinkingContainer.value) {
    thinkingContainer.value.scrollTop = thinkingContainer.value.scrollHeight;
  }
});
</script>

<style scoped>
.execution-panel { margin-top: 16px; width: 99%; border-color: #d9ecff; }
.progress-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 10px; }
.stage-label { color: #303133; font-weight: 600; }
.model-meta, .chunk-count { margin-top: 5px; color: #909399; font-size: 13px; }
.thinking-collapse { margin-top: 14px; }
.thinking-title { color: #606266; font-weight: 600; }
.thinking-container { max-height: 300px; overflow-y: auto; padding: 12px; border: 1px solid #ebeef5; border-radius: 6px; background: #f8fafc; }
.thinking-placeholder { color: #909399; }
.thinking-section + .thinking-section { margin-top: 14px; padding-top: 14px; border-top: 1px dashed #dcdfe6; }
.thinking-stage { margin-bottom: 6px; color: #409eff; font-size: 13px; font-weight: 600; }
pre { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; color: #606266; font-family: inherit; line-height: 1.65; }
.usage-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
.usage-item { display: flex; flex-direction: column; gap: 4px; padding: 10px; border-radius: 6px; background: #f5f7fa; color: #606266; font-size: 13px; }
.usage-item strong { color: #303133; font-size: 15px; }
.result-alert { margin-top: 14px; }
@media (max-width: 720px) { .usage-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
