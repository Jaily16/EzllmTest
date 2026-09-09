// 为 TypeScript 声明 Vue 单文件组件模块，类型指令保持工具契约。
/* eslint-disable */
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
