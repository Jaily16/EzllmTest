# ez_front_dev

## Project setup

本目录是 Vite 前端入口；依赖安装使用已提交的 npm lock，不要使用 Vue CLI。

```
npm ci
```

### Compiles and hot-reloads for development
```
npm run serve
```

### Compiles and minifies for production
```
npm run build
```

### Lints files
```
npm run lint -- --no-fix
npm run type-check
npm run format:check
```

### Build
```
npm run build
```

代码规范和目录迁移说明见 [`../docs/development/iteration-5/style-guide.md`](../docs/development/iteration-5/style-guide.md) 与 [`../docs/architecture/frontend-structure.md`](../docs/architecture/frontend-structure.md)。当前分模块启动、readiness 和安全停止见 [`../docs/operations/modular-runtime.md`](../docs/operations/modular-runtime.md)，Iteration 6 最终边界见[收口报告](../docs/iteration-6-closeout.md)。[`container-delivery.md`](../docs/operations/container-delivery.md) 与 [`dual-mode-acceptance.md`](../docs/operations/dual-mode-acceptance.md) 仅为 Iteration 5 历史资料，其执行设施已不在当前 V6 树中。
