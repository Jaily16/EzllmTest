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

代码规范和目录迁移说明见 [`../docs/development/iteration-5/style-guide.md`](../docs/development/iteration-5/style-guide.md) 与 [`../docs/architecture/frontend-structure.md`](../docs/architecture/frontend-structure.md)。分模块启动、readiness 和安全停止见 [`../docs/operations/modular-runtime.md`](../docs/operations/modular-runtime.md)；容器交付与卷运维边界见 [`../docs/operations/container-delivery.md`](../docs/operations/container-delivery.md)；双模式验收见 [`../docs/operations/dual-mode-acceptance.md`](../docs/operations/dual-mode-acceptance.md)。
