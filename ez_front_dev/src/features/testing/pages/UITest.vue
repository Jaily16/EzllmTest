<template>
  <!-- WorkspacePageHeader 与 WorkflowStepper 由共享 scaffold 呈现。 -->
  <TestWorkspaceScaffold
    eyebrow="UI TESTING"
    title="前端 UI 测试"
    description="依次恢复或生成 UI 设计分析与测试用例，恢复后可继续工作；每个阶段都明确显示保存、过期和运行状态。"
    :steps="workflowSteps"
    :active-operation="activeOperation"
    :hydrating="hydrating"
    :hydration-error="hydrationError"
  >
    <template #hydration-actions
      ><el-button :disabled="hydrating" @click="restoreWorkflow">重新读取</el-button></template
    >

    <WorkspaceSection
      title="1. UI 设计分析"
      description="提取界面、交互和状态设计信息。"
      :busy="activeOperation === 'ui_info' && isRunning"
    >
      <el-alert
        v-if="staleWarning('ui_info')"
        :title="staleWarning('ui_info')"
        type="warning"
        show-icon
        :closable="false"
      />
      <ModelSelector
        v-model="llm"
        :options="MODEL_OPTIONS"
        :disabled="isRunning"
        label="本阶段使用的大语言模型"
        description="当前页面各阶段共用此模型；匹配原模型与输入时可复用已保存结果。"
      />
      <WorkflowActionBar aria-label="UI 设计分析操作">
        <el-button
          v-if="!hasVisibleResult('ui_info') && !staleWithoutContent('ui_info')"
          type="primary"
          :icon="Right"
          :disabled="isRunning || !canRunStep('ui_info')"
          round
          @click="analyzeUi(false)"
          >{{
            needsResultRecovery("ui_info") ? "恢复匹配的已保存结果" : "开始 UI 设计分析"
          }}</el-button
        >
        <el-button
          v-if="hasSavedResult('ui_info')"
          type="warning"
          :icon="Refresh"
          :disabled="isRunning"
          plain
          round
          @click="regenerateAnalysis"
          >重新生成 UI 设计分析</el-button
        >
      </WorkflowActionBar>
      <p v-if="needsResultRecovery('ui_info')" class="recovery-note">
        恢复会按当前模型与输入查找已保存结果；匹配时直接恢复，不匹配时会开始新的分析。
      </p>
      <LlmWorkflowExecution
        v-if="activeOperation === 'ui_info'"
        v-bind="executionProps"
        @cancel="cancel"
      />
      <ResultContainer
        v-if="showAnalysis"
        title="业务资料中的 UI 设计内容"
        :status="staleWarning('ui_info') ? 'stale' : 'default'"
        retention="persistent"
        ><TestResultText :text="uiInfo"
      /></ResultContainer>
    </WorkspaceSection>

    <WorkspaceSection
      v-if="showAnalysis"
      title="2. UI 测试用例"
      description="根据已显示的 UI 设计分析生成结构化测试知识和用例。"
      :busy="activeOperation === 'ui_case' && isRunning"
    >
      <el-alert
        v-if="staleWarning('ui_case')"
        :title="staleWarning('ui_case')"
        type="warning"
        show-icon
        :closable="false"
      />
      <TestRetentionNotice retention="persistent" />
      <ModelSelector
        v-model="llm"
        :options="MODEL_OPTIONS"
        :disabled="isRunning"
        label="本阶段使用的大语言模型"
      />
      <WorkflowActionBar aria-label="UI 测试用例操作">
        <el-button
          v-if="!hasVisibleResult('ui_case') && !staleWithoutContent('ui_case')"
          type="primary"
          :icon="Right"
          :disabled="isRunning || !canRunStep('ui_case')"
          round
          @click="generateCases(false)"
          >{{
            needsResultRecovery("ui_case") ? "恢复匹配的已保存结果" : "生成 UI 测试用例"
          }}</el-button
        >
        <el-button
          v-if="hasSavedResult('ui_case')"
          type="warning"
          :icon="Refresh"
          :disabled="isRunning"
          plain
          round
          @click="regenerateCases"
          >重新生成 UI 测试用例</el-button
        >
      </WorkflowActionBar>
      <p v-if="needsResultRecovery('ui_case')" class="recovery-note">
        恢复会按当前模型与输入查找已保存结果；匹配时直接恢复，不匹配时会开始新的分析。
      </p>
      <LlmWorkflowExecution
        v-if="activeOperation === 'ui_case'"
        v-bind="executionProps"
        @cancel="cancel"
      />

      <FeedbackState
        v-if="showCases && finalResultHidden"
        kind="empty"
        title="当前结果已隐藏"
        description="结果仍保留在本页面和项目中，没有发送删除或生成请求。"
        ><template #actions
          ><el-button @click="finalResultHidden = false">重新显示</el-button></template
        ></FeedbackState
      >
      <div v-else-if="showCases" class="test-results">
        <ResultContainer
          title="知识库中的 UI 测试知识"
          :status="staleWarning('ui_case') ? 'stale' : 'default'"
          retention="persistent"
          ><TestResultText :text="knowledge"
        /></ResultContainer>
        <ResultContainer
          title="模型生成的 UI 测试用例"
          :status="staleWarning('ui_case') ? 'stale' : 'default'"
          retention="persistent"
          ><TestResultText :text="testCases"
        /></ResultContainer>
        <WorkflowActionBar aria-label="UI 测试结果显示操作"
          ><el-button type="info" plain @click="hidePersistentResult"
            >隐藏当前结果</el-button
          ></WorkflowActionBar
        >
      </div>
    </WorkspaceSection>
  </TestWorkspaceScaffold>
