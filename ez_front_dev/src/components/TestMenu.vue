<template>
  <div class="planning-menu">
    <WorkspacePageHeader
      eyebrow="PLANNING COCKPIT"
      title="测试菜单工作台"
      description="查看八类测试工作区的推荐、可进入和资料版本状态。推荐状态不代表测试已完成。"
    >
      <template #actions>
        <el-button @click="router.push('/plan')">返回测试计划</el-button>
      </template>
    </WorkspacePageHeader>

    <FeedbackState
      v-if="loading"
      kind="loading"
      title="正在读取测试菜单"
      description="只读取当前项目的已保存状态，不会自动调用模型。"
      skeleton="cards"
      busy
    />

    <FeedbackState
      v-else-if="loadError"
      kind="error"
      title="测试菜单读取失败"
      :description="loadError"
    >
      <template #actions>
        <el-button type="primary" @click="loadMenuStatus">重新读取</el-button>
      </template>
    </FeedbackState>

    <FeedbackState
      v-else-if="!analysisReady || !analysisMenu"
      kind="empty"
      title="尚未生成测试菜单"
      description="请先在测试计划页显式生成并保存业务摘要、测试计划和推荐类型。"
    >
      <template #actions>
        <el-button type="primary" @click="router.push('/plan')">前往测试计划</el-button>
      </template>
    </FeedbackState>

    <template v-else>
      <p class="ez-sr-only" role="status" aria-live="polite" aria-atomic="true">
        {{ menuStatusAnnouncement }}
      </p>
      <WorkspaceSection
        title="规划概览"
        description="这些信息来自服务器保存的项目状态；打开本页不会发起模型请求。"
      >
        <dl class="planning-overview">
          <div>
            <dt>资料版本</dt>
            <dd>{{ sourceRevision || "未提供版本标识" }}</dd>
          </div>
          <div>
            <dt>推荐类型</dt>
            <dd>{{ recommendedCount }} / 8</dd>
          </div>
          <div>
            <dt>当前可进入</dt>
            <dd>{{ availableCount }} / 8</dd>
          </div>
          <div>
            <dt>已过期</dt>
            <dd>{{ staleCount }} / 8</dd>
          </div>
        </dl>
        <p class="planning-overview__note">
          推荐状态不代表测试已完成；即使存在已保存结果，卡片主状态仍保持“可进入”。
        </p>
      </WorkspaceSection>

      <WorkspaceSection
        title="八类测试工作区"
        :description="projectAnalysisRegenerating
          ? '测试计划正在重新生成，所有工作区暂时锁定；上一版结果仍可阅读。'
          : '未推荐的类型仍会完整展示，并说明当前不能进入的原因。'"
        :busy="projectAnalysisRegenerating"
      >
        <div class="workspace-grid">
          <TestWorkspaceCard
            v-for="item in dashboardItems"
            :key="item.key"
            :item="item"
          />
        </div>
      </WorkspaceSection>
    </template>
  </div>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import FeedbackState from "@/components/workspace/FeedbackState.vue";
import WorkspacePageHeader from "@/components/workspace/WorkspacePageHeader.vue";
import WorkspaceSection from "@/components/workspace/WorkspaceSection.vue";
import TestWorkspaceCard from "@/components/planning/TestWorkspaceCard.vue";
import {
  TEST_WORKSPACES,
  type TestWorkspaceCardViewModel,
  type TestWorkspaceDefinition,
} from "@/config/testWorkspaces";
import {
  analysisMenu,
  analysisReady,
  isWorkflowRouteAllowed,
  loadProjectWorkflowStatus,
  projectAnalysisRegenerating,
  projectWorkflowStatus,
  staleOperations,
  workflowStatusLoaded,
} from "@/state/projectAnalysis";

const router = useRouter();
const instance = getCurrentInstance();
const loading = ref(true);
const loadError = ref("");
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");
const sourceRevision = computed(() => projectWorkflowStatus.value?.source_revision || "");

type TestTypeStatus = "available" | "locked" | "stale";
const testTypeStatusLabels: Record<TestTypeStatus, string> = {
  available: "可进入",
  locked: "已锁定",
  stale: "已过期",
};

const statusForTestType = (type: { link: string }): TestTypeStatus => {
  if (!isWorkflowRouteAllowed(type.link)) return "locked";
  return "available";
};

const operationIsStale = (operation: string): boolean => {
  const family = operation.replace(/_case$/, "");
  return staleOperations.value.some(
    (item) => item === operation || item.startsWith(`${family}_`)
  );
};

