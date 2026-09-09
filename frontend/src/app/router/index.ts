// 路由表保持稳定 URL 与懒加载；守卫使用项目状态限制访问，页面初始化负责身份和状态读取。
import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import { nextTick } from "vue";
import { routeTitleFor } from "@/shared/config/routePresentation";
import {
  getWorkflowRedirectPath,
  isWorkflowRouteAllowed,
  projectWorkflowStatus,
  setWorkflowRedirectMessage,
  workflowStatusLoaded,
} from "@/entities/project/model/analysis";

// 懒加载路由保持 legacy 测试页与 Agent 工作台的现有入口，不在加载时发起模型请求。
const routes: Array<RouteRecordRaw> = [
  {
    path: "/",
    name: "home",

    component: () => import("../../features/onboarding/pages/LoginView.vue"),
  },
  {
    path: "/about",
    name: "about",

    component: () => import("../../features/about/pages/AboutView.vue"),
  },
  {
    path: "/observability",
    name: "observability",

    component: () => import("../../features/observability/pages/ObservabilityView.vue"),
  },
  {
    path: "/create",
    name: "create",

    component: () => import("../../features/onboarding/pages/CreateView.vue"),
  },
  {
    path: "/test",
    name: "testMain",
    redirect: "/plan",

    component: () => import("../../features/workspace/pages/MainView.vue"),
    children: [
      {
        path: "/menu",
        meta: { requiresWorkflow: true },

        component: () => import("../../features/planning/pages/TestMenu.vue"),
      },
      {
        path: "/plan",
        meta: { requiresWorkflow: true },

        component: () => import("../../features/planning/pages/TestPlan.vue"),
      },
      {
        path: "/unit",
        meta: { requiresWorkflow: true },

        component: () => import("../../features/test-generation/pages/UnitTest.vue"),
      },
      {
        path: "/integration",
        meta: { requiresWorkflow: true },

        component: () => import("../../features/test-generation/pages/IntegrationTest.vue"),
      },
      {
        path: "/api",
        meta: { requiresWorkflow: true },

        component: () => import("../../features/test-generation/pages/ApiTest.vue"),
      },
      {
        path: "/ui",
        meta: { requiresWorkflow: true },

        component: () => import("../../features/test-generation/pages/UITest.vue"),
      },
      {
        path: "/database",
        meta: { requiresWorkflow: true },

        component: () => import("../../features/test-generation/pages/DatabaseTest.vue"),
      },
      {
        path: "/functional",
        meta: { requiresWorkflow: true },

        component: () => import("../../features/test-generation/pages/FunctionalTest.vue"),
      },
      {
        path: "/nfunctional",
        meta: { requiresWorkflow: true },

        component: () => import("../../features/test-generation/pages/NonfunctionalTest.vue"),
      },
      {
        path: "/acceptance",
        meta: { requiresWorkflow: true },

        component: () => import("../../features/test-generation/pages/AcceptanceTest.vue"),
      },
      {
        path: "/agent",
        meta: { requiresAgent: true },

        component: () => import("../../features/agent-workbench/pages/AgentWorkbench.vue"),
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

/** 以已加载的项目阶段限制 Agent 和测试路由；尚未加载的身份核对交给页面初始化，路由变化不启动生成。 */
router.beforeEach((to) => {
  if (
    to.meta.requiresAgent &&
    workflowStatusLoaded.value &&
    projectWorkflowStatus.value?.stage === "setup_required"
  ) {
    return "/create";
  }
  if (to.meta.requiresWorkflow && workflowStatusLoaded.value && !isWorkflowRouteAllowed(to.path)) {
    setWorkflowRedirectMessage(to.path);
    const redirect = getWorkflowRedirectPath();
    if (redirect !== to.path) return redirect;
  }
  return true;
});

/** 导航完成后更新标题并将焦点移到主内容，支持键盘和读屏连续浏览。 */
router.afterEach(async (to) => {
  document.title = `${routeTitleFor(to.path)} | EzllmTest`;
  await nextTick();
  const main = document.querySelector<HTMLElement>("main");
  main?.focus({ preventScroll: true });
});

export default router;
