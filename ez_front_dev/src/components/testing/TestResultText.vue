<template>
  <div class="test-result-text">{{ text || emptyText }}</div>
</template>

<script lang="ts" setup>
/* global defineProps, withDefaults */
withDefaults(defineProps<{
  text: string;
  emptyText?: string;
}>(), {
  emptyText: "暂无内容",
});
</script>

<style scoped>
.test-result-text {
  max-width: var(--ez-reading-measure);
  color: var(--ez-color-text-primary);
  font-family: var(--ez-font-body);
  line-height: var(--ez-line-height-body);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  user-select: text;
}
</style>
