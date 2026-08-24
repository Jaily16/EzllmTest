<template>
  <div class="planning-cockpit">
    <WorkspacePageHeader
      eyebrow="PROJECT ANALYSIS"
      title="测试计划工作台"
      description="先读取服务器已保存的业务摘要、测试计划和推荐类型；只有显式操作才会调用模型。"
    >
      <template #actions>
        <el-button v-if="savedBundle" @click="router.push('/menu')">查看测试菜单</el-button>
      </template>
    </WorkspacePageHeader>

    <FeedbackState
      v-if="bundleLoading"
      kind="loading"
      title="正在读取已保存计划"
      description="正在通过只读接口恢复当前资料版本，不会自动调用模型。"
      skeleton="content"
      busy
    />

    <FeedbackState
      v-else-if="bundleError"
      kind="error"
      title="已保存计划读取失败"
      :description="bundleError"
    >
      <template #actions>
        <el-button type="primary" @click="hydratePlan">重新读取</el-button>
      </template>
    </FeedbackState>

    <template v-else>
      <WorkspaceSection
        v-if="savedBundle"
        title="当前已保存版本"
        :description="bundleIsStale
          ? '业务资料版本已经变化。上一版仍可阅读，但必须重新生成后才能恢复下游工作区。'
          : '以下三部分来自服务器保存的同一份项目分析。'"
      >
        <div class="revision-fact">
          <span>资料版本</span>
          <strong>{{ sourceRevisionLabel }}</strong>
        </div>

        <div class="saved-results">
          <ResultContainer
            title="业务文档的初步分析与总结"
            :status="bundleStatus"
            retention="persistent"
          >
            <div class="planning-prose">{{ savedBundle.summary }}</div>
          </ResultContainer>

          <ResultContainer
            title="建议测试计划"
            description="这是整体建议；具体用例需要进入相应测试工作区继续生成。"
            :status="bundleStatus"
            retention="persistent"
          >
            <div class="planning-prose">{{ savedBundle.plan }}</div>
          </ResultContainer>

          <ResultContainer
            title="推荐测试类型"
            description="推荐表示计划建议开展该类型，不代表对应工作区已经完成。"
            :status="bundleStatus"
            retention="persistent"
          >
            <ul class="recommendation-list">
              <li v-for="workspace in TEST_WORKSPACES" :key="workspace.key">
                <span>{{ workspace.title }}</span>
                <strong :data-recommended="savedBundle.menu[workspace.key]">
                  {{ savedBundle.menu[workspace.key] ? "推荐" : "未推荐" }}
                </strong>
              </li>
            </ul>
          </ResultContainer>
        </div>
      </WorkspaceSection>

      <WorkspaceSection
        title="生成控制"
        :description="savedBundle
          ? '重新生成前会再次确认；失败或取消不会替换上方的已保存版本。'
          : '当前项目尚无完整计划。选择模型后显式生成并保存，不会在页面加载时自动开始。'"
        :busy="isRunning"
      >
        <FeedbackState
          v-if="!savedBundle && !hasActivity"
          kind="empty"
          title="尚未生成测试计划"
          description="完成项目资料上传后，可在这里显式分析业务并生成测试计划和推荐菜单。"
          compact
        />

        <ModelSelector
          v-model="llm"
          :options="MODEL_OPTIONS"
          :disabled="isRunning"
          label="选择用于业务分析和测试计划的大语言模型"
          description="选择模型不会产生请求；点击下方按钮后才开始生成。"
          id="planning-model"
        />

        <WorkflowActionBar aria-label="测试计划生成操作">
          <el-button
            v-if="!savedBundle"
            type="primary"
            :loading="isRunning"
            :disabled="isRunning"
            @click="startTestPlan"
          >
            生成并保存
          </el-button>
          <el-button
            v-else
            type="primary"
            plain
            :loading="isRunning"
            :disabled="isRunning"
            @click="restartTestPlan"
          >
            重新分析业务和生成测试计划
          </el-button>
        </WorkflowActionBar>

        <p v-if="projectAnalysisRegenerating" class="regeneration-notice" role="status">
          正在重新分析：测试菜单和八类测试工作区已临时锁定，上方已保存版本仍可阅读。
        </p>
        <p v-if="runError" class="run-error" role="alert">{{ runError }}</p>

        <LlmExecutionPanel
          :visible="hasActivity"
          :running="isRunning"
          :completed="completed"
          :cancelled="cancelled"
          :saved="saved"
          :from-cache="fromCache"
          :progress="progress"
          :meta="meta"
          :reasoning-sections="reasoningSections"
          :usage="usage"
          :usage-received="usageReceived"
          :error="streamError"
          success-title="测试计划已完成"
          @cancel="cancelTestPlan"
        />
      </WorkspaceSection>

      <WorkspaceSection
        v-if="draftVisible"
        title="本次未保存草稿"
        description="这是本轮流式响应中已经收到的内容。只有完整完成且服务器确认已保存后，才会替换当前有效版本。"
        :busy="isRunning"
      >
        <div class="draft-results">
          <ResultContainer v-if="summary" title="草稿摘要">
            <div class="planning-prose">{{ summary }}</div>
          </ResultContainer>
          <ResultContainer v-if="answer" title="草稿测试计划">
            <div class="planning-prose">{{ answer }}</div>
          </ResultContainer>
        </div>
      </WorkspaceSection>
    </template>
  </div>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "@/plugins/elementPlus";
