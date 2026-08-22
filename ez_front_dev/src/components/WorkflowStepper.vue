<template>
  <ol class="workflow-stepper" aria-label="测试工作流进度">
    <li
      v-for="(step, index) in steps"
      :key="step.operation"
      class="workflow-step"
      :class="[`is-${step.state}`, { 'is-active': activeOperation === step.operation }]"
    >
      <span class="step-index">{{ index + 1 }}</span>
      <span class="step-content">
        <span class="step-label">{{ step.label }}</span>
        <span class="step-state">{{ STATE_LABELS[step.state] }}</span>
      </span>
    </li>
  </ol>
</template>

<script lang="ts" setup>
/* global defineProps */
import type { PropType } from "vue";
import type { TestWorkflowStep, WorkflowStepState } from "@/composables/useTestWorkflow";

defineProps({
  steps: {
    type: Array as PropType<TestWorkflowStep[]>,
    required: true,
  },
  activeOperation: {
    type: String,
    default: "",
  },
});

const STATE_LABELS: Record<WorkflowStepState, string> = {
  locked: "已锁定",
  ready: "可开始",
  running: "进行中",
  completed: "已完成",
  stale: "已过期",
  failed: "失败",
};
</script>

<style scoped>
.workflow-stepper {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  padding: 0;
  margin: 0 0 18px;
  list-style: none;
}
.workflow-step {
  display: flex;
  align-items: center;
  min-height: 52px;
  padding: 8px 12px;
  color: #606266;
  background: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
}
.step-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  margin-right: 9px;
  color: #fff;
  background: #909399;
  border-radius: 50%;
}
.step-content { display: flex; flex-direction: column; }
.step-label { color: #303133; font-weight: 600; }
.step-state { margin-top: 2px; font-size: 12px; }
.is-running, .is-active { border-color: #409eff; }
.is-running .step-index, .is-active .step-index { background: #409eff; }
.is-completed { border-color: #67c23a; }
.is-completed .step-index { background: #67c23a; }
.is-stale { background: #fdf6ec; border-color: #e6a23c; }
.is-stale .step-index { background: #e6a23c; }
.is-failed { background: #fef0f0; border-color: #f56c6c; }
.is-failed .step-index { background: #f56c6c; }
.is-locked { opacity: 0.68; }
</style>
