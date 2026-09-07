<template>
  <article
    class="test-workspace-card"
    :data-state="item.status"
    :aria-labelledby="`${item.key}-title`"
    :aria-describedby="`${item.key}-reason`"
  >
    <header class="test-workspace-card__header">
      <img
        class="test-workspace-card__illustration"
        :src="item.illustration"
        alt=""
        width="256"
        height="256"
        loading="lazy"
        decoding="async"
        aria-hidden="true"
      />
      <div class="test-workspace-card__identity">
        <p class="test-workspace-card__english">{{ item.englishTitle }}</p>
        <h4 :id="`${item.key}-title`">{{ item.title }}</h4>
      </div>
      <span class="test-workspace-card__status">{{ item.statusLabel }}</span>
    </header>

    <p :id="`${item.key}-reason`" class="test-workspace-card__reason">
      {{ item.reason }}
    </p>
    <p class="test-workspace-card__next"><strong>进入后：</strong>{{ item.nextStep }}</p>
    <p class="test-workspace-card__progress">{{ item.progressHint }}</p>

    <footer class="test-workspace-card__footer">
      <RouterLink
        v-if="!item.disabled"
        class="test-workspace-card__link"
        :to="item.route"
        :aria-label="`进入${item.title}工作区`"
      >
        进入工作区
      </RouterLink>
      <span v-else class="test-workspace-card__disabled" aria-disabled="true"> 暂不可进入 </span>
    </footer>
  </article>
</template>

<script lang="ts" setup>
/* global defineProps */
import { RouterLink } from "vue-router";
import type { TestWorkspaceCardViewModel } from "@/features/testing/config/testWorkspaces";

defineProps<{
  item: TestWorkspaceCardViewModel;
}>();
</script>

<style scoped>
.test-workspace-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: var(--ez-space-4);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-large);
  background: var(--ez-color-surface);
  box-shadow: var(--ez-shadow-small);
}

.test-workspace-card__header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--ez-space-3);
}

.test-workspace-card__illustration {
  width: clamp(64px, 7vw, 88px);
  height: clamp(64px, 7vw, 88px);
  object-fit: contain;
}

.test-workspace-card__identity {
  min-width: 0;
}

.test-workspace-card__english,
.test-workspace-card__reason,
.test-workspace-card__next,
.test-workspace-card__progress {
  overflow-wrap: anywhere;
}

.test-workspace-card__english {
  margin: 0 0 var(--ez-space-1);
  color: var(--ez-color-text-muted);
  font-family: var(--ez-font-brand);
  font-size: var(--ez-font-size-12);
  letter-spacing: 0.04em;
}

h4 {
  margin: 0;
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-16);
  line-height: var(--ez-line-height-tight);
}

.test-workspace-card__status {
  align-self: start;
  padding: var(--ez-space-1) var(--ez-space-2);
  border-radius: var(--ez-radius-pill);
  background: var(--ez-color-info-bg);
  color: var(--ez-color-info);
  font-size: var(--ez-font-size-12);
  font-weight: 700;
  white-space: nowrap;
}

.test-workspace-card[data-state="available"] .test-workspace-card__status {
  background: var(--ez-color-success-bg);
  color: var(--ez-color-success);
}

.test-workspace-card[data-state="stale"] {
  border-color: var(--ez-color-warning);
  background: var(--ez-color-warning-bg);
}

.test-workspace-card[data-state="stale"] .test-workspace-card__status {
  background: var(--ez-color-warning-bg);
  color: var(--ez-color-warning);
}

.test-workspace-card[data-state="locked"] .test-workspace-card__status,
.test-workspace-card[data-state="not-recommended"] .test-workspace-card__status,
.test-workspace-card[data-state="regenerating"] .test-workspace-card__status {
  background: var(--ez-color-locked-bg);
  color: var(--ez-color-locked);
}

.test-workspace-card__reason {
  margin: var(--ez-space-4) 0 0;
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-14);
  line-height: var(--ez-line-height-body);
}

.test-workspace-card__next,
.test-workspace-card__progress {
  margin: var(--ez-space-2) 0 0;
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
  line-height: var(--ez-line-height-body);
}

.test-workspace-card__progress {
  padding-top: var(--ez-space-2);
  border-top: 1px solid var(--ez-color-border);
}

.test-workspace-card__footer {
  display: flex;
  align-items: center;
  margin-top: auto;
  padding-top: var(--ez-space-4);
}

.test-workspace-card__link,
.test-workspace-card__disabled {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: var(--ez-control-height);
  padding: var(--ez-space-2) var(--ez-space-4);
  border-radius: var(--ez-radius-medium);
  font-size: var(--ez-font-size-14);
  font-weight: 700;
  text-align: center;
}

.test-workspace-card__link {
  color: var(--ez-color-surface);
  background: var(--ez-color-brand-500);
  text-decoration: none;
}

.test-workspace-card__link:hover {
  background: var(--ez-color-brand-600);
}

.test-workspace-card__disabled {
  color: var(--ez-color-locked);
  background: var(--ez-color-locked-bg);
}

@media (max-width: 480px) {
  .test-workspace-card__header {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .test-workspace-card__status {
    grid-column: 1 / -1;
    justify-self: start;
  }

  .test-workspace-card__link,
  .test-workspace-card__disabled {
    width: 100%;
  }
}
</style>
