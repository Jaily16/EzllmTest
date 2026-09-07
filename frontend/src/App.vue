<template>
  <router-view />
</template>

<script lang="ts" setup>
import debounce from "lodash/debounce";

const NativeResizeObserver = window.ResizeObserver;
type ResizeCallback = ConstructorParameters<typeof NativeResizeObserver>[0];
window.ResizeObserver = class DebouncedResizeObserver extends NativeResizeObserver {
  /**
   * 处理constructor，并保持现有输入输出约定。
   */
  constructor(callback: ResizeCallback) {
    super(debounce(callback, 100));
  }
};
</script>
