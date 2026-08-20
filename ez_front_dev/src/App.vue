<template>
  <router-view/>
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

<style scoped>
@font-face {
    font-family: 'Quantify';
    src: url('/src/assets/static/font/Quantify.ttf');
}
@font-face {
    font-family: 'Gjhn';
    src: url('/src/assets/static/font/GjhnGZcrG5SS.woff2');
}
@font-face {
    font-family: 'Ali';
    src: url('/src/assets/static/font/AlimamaFangYuan.ttf');
}

.cn_name {
  font-family: "Ali";
}

.en_name {
  font-family: "Quantify";
}

</style>
