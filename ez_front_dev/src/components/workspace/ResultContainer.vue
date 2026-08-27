<template>
  <section class="result-container" :data-status="status">
    <header class="result-container__header">
      <div class="result-container__copy">
        <h4>{{ title }}</h4>
        <p v-if="description">{{ description }}</p>
      </div>
      <span v-if="retention" class="result-container__retention" :data-retention="retention">
        {{ retentionLabel }}
      </span>
    </header>
    <div class="result-container__body">
      <slot />
    </div>
  </section>
</template>

<script lang="ts" setup>
/* global defineProps, withDefaults */
import { computed } from "vue";

type ResultStatus = "default" | "stale";
type ResultRetention = "persistent" | "session-only";

const props = withDefaults(defineProps<{
  title: string;
  description?: string;
  status?: ResultStatus;
  retention?: ResultRetention;
  retentionText?: string;
}>(), {
  description: "",
  status: "default",
  retention: undefined,
  retentionText: "",
});

const retentionLabel = computed(() =>
  props.retentionText ||
  (props.retention === "session-only" ? "仅当前页面保留" : "已保存")
);
</script>

<style scoped>
.result-container {
  min-width: 0;
  padding: var(--ez-space-4);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
  background: var(--ez-color-surface-subtle);
}

.result-container[data-status="stale"] {
  border-color: var(--ez-color-warning);
  background: var(--ez-color-warning-bg);
}

.result-container__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ez-space-3);
  margin-bottom: var(--ez-space-3);
}

.result-container__copy {
  min-width: 0;
}

h4 {
  margin: 0;
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-16);
  overflow-wrap: anywhere;
}

p {
  max-width: var(--ez-reading-measure);
  margin: var(--ez-space-1) 0 0;
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
  line-height: var(--ez-line-height-body);
  overflow-wrap: anywhere;
}

.result-container__retention {
  flex: 0 0 auto;
  padding: var(--ez-space-1) var(--ez-space-2);
  border-radius: var(--ez-radius-pill);
  background: var(--ez-color-success-bg);
  color: var(--ez-color-success);
  font-size: var(--ez-font-size-12);
  font-weight: 700;
}

.result-container__retention[data-retention="session-only"] {
  background: var(--ez-color-warning-bg);
  color: var(--ez-color-warning);
}

.result-container__body {
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
}

@media (max-width: 480px) {
  .result-container__header {
    flex-direction: column;
  }
}
</style>
