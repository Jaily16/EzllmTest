<template>
  <!-- WorkflowStepper 由共享 scaffold 呈现。 -->
  <TestWorkspaceScaffold
    eyebrow="NONFUNCTIONAL TESTING"
    title="系统非功能性测试"
    description="先恢复或识别质量属性，再继续为指定非功能测试类型生成当前页面结果。"
    :steps="workflowSteps"
    :active-operation="activeOperation"
    :hydrating="hydrating"
    :hydration-error="hydrationError"
  >
    <template #hydration-actions
      ><el-button :disabled="hydrating" @click="restoreWorkflow">重新读取</el-button></template
    >
    <WorkspaceSection
      title="1. 非功能需求分析"
      description="提取性能、可靠性、安全性等质量属性与约束。"
      :busy="activeOperation === 'nonfunctional_info' && isRunning"
    >
      <el-alert
        v-if="staleWarning('nonfunctional_info')"
        :title="staleWarning('nonfunctional_info')"
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
      <WorkflowActionBar aria-label="非功能需求分析操作">
        <el-button
          v-if="
            !hasVisibleResult('nonfunctional_info') && !staleWithoutContent('nonfunctional_info')
          "
          type="primary"
          :icon="Right"
          :disabled="isRunning || !canRunStep('nonfunctional_info')"
          round
          @click="analyzeRequirements(false)"
          >{{
            needsResultRecovery("nonfunctional_info")
              ? "恢复匹配的已保存结果"
              : "开始非功能需求分析"
          }}</el-button
        >
        <el-button
          v-if="hasSavedResult('nonfunctional_info')"
          type="warning"
          :icon="Refresh"
          :disabled="isRunning"
          plain
          round
          @click="regenerateAnalysis"
          >重新生成非功能需求分析</el-button
        >
      </WorkflowActionBar>
      <p v-if="needsResultRecovery('nonfunctional_info')" class="recovery-note">
        恢复会按当前模型与输入查找已保存结果；匹配时直接恢复，不匹配时会开始新的分析。
      </p>
      <LlmWorkflowExecution
        v-if="activeOperation === 'nonfunctional_info'"
        v-bind="executionProps"
        @cancel="cancel"
      />
      <ResultContainer
        v-if="showAnalysis"
        title="业务资料中的非功能需求"
        :status="staleWarning('nonfunctional_info') ? 'stale' : 'default'"
        retention="persistent"
        ><TestResultText :text="nonfunctionalInfo"
      /></ResultContainer>
    </WorkspaceSection>
    <WorkspaceSection
      v-if="showAnalysis"
      title="2. 非功能测试用例"
      description="选择质量属性后生成相应测试知识与用例。"
      :busy="activeOperation === 'nonfunctional_case' && isRunning"
    >
      <el-alert
        v-if="caseWarning"
        :title="caseWarning"
        type="warning"
        show-icon
        :closable="false"
      />
      <TestTargetSelector
        v-model="methodName"
        :options="methodOptions"
        label="非功能测试类型"
        field-id="nonfunctional-target"
        description="改变测试类型会把当前页面中的旧用例标记为过期。"
        placeholder="请选择测试类型"
        required
        @update:model-value="markCaseStale"
      />
      <TestRetentionNotice retention="session-only" />
      <ModelSelector
        v-model="llm"
        :options="MODEL_OPTIONS"
        :disabled="isRunning"
        label="本阶段使用的大语言模型"
      />
      <WorkflowActionBar aria-label="非功能测试用例操作">
        <el-button
          v-if="!caseResultVisible"
          type="primary"
          :icon="Right"
          :disabled="isRunning || !methodName || !canRunStep('nonfunctional_case')"
          round
          @click="generateCases(false)"
          >生成相应测试用例</el-button
        >
        <el-button
          v-if="caseResultVisible"
          type="warning"
          :icon="Refresh"
          :disabled="isRunning"
          plain
          round
          @click="regenerateCases"
          >重新生成相应测试用例</el-button
        >
      </WorkflowActionBar>
      <span class="recovery-copy"
        >恢复匹配的已保存结果仅适用于持久化步骤；本阶段结果不会跨页面恢复。</span
      >
      <template v-if="caseExecutionVisible">
        <LlmWorkflowExecution
          v-if="activeOperation === 'nonfunctional_case'"
          v-bind="executionProps"
          @cancel="cancel"
        />
      </template>
      <div v-if="showCases && caseResultVisible" class="test-results">
        <ResultContainer
          :title="`知识库中的${methodName}知识`"
          :status="caseWarning ? 'stale' : 'default'"
          retention="session-only"
          ><TestResultText :text="knowledge"
        /></ResultContainer>
        <ResultContainer
          title="模型生成的非功能测试用例"
          :status="caseWarning ? 'stale' : 'default'"
          retention="session-only"
          ><TestResultText :text="testCases"
        /></ResultContainer>
        <WorkflowActionBar aria-label="非功能测试结果操作"
          ><el-button type="info" plain @click="reset"
            >清空当前页面结果</el-button
          ></WorkflowActionBar
        >
      </div>
    </WorkspaceSection>
  </TestWorkspaceScaffold>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, onMounted, ref } from "vue";
