<template>
  <!-- WorkflowStepper 由共享 scaffold 呈现。 -->
  <TestWorkspaceScaffold
    eyebrow="DATABASE TESTING"
    title="数据库测试"
    description="恢复或生成数据库设计分析，并继续基于有效分析生成可持久化的测试用例。"
    :steps="workflowSteps"
    :active-operation="activeOperation"
    :hydrating="hydrating"
    :hydration-error="hydrationError"
  >
    <template #hydration-actions
      ><el-button :disabled="hydrating" @click="restoreWorkflow">重新读取</el-button></template
    >
    <WorkspaceSection
      title="1. 数据库设计分析"
      description="从开发设计资料中提取数据结构、关系和约束。"
      :busy="activeOperation === 'db_info' && isRunning"
    >
      <el-alert
        v-if="staleWarning('db_info')"
        :title="staleWarning('db_info')"
        type="warning"
        show-icon
        :closable="false"
      />
      <ModelSelector
        v-model="llm"
        :options="MODEL_OPTIONS"
        :disabled="isRunning"
        label="本阶段使用的大语言模型"
        description="当前页面各阶段共用此模型。"
      />
      <WorkflowActionBar aria-label="数据库设计分析操作">
        <el-button
          v-if="!hasVisibleResult('db_info') && !staleWithoutContent('db_info')"
          type="primary"
          :icon="Right"
          :disabled="isRunning || !canRunStep('db_info')"
          round
          @click="analyzeDatabase(false)"
          >{{
            needsResultRecovery("db_info") ? "恢复匹配的已保存结果" : "开始数据库设计分析"
          }}</el-button
        >
        <el-button
          v-if="hasSavedResult('db_info')"
          type="warning"
          :icon="Refresh"
          :disabled="isRunning"
          plain
          round
          @click="regenerateAnalysis"
          >重新生成数据库设计分析</el-button
        >
      </WorkflowActionBar>
      <p v-if="needsResultRecovery('db_info')" class="recovery-note">
        恢复会按当前模型与输入查找已保存结果；匹配时直接恢复，不匹配时会开始新的分析。
      </p>
      <LlmWorkflowExecution
        v-if="activeOperation === 'db_info'"
        v-bind="executionProps"
        @cancel="cancel"
      />
      <ResultContainer
        v-if="showAnalysis"
        title="业务资料中的数据库设计内容"
        :status="staleWarning('db_info') ? 'stale' : 'default'"
        retention="persistent"
        ><TestResultText :text="databaseInfo"
      /></ResultContainer>
    </WorkspaceSection>
    <WorkspaceSection
      v-if="showAnalysis"
      title="2. 数据库测试用例"
      description="根据数据库设计分析生成测试知识和用例。"
      :busy="activeOperation === 'db_case' && isRunning"
    >
      <el-alert
        v-if="staleWarning('db_case')"
        :title="staleWarning('db_case')"
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
      <WorkflowActionBar aria-label="数据库测试用例操作">
        <el-button
          v-if="!hasVisibleResult('db_case') && !staleWithoutContent('db_case')"
          type="primary"
          :icon="Right"
          :disabled="isRunning || !canRunStep('db_case')"
          round
          @click="generateCases(false)"
          >{{
            needsResultRecovery("db_case") ? "恢复匹配的已保存结果" : "生成数据库测试用例"
          }}</el-button
        >
        <el-button
          v-if="hasSavedResult('db_case')"
          type="warning"
          :icon="Refresh"
          :disabled="isRunning"
          plain
          round
          @click="regenerateCases"
          >重新生成数据库测试用例</el-button
        >
      </WorkflowActionBar>
      <p v-if="needsResultRecovery('db_case')" class="recovery-note">
        恢复会按当前模型与输入查找已保存结果；匹配时直接恢复，不匹配时会开始新的分析。
      </p>
      <LlmWorkflowExecution
        v-if="activeOperation === 'db_case'"
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
          title="知识库中的数据库测试知识"
          :status="staleWarning('db_case') ? 'stale' : 'default'"
          retention="persistent"
          ><TestResultText :text="knowledge"
        /></ResultContainer>
        <ResultContainer
          title="模型生成的数据库测试用例"
          :status="staleWarning('db_case') ? 'stale' : 'default'"
          retention="persistent"
          ><TestResultText :text="testCases"
        /></ResultContainer>
        <WorkflowActionBar aria-label="数据库测试结果显示操作"
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

