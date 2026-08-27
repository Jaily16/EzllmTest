<template>
  <main class="onboarding-shell" :class="{ 'onboarding-shell--wide': wide }" tabindex="-1">
    <div class="onboarding-shell__frame">
      <header class="onboarding-shell__brand">
        <img
          class="onboarding-shell__logo"
          :src="workbenchLogo"
          width="52"
          height="52"
          alt=""
          aria-hidden="true"
        />
        <div>
          <p class="onboarding-shell__product">EzllmTest</p>
          <p class="onboarding-shell__tagline">LLM 驱动的软件测试工作台</p>
        </div>
      </header>

      <div class="onboarding-shell__body">
        <section class="onboarding-shell__panel" aria-labelledby="onboarding-title">
          <p v-if="eyebrow" class="onboarding-shell__eyebrow">{{ eyebrow }}</p>
          <h1 id="onboarding-title">{{ title }}</h1>
          <p v-if="description" class="onboarding-shell__description">
            {{ description }}
          </p>
          <div class="onboarding-shell__content"><slot /></div>
        </section>

        <aside v-if="$slots.secondary" class="onboarding-shell__secondary">
          <slot name="secondary" />
        </aside>
      </div>

      <footer class="onboarding-shell__footer">
        <slot name="footer">2.0 测试版 · 本地 AI 测试工作台</slot>
      </footer>
    </div>
  </main>
</template>

<script lang="ts" setup>
import workbenchLogo from "@/assets/static/image/ezlogo-workbench-v2.png";

withDefaults(defineProps<{
  title: string;
  description?: string;
  eyebrow?: string;
  wide?: boolean;
}>(), {
  description: "",
  eyebrow: "",
  wide: false,
});
</script>

<style scoped>
.onboarding-shell {
  min-height: 100vh;
  min-height: 100dvh;
  padding: var(--ez-page-gutter);
  background: var(--ez-color-canvas);
  color: var(--ez-color-text-primary);
}

.onboarding-shell__frame {
  width: 100%;
  max-width: 1040px;
  margin: 0 auto;
}

.onboarding-shell--wide .onboarding-shell__frame {
  max-width: var(--ez-content-wide);
}

.onboarding-shell__brand {
  display: flex;
  align-items: center;
  gap: var(--ez-space-3);
  min-width: 0;
  margin-bottom: var(--ez-space-8);
}

.onboarding-shell__logo {
  flex: 0 0 auto;
  width: 52px;
  height: 52px;
  object-fit: contain;
}

.onboarding-shell__product,
.onboarding-shell__tagline {
  margin: 0;
}

.onboarding-shell__product {
  font-family: var(--ez-font-brand);
  font-size: var(--ez-font-size-24);
  line-height: var(--ez-line-height-tight);
}

.onboarding-shell__tagline {
  margin-top: var(--ez-space-1);
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
}

.onboarding-shell__body {
  display: grid;
  gap: var(--ez-space-6);
  min-width: 0;
}

.onboarding-shell__panel,
.onboarding-shell__secondary {
  min-width: 0;
  padding: var(--ez-space-6);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-large);
  background: var(--ez-color-surface);
  box-shadow: var(--ez-shadow-medium);
}

.onboarding-shell__secondary {
  align-self: start;
  background: var(--ez-color-surface-subtle);
  box-shadow: var(--ez-shadow-small);
}

.onboarding-shell__eyebrow {
  margin: 0 0 var(--ez-space-1);
  color: var(--ez-color-brand-600);
  font-size: var(--ez-font-size-13);
  font-weight: 700;
  letter-spacing: .06em;
}

h1 {
  margin: 0;
  font-size: clamp(var(--ez-font-size-24), 5vw, var(--ez-font-size-32));
  line-height: var(--ez-line-height-tight);
  overflow-wrap: anywhere;
}

.onboarding-shell__description {
  max-width: var(--ez-reading-measure);
  margin: var(--ez-space-2) 0 0;
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
  overflow-wrap: anywhere;
}

.onboarding-shell__content {
  min-width: 0;
  margin-top: var(--ez-space-6);
}

.onboarding-shell__footer {
  margin-top: var(--ez-space-6);
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
  text-align: right;
}

@media (min-width: 768px) {
  .onboarding-shell { padding: var(--ez-page-gutter-tablet); }
  .onboarding-shell__panel,
  .onboarding-shell__secondary { padding: var(--ez-space-8); }
}

@media (min-width: 1024px) {
  .onboarding-shell { padding: var(--ez-page-gutter-desktop); }
  .onboarding-shell:not(.onboarding-shell--wide) .onboarding-shell__body {
    grid-template-columns: minmax(0, 1.55fr) minmax(280px, .85fr);
  }
}

@media (min-width: 1440px) {
  .onboarding-shell { padding: var(--ez-page-gutter-wide); }
}

@media (min-width: 1920px) {
  .onboarding-shell { padding: var(--ez-page-gutter-ultrawide); }
}
</style>
