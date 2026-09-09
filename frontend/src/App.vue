<template>
  <router-view />
</template>

<script lang="ts" setup>
// 应用根组件承载路由视图和全局尺寸观察适配，具体业务状态由各功能维护。

import debounce from "lodash/debounce";

const NativeResizeObserver = window.ResizeObserver;
type ResizeCallback = ConstructorParameters<typeof NativeResizeObserver>[0];
window.ResizeObserver = class DebouncedResizeObserver extends NativeResizeObserver {
  /** 对 ResizeObserver 回调做一百毫秒防抖，降低布局变化期间的重复测量；保留原浏览器观察器接口。 */
  constructor(callback: ResizeCallback) {
    super(debounce(callback, 100));
  }
};
</script>
