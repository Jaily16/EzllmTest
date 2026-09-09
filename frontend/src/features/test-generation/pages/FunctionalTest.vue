<template>
  <!-- WorkflowStepper 由共享 scaffold 呈现。 -->
  <TestWorkspaceScaffold
    eyebrow="FUNCTIONAL TESTING"
    title="系统功能性测试"
    description="先恢复或识别业务用例，再继续为指定用例生成当前页面测试结果。"
    :steps="workflowSteps"
    :active-operation="activeOperation"
    :hydrating="hydrating"
    :hydration-error="hydrationError"
  >
    <template #hydration-actions
      ><el-button :disabled="hydrating" @click="restoreWorkflow">重新读取</el-button></template
    >
    <WorkspaceSection
      title="1. 功能需求分析"
      description="从业务需求资料中提取可测试的用例与功能边界。"
      :busy="activeOperation === 'functional_info' && isRunning"
    >
      <el-alert
        v-if="staleWarning('functional_info')"
        :title="staleWarning('functional_info')"
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
      <WorkflowActionBar aria-label="功能需求分析操作">
        <el-button
          v-if="!hasVisibleResult('functional_info') && !staleWithoutContent('functional_info')"
          type="primary"
          :icon="Right"
          :disabled="isRunning || !canRunStep('functional_info')"
          round
          @click="analyzeUseCases(false)"
          >{{
            needsResultRecovery("functional_info") ? "恢复匹配的已保存结果" : "开始功能需求分析"
          }}</el-button
        >
        <el-button
          v-if="hasSavedResult('functional_info')"
          type="warning"
          :icon="Refresh"
          :disabled="isRunning"
          plain
          round
          @click="regenerateAnalysis"
          >重新生成功能需求分析</el-button
        >
      </WorkflowActionBar>
      <p v-if="needsResultRecovery('functional_info')" class="recovery-note">
        恢复会按当前模型与输入查找已保存结果；匹配时直接恢复，不匹配时会开始新的分析。
      </p>
      <LlmWorkflowExecution
        v-if="activeOperation === 'functional_info'"
        v-bind="executionProps"
        @cancel="cancel"
      />
      <ResultContainer
        v-if="showAnalysis"
        title="业务资料中的功能用例内容"
        :status="staleWarning('functional_info') ? 'stale' : 'default'"
        retention="persistent"
        ><TestResultText :text="useCasesInfo"
      /></ResultContainer>
    </WorkspaceSection>
    <WorkspaceSection
      v-if="showAnalysis"
      title="2. 功能测试用例"
      description="选择业务用例与输出格式后生成测试结果。"
      :busy="activeOperation === 'functional_case' && isRunning"
    >
      <el-alert
        v-if="caseWarning"
        :title="caseWarning"
        type="warning"
        show-icon
        :closable="false"
      />
      <TestTargetSelector
        v-model="useCaseName"
        :options="useCaseOptions"
        label="待测业务用例"
        field-id="functional-target"
        description="选择完整用例名称；改变选择会把已有结果标记为过期。"
        placeholder="请选择用例"
        required
        @update:model-value="markCaseStale"
      />
      <TestFieldGroup legend="测试用例输出格式" field-id="functional-output-format"
        ><el-radio-group v-model="outputFormat" @change="markCaseStale"
          ><el-radio-button
            v-for="(format, index) in outputFormats"
            :key="format"
            :label="format"
            :value="index" /></el-radio-group
      ></TestFieldGroup>
      <TestRetentionNotice retention="session-only" />
      <ModelSelector
        v-model="llm"
        :options="MODEL_OPTIONS"
        :disabled="isRunning"
        label="本阶段使用的大语言模型"
      />
      <WorkflowActionBar aria-label="功能测试用例操作">
        <el-button
          v-if="!caseResultVisible"
          type="primary"
          :icon="Right"
          :disabled="isRunning || !useCaseName || !canRunStep('functional_case')"
          round
          @click="generateCases(false)"
          >生成功能性测试用例</el-button
        >
        <el-button
          v-if="caseResultVisible"
          type="warning"
          :icon="Refresh"
          :disabled="isRunning"
          plain
          round
          @click="regenerateCases"
          >重新生成功能性测试用例</el-button
        >
      </WorkflowActionBar>
      <span class="recovery-copy"
        >恢复匹配的已保存结果仅适用于持久化步骤；本阶段结果不会跨页面恢复。</span
      >
      <template v-if="caseExecutionVisible">
        <LlmWorkflowExecution
          v-if="activeOperation === 'functional_case'"
          v-bind="executionProps"
          @cancel="cancel"
        />
      </template>
      <div v-if="showCases && caseResultVisible" class="test-results">
        <ResultContainer
          title="知识库中的功能性测试知识"
          :status="caseWarning ? 'stale' : 'default'"
          retention="session-only"
          ><TestResultText :text="knowledge"
        /></ResultContainer>
        <ResultContainer
          title="模型生成的功能性测试用例"
          :status="caseWarning ? 'stale' : 'default'"
          retention="session-only"
          ><TestResultText :text="testCases"
        /></ResultContainer>
        <WorkflowActionBar aria-label="功能测试结果操作"
          ><el-button type="info" plain @click="reset"
            >清空当前页面结果</el-button
          ></WorkflowActionBar
        >
      </div>
    </WorkspaceSection>
  </TestWorkspaceScaffold>
