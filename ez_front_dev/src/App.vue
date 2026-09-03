<template>
  <router-view />
</template>

<script lang="ts" setup>
import debounce from "lodash/debounce";

const NativeResizeObserver = window.ResizeObserver;
type ResizeCallback = ConstructorParameters<typeof NativeResizeObserver>[0];
window.ResizeObserver = class DebouncedResizeObserver extends NativeResizeObserver {
  constructor(callback: ResizeCallback) {
    super(debounce(callback, 100));
  }
};
</script>
