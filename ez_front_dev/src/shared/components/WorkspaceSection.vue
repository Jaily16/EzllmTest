<template>
  <section class="workspace-section" :aria-busy="busy || undefined">
    <header class="workspace-section__header">
      <div class="workspace-section__copy">
        <h3>{{ title }}</h3>
        <p v-if="description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="workspace-section__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="workspace-section__body">
      <slot />
    </div>
  </section>
</template>

<script lang="ts" setup>
/* global defineProps, withDefaults */
withDefaults(
  defineProps<{
    title: string;
    description?: string;
    busy?: boolean;
  }>(),
  {
    description: "",
    busy: false,
  },
);
</script>

<style scoped>
.workspace-section {
  min-width: 0;
  padding: var(--ez-space-6);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-large);
  background: var(--ez-color-surface);
  box-shadow: var(--ez-shadow-small);
}

.workspace-section__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ez-space-4);
  margin-bottom: var(--ez-space-6);
}

.workspace-section__copy {
  min-width: 0;
}

h3 {
  margin: 0;
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-20);
  line-height: var(--ez-line-height-tight);
  overflow-wrap: anywhere;
}

p {
  max-width: var(--ez-reading-measure);
  margin: var(--ez-space-2) 0 0;
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
  overflow-wrap: anywhere;
}

.workspace-section__actions {
  flex: 0 0 auto;
}

.workspace-section__body {
  min-width: 0;
}

@media (max-width: 767px) {
  .workspace-section {
    padding: var(--ez-space-4);
  }

  .workspace-section__header {
    flex-direction: column;
  }

  .workspace-section__actions {
    width: 100%;
  }
}
</style>
