<template>
  <div class="workflow-action-bar" role="group" :aria-label="ariaLabel">
    <slot />
  </div>
</template>

<script lang="ts" setup>
/* global defineProps */
defineProps<{
  ariaLabel?: string;
}>();
</script>

<style scoped>
.workflow-action-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ez-space-3);
  min-width: 0;
  margin-top: var(--ez-space-4);
}

.workflow-action-bar :deep(.el-button) {
  min-height: var(--ez-control-height);
  margin: 0;
}

@media (max-width: 480px) {
  .workflow-action-bar {
    align-items: stretch;
  }

  .workflow-action-bar :deep(.el-button) {
    width: 100%;
    white-space: normal;
  }
}
</style>
