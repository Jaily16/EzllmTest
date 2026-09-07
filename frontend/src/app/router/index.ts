import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import { nextTick } from "vue";
import { routeTitleFor } from "@/shared/config/routePresentation";
import {
  getWorkflowRedirectPath,
  isWorkflowRouteAllowed,
  projectWorkflowStatus,
  setWorkflowRedirectMessage,
  workflowStatusLoaded,
} from "@/features/planning/state/projectAnalysis";

// 懒加载路由保持 legacy 测试页与 Agent 工作台的现有入口，不在加载时发起模型请求。
const routes: Array<RouteRecordRaw> = [
  {
    path: "/",
    name: "home",
    /**
     * 处理component，并保持现有输入输出约定。
     */
    component: () => import("../../features/onboarding/views/LoginView.vue"),
  },
  {
    path: "/about",
    name: "about",
    /**
     * 处理component，并保持现有输入输出约定。
     */
    component: () => import("../../features/about/AboutView.vue"),
  },
  {
    path: "/observability",
    name: "observability",
    /**
     * 处理component，并保持现有输入输出约定。
     */
    component: () => import("../../features/observability/ObservabilityView.vue"),
  },
  {
    path: "/create",
    name: "create",
    /**
     * 处理component，并保持现有输入输出约定。
     */
    component: () => import("../../features/onboarding/views/CreateView.vue"),
  },
  {
    path: "/test",
    name: "testMain",
    redirect: "/plan",
    /**
     * 处理component，并保持现有输入输出约定。
     */
    component: () => import("../../features/workspace/MainView.vue"),
    children: [
      {
        path: "/menu",
        meta: { requiresWorkflow: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/planning/views/TestMenu.vue"),
      },
      {
        path: "/plan",
        meta: { requiresWorkflow: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/planning/views/TestPlan.vue"),
      },
      {
        path: "/unit",
        meta: { requiresWorkflow: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/testing/pages/UnitTest.vue"),
      },
      {
        path: "/integration",
        meta: { requiresWorkflow: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/testing/pages/IntegrationTest.vue"),
      },
      {
        path: "/api",
        meta: { requiresWorkflow: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/testing/pages/ApiTest.vue"),
      },
      {
        path: "/ui",
        meta: { requiresWorkflow: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/testing/pages/UITest.vue"),
      },
      {
        path: "/database",
        meta: { requiresWorkflow: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/testing/pages/DatabaseTest.vue"),
      },
      {
        path: "/functional",
        meta: { requiresWorkflow: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/testing/pages/FunctionalTest.vue"),
      },
      {
        path: "/nfunctional",
        meta: { requiresWorkflow: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/testing/pages/NonfunctionalTest.vue"),
      },
      {
        path: "/acceptance",
        meta: { requiresWorkflow: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/testing/pages/AcceptanceTest.vue"),
      },
      {
        path: "/agent",
        meta: { requiresAgent: true },
        /**
         * 处理component，并保持现有输入输出约定。
         */
        component: () => import("../../features/agent/AgentWorkbench.vue"),
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

/**
 * 导航前应用项目恢复与页面访问约束。
 */
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

/**
 * 导航完成后同步页面展示与可访问性状态。
 */
router.afterEach(async (to) => {
  document.title = `${routeTitleFor(to.path)} | EzllmTest`;
  await nextTick();
  const main = document.querySelector<HTMLElement>("main");
  main?.focus({ preventScroll: true });
});

export default router;
