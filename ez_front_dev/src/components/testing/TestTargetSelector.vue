<template>
  <TestFieldGroup
    :legend="label"
    :description="description"
    :field-id="fieldId"
    :disabled="disabled"
    :required="required"
  >
    <el-select
      :id="fieldId"
      v-model="value"
      class="test-target-selector__control"
      :class="controlClasses"
      :placeholder="placeholder"
      :disabled="disabled"
      :filterable="filterable"
      fit-input-width
      popper-class="test-target-selector-popper"
      :aria-label="label"
      :aria-required="required || undefined"
      :aria-describedby="describedBy"
      @visible-change="handleVisibleChange"
    >
      <slot name="options">
        <el-option
          v-for="(option, index) in options"
          :key="`${option.value}-${index}`"
          :label="option.label"
          :value="option.value"
        />
      </slot>
    </el-select>
    <div
      v-if="selectedOption"
      :id="selectionDescriptionId"
      class="test-target-selector__summary"
    >
      <span class="test-target-selector__summary-label">当前选择</span>
      <strong>{{ selectedOption.label }}</strong>
      <span
        v-if="selectedOption.detail && selectedOption.detail !== selectedOption.label"
        class="test-target-selector__detail"
      >
        完整标识：{{ selectedOption.detail }}
      </span>
    </div>
  </TestFieldGroup>
</template>

<script lang="ts" setup>
/* global defineProps, defineEmits, withDefaults */
import { computed, ref } from "vue";
import TestFieldGroup from "@/components/testing/TestFieldGroup.vue";

export interface TestTargetOption {
  value: string;
  label: string;
  detail?: string;
}

const props = withDefaults(defineProps<{
  modelValue: string;
  options: TestTargetOption[];
  label: string;
  fieldId: string;
  description?: string;
  placeholder?: string;
  disabled?: boolean;
  filterable?: boolean;
  required?: boolean;
}>(), {
  description: "",
  placeholder: "请选择",
  disabled: false,
  filterable: true,
  required: false,
});

const emit = defineEmits<{
  (event: "update:modelValue", value: string): void;
}>();

const value = computed({
  get: () => props.modelValue,
  set: (next: string) => emit("update:modelValue", next),
});
const selectedOption = computed(() =>
  props.options.find((option) => option.value === props.modelValue)
);
const dropdownOpen = ref(false);
const controlClasses = computed(() => ({
  "test-target-selector__control--selected": Boolean(selectedOption.value),
  "test-target-selector__control--open": dropdownOpen.value,
}));
const handleVisibleChange = (visible: boolean) => {
  dropdownOpen.value = visible;
};
const selectionDescriptionId = computed(
  () => `${props.fieldId}-selection-description`
);
const describedBy = computed(() => {
  const ids: string[] = [];
  if (props.description) ids.push(`${props.fieldId}-description`);
  if (selectedOption.value) ids.push(selectionDescriptionId.value);
  return ids.join(" ") || undefined;
});
</script>

<style scoped>
.test-target-selector__control {
  width: min(100%, var(--ez-content-compact));
  max-width: 100%;
}

.test-target-selector__control :deep(.el-select__selection),
.test-target-selector__control :deep(.el-select__placeholder) {
  min-width: 0;
  max-width: 100%;
}

.test-target-selector__control :deep(.el-select__placeholder > span) {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.test-target-selector__control--selected:not(
  .test-target-selector__control--open
) :deep(.el-select__input) {
  caret-color: transparent;
}

.test-target-selector__control--open :deep(.el-select__placeholder) {
  visibility: hidden;
}

.test-target-selector__summary {
  display: grid;
  gap: var(--ez-space-1);
  max-width: var(--ez-reading-measure);
  margin: var(--ez-space-2) 0 0;
  padding: var(--ez-space-2) var(--ez-space-3);
  border-left: 3px solid var(--ez-color-brand-300);
  border-radius: var(--ez-radius-small);
  background: var(--ez-color-surface-subtle);
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
  line-height: var(--ez-line-height-body);
  overflow-wrap: anywhere;
}

.test-target-selector__summary strong,
.test-target-selector__detail {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.test-target-selector__summary-label {
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
  font-weight: 700;
}

:global(.test-target-selector-popper .el-select-dropdown__item) {
  display: flex;
  align-items: center;
  min-height: var(--ez-touch-target);
  height: auto;
  padding-top: var(--ez-space-2);
  padding-bottom: var(--ez-space-2);
  line-height: var(--ez-line-height-body);
  text-overflow: clip;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}
</style>
