<template>
  <div class="workspace-shell">
    <a class="skip-link" href="#workspace-main">跳到主要内容</a>

    <header class="workspace-header">
      <div class="header-brand">
        <button
          ref="navigationToggleRef"
          class="navigation-toggle"
          type="button"
          aria-label="打开项目导航"
          aria-controls="workspace-navigation"
          :aria-expanded="mobileNavigationOpen"
          @click="openMobileNavigation"
        >
          <el-icon aria-hidden="true"><Menu /></el-icon>
        </button>
        <img
          class="brand-logo"
          :src="workbenchLogo"
          width="38"
          height="38"
          alt=""
          aria-hidden="true"
        />
        <span class="brand-wordmark">EzllmTest</span>
      </div>

      <div class="route-context">
        <span class="route-eyebrow">项目工作区</span>
        <h1 :title="currentRouteTitle">{{ currentRouteTitle }}</h1>
      </div>

      <div class="header-status" aria-live="polite">
        <span class="header-project-name" :title="name || '项目加载中'">
          {{ name || "项目加载中" }}
        </span>
        <span class="lifecycle-chip" :data-status-loaded="workflowStatusLoaded">
          {{ workflowStageLabel }}
        </span>
      </div>
    </header>

    <div class="workspace-body">
      <button
        v-if="mobileNavigationOpen && !isDesktop"
        class="navigation-backdrop"
        type="button"
        aria-label="关闭项目导航"
        @click="closeMobileNavigation()"
      />

      <aside
        id="workspace-navigation"
        ref="navigationPanelRef"
        class="workspace-aside"
        :class="{ 'is-open': mobileNavigationOpen }"
        :aria-hidden="!isDesktop && !mobileNavigationOpen"
        :inert="!isDesktop && !mobileNavigationOpen ? true : undefined"
        @keydown="handleNavigationKeydown"
      >
        <div class="drawer-header">
          <div>
            <span class="drawer-eyebrow">项目导航</span>
            <strong>{{ currentRouteTitle }}</strong>
          </div>
          <button
            ref="navigationCloseRef"
            class="navigation-close"
            type="button"
            aria-label="关闭项目导航"
            @click="closeMobileNavigation()"
          >
            <el-icon aria-hidden="true"><Close /></el-icon>
          </button>
        </div>

        <section
          class="project-summary"
          aria-labelledby="project-summary-title"
          :aria-busy="!workflowStatusLoaded"
        >
          <span id="project-summary-title" class="project-summary-eyebrow">当前项目</span>
          <strong class="project-name" :title="name || '项目加载中'">
            {{ name || "项目加载中" }}
          </strong>
          <span class="project-id">项目 ID · {{ id || "读取中" }}</span>
          <div class="summary-status">
            <el-tag :type="workflowStageTagType" effect="plain">
              {{ workflowStageLabel }}
            </el-tag>
            <span>已完成 {{ completedOperations.length }} 项</span>
            <el-tag v-if="staleOperations.length" type="warning" size="small">
              已过期 {{ staleOperations.length }} 项
            </el-tag>
          </div>
        </section>

        <nav aria-label="项目工作区导航">
          <el-menu
            :default-active="route.path"
            :default-openeds="['analysis', 'manual']"
            class="workspace-menu"
            router
            @select="handleNavigationSelect"
          >
            <el-sub-menu index="analysis">
              <template #title>
                <el-icon><DataAnalysis /></el-icon>
                <span>业务分析与测试规划</span>
              </template>
              <el-menu-item-group title="规划工作流">
                <el-menu-item index="/plan" :disabled="!isWorkflowRouteAllowed('/plan')"
                  :aria-current="route.path === '/plan' ? 'page' : undefined"
                  :data-navigation-state="navigationState('/plan', 'project_analysis')"
                >
                  <el-icon><Notebook /></el-icon>
                  <span>测试计划</span>
                  <el-tag
                    class="nav-state"
                    size="small"
                    :type="navigationTagType('/plan', 'project_analysis')"
                  >{{ navigationStateLabel('/plan', 'project_analysis') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/menu" :disabled="!isWorkflowRouteAllowed('/menu')"
                  :aria-current="route.path === '/menu' ? 'page' : undefined"
                  :data-navigation-state="navigationState('/menu', 'project_analysis')"
                >
                  <el-icon><Menu /></el-icon>
                  <span>测试菜单</span>
                  <el-tag
                    class="nav-state"
                    size="small"
                    :type="navigationTagType('/menu', 'project_analysis')"
                  >{{ navigationStateLabel('/menu', 'project_analysis') }}</el-tag>
                </el-menu-item>
              </el-menu-item-group>
            </el-sub-menu>

            <el-sub-menu index="manual">
              <template #title>
                <el-icon><HelpFilled /></el-icon>
                <span>八种测试工作区</span>
                <el-icon v-if="!hasEnabledTestRoute" class="lock-icon"><Lock /></el-icon>
              </template>
              <el-menu-item-group
                :title="hasEnabledTestRoute ? '当前项目已启用的测试类型' : '请先完成业务分析、测试计划和测试菜单'"
              >
                <el-menu-item index="/unit" :disabled="!isWorkflowRouteAllowed('/unit')"
                  :aria-current="route.path === '/unit' ? 'page' : undefined"
                  :data-navigation-state="navigationState('/unit', 'unit_case')"
                >
                  <el-icon><CollectionTag /></el-icon><span>单元测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/unit', 'unit_case')">{{ navigationStateLabel('/unit', 'unit_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/integration" :disabled="!isWorkflowRouteAllowed('/integration')"
                  :aria-current="route.path === '/integration' ? 'page' : undefined"
                  :data-navigation-state="navigationState('/integration', 'integration_case')"
                >
                  <el-icon><Files /></el-icon><span>集成测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/integration', 'integration_case')">{{ navigationStateLabel('/integration', 'integration_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/api" :disabled="!isWorkflowRouteAllowed('/api')"
                  :aria-current="route.path === '/api' ? 'page' : undefined"
                  :data-navigation-state="navigationState('/api', 'api_case')"
                >
                  <el-icon><Magnet /></el-icon><span>API 接口测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/api', 'api_case')">{{ navigationStateLabel('/api', 'api_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/ui" :disabled="!isWorkflowRouteAllowed('/ui')"
                  :aria-current="route.path === '/ui' ? 'page' : undefined"
                  :data-navigation-state="navigationState('/ui', 'ui_case')"
                >
                  <el-icon><Monitor /></el-icon><span>前端 UI 测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/ui', 'ui_case')">{{ navigationStateLabel('/ui', 'ui_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/database" :disabled="!isWorkflowRouteAllowed('/database')"
                  :aria-current="route.path === '/database' ? 'page' : undefined"
                  :data-navigation-state="navigationState('/database', 'db_case')"
                >
                  <el-icon><MessageBox /></el-icon><span>数据库测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/database', 'db_case')">{{ navigationStateLabel('/database', 'db_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/functional" :disabled="!isWorkflowRouteAllowed('/functional')"
                  :aria-current="route.path === '/functional' ? 'page' : undefined"
                  :data-navigation-state="navigationState('/functional', 'functional_case')"
                >
                  <el-icon><Orange /></el-icon><span>系统功能性测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/functional', 'functional_case')">{{ navigationStateLabel('/functional', 'functional_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/nfunctional" :disabled="!isWorkflowRouteAllowed('/nfunctional')"
                  :aria-current="route.path === '/nfunctional' ? 'page' : undefined"
                  :data-navigation-state="navigationState('/nfunctional', 'nonfunctional_case')"
                >
                  <el-icon><HelpFilled /></el-icon><span>系统非功能性测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/nfunctional', 'nonfunctional_case')">{{ navigationStateLabel('/nfunctional', 'nonfunctional_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/acceptance" :disabled="!isWorkflowRouteAllowed('/acceptance')"
                  :aria-current="route.path === '/acceptance' ? 'page' : undefined"
                  :data-navigation-state="navigationState('/acceptance', 'acceptance_case')"
                >
                  <el-icon><Box /></el-icon><span>验收测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/acceptance', 'acceptance_case')">{{ navigationStateLabel('/acceptance', 'acceptance_case') }}</el-tag>
                </el-menu-item>
              </el-menu-item-group>
            </el-sub-menu>

            <el-menu-item-group title="Agent 编排">
              <el-menu-item
                index="/agent"
                :disabled="!agentRouteReady"
                :aria-current="route.path === '/agent' ? 'page' : undefined"
              >
                <el-icon><DataAnalysis /></el-icon>
                <span>Agent 编排</span>
                <el-tag class="nav-state" size="small" :type="agentRouteReady ? 'primary' : 'info'">
                  {{ agentRouteReady ? "可进入" : "资料未完成" }}
                </el-tag>
              </el-menu-item>
            </el-menu-item-group>

            <el-menu-item-group title="平台说明">
              <el-menu-item index="guide" disabled>
                <el-icon><Reading /></el-icon>
                <span>如何正确使用本平台</span>
              </el-menu-item>
            </el-menu-item-group>

            <el-menu-item-group title="项目操作">
              <el-menu-item index="/create">
                <el-icon><Platform /></el-icon><span>创建新项目</span>
              </el-menu-item>
              <el-menu-item index="/">
                <el-icon><HomeFilled /></el-icon><span>返回开始界面</span>
              </el-menu-item>
            </el-menu-item-group>
          </el-menu>
        </nav>
      </aside>

      <main id="workspace-main" ref="workspaceMainRef" class="workspace-main" tabindex="-1">
        <div class="workspace-content ez-content ez-content--wide">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<script lang="ts" setup>
import {
  computed,
  getCurrentInstance,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { ElMessage } from "@/plugins/elementPlus";
import axios from "axios";
import { useRoute, useRouter } from "vue-router";
import { ROUTE_PRESENTATION } from "@/config/routePresentation";
import workbenchLogo from "@/assets/static/image/ezlogo-workbench-v2.png";
import {
  analysisMenu,
  completedOperations,
  getWorkflowRedirectPath,
  isWorkflowRouteAllowed,
  loadProjectWorkflowStatus,
  projectAnalysisRegenerating,
  projectWorkflowStatus,
  staleOperations,
  workflowRedirectMessage,
  workflowStatusLoaded,
} from "@/state/projectAnalysis";

const instance = getCurrentInstance();
const route = useRoute();
const router = useRouter();
const id = ref("");
const name = ref("");
type NavigationState =
  | "loading"
  | "completed"
  | "current"
  | "locked"
  | "stale"
  | "available"
  | "regenerating";
type TagType = "primary" | "success" | "warning" | "info" | "danger";

const testRoutes = [
  "/unit",
  "/integration",
  "/api",
  "/ui",
  "/database",
  "/functional",
  "/nfunctional",
  "/acceptance",
];

const desktopMedia = window.matchMedia("(min-width: 1024px)");
const isDesktop = ref(desktopMedia.matches);
const mobileNavigationOpen = ref(false);
const navigationToggleRef = ref<HTMLButtonElement | null>(null);
const navigationCloseRef = ref<HTMLButtonElement | null>(null);
const navigationPanelRef = ref<HTMLElement | null>(null);
const workspaceMainRef = ref<HTMLElement | null>(null);

const currentRouteTitle = computed(
  () => ROUTE_PRESENTATION[route.path]?.title || "项目工作区"
);
const hasEnabledTestRoute = computed(() =>
  testRoutes.some((path) => isWorkflowRouteAllowed(path))
);
const agentRouteReady = computed(
  () => workflowStatusLoaded.value && projectWorkflowStatus.value?.stage !== "setup_required"
);
const workflowStageLabel = computed(() => {
  if (!workflowStatusLoaded.value) return "状态加载中";
  if (projectAnalysisRegenerating.value) return "测试计划重新生成中";
  const labels = {
    setup_required: "资料待确认",
    analysis_required: "分析待完成",
    analysis_ready: "分析已就绪",
    testing_in_progress: "测试进行中",
    testing_ready: "测试已就绪",
  };
  const stage = projectWorkflowStatus.value?.stage;
  return stage ? labels[stage] : "状态加载中";
});
const workflowStageTagType = computed<TagType>(() => {
  if (!workflowStatusLoaded.value) return "info";
  if (projectAnalysisRegenerating.value) return "warning";
  const stage = projectWorkflowStatus.value?.stage;
  if (stage === "testing_ready") return "success";
  if (stage === "testing_in_progress" || stage === "analysis_ready") return "primary";
  return "warning";
});

const operationIsStale = (operation: string): boolean => {
  if (operation === "project_analysis") {
    return staleOperations.value.includes(operation);
  }
  const family = operation.replace(/_case$/, "");
  return staleOperations.value.some(
    (item) => item === operation || item.startsWith(`${family}_`)
  );
};

const navigationState = (path: string, operation: string): NavigationState => {
  if (!workflowStatusLoaded.value) return "loading";
  if (projectAnalysisRegenerating.value && path !== "/plan") return "regenerating";
  if (operationIsStale(operation)) return "stale";
  if (!isWorkflowRouteAllowed(path)) return "locked";
  if (route.path === path) return "current";
  if (testRoutes.includes(path)) return "available";
  if (completedOperations.value.includes(operation)) return "completed";
  return "available";
};

const navigationStateLabel = (path: string, operation: string): string => {
  const labels: Record<NavigationState, string> = {
    loading: "加载中",
    completed: "已完成",
    current: "当前",
    locked: "已锁定",
    stale: "已过期",
    available: "可进入",
    regenerating: "分析中",
  };
  return labels[navigationState(path, operation)];
};

const navigationTagType = (path: string, operation: string): TagType => {
  const types: Record<NavigationState, TagType> = {
    loading: "info",
    completed: "success",
    current: "primary",
    locked: "info",
    stale: "warning",
    available: "info",
    regenerating: "warning",
  };
  return types[navigationState(path, operation)];
};

const openMobileNavigation = async () => {
  if (isDesktop.value) return;
  mobileNavigationOpen.value = true;
  await nextTick();
  navigationCloseRef.value?.focus();
};

const closeMobileNavigation = async (restoreFocus = true) => {
  if (!mobileNavigationOpen.value) return;
  mobileNavigationOpen.value = false;
  await nextTick();
  if (restoreFocus) navigationToggleRef.value?.focus();
};

const visibleDrawerFocusTargets = (): HTMLElement[] => {
  if (!navigationPanelRef.value) return [];
  const targets = Array.from(
    navigationPanelRef.value.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), [role="menuitem"]:not(.is-disabled), [tabindex]:not([tabindex="-1"])'
    )
  );
  return Array.from(new Set(targets)).filter((target) => {
    const styles = window.getComputedStyle(target);
    return styles.display !== "none" && styles.visibility !== "hidden";
  });
};

const handleNavigationKeydown = (event: KeyboardEvent) => {
  if (isDesktop.value || !mobileNavigationOpen.value) return;
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    void closeMobileNavigation();
    return;
  }
  if (event.key !== "Tab") return;

  const targets = visibleDrawerFocusTargets();
  if (!targets.length) {
    event.preventDefault();
    return;
  }
  const activeIndex = targets.indexOf(document.activeElement as HTMLElement);
  const offset = event.shiftKey ? -1 : 1;
  const nextIndex =
    activeIndex < 0
      ? 0
      : (activeIndex + offset + targets.length) % targets.length;
  event.preventDefault();
  targets[nextIndex].focus();
};