</template>

<script lang="ts" setup>
import { getCurrentInstance, onMounted, ref } from "vue";
import { Refresh, Right } from "@element-plus/icons-vue";
import { ElMessage } from "@/shared/plugins/elementPlus";
import FeedbackState from "@/shared/components/FeedbackState.vue";
import LlmWorkflowExecution from "@/features/testing/components/LlmWorkflowExecution.vue";
import ModelSelector from "@/shared/components/ModelSelector.vue";
import ResultContainer from "@/shared/components/ResultContainer.vue";
import TestResultText from "@/features/testing/components/TestResultText.vue";
import TestRetentionNotice from "@/features/testing/components/TestRetentionNotice.vue";
import TestWorkspaceScaffold from "@/features/testing/components/TestWorkspaceScaffold.vue";
import WorkflowActionBar from "@/shared/components/WorkflowActionBar.vue";
import WorkspaceSection from "@/shared/components/WorkspaceSection.vue";
import { useLlmWorkflow } from "@/shared/composables/useLlmWorkflow";
import { useTestWorkflow } from "@/features/testing/composables/useTestWorkflow";
import { DEFAULT_MODEL, MODEL_OPTIONS } from "@/shared/config/models";

interface UiCaseResult {
  ui_test_knowledge: string;
  test_cases: string;
}

const instance = getCurrentInstance();
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");
const llm = ref(DEFAULT_MODEL);
const showAnalysis = ref(false);
const showCases = ref(false);
const finalResultHidden = ref(false);
const uiInfo = ref("");
const knowledge = ref("");
const testCases = ref("");
const testWorkflow = useTestWorkflow({
  baseUrl: requestUrl,
  pid: projectId,
  steps: [
    { operation: "ui_info", label: "UI 设计分析", artifactKey: "ui_info" },
    { operation: "ui_case", label: "UI 测试用例", artifactKey: "ui_case", dependsOn: ["ui_info"] },
  ],
});
const {
  steps: workflowSteps,
  hydrating,
  hydrationError,
  hydrateWorkflow,
  canRunStep,
  regenerateStep,
  resultFor,
  hasSavedResult,
  hasVisibleResult,
  needsResultRecovery,
  staleWarning,
} = testWorkflow;
const {
  isRunning,
  result,
  error,
  activeOperation,
  executionProps,
  runWorkflow,
  cancel,
  resetStream,
} = useLlmWorkflow(requestUrl, projectId, testWorkflow);

const staleWithoutContent = (operation: string) =>
  workflowSteps.value.some(
    (step) => step.operation === operation && step.state === "stale" && step.result === null,
  );
const analyzeUi = async (regenerate = false): Promise<boolean> => {
  const succeeded = await runWorkflow(
    "ui_info",
    llm.value,
    {},
    {
      answerTitle: "前端 UI 设计分析（流式输出）",
      successTitle: "前端 UI 设计分析已完成",
      regenerate,
      keepPreviousOnFailure: true,
    },
  );
  if (succeeded && typeof result.value === "string") {
    uiInfo.value = result.value;
    showAnalysis.value = true;
  } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("ui_case")) {
    ElMessage.warning("请先完成有效的 UI 设计分析");
    return false;
  }
  const succeeded = await runWorkflow(
    "ui_case",
    llm.value,
    { info: uiInfo.value },
    {
      answerTitle: "前端 UI 测试用例（流式输出）",
      successTitle: "前端 UI 测试用例已生成",
      regenerate,
      keepPreviousOnFailure: true,
    },
  );
  if (succeeded) {
    const value = result.value as UiCaseResult;
    knowledge.value = value.ui_test_knowledge;
    testCases.value = value.test_cases;
    showCases.value = true;
    finalResultHidden.value = false;
  } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
const regenerateAnalysis = () => regenerateStep("ui_info", () => analyzeUi(true));
const regenerateCases = () => regenerateStep("ui_case", () => generateCases(true));
const restoreWorkflow = async () => {
  await hydrateWorkflow();
  const savedInfo = resultFor<string>("ui_info");
  const savedCases = resultFor<UiCaseResult>("ui_case");
  if (savedInfo) {
    uiInfo.value = savedInfo;
    showAnalysis.value = true;
  }
  if (savedCases) {
    knowledge.value = savedCases.ui_test_knowledge;
    testCases.value = savedCases.test_cases;
    showCases.value = true;
  }
};
onMounted(restoreWorkflow);
const hidePersistentResult = () => {
  resetStream();
  finalResultHidden.value = true;
};
</script>

<style scoped>
.test-results {
  display: grid;
  min-width: 0;
  gap: var(--ez-space-4);
  margin-top: var(--ez-space-4);
}
.recovery-note {
  max-width: var(--ez-reading-measure);
  margin: var(--ez-space-2) 0 0;
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-13);
  overflow-wrap: anywhere;
}
</style>