</template>

<script lang="ts" setup>
// 测试生成页面只编排本类目标选择与工作流动作；依赖、失效和旧结果恢复统一交给 workflow entity。

import { computed, getCurrentInstance, onMounted, ref } from "vue";
import { Refresh, Right } from "@element-plus/icons-vue";
import { ElMessage } from "@/shared/ui/messages";
import "@/shared/components/FeedbackState.vue";
import LlmWorkflowExecution from "@/features/test-generation/components/LlmWorkflowExecution.vue";
import ModelSelector from "@/shared/components/ModelSelector.vue";
import ResultContainer from "@/shared/components/ResultContainer.vue";
import TestFieldGroup from "@/features/test-generation/components/TestFieldGroup.vue";
import TestResultText from "@/features/test-generation/components/TestResultText.vue";
import TestRetentionNotice from "@/features/test-generation/components/TestRetentionNotice.vue";
import TestTargetSelector from "@/features/test-generation/components/TestTargetSelector.vue";
import TestWorkspaceScaffold from "@/features/test-generation/components/TestWorkspaceScaffold.vue";
import WorkflowActionBar from "@/shared/components/WorkflowActionBar.vue";
import WorkspaceSection from "@/shared/components/WorkspaceSection.vue";
import { useLlmWorkflow } from "@/entities/workflow/model/useLlmWorkflow";
import { useTestWorkflow } from "@/entities/workflow/model/useTestWorkflow";
import { DEFAULT_MODEL, MODEL_OPTIONS } from "@/shared/config/models";
import { confirmSessionOnlyResultReset } from "@/entities/workflow/ui/confirmations";

interface FunctionalAnalysisResult {
  text_info: string;
  list_info: { use_case_list: string[] };
}
interface FunctionalCaseResult {
  functional_test_knowledge: string;
  test_cases: string;
}
const instance = getCurrentInstance();
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");
const llm = ref(DEFAULT_MODEL);
const showAnalysis = ref(false);
const showCases = ref(false);
const outputFormat = ref(0);
const outputFormats = [".txt(文字形式)", ".md(表格形式)", ".xml", ".csv"];
const useCasesInfo = ref("");
const useCaseName = ref("");
const useCases = ref<string[]>([]);
/**
 * 派生用于界面展示或请求判断的use用例选项。
 */
