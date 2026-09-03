<template>
  <div
    class="feedback-state"
    :class="[`feedback-state--${kind}`, { 'feedback-state--compact': compact }]"
    :role="semanticRole"
    :aria-busy="busy || kind === 'loading' ? 'true' : undefined"
  >
    <span v-if="kind === 'loading'" class="feedback-state__spinner" aria-hidden="true" />
    <span v-else class="feedback-state__marker" aria-hidden="true">
      {{ kind === "error" ? "!" : "—" }}
    </span>
    <div class="feedback-state__copy">
      <strong>{{ title }}</strong>
      <p v-if="description">{{ description }}</p>
      <div
        v-if="showSkeleton"
        class="feedback-state__skeleton"
        :data-skeleton="skeleton"
        aria-hidden="true"
      >
        <span v-for="index in skeletonItems" :key="index" />
      </div>
      <div v-if="$slots.actions" class="feedback-state__actions">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
/* global defineProps, withDefaults */
import { computed } from "vue";

type FeedbackKind = "loading" | "empty" | "error";
export type FeedbackSkeleton = "none" | "content" | "form" | "cards";

const props = withDefaults(
  defineProps<{
    kind: FeedbackKind;
    title: string;
    description?: string;
    busy?: boolean;
    compact?: boolean;
    skeleton?: FeedbackSkeleton;
  }>(),
  {
    description: "",
    busy: false,
    compact: false,
    skeleton: "none",
  },
);

const semanticRole = computed(() => (props.kind === "error" ? "alert" : "status"));
const showSkeleton = computed(() => props.kind === "loading" && props.skeleton !== "none");
const skeletonItems = computed(() =>
  props.skeleton === "cards" ? 6 : props.skeleton === "form" ? 5 : 4,
);
</script>

<style scoped>
.feedback-state {
  display: flex;
  align-items: flex-start;
  gap: var(--ez-space-3);
  min-width: 0;
  padding: var(--ez-space-6);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
  background: var(--ez-color-surface-subtle);
  color: var(--ez-color-text-primary);
}

.feedback-state--compact {
  padding: var(--ez-space-4);
}

.feedback-state--error {
  border-color: var(--ez-color-danger);
  background: var(--ez-color-danger-bg);
}

.feedback-state__spinner,
.feedback-state__marker {
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
  width: var(--ez-space-6);
  height: var(--ez-space-6);
  border-radius: var(--ez-radius-pill);
  color: var(--ez-color-brand-600);
  font-weight: 700;
}

.feedback-state__spinner {
  border: 2px solid var(--ez-color-brand-100);
  border-top-color: var(--ez-color-brand-600);
  animation: feedback-spin var(--ez-motion-slow) linear infinite;
}

.feedback-state--error .feedback-state__marker {
  background: var(--ez-color-danger);
  color: var(--ez-color-surface);
}

.feedback-state__copy {
  flex: 1 1 auto;
  min-width: 0;
}

strong,
p {
  overflow-wrap: anywhere;
}

p {
  max-width: var(--ez-reading-measure);
  margin: var(--ez-space-1) 0 0;
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
}

.feedback-state__actions {
  margin-top: var(--ez-space-3);
}

.feedback-state__skeleton {
  display: grid;
  gap: var(--ez-space-3);
  width: 100%;
  min-height: var(--ez-skeleton-min-height-content);
  margin-top: var(--ez-space-4);
}

.feedback-state__skeleton[data-skeleton="form"] {
  min-height: var(--ez-skeleton-min-height-form);
}

.feedback-state__skeleton[data-skeleton="cards"] {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 160px), 1fr));
  min-height: var(--ez-skeleton-min-height-cards);
}

.feedback-state__skeleton span {
  display: block;
  min-height: var(--ez-space-6);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-small);
  background: linear-gradient(
    90deg,
    var(--ez-color-canvas),
    var(--ez-color-surface),
    var(--ez-color-canvas)
  );
  background-size: 200% 100%;
  animation: feedback-skeleton var(--ez-motion-slow) var(--ez-motion-easing) infinite alternate;
}

.feedback-state__skeleton[data-skeleton="content"] span:first-child,
.feedback-state__skeleton[data-skeleton="form"] span {
  min-height: var(--ez-control-height);
}

.feedback-state__skeleton[data-skeleton="cards"] span {
  min-height: 112px;
  border-radius: var(--ez-radius-medium);
}

@keyframes feedback-spin {
  to {
    transform: rotate(1turn);
  }
}

@keyframes feedback-skeleton {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: 0 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .feedback-state__spinner {
    animation: none;
    border-color: var(--ez-color-brand-600);
  }

  .feedback-state__skeleton span {
    animation: none;
    background: var(--ez-color-canvas);
  }
}
</style>