const handleNavigationSelect = async () => {
  if (isDesktop.value) return;
  mobileNavigationOpen.value = false;
  await nextTick();
  workspaceMainRef.value?.focus();
};

const handleBreakpointChange = (event: MediaQueryListEvent) => {
  isDesktop.value = event.matches;
  if (event.matches) {
    mobileNavigationOpen.value = false;
    document.body.classList.remove("ez-navigation-open");
  }
};

watch(
  [mobileNavigationOpen, isDesktop],
  () => {
    document.body.classList.toggle(
      "ez-navigation-open",
      mobileNavigationOpen.value && !isDesktop.value
    );
  },
  { flush: "post" }
);

watch(() => route.path, async () => {
  if (isDesktop.value || !mobileNavigationOpen.value) return;
  mobileNavigationOpen.value = false;
  await nextTick();
  workspaceMainRef.value?.focus();
});

if (instance === null) {
  ElMessage({ message: "平台出现了一些问题,无法获取关键信息", type: "error" });
}
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");

const initializeProject = async () => {
  const projectId = instance?.appContext.config.globalProperties.$id;
  if (!projectId) {
    ElMessage({ message: "请先通过项目 ID 进行登录", type: "error" });
    await router.replace("/");
    return;
  }

  id.value = String(projectId);
  try {
    const [projectResponse, workflowStatus] = await Promise.all([
      axios.get(`${requestUrl}/project/login/${id.value}`),
      loadProjectWorkflowStatus(requestUrl, id.value),
    ]);
    name.value = String(projectResponse.data?.data || "");
    if (instance) {
      instance.appContext.config.globalProperties.$test_menu = analysisMenu.value;
    }
    if (route.path === "/agent" && !agentRouteReady.value) {
      ElMessage({ message: "请先完成项目资料配置", type: "warning" });
      await router.replace("/create");
    } else if (route.path !== "/agent" && !isWorkflowRouteAllowed(route.path)) {
      ElMessage({ message: workflowStatus.message, type: "warning" });
      const redirect = getWorkflowRedirectPath();
      if (redirect !== route.path) await router.replace(redirect);
    } else if (workflowRedirectMessage.value) {
      ElMessage({ message: workflowRedirectMessage.value, type: "warning" });
      workflowRedirectMessage.value = "";
    }
  } catch (caught) {
    ElMessage({
      message: caught instanceof Error ? caught.message : "项目分析状态获取失败",
      type: "warning",
    });
    if (route.path !== "/plan") await router.replace("/plan");
  }
};

