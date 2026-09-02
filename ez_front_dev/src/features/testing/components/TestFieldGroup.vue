<template>
  <fieldset
    class="test-field-group"
    :disabled="disabled"
    :aria-describedby="description ? `${fieldId}-description` : undefined"
  >
    <legend>
      {{ legend }}<span v-if="required" aria-hidden="true"> *</span>
      <span v-if="required" class="ez-sr-only">（必填）</span>
    </legend>
    <p v-if="description" :id="`${fieldId}-description`">{{ description }}</p>
    <div class="test-field-group__control"><slot /></div>
  </fieldset>
</template>

<script lang="ts" setup>
/* global defineProps, withDefaults */
withDefaults(
  defineProps<{
    legend: string;
    description?: string;
    fieldId: string;
    disabled?: boolean;
    required?: boolean;
  }>(),
  {
    description: "",
    disabled: false,
    required: false,
  },
);
</script>

<style scoped>
.test-field-group {
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
  overflow-wrap: anywhere;
}

.test-field-group__control {
  min-width: 0;
  max-width: 100%;
}

.test-field-group__control :deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
  max-width: 100%;
}

.test-field-group__control :deep(.el-radio-group[aria-required="true"]) {
  padding: 1px;
}

.test-field-group__control :deep(.el-radio-button__inner) {
  min-height: var(--ez-control-height);
  white-space: normal;
}
</style>