import { useRouter } from "vue-router";
import LlmExecutionPanel from "@/components/LlmExecutionPanel.vue";
import FeedbackState from "@/components/workspace/FeedbackState.vue";
import ModelSelector from "@/components/workspace/ModelSelector.vue";
import ResultContainer from "@/components/workspace/ResultContainer.vue";
import WorkflowActionBar from "@/components/workspace/WorkflowActionBar.vue";
import WorkspacePageHeader from "@/components/workspace/WorkspacePageHeader.vue";
import WorkspaceSection from "@/components/workspace/WorkspaceSection.vue";
import { useLlmStream } from "@/composables/useLlmStream";
import { DEFAULT_MODEL, MODEL_OPTIONS, type ModelLabel } from "@/config/models";
import { TEST_WORKSPACES } from "@/config/testWorkspaces";
import {
  beginProjectAnalysisRegeneration,
  completedOperations,
  fetchProjectAnalysisBundle,
  finishProjectAnalysisRegeneration,
  loadProjectWorkflowStatus,
  projectAnalysisRegenerating,
  projectWorkflowStatus,
  setProjectAnalysisReady,
  staleOperations,
  workflowStatusLoaded,
  type ProjectAnalysisBundle,
  type TestMenuState,
} from "@/state/projectAnalysis";
import { confirmProjectAnalysisRegeneration } from "@/ui/confirmations";

const router = useRouter();
const instance = getCurrentInstance();
if (instance === null) {
  ElMessage({ message: "平台出现了一些问题，无法获取关键信息", type: "error" });
}
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");

const llm = ref<ModelLabel>(DEFAULT_MODEL);
const savedBundle = ref<ProjectAnalysisBundle | null>(null);
const previousBundle = ref<ProjectAnalysisBundle | null>(null);
const bundleLoading = ref(true);
const bundleError = ref("");
const runError = ref("");
const streamPromoted = ref(false);
let bundleController: AbortController | null = null;

const {
  isRunning,
  completed,
  cancelled,
  saved,
  fromCache,
  ready,
  summary,
  menu,
  answer,
  reasoningSections,
  usage,
  usageReceived,
  error: streamError,
  progress,
  meta,
  artifact,
  hasActivity,
  start,
  cancel,
} = useLlmStream(requestUrl);

const bundleIsStale = computed(() => staleOperations.value.includes("project_analysis"));
const bundleStatus = computed<"default" | "stale">(() =>
  bundleIsStale.value ? "stale" : "default"
);
const sourceRevisionLabel = computed(() =>
  projectWorkflowStatus.value?.source_revision || artifact.sourceRevision || "未提供版本标识"
);
const draftVisible = computed(() =>
  !streamPromoted.value && Boolean(summary.value || answer.value)
);

const menuIsComplete = (candidate: TestMenuState | null): candidate is TestMenuState =>
  candidate !== null && [
    "test_plan",
    "unit_test",
    "integration_test",
    "api_test",
    "ui_test",
    "db_test",
    "functional_test",
    "nonfunctional_test",
    "acceptance_test",
  ].every((key) => typeof candidate[key as keyof TestMenuState] === "boolean");

const loadSavedBundle = async () => {
  bundleController?.abort();
  const activeController = new AbortController();
  bundleController = activeController;
  bundleLoading.value = true;
  bundleError.value = "";
  try {
    savedBundle.value = await fetchProjectAnalysisBundle(
      requestUrl,
      projectId,
      activeController.signal
    );
  } catch (caught) {
    if (activeController.signal.aborted) return;
    bundleError.value = caught instanceof Error
      ? caught.message
      : "已保存计划读取失败，请稍后重试。";
  } finally {
    if (bundleController === activeController) {
      bundleController = null;
      bundleLoading.value = false;
    }
  }
};