onMounted(() => {
  desktopMedia.addEventListener("change", handleBreakpointChange);
  void initializeProject();
});

onBeforeUnmount(() => {
  desktopMedia.removeEventListener("change", handleBreakpointChange);
  document.body.classList.remove("ez-navigation-open");
});
</script>

<style scoped>
.workspace-shell {
  min-height: 100dvh;
  color: var(--ez-color-text-primary);
  background: var(--ez-color-canvas);
  overflow-x: clip;
}

.skip-link {
  position: fixed;
  top: var(--ez-space-3);
  left: var(--ez-space-4);
  z-index: calc(var(--ez-z-overlay) + 1);
  padding: var(--ez-space-2) var(--ez-space-3);
  color: var(--ez-color-surface);
  background: var(--ez-color-brand-700);
  border-radius: var(--ez-radius-small);
  box-shadow: var(--ez-shadow-medium);
  transform: translateY(calc(-100% - var(--ez-space-6)));
  transition: transform var(--ez-motion-fast) var(--ez-motion-easing);
}

.skip-link:focus {
  transform: translateY(0);
}

.workspace-header {
  position: sticky;
  top: 0;
  z-index: var(--ez-z-sticky);
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--ez-space-3);
  height: var(--ez-shell-header-height);
  min-width: 0;
  padding: 0 var(--ez-page-gutter);
  background: var(--ez-color-surface);
  border-bottom: 1px solid var(--ez-color-border);
  box-shadow: var(--ez-shadow-small);
}