const cardFor = (definition: TestWorkspaceDefinition): TestWorkspaceCardViewModel => {
  const recommended = Boolean(analysisMenu.value?.[definition.key]);
  const hasSavedResult = projectWorkflowStatus.value?.completed_operations.includes(
    definition.terminalOperation
  ) === true;

  if (projectAnalysisRegenerating.value) {
    return {
      ...definition,
      status: "regenerating",
      statusLabel: "分析中",
      reason: "测试计划正在重新生成，工作区会在服务器状态刷新后重新开放。",
      progressHint: hasSavedResult ? "上一份已保存结果仍会保留。" : "当前没有可恢复结果。",
      disabled: true,
    };
  }
  if (!recommended) {
    return {
      ...definition,
      status: "not-recommended",
      statusLabel: "未推荐",
      reason: "当前测试计划未推荐此类型；重新生成计划后推荐范围可能变化。",
      progressHint: "如需开展此类测试，请先重新生成并确认测试计划。",
      disabled: true,
    };
  }
  if (operationIsStale(definition.terminalOperation)) {
    return {
      ...definition,
      status: "stale",
      statusLabel: testTypeStatusLabels.stale,
      reason: "业务资料版本已变化，进入前需要按服务器状态重新生成相关结果。",
      progressHint: hasSavedResult ? "上一份结果可供参考，但不再代表当前资料。" : "当前没有有效结果。",
      disabled: !isWorkflowRouteAllowed(definition.route),
    };
  }
  if (statusForTestType({ link: definition.route }) === "locked") {
    return {
      ...definition,
      status: "locked",
      statusLabel: testTypeStatusLabels.locked,
      reason: "当前项目生命周期尚未开放此工作区。",
      progressHint: hasSavedResult ? "服务器记录了历史结果，待工作区开放后可恢复。" : "请先完成前置步骤。",
      disabled: true,
    };
  }
  return {
    ...definition,
    status: "available",
    statusLabel: testTypeStatusLabels.available,
    reason: "当前测试计划推荐此类型，且项目生命周期允许进入。",
    progressHint: hasSavedResult
      ? "已有可恢复结果；进入后可查看或重新生成。"
      : "尚无可恢复的最终结果。",
    disabled: false,
  };
};

const dashboardItems = computed(() => TEST_WORKSPACES.map(cardFor));
const recommendedCount = computed(() =>
  TEST_WORKSPACES.filter((item) => Boolean(analysisMenu.value?.[item.key])).length
);
const availableCount = computed(() =>
  dashboardItems.value.filter((item) => item.status === "available").length
);
const staleCount = computed(() =>
  dashboardItems.value.filter((item) => item.status === "stale").length
);
const menuStatusAnnouncement = computed(() => {
  const count = (status: TestWorkspaceCardViewModel["status"]) =>
    dashboardItems.value.filter((item) => item.status === status).length;
  const lockedOrRunning = count("locked") + count("regenerating");
  return `共 8 类工作区：${count("available")} 类可进入，${count("not-recommended")} 类未推荐，${count("stale")} 类已过期，${lockedOrRunning} 类已锁定或分析中`;
});

const loadMenuStatus = async () => {
  loading.value = true;
  loadError.value = "";
  try {
    if (!workflowStatusLoaded.value || projectWorkflowStatus.value?.pid !== projectId) {
      await loadProjectWorkflowStatus(requestUrl, projectId);
    }
    if (instance) {
      instance.appContext.config.globalProperties.$test_menu = analysisMenu.value;
    }
  } catch (caught) {
    loadError.value = caught instanceof Error ? caught.message : "测试菜单读取失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
};

onMounted(loadMenuStatus);
</script>

<style scoped>
.planning-menu {
  display: grid;
  gap: var(--ez-space-6);
  min-width: 0;
}

.planning-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 140px), 1fr));
  gap: var(--ez-space-4);
  margin: 0;
}

.planning-overview > div {
  padding: var(--ez-space-4);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
  background: var(--ez-color-surface-subtle);
}

.planning-overview dt {
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-13);
}

.planning-overview dd {
  margin: var(--ez-space-2) 0 0;
  color: var(--ez-color-text-primary);
  font-weight: 700;
  overflow-wrap: anywhere;
}

.planning-overview__note {
  margin: var(--ez-space-4) 0 0;
  color: var(--ez-color-text-secondary);
}

.workspace-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  gap: var(--ez-space-4);
  min-width: 0;
}
</style>
