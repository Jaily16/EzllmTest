<template>
  <div class="common-layout">
    <el-container>
      <el-header style="position: sticky; top: 0; z-index: 999">
        <el-image
          style="width: 50px; height: 50px; margin-top: 5px"
          :src="require('@/assets/static/image/ezlogo.png')"
          fit="fill"
        />
        <div class="en_name">EzllmTest</div>
      </el-header>
      <el-container>
        <el-aside width="280px">
          <el-row style="text-align: center">
            <div class="info" style="margin-left: 5px">项目名称: {{ name }}</div>
          </el-row>
          <el-row style="text-align: center">
            <div class="info" style="margin-left: 5px">项目id: {{ id }}</div>
          </el-row>
          <el-row v-if="workflowStatusLoaded" class="workflow-summary">
            <el-tag :type="workflowStageTagType" effect="plain">
              {{ workflowStageLabel }}
            </el-tag>
            <span>已完成 {{ completedOperations.length }} 项</span>
            <el-tag v-if="staleOperations.length" type="danger" size="small">
              已过期 {{ staleOperations.length }} 项
            </el-tag>
          </el-row>
          <el-menu :default-active="route.path" class="el-menu-vertical-demo" router>
            <el-sub-menu index="analysis">
              <template #title>
                <el-icon><DataAnalysis /></el-icon>
                <span>LLM智能测试分析</span>
              </template>
              <el-menu-item-group title="业务分析与测试规划">
                <el-menu-item index="/plan" :disabled="!isWorkflowRouteAllowed('/plan')">
                  <el-icon><Notebook /></el-icon>
                  <span>测试计划</span>
                  <el-tag
                    class="nav-state"
                    size="small"
                    :type="navigationTagType('/plan', 'project_analysis')"
                  >{{ navigationStateLabel('/plan', 'project_analysis') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/menu" :disabled="!isWorkflowRouteAllowed('/menu')">
                  <el-icon><Menu /></el-icon>
                  <span>测试菜单</span>
                  <el-tag
                    class="nav-state"
                    size="small"
                    :type="navigationTagType('/menu', 'project_analysis')"
                  >{{ navigationStateLabel('/menu', 'project_analysis') }}</el-tag>
                </el-menu-item>
              </el-menu-item-group>
              <el-menu-item-group title="如何正确使用本平台">
                <el-menu-item index="guide" disabled>
                  <el-icon><Reading /></el-icon>
                  <span>平台说明</span>
                </el-menu-item>
              </el-menu-item-group>
            </el-sub-menu>

            <el-sub-menu index="manual">
              <template #title>
                <el-icon><HelpFilled /></el-icon>
                <span>手动选择LLM测试类型</span>
                <el-icon v-if="!hasEnabledTestRoute" class="lock-icon"><Lock /></el-icon>
              </template>
              <el-menu-item-group
                :title="hasEnabledTestRoute ? '当前项目已启用的测试类型' : '请先完成业务分析、测试计划和测试菜单'"
              >
                <el-menu-item index="/unit" :disabled="!isWorkflowRouteAllowed('/unit')">
                  <el-icon><CollectionTag /></el-icon><span>单元测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/unit', 'unit_case')">{{ navigationStateLabel('/unit', 'unit_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/integration" :disabled="!isWorkflowRouteAllowed('/integration')">
                  <el-icon><Files /></el-icon><span>集成测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/integration', 'integration_case')">{{ navigationStateLabel('/integration', 'integration_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/api" :disabled="!isWorkflowRouteAllowed('/api')">
                  <el-icon><Magnet /></el-icon><span>api接口测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/api', 'api_case')">{{ navigationStateLabel('/api', 'api_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/ui" :disabled="!isWorkflowRouteAllowed('/ui')">
                  <el-icon><Monitor /></el-icon><span>前端UI测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/ui', 'ui_case')">{{ navigationStateLabel('/ui', 'ui_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/database" :disabled="!isWorkflowRouteAllowed('/database')">
                  <el-icon><MessageBox /></el-icon><span>数据库测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/database', 'db_case')">{{ navigationStateLabel('/database', 'db_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/functional" :disabled="!isWorkflowRouteAllowed('/functional')">
                  <el-icon><Orange /></el-icon><span>系统功能性测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/functional', 'functional_case')">{{ navigationStateLabel('/functional', 'functional_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/nfunctional" :disabled="!isWorkflowRouteAllowed('/nfunctional')">
                  <el-icon><HelpFilled /></el-icon><span>系统非功能性测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/nfunctional', 'nonfunctional_case')">{{ navigationStateLabel('/nfunctional', 'nonfunctional_case') }}</el-tag>
                </el-menu-item>
                <el-menu-item index="/acceptance" :disabled="!isWorkflowRouteAllowed('/acceptance')">
                  <el-icon><Box /></el-icon><span>验收测试</span>
                  <el-tag class="nav-state" size="small" :type="navigationTagType('/acceptance', 'acceptance_case')">{{ navigationStateLabel('/acceptance', 'acceptance_case') }}</el-tag>
                </el-menu-item>
              </el-menu-item-group>
            </el-sub-menu>

            <el-menu-item index="/create">
              <el-icon><Platform /></el-icon><span>创建新项目</span>
            </el-menu-item>
            <el-menu-item index="/">
              <el-icon><HomeFilled /></el-icon><span>返回开始界面</span>
            </el-menu-item>
          </el-menu>
        </el-aside>
        <el-main><router-view /></el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import axios from "axios";
import { useRoute, useRouter } from "vue-router";
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
type NavigationState = "completed" | "current" | "locked" | "stale" | "available" | "regenerating";
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
const hasEnabledTestRoute = computed(() =>
  testRoutes.some((path) => isWorkflowRouteAllowed(path))
);
const workflowStageLabel = computed(() => {
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
    completed: "success",
    current: "primary",
    locked: "info",
    stale: "danger",
    available: "warning",
    regenerating: "warning",
  };
  return types[navigationState(path, operation)];
};

if (instance === null) {
  ElMessage({ message: "平台出现了一些问题,无法获取关键信息", type: "error" });
}
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");

const initializeProject = async () => {
  const projectId = instance?.appContext.config.globalProperties.$id;
  if (!projectId) {
    ElMessage({ message: "请先通过项目id进行登录", type: "error" });
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
    if (!isWorkflowRouteAllowed(route.path)) {
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

onMounted(initializeProject);
</script>

<style scoped>
.el-menu-vertical-demo {
  font-family: "Ali";
}
.info {
  font-family: "Ali";
  font-size: 15px;
  margin-top: 10px;
}
.el-header {
  background-color: #d1ffd3;
  display: flex;
}
.en_name {
  position: absolute;
  font-family: "Quantify";
  font-size: 40px;
  margin-top: 10px;
  margin-left: -60px;
  left: 50%;
}
.lock-icon {
  margin-left: auto;
}
.workflow-summary {
  align-items: center;
  gap: 8px;
  margin: 10px 5px;
  font-family: "Ali";
  font-size: 13px;
}
.nav-state {
  margin-left: auto;
}
</style>