interface DatabaseCaseResult {
  db_test_knowledge: string;
  test_cases: string;
}
const instance = getCurrentInstance();
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");
const llm = ref(DEFAULT_MODEL);
const showAnalysis = ref(false);
const showCases = ref(false);
const finalResultHidden = ref(false);
const databaseInfo = ref("");
const knowledge = ref("");
const testCases = ref("");
const testWorkflow = useTestWorkflow({
  baseUrl: requestUrl,
  pid: projectId,
  steps: [
    { operation: "db_info", label: "数据库设计分析", artifactKey: "db_info" },
    {
      operation: "db_case",
      label: "数据库测试用例",
      artifactKey: "db_case",
      dependsOn: ["db_info"],
    },
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
/**
 * 处理过期 without内容，并保持现有输入输出约定。
 */
const staleWithoutContent = (operation: string) =>
  workflowSteps.value.some(
    (step) => step.operation === operation && step.state === "stale" && step.result === null,
  );
/**
 * 分析数据库，并保持现有状态与错误处理语义。
 *
 * @param regenerate 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const analyzeDatabase = async (regenerate = false): Promise<boolean> => {
  const succeeded = await runWorkflow(
    "db_info",
    llm.value,
    {},
    {
      answerTitle: "数据库设计分析（流式输出）",
      successTitle: "数据库设计分析已完成",
      regenerate,
      keepPreviousOnFailure: true,
    },
  );
  if (succeeded && typeof result.value === "string") {
    databaseInfo.value = result.value;
    showAnalysis.value = true;
  } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
/**
 * 按当前选择条件请求生成测试用例，并保留失败不覆盖语义。
 *
 * @param regenerate 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("db_case")) {
    ElMessage.warning("请先完成有效的数据库设计分析");
    return false;
  }
  const succeeded = await runWorkflow(
    "db_case",
    llm.value,
    { info: databaseInfo.value },
    {
      answerTitle: "数据库测试用例（流式输出）",
      successTitle: "数据库测试用例已生成",
      regenerate,
      keepPreviousOnFailure: true,
    },
  );
  if (succeeded) {
    const value = result.value as DatabaseCaseResult;
    knowledge.value = value.db_test_knowledge;
    testCases.value = value.test_cases;
    showCases.value = true;
    finalResultHidden.value = false;
  } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
/**
 * 重新生成分析，并保持现有状态与错误处理语义。
 */
const regenerateAnalysis = () => regenerateStep("db_info", () => analyzeDatabase(true));
/**
 * 重新生成用例，并保持现有状态与错误处理语义。
 */
const regenerateCases = () => regenerateStep("db_case", () => generateCases(true));
/**
 * 从服务端已保存产物恢复当前工作流，不自动触发生成。
 */
const restoreWorkflow = async () => {
  await hydrateWorkflow();
  const savedInfo = resultFor<string>("db_info");
  const savedCases = resultFor<DatabaseCaseResult>("db_case");
  if (savedInfo) {
    databaseInfo.value = savedInfo;
    showAnalysis.value = true;
  }
  if (savedCases) {
    knowledge.value = savedCases.db_test_knowledge;
    testCases.value = savedCases.test_cases;
    showCases.value = true;
  }
};
/**
 * 组件挂载后执行既有初始化或恢复流程。
 */
onMounted(restoreWorkflow);
/**
 * 处理hide持久化结果，并保持现有输入输出约定。
 */
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