.header-brand,
.route-context,
.header-status {
  min-width: 0;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: var(--ez-space-2);
}

.navigation-toggle,
.navigation-close {
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
  width: 40px;
  height: 40px;
  padding: 0;
  color: var(--ez-color-text-primary);
  background: var(--ez-color-surface);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
  cursor: pointer;
  transition:
    color var(--ez-motion-fast) var(--ez-motion-easing),
    border-color var(--ez-motion-fast) var(--ez-motion-easing),
    background-color var(--ez-motion-fast) var(--ez-motion-easing);
}

.navigation-toggle:hover,
.navigation-close:hover {
  color: var(--ez-color-brand-700);
  background: var(--ez-color-brand-50);
  border-color: var(--ez-color-brand-300);
}

.brand-logo {
  width: 38px;
  height: 38px;
  object-fit: contain;
}

.brand-wordmark {
  color: var(--ez-color-brand-700);
  font-family: var(--ez-font-brand);
  font-size: var(--ez-font-size-20);
  line-height: 1;
  white-space: nowrap;
}

.route-context {
  padding-left: var(--ez-space-3);
  border-left: 1px solid var(--ez-color-border);
}

.route-eyebrow,
.drawer-eyebrow,
.project-summary-eyebrow {
  display: block;
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
  line-height: 1.25;
}

