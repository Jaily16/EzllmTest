<template>
  <router-view/>
</template>

<script lang="ts" setup>
import { debounce } from "lodash";

const _ = (window as any).ResizeObserver;
(window as any).ResizeObserver = class ResizeObserver extends _ {
  constructor(callback: (...args: any[]) => void) {
    callback = debounce(callback, 100);
    super(callback);
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