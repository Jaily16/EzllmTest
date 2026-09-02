export interface RoutePresentation {
  title: string;
}

export const ROUTE_PRESENTATION: Record<string, RoutePresentation> = {
  "/": { title: "项目入口" },
  "/create": { title: "创建与恢复项目" },
  "/about": { title: "平台说明" },
  "/plan": { title: "测试计划" },
  "/menu": { title: "测试菜单" },
  "/unit": { title: "单元测试" },
  "/integration": { title: "集成测试" },
  "/api": { title: "API 接口测试" },
  "/ui": { title: "前端 UI 测试" },
  "/database": { title: "数据库测试" },
  "/functional": { title: "系统功能性测试" },
  "/nfunctional": { title: "系统非功能性测试" },
  "/acceptance": { title: "验收测试" },
  "/agent": { title: "Agent 编排" },
};

export const routeTitleFor = (path: string): string =>
  ROUTE_PRESENTATION[path]?.title || "EzllmTest";
