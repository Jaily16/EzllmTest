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
  <div v-if="answer && (!completed || error || cancelled)" class="streamed-answer">
    <div class="answer-title">{{ answerTitle }}</div>
    <el-input
      :model-value="answer"
      :autosize="{ minRows: 4, maxRows: 50 }"
      type="textarea"
      readonly
    />
  </div>
</template>

<script lang="ts" setup>
/* global defineProps, defineEmits */
import LlmExecutionPanel from "@/components/LlmExecutionPanel.vue";
import type {
  LlmProgress,
  LlmReasoningSection,
  LlmStreamError,
  LlmTokenUsage,
} from "@/composables/useLlmStream";

defineProps<{
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
  answer: string;
  answerTitle: string;
  successTitle: string;
}>();

defineEmits<{ (event: "cancel"): void }>();
</script>

<style scoped>
.streamed-answer {
  width: 99%;
  margin-top: 14px;
}
.answer-title {
  margin-bottom: 8px;
  color: #06b009;
  font-family: "Ali";
}
</style>
