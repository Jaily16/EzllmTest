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

代码规范和目录迁移说明见 [`../docs/project-design.md#development`](../docs/project-design.md#development) 与 [`../docs/project-design.md#architecture`](../docs/project-design.md#architecture)。当前分模块启动、readiness 和安全停止见 [`../docs/project-design.md#startup`](../docs/project-design.md#startup)，Iteration 6 最终边界见[收口报告](../docs/iteration-history.md#iteration-6)。[`container-delivery.md`](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/operations/container-delivery.md) 与 [`dual-mode-acceptance.md`](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/operations/dual-mode-acceptance.md) 仅为 Iteration 5 历史资料，其执行设施已不在当前 V6 树中。