.route-context h1 {
  margin: 2px 0 0;
  overflow: hidden;
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-16);
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-status {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--ez-space-2);
}

.header-project-name {
  display: none;
  max-width: 240px;
  overflow: hidden;
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lifecycle-chip {
  display: inline-flex;
  align-items: center;
  max-width: 180px;
  min-height: 28px;
  padding: 3px var(--ez-space-2);
  overflow: hidden;
  color: var(--ez-color-brand-700);
  font-size: var(--ez-font-size-12);
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: var(--ez-color-brand-50);
  border: 1px solid var(--ez-color-brand-100);
  border-radius: var(--ez-radius-pill);
}

.lifecycle-chip[data-status-loaded="false"] {
  color: var(--ez-color-text-muted);
  background: var(--ez-color-locked-bg);
  border-color: var(--ez-color-border);
}

.workspace-body,
.workspace-main,
.workspace-content {
  min-width: 0;
}

.workspace-body {
  min-height: calc(100dvh - var(--ez-shell-header-height));
}

.navigation-backdrop {
  position: fixed;
  inset: 0;
  z-index: calc(var(--ez-z-overlay) - 1);
  width: 100%;
  height: 100%;
  padding: 0;
  background: rgba(23, 33, 27, 0.44);
  border: 0;
  cursor: pointer;
}

.workspace-aside {
  min-width: 0;
  color: var(--ez-color-text-primary);
  background: var(--ez-color-surface);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: var(--ez-shell-header-height);
  padding: var(--ez-space-3) var(--ez-space-4);
  border-bottom: 1px solid var(--ez-color-border);
}

.drawer-header strong {
  display: block;
  margin-top: 2px;
  font-size: var(--ez-font-size-16);
  line-height: 1.3;
}

.project-summary {
  margin: var(--ez-space-4);
  padding: var(--ez-space-4);
  background: var(--ez-color-surface-subtle);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-large);
  box-shadow: var(--ez-shadow-small);
}