const hydratePlan = async () => {
  bundleController?.abort();
  bundleLoading.value = true;
  bundleError.value = "";
  try {
    if (!workflowStatusLoaded.value || projectWorkflowStatus.value?.pid !== projectId) {
      await loadProjectWorkflowStatus(requestUrl, projectId);
    }
    const hasSavedAnalysis =
      completedOperations.value.includes("project_analysis") || bundleIsStale.value;
    if (hasSavedAnalysis) {
      await loadSavedBundle();
    } else {
      savedBundle.value = null;
      bundleLoading.value = false;
    }
  } catch (caught) {
    bundleError.value = caught instanceof Error
      ? caught.message
      : "项目分析状态读取失败，请稍后重试。";
    bundleLoading.value = false;
  }
};

const restartTestPlan = async () => {
  const confirmed = await confirmProjectAnalysisRegeneration();
  if (!confirmed) return;
  await runTestPlan(true);
};

async function runTestPlan(regenerate: boolean) {
  previousBundle.value = savedBundle.value;
  runError.value = "";
  streamPromoted.value = false;
  if (regenerate) beginProjectAnalysisRegeneration();
  try {
    const succeeded = await start("/project/llm/plan/stream", {
      pid: projectId,
      llm_name: llm.value,
      regenerate,
    });
    const completeMenu = menuIsComplete(menu.value) ? menu.value : null;
    const completeSavedBundle =
      succeeded && saved.value && ready.value && completeMenu !== null &&
      summary.value.trim().length > 0 && answer.value.trim().length > 0;

    if (completeSavedBundle) {
      savedBundle.value = {
        summary: summary.value.trim(),
        plan: answer.value.trim(),
        menu: completeMenu,
      };
      streamPromoted.value = true;
      setProjectAnalysisReady(menu.value);
      if (instance) instance.appContext.config.globalProperties.$test_menu = menu.value;
      try {
        await loadProjectWorkflowStatus(requestUrl, projectId);
      } catch {
        ElMessage({
          message: "分析结果已保存，但项目导航状态刷新失败，请稍后重试",
          type: "warning",
        });
      }
      ElMessage({
        message: fromCache.value
          ? "已读取保存的业务分析、测试计划和测试菜单"
          : "业务分析、测试计划和测试菜单已生成并保存",
        type: "success",
      });
    } else {
      savedBundle.value = previousBundle.value;
      if (streamError.value) {
        runError.value = `生成失败：${streamError.value.message} ${
          streamError.value.retryable ? "可安全重试；当前有效版本未被替换。" : "当前有效版本未被替换。"
        }`;
      } else if (cancelled.value) {
        runError.value = "本次生成已取消，当前有效版本未被替换，已接收内容保留为草稿。";
      } else if (succeeded) {
        runError.value = "服务器未确认完整保存，本次内容只作为未保存草稿保留。";
      }
    }
  } finally {
    if (regenerate) finishProjectAnalysisRegeneration();
  }
}

const startTestPlan = () => runTestPlan(false);
const cancelTestPlan = () => {
  cancel();
  runError.value = "本次生成已取消，当前有效版本未被替换，已接收内容保留为草稿。";
};

onMounted(hydratePlan);
onBeforeUnmount(() => bundleController?.abort());
</script>

<style scoped>
.planning-cockpit,
.saved-results,
.draft-results {
  display: grid;
  gap: var(--ez-space-6);
  min-width: 0;
}

.revision-fact {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--ez-space-2);
  margin-bottom: var(--ez-space-4);
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
}

.revision-fact strong {
  color: var(--ez-color-text-primary);
  overflow-wrap: anywhere;
}

.planning-prose {
  max-width: var(--ez-reading-measure);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--ez-color-text-primary);
  line-height: var(--ez-line-height-body);
  user-select: text;
}

.recommendation-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  gap: var(--ez-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.recommendation-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ez-space-2);
  min-width: 0;
  padding: var(--ez-space-3);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
  background: var(--ez-color-surface-subtle);
}

.recommendation-list span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.recommendation-list strong {
  flex: 0 0 auto;
  color: var(--ez-color-locked);
  font-size: var(--ez-font-size-13);
}

.recommendation-list strong[data-recommended="true"] {
  color: var(--ez-color-success);
}

.regeneration-notice,
.run-error {
  margin: var(--ez-space-4) 0 0;
  padding: var(--ez-space-3) var(--ez-space-4);
  border-radius: var(--ez-radius-medium);
  line-height: var(--ez-line-height-body);
  overflow-wrap: anywhere;
}

.regeneration-notice {
  color: var(--ez-color-warning);
  background: var(--ez-color-warning-bg);
}

.run-error {
  color: var(--ez-color-danger);
  background: var(--ez-color-danger-bg);
}

@media (max-width: 480px) {
  .planning-cockpit,
  .saved-results,
  .draft-results {
    gap: var(--ez-space-4);
  }
}
</style>