import { Refresh, Right } from "@element-plus/icons-vue";
import { ElMessage } from "@/shared/plugins/elementPlus";
import "@/shared/components/FeedbackState.vue";
import LlmWorkflowExecution from "@/features/testing/components/LlmWorkflowExecution.vue";
import ModelSelector from "@/shared/components/ModelSelector.vue";
import ResultContainer from "@/shared/components/ResultContainer.vue";
import TestResultText from "@/features/testing/components/TestResultText.vue";
import TestRetentionNotice from "@/features/testing/components/TestRetentionNotice.vue";
import TestTargetSelector from "@/features/testing/components/TestTargetSelector.vue";
import TestWorkspaceScaffold from "@/features/testing/components/TestWorkspaceScaffold.vue";
import WorkflowActionBar from "@/shared/components/WorkflowActionBar.vue";
import WorkspaceSection from "@/shared/components/WorkspaceSection.vue";
import { useLlmWorkflow } from "@/shared/composables/useLlmWorkflow";
import { useTestWorkflow } from "@/features/testing/composables/useTestWorkflow";
import { DEFAULT_MODEL, MODEL_OPTIONS } from "@/shared/config/models";
import { confirmSessionOnlyResultReset } from "@/shared/ui/confirmations";

interface NonfunctionalAnalysisResult {
  nonfunctional_info: string;
  list: { method_list: string[] };
}
interface NonfunctionalCaseResult {
  nonfunctional_test_knowledge: string;
  test_cases: string;
}
const instance = getCurrentInstance();
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");
const llm = ref(DEFAULT_MODEL);
const showAnalysis = ref(false);
const showCases = ref(false);
const methodName = ref("");
const methods = ref<string[]>([]);
/**
 * 派生用于界面展示或请求判断的方法选项。
 */
