<template>
  <fieldset
    class="model-selector"
    :disabled="disabled"
    :aria-describedby="description ? `${resolvedId}-description` : undefined"
  >
    <legend>{{ label }}</legend>
    <p v-if="description" :id="`${resolvedId}-description`">{{ description }}</p>
    <div class="model-selector__control">
      <el-segmented
        :id="resolvedId"
        v-model="value"
        :options="options"
        size="large"
        :disabled="disabled"
        :aria-label="label"
        :aria-describedby="description ? `${resolvedId}-description` : undefined"
      />
    </div>
  </fieldset>
</template>

<script lang="ts" setup>
// 无业务存储能力的公共展示组件，状态来自 props，用户意图通过事件交回调用方。

/* global defineProps, defineEmits, withDefaults */
import { computed, getCurrentInstance } from "vue";
import type { ModelLabel } from "@/shared/config/models";

interface ModelOption {
  label: string;
  value: ModelLabel;
}

const props = withDefaults(
  defineProps<{
    modelValue: ModelLabel;
    options: ModelOption[];
    disabled?: boolean;
    label: string;
    description?: string;
    id?: string;
  }>(),
  {
    disabled: false,
    description: "",
    id: "",
  },
);

const emit = defineEmits<{
  (event: "update:modelValue", value: ModelLabel): void;
}>();

const instance = getCurrentInstance();
/**
 * 派生用于界面展示或请求判断的resolved ID。
 */
const resolvedId = computed(() => props.id || `workspace-model-selector-${instance?.uid ?? 0}`);

const value = computed({
  /** 读取父组件的模型选择值。 */
  get: () => props.modelValue,
  /** 只发出选择变更事件，模型执行由业务动作显式触发。 */
  set: (next: ModelLabel) => emit("update:modelValue", next),
});
</script>

<style scoped>
.model-selector {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

legend {
  padding: 0;
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-14);
  font-weight: 700;
}

p {
  max-width: var(--ez-reading-measure);
  margin: var(--ez-space-1) 0 var(--ez-space-3);
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-13);
  line-height: var(--ez-line-height-body);
}

.model-selector__control {
  max-width: 100%;
  padding: var(--ez-space-1);
}

@media (max-width: 480px) {
  .model-selector__control {
    padding-inline: 0;
  }

  .model-selector__control :deep(.el-segmented) {
    display: block;
    width: 100%;
    height: auto;
  }

  .model-selector__control :deep(.el-segmented__group) {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--ez-space-1);
  }

  .model-selector__control :deep(.el-segmented__item-selected) {
    /* Element Plus writes display:block inline while recalculating the indicator. */
    display: none !important;
  }

  .model-selector__control :deep(.el-segmented__item) {
    min-width: 0;
    min-height: var(--ez-touch-target);
    padding: var(--ez-space-2);
  }

  .model-selector__control :deep(.el-segmented__item.is-selected) {
    color: var(--ez-color-surface);
    background: var(--ez-color-brand-500);
  }

  .model-selector__control :deep(.el-segmented__item-label) {
    overflow: visible;
    text-overflow: clip;
    white-space: normal;
    overflow-wrap: anywhere;
  }
}

@media (max-width: 320px) {
  .model-selector__control :deep(.el-segmented__group) {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
