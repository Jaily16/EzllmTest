<template>
  <aside class="test-retention-notice" :data-retention="retention" role="note">
    <strong>{{ label }}</strong>
    <span>{{ description }}</span>
  </aside>
</template>

<script lang="ts" setup>
/* global defineProps */
import { computed } from "vue";

const props = defineProps<{
  retention: "persistent" | "session-only";
}>();

const label = computed(() =>
  props.retention === "session-only" ? "仅当前页面保留" : "生成成功后已保存"
);
const description = computed(() =>
  props.retention === "session-only"
    ? "结果不会写入项目；刷新或离开本页面后无法恢复。"
    : "结果会保存到当前项目，并可在后续会话中按匹配的模型与输入恢复。"
);
</script>

<style scoped>
.test-retention-notice {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ez-space-2);
  padding: var(--ez-space-3) var(--ez-space-4);
  border: 1px solid var(--ez-color-success);
  border-radius: var(--ez-radius-medium);
  background: var(--ez-color-success-bg);
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
  line-height: var(--ez-line-height-body);
  overflow-wrap: anywhere;
}

.test-retention-notice[data-retention="session-only"] {
  border-color: var(--ez-color-warning);
  background: var(--ez-color-warning-bg);
}

strong { color: var(--ez-color-text-primary); }
</style>
