<template>
  <p class="ez-sr-only" role="status" aria-live="polite" aria-atomic="true">
    {{ stepperAnnouncement }}
  </p>
  <ol class="workflow-stepper" aria-label="测试工作流进度">
    <li
      v-for="(step, index) in steps"
      :key="step.operation"
      class="workflow-step"
      :class="[`is-${step.state}`, { 'is-active': activeOperation === step.operation }]"
      :data-state="step.state"
      :aria-current="activeOperation === step.operation ? 'step' : undefined"
    >
      <span class="step-index" aria-hidden="true">{{ index + 1 }}</span>
      <span class="step-content">
        <span class="step-label">{{ step.label }}</span>
        <span class="step-state">{{ STATE_LABELS[step.state] }}</span>
      </span>
    </li>
  </ol>
</template>

<script lang="ts" setup>
/* global defineProps */
import { computed, type PropType } from "vue";
import type {
  TestWorkflowStep,
  WorkflowStepState,
} from "@/features/testing/composables/useTestWorkflow";

const props = defineProps({
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

const stepperAnnouncement = computed(() => {
  const active = props.steps.find((step) => step.operation === props.activeOperation);
  const running = active || props.steps.find((step) => step.state === "running");
  if (running) return `当前阶段：${running.label}，${STATE_LABELS[running.state]}`;
  const failed = props.steps.find((step) => step.state === "failed");
  if (failed) return `工作流阶段失败：${failed.label}`;
  const completed = props.steps.filter((step) => step.state === "completed").length;
  return `工作流进度：已完成 ${completed} / ${props.steps.length} 个阶段`;
});
</script>

<style scoped>
.workflow-stepper {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  gap: var(--ez-space-3);
  padding: 0;
  margin: 0 0 var(--ez-space-6);
  list-style: none;
  container-name: workflow-stepper;
  container-type: inline-size;
}

.workflow-step {
  --step-accent: var(--ez-color-info);
  --step-background: var(--ez-color-info-bg);

  display: flex;
  align-items: center;
  min-width: 0;
  min-height: 60px;
  max-width: 100%;
  padding: var(--ez-space-3) var(--ez-space-4);
  overflow-wrap: anywhere;
  color: var(--ez-color-text-secondary);
  background: var(--step-background);
  border: 1px solid color-mix(in srgb, var(--step-accent) 42%, var(--ez-color-border));
  border-radius: var(--ez-radius-medium);
  box-shadow: var(--ez-shadow-small);
  transition:
    background-color var(--ez-motion-normal) var(--ez-motion-easing),
    border-color var(--ez-motion-normal) var(--ez-motion-easing),
    box-shadow var(--ez-motion-normal) var(--ez-motion-easing);
}

.step-index {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  margin-right: var(--ez-space-3);
  color: var(--ez-color-surface);
  background: var(--step-accent);
  border-radius: var(--ez-radius-pill);
  font-size: var(--ez-font-size-13);
  font-weight: 700;
  line-height: 1;
}

.step-content {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
}

.step-label {
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-14);
  font-weight: 650;
  line-height: var(--ez-line-height-tight);
}

.step-state {
  margin-top: var(--ez-space-1);
  color: var(--step-accent);
  font-size: var(--ez-font-size-12);
  font-weight: 600;
  line-height: var(--ez-line-height-tight);
}

.is-locked {
  --step-accent: var(--ez-color-locked);
  --step-background: var(--ez-color-locked-bg);
}

.is-ready {
  --step-accent: var(--ez-color-info);
  --step-background: var(--ez-color-info-bg);
}

.is-running,
.is-active {
  --step-accent: var(--ez-color-brand-500);
  --step-background: var(--ez-color-brand-50);
  box-shadow:
    0 0 0 1px var(--ez-color-brand-100),
    var(--ez-shadow-small);
}

.is-completed {
  --step-accent: var(--ez-color-success);
  --step-background: var(--ez-color-success-bg);
}

.is-stale {
  --step-accent: var(--ez-color-warning);
  --step-background: var(--ez-color-warning-bg);
}

.is-failed {
  --step-accent: var(--ez-color-danger);
  --step-background: var(--ez-color-danger-bg);
}

.is-running .step-index {
  animation: ez-stepper-running var(--ez-motion-slow) var(--ez-motion-easing) infinite alternate;
}

@keyframes ez-stepper-running {
  from {
    box-shadow: 0 0 0 0 rgba(47, 125, 74, 0.12);
  }
  to {
    box-shadow: 0 0 0 4px rgba(47, 125, 74, 0.24);
  }
}

@container workflow-stepper (max-width: 96px) {
  .workflow-stepper {
    gap: var(--ez-space-2);
  }

  .workflow-step {
    align-items: flex-start;
    flex-direction: column;
    padding: var(--ez-space-1);
  }

  .step-index {
    width: 14px;
    height: 14px;
    margin: 0 0 var(--ez-space-1);
    font-size: 9px;
  }

  .step-content {
    width: 100%;
  }

  .step-label {
    font-size: var(--ez-font-size-12);
    word-break: break-all;
  }

  .step-state {
    font-size: 10px;
    word-break: break-all;
  }
}

@media (prefers-reduced-motion: reduce) {
  .is-running .step-index {
    animation: none;
  }
}
</style>