.project-name {
  display: block;
  min-width: 0;
  margin-top: var(--ez-space-1);
  overflow: hidden;
  font-size: var(--ez-font-size-16);
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-id {
  display: block;
  min-width: 0;
  margin-top: var(--ez-space-1);
  color: var(--ez-color-text-muted);
  font-family: var(--ez-font-code);
  font-size: var(--ez-font-size-12);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.summary-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ez-space-2);
  margin-top: var(--ez-space-3);
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-12);
}

.lock-icon {
  margin-left: auto;
}

.nav-state {
  flex: 0 0 auto;
  margin-left: auto;
}

:deep(.workspace-menu) {
  min-width: 0;
  background: transparent;
  border-right: 0;
}

:deep(.workspace-menu .el-sub-menu__title),
:deep(.workspace-menu .el-menu-item) {
  min-width: 0;
}

:deep(.workspace-menu .el-menu-item > span:not(.el-tag)) {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.workspace-menu .el-menu-item.is-active) {
  color: var(--ez-color-brand-700);
  background: var(--ez-color-brand-50);
  box-shadow: inset 3px 0 0 var(--ez-color-brand-500);
}

:deep(.workspace-menu .el-menu-item.is-disabled) {
  color: var(--ez-color-text-muted);
}

.workspace-main {
  width: 100%;
  padding: var(--ez-page-gutter);
  overflow-x: clip;
  outline-offset: calc(-1 * var(--ez-focus-offset));
}

