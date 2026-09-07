<template>
  <LlmExecutionPanel
    :visible="visible"
    :running="running"
    :completed="completed"
    :cancelled="cancelled"
    :saved="saved"
    :from-cache="fromCache"
    :progress="progress"
    :meta="meta"
    :reasoning-sections="reasoningSections"
    :usage="usage"
    :usage-received="usageReceived"
    :error="error"
    :success-title="successTitle"
    @cancel="$emit('cancel')"
  />
  <ResultContainer
    v-if="answer && (!completed || error || cancelled)"
    class="streamed-answer"
    :title="answerTitle"
    description="这是当前连接已接收的流式正文；失败或取消时仍会保留在页面中。"
  >
    <div class="streamed-answer__text">{{ answer }}</div>
  </ResultContainer>
</template>

<script lang="ts" setup>
/* global defineProps, defineEmits */
import LlmExecutionPanel from "@/features/testing/components/LlmExecutionPanel.vue";
import ResultContainer from "@/shared/components/ResultContainer.vue";
import type {
  LlmExecutionMeta,
  LlmProgress,
  LlmReasoningSection,
  LlmStreamError,
  LlmTokenUsage,
} from "@/shared/composables/useLlmStream";

defineProps<{
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
  answer: string;
  answerTitle: string;
  successTitle: string;
}>();

defineEmits<{ (event: "cancel"): void }>();
</script>

<style scoped>
.streamed-answer {
  margin-top: var(--ez-space-4);
}

.streamed-answer__text {
  max-width: var(--ez-reading-measure);
  line-height: var(--ez-line-height-body);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  user-select: text;
}
</style>
