<template>
  <div class="test-workspace-scaffold">
    <WorkspacePageHeader :eyebrow="eyebrow" :title="title" :description="description" />
    <WorkflowStepper :steps="steps" :active-operation="activeOperation" />

    <FeedbackState
      v-if="hydrating"
      kind="loading"
      :title="`正在恢复${title}工作区`"
      description="正在读取工作流状态与当前标签页中的已保存结果，不会自动发起模型请求。"
      skeleton="content"
      busy
    />
    <template v-else>
      <FeedbackState
        v-if="hydrationError"
        kind="error"
        title="工作流状态恢复失败"
        :description="`${hydrationError}。当前页面不会自动生成内容，请手动重新读取。`"
        compact
      >
        <template v-if="$slots['hydration-actions']" #actions>
          <slot name="hydration-actions" />
        </template>
      </FeedbackState>
      <slot />
    </template>
  </div>
</template>

<script lang="ts" setup>
/* global defineProps */
import type { PropType } from "vue";
import FeedbackState from "@/shared/components/FeedbackState.vue";
import WorkflowStepper from "@/features/workspace/components/WorkflowStepper.vue";
import WorkspacePageHeader from "@/shared/components/WorkspacePageHeader.vue";
import type { TestWorkflowStep } from "@/features/testing/composables/useTestWorkflow";

defineProps({
  eyebrow: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
  steps: { type: Array as PropType<TestWorkflowStep[]>, required: true },
  activeOperation: { type: String, default: "" },
  hydrating: { type: Boolean, default: false },
  hydrationError: { type: String, default: "" },
});
</script>

<style scoped>
.test-workspace-scaffold {
  display: grid;
  min-width: 0;
  gap: var(--ez-space-6);
}

.test-workspace-scaffold :deep(.workflow-stepper) {
  margin-bottom: 0;
}

@media (max-width: 767px) {
  .test-workspace-scaffold {
    gap: var(--ez-space-4);
  }
}
</style>