.workspace-content {
  width: 100%;
  max-width: var(--ez-content-wide);
  margin-inline: auto;
}

.workspace-content :deep(.el-row),
.workspace-content :deep(.el-col),
.workspace-content :deep(.el-card),
.workspace-content :deep(.el-select),
.workspace-content :deep(.el-segmented) {
  min-width: 0 !important;
  max-width: 100%;
}

.workspace-content :deep(.el-segmented) {
  overflow-x: auto;
}

:global(body.ez-navigation-open) {
  overflow: hidden;
}

@media (max-width: 1023px) {
  .workspace-aside {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: var(--ez-z-overlay);
    width: min(var(--ez-shell-drawer-width), calc(100vw - 48px));
    height: 100dvh;
    overflow-y: auto;
    border-right: 1px solid var(--ez-color-border);
    box-shadow: var(--ez-shadow-large);
    visibility: hidden;
    pointer-events: none;
    transform: translateX(-100%);
    transition:
      transform var(--ez-motion-normal) var(--ez-motion-easing),
      visibility 0s linear var(--ez-motion-normal);
  }

  .workspace-aside.is-open {
    visibility: visible;
    pointer-events: auto;
    transform: translateX(0);
    transition-delay: 0s;
  }
}

@media (min-width: 480px) {
  .header-project-name {
    display: block;
    max-width: 160px;
  }
}

@media (min-width: 768px) {
  .workspace-header,
  .workspace-main {
    padding-right: var(--ez-page-gutter-tablet);
    padding-left: var(--ez-page-gutter-tablet);
  }

  .header-project-name {
    max-width: 240px;
  }
}

@media (min-width: 1024px) {
  .workspace-header,
  .workspace-main {
    padding-right: var(--ez-page-gutter-desktop);
    padding-left: var(--ez-page-gutter-desktop);
  }

  .navigation-toggle,
  .drawer-header,
  .navigation-backdrop {
    display: none;
  }

  .workspace-body {
    display: grid;
    grid-template-columns: var(--ez-shell-sidebar-width) minmax(0, 1fr);
    align-items: start;
  }

  .workspace-aside {
    position: sticky;
    top: var(--ez-shell-header-height);
    z-index: var(--ez-z-raised);
    width: var(--ez-shell-sidebar-width);
    height: calc(100dvh - var(--ez-shell-header-height));
    overflow-y: auto;
    border-right: 1px solid var(--ez-color-border);
    visibility: visible;
    pointer-events: auto;
    transform: none;
  }

  .project-summary {
    margin-top: var(--ez-space-6);
  }

  .workspace-main {
    min-height: calc(100dvh - var(--ez-shell-header-height));
  }
}

@media (min-width: 1440px) {
  .workspace-header,
  .workspace-main {
    padding-right: var(--ez-page-gutter-wide);
    padding-left: var(--ez-page-gutter-wide);
  }
}

@media (min-width: 1920px) {
  .workspace-header,
  .workspace-main {
    padding-right: var(--ez-page-gutter-ultrawide);
    padding-left: var(--ez-page-gutter-ultrawide);
  }
}

@media (max-width: 479px) {
  .brand-wordmark,
  .header-project-name,
  .route-eyebrow {
    display: none;
  }

  .workspace-header {
    gap: var(--ez-space-2);
  }

  .route-context {
    padding-left: var(--ez-space-2);
  }

  .lifecycle-chip {
    max-width: 92px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .workspace-aside,
  .skip-link,
  .navigation-toggle,
  .navigation-close {
    transition: none;
  }
}
</style>
