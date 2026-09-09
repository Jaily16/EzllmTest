<template>
  <header class="workspace-page-header">
    <div class="workspace-page-header__copy">
      <p v-if="eyebrow" class="workspace-page-header__eyebrow">{{ eyebrow }}</p>
      <h2>{{ title }}</h2>
      <p v-if="description" class="workspace-page-header__description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="workspace-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script lang="ts" setup>
// 无业务存储能力的公共展示组件，状态来自 props，用户意图通过事件交回调用方。

/* global defineProps */
defineProps<{
  title: string;
  eyebrow?: string;
  description?: string;
}>();
</script>

<style scoped>
.workspace-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ez-space-6);
  min-width: 0;
}

.workspace-page-header__copy {
  min-width: 0;
  max-width: var(--ez-reading-measure);
}

.workspace-page-header__eyebrow {
  margin: 0 0 var(--ez-space-1);
  color: var(--ez-color-brand-600);
  font-size: var(--ez-font-size-13);
  font-weight: 700;
  letter-spacing: 0.06em;
}

h2 {
  margin: 0;
  color: var(--ez-color-text-primary);
  font-size: clamp(var(--ez-font-size-24), 3vw, var(--ez-font-size-32));
  line-height: var(--ez-line-height-tight);
  overflow-wrap: anywhere;
}

.workspace-page-header__description {
  margin: var(--ez-space-2) 0 0;
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
  overflow-wrap: anywhere;
}

.workspace-page-header__actions {
  flex: 0 0 auto;
}

@media (max-width: 767px) {
  .workspace-page-header {
    flex-direction: column;
    gap: var(--ez-space-4);
  }

  .workspace-page-header__actions {
    width: 100%;
  }
}
</style>