const useCaseOptions = computed(() => useCases.value.map((value) => ({ value, label: value })));
const knowledge = ref("");
const testCases = ref("");
const testWorkflow = useTestWorkflow({
  baseUrl: requestUrl,
  pid: projectId,
  steps: [
    { operation: "functional_info", label: "功能需求分析", artifactKey: "functional_info" },
    {
      operation: "functional_case",
      label: "功能测试用例",
      artifactKey: "functional_case",
      dependsOn: ["functional_info"],
      selectionFields: ["test_type", "output_type", "use_case_name"],
      persistResult: false,
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
  reconcileStepSelection,
  resetStep,
  resultFor,
  selectionFor,
  selectionsMatch,
  hasSavedResult,
  hasVisibleResult,
  hasVisibleResultFor,
  needsResultRecovery,
  staleWarning,
} = testWorkflow;
const {
  isRunning,
  result,
  error,
  activeOperation,
  activeSelection,
  executionProps,
  runWorkflow,
  cancel,
  resetStream,
} = useLlmWorkflow(requestUrl, projectId, testWorkflow);
/** 区分已有失效记录但没有本地正文的步骤，供界面提示恢复或重生成。 */
const staleWithoutContent = (operation: string) =>
  workflowSteps.value.some(
    (step) => step.operation === operation && step.state === "stale" && step.result === null,
  );
/** 从当前目标与生成选项构造输入快照，用于判断现有结果是否匹配；计算本身不提交请求。 */
const currentFunctionalCaseSelection = computed(() => ({
  test_type: 1,
  output_type: outputFormat.value,
  use_case_name: useCaseName.value,
}));
/** 仅展示当前工作流及匹配选择条件的结果或执行状态，避免切换目标后混用其他目标的内容。 */
const caseResultVisible = computed(() =>
  hasVisibleResultFor("functional_case", currentFunctionalCaseSelection.value),
);
/** 仅展示当前工作流及匹配选择条件的结果或执行状态，避免切换目标后混用其他目标的内容。 */
const caseExecutionVisible = computed(
  () =>
    activeOperation.value === "functional_case" &&
    (isRunning.value ||
      selectionsMatch(
        "functional_case",
        activeSelection.value,
        currentFunctionalCaseSelection.value,
      )),
);
/** 只为当前可见且已失效的结果展示参考提示，隐藏结果不产生误导性过期警告。 */
const caseWarning = computed(() =>
  caseResultVisible.value ? staleWarning("functional_case") : "",
);
/** 用当前用例选择条件核对已保存结果，输入改变时标记失效而不丢弃旧正文。 */
const markCaseStale = () =>
  reconcileStepSelection("functional_case", currentFunctionalCaseSelection.value, false);
/**
 * 提交 functional_info 流式工作流；仅成功后更新页面结果，失败保留原结果并显示错误。
 * @param regenerate 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const analyzeUseCases = async (regenerate = false): Promise<boolean> => {
  const succeeded = await runWorkflow(
    "functional_info",
    llm.value,
    {},
    {
      answerTitle: "系统功能性需求分析（流式输出）",
      successTitle: "系统功能性需求分析已完成",
      regenerate,
      keepPreviousOnFailure: true,
    },
  );
  if (succeeded) {
    const value = result.value as FunctionalAnalysisResult;
    useCasesInfo.value = value.text_info;
    useCases.value = value.list_info.use_case_list;
    showAnalysis.value = true;
  } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
/**
 * 提交 functional_case 流式工作流；仅成功后更新页面结果，失败保留原结果并显示错误。
 * @param regenerate 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("functional_case")) {
    ElMessage.warning("请先完成有效的功能需求分析");
    return false;
  }
  if (!useCaseName.value) {
    ElMessage.warning("请先选择要测试的用例（故事）");
    return false;
  }
  const succeeded = await runWorkflow(
    "functional_case",
    llm.value,
    {
      info: useCasesInfo.value,
      test_type: 1,
      output_type: outputFormat.value,
      use_case_name: useCaseName.value,
    },
    {
      answerTitle: "系统功能性测试用例（流式输出）",
      successTitle: "系统功能性测试用例已生成",
      regenerate,
      keepPreviousOnFailure: true,
    },
  );
  if (succeeded) {
    const value = result.value as FunctionalCaseResult;
    knowledge.value = value.functional_test_knowledge;
    testCases.value = value.test_cases;
    showCases.value = true;
  } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
/** 通过工作流替换确认后重执行对应步骤，使用当前选择条件并让下游按依赖规则失效。 */
const regenerateAnalysis = () => regenerateStep("functional_info", () => analyzeUseCases(true));
/** 通过工作流替换确认后重执行对应步骤，使用当前选择条件并让下游按依赖规则失效。 */
const regenerateCases = () => regenerateStep("functional_case", () => generateCases(true));
/** 先恢复工作流状态，再按产物及其选择条件填充页面，进入页面本身不启动模型。 */
const restoreWorkflow = async () => {
  await hydrateWorkflow();
  const savedInfo = resultFor<FunctionalAnalysisResult>("functional_info");
  const savedCases = resultFor<FunctionalCaseResult>("functional_case");
  const savedSelection = selectionFor("functional_case");
  if (savedInfo) {
    useCasesInfo.value = savedInfo.text_info;
    useCases.value = savedInfo.list_info.use_case_list;
    showAnalysis.value = true;
  }
  if (typeof savedSelection.use_case_name === "string")
    useCaseName.value = savedSelection.use_case_name;
  if (typeof savedSelection.output_type === "number")
    outputFormat.value = savedSelection.output_type;
  if (savedCases) {
    knowledge.value = savedCases.functional_test_knowledge;
    testCases.value = savedCases.test_cases;
    showCases.value = true;
  }
};

onMounted(restoreWorkflow);
/** 用户确认后清空本次用例展示和会话步骤，不发送服务端产物删除请求。 */
const reset = async () => {
  if (!(await confirmSessionOnlyResultReset("功能性测试用例"))) return;
  resetStream();
  showCases.value = false;
  knowledge.value = "";
  testCases.value = "";
  resetStep("functional_case");
};
</script>

<style scoped>
.test-results {
  display: grid;
  min-width: 0;
  gap: var(--ez-space-4);
  margin-top: var(--ez-space-4);
}
.recovery-note,
.recovery-copy {
  display: block;
  max-width: var(--ez-reading-measure);
  margin: var(--ez-space-2) 0 0;
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-13);
  overflow-wrap: anywhere;
}
</style>