const methodOptions = computed(() => methods.value.map((value) => ({ value, label: value })));
const nonfunctionalInfo = ref("");
const knowledge = ref("");
const testCases = ref("");
const testWorkflow = useTestWorkflow({
  baseUrl: requestUrl,
  pid: projectId,
  steps: [
    { operation: "nonfunctional_info", label: "非功能需求分析", artifactKey: "nonfunctional_info" },
    {
      operation: "nonfunctional_case",
      label: "非功能测试用例",
      artifactKey: "nonfunctional_case",
      dependsOn: ["nonfunctional_info"],
      selectionFields: ["method_name"],
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
/**
 * 处理过期 without内容，并保持现有输入输出约定。
 */
const staleWithoutContent = (operation: string) =>
  workflowSteps.value.some(
    (step) => step.operation === operation && step.state === "stale" && step.result === null,
  );
/**
 * 派生用于界面展示或请求判断的当前非功能测试用例选择条件。
 */
const currentNonfunctionalCaseSelection = computed(() => ({ method_name: methodName.value }));
/**
 * 派生用于界面展示或请求判断的用例结果可见状态。
 */
const caseResultVisible = computed(() =>
  hasVisibleResultFor("nonfunctional_case", currentNonfunctionalCaseSelection.value),
);
/**
 * 派生用于界面展示或请求判断的用例 execution可见状态。
 */
const caseExecutionVisible = computed(
  () =>
    activeOperation.value === "nonfunctional_case" &&
    (isRunning.value ||
      selectionsMatch(
        "nonfunctional_case",
        activeSelection.value,
        currentNonfunctionalCaseSelection.value,
      )),
);
/**
 * 派生用于界面展示或请求判断的用例警告。
 */
const caseWarning = computed(() =>
  caseResultVisible.value ? staleWarning("nonfunctional_case") : "",
);
/**
 * 标记用例过期，并保持现有状态与错误处理语义。
 */
const markCaseStale = () =>
  reconcileStepSelection("nonfunctional_case", currentNonfunctionalCaseSelection.value, false);
/**
 * 分析requirements，并保持现有状态与错误处理语义。
 *
 * @param regenerate 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const analyzeRequirements = async (regenerate = false): Promise<boolean> => {
  const succeeded = await runWorkflow(
    "nonfunctional_info",
    llm.value,
    {},
    {
      answerTitle: "非功能性需求分析（流式输出）",
      successTitle: "非功能性需求分析已完成",
      regenerate,
      keepPreviousOnFailure: true,
    },
  );
  if (succeeded) {
    const value = result.value as NonfunctionalAnalysisResult;
    nonfunctionalInfo.value = value.nonfunctional_info;
    methods.value = value.list.method_list;
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
  if (!canRunStep("nonfunctional_case")) {
    ElMessage.warning("请先完成有效的非功能需求分析");
    return false;
  }
  if (!methodName.value) {
    ElMessage.warning("请先选择非功能性测试类型");
    return false;
  }
  const succeeded = await runWorkflow(
    "nonfunctional_case",
    llm.value,
    { info: nonfunctionalInfo.value, method_name: methodName.value },
    {
      answerTitle: methodName.value + "用例（流式输出）",
      successTitle: methodName.value + "用例已生成",
      regenerate,
      keepPreviousOnFailure: true,
    },
  );
  if (succeeded) {
    const value = result.value as NonfunctionalCaseResult;
    knowledge.value = value.nonfunctional_test_knowledge;
    testCases.value = value.test_cases;
    showCases.value = true;
  } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
/**
 * 重新生成分析，并保持现有状态与错误处理语义。
 */
const regenerateAnalysis = () =>
  regenerateStep("nonfunctional_info", () => analyzeRequirements(true));
/**
 * 重新生成用例，并保持现有状态与错误处理语义。
 */
const regenerateCases = () => regenerateStep("nonfunctional_case", () => generateCases(true));
/**
 * 从服务端已保存产物恢复当前工作流，不自动触发生成。
 */
const restoreWorkflow = async () => {
  await hydrateWorkflow();
  const savedInfo = resultFor<NonfunctionalAnalysisResult>("nonfunctional_info");
  const savedCases = resultFor<NonfunctionalCaseResult>("nonfunctional_case");
  const savedSelection = selectionFor("nonfunctional_case");
  if (savedInfo) {
    nonfunctionalInfo.value = savedInfo.nonfunctional_info;
    methods.value = savedInfo.list.method_list;
    showAnalysis.value = true;
  }
  if (typeof savedSelection.method_name === "string") methodName.value = savedSelection.method_name;
  if (savedCases) {
    knowledge.value = savedCases.nonfunctional_test_knowledge;
    testCases.value = savedCases.test_cases;
    showCases.value = true;
  }
};
/**
 * 组件挂载后执行既有初始化或恢复流程。
 */
onMounted(restoreWorkflow);
/**
 * 重置内部状态，并保持现有状态与错误处理语义。
 */
const reset = async () => {
  if (!(await confirmSessionOnlyResultReset("非功能测试用例"))) return;
  resetStream();
  showCases.value = false;
  knowledge.value = "";
  testCases.value = "";
  resetStep("nonfunctional_case");
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
