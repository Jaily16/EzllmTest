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
// 测试生成页面只编排本类目标选择与工作流动作；依赖、失效和旧结果恢复统一交给 workflow entity。

import { computed, getCurrentInstance, onMounted, ref } from "vue";
import { Refresh, Right } from "@element-plus/icons-vue";
import { ElMessage } from "@/shared/ui/messages";
import "@/shared/components/FeedbackState.vue";
import LlmWorkflowExecution from "@/features/test-generation/components/LlmWorkflowExecution.vue";
import ModelSelector from "@/shared/components/ModelSelector.vue";
import ResultContainer from "@/shared/components/ResultContainer.vue";
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
/** 区分已有失效记录但没有本地正文的步骤，供界面提示恢复或重生成。 */
const staleWithoutContent = (operation: string) =>
  workflowSteps.value.some(
    (step) => step.operation === operation && step.state === "stale" && step.result === null,
  );
/** 从当前目标与生成选项构造输入快照，用于判断现有结果是否匹配；计算本身不提交请求。 */
const currentNonfunctionalCaseSelection = computed(() => ({ method_name: methodName.value }));
/** 仅展示当前工作流及匹配选择条件的结果或执行状态，避免切换目标后混用其他目标的内容。 */
const caseResultVisible = computed(() =>
  hasVisibleResultFor("nonfunctional_case", currentNonfunctionalCaseSelection.value),
);
/** 仅展示当前工作流及匹配选择条件的结果或执行状态，避免切换目标后混用其他目标的内容。 */
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
/** 只为当前可见且已失效的结果展示参考提示，隐藏结果不产生误导性过期警告。 */
const caseWarning = computed(() =>
  caseResultVisible.value ? staleWarning("nonfunctional_case") : "",
);
/** 用当前用例选择条件核对已保存结果，输入改变时标记失效而不丢弃旧正文。 */
const markCaseStale = () =>
  reconcileStepSelection("nonfunctional_case", currentNonfunctionalCaseSelection.value, false);
/**
 * 提交 nonfunctional_info 流式工作流；仅成功后更新页面结果，失败保留原结果并显示错误。
 * @param regenerate 沿用当前 TypeScript 类型约束的输入。
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
 * 提交 nonfunctional_case 流式工作流；仅成功后更新页面结果，失败保留原结果并显示错误。
 * @param regenerate 沿用当前 TypeScript 类型约束的输入。
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
/** 通过工作流替换确认后重执行对应步骤，使用当前选择条件并让下游按依赖规则失效。 */
const regenerateAnalysis = () =>
  regenerateStep("nonfunctional_info", () => analyzeRequirements(true));
/** 通过工作流替换确认后重执行对应步骤，使用当前选择条件并让下游按依赖规则失效。 */
const regenerateCases = () => regenerateStep("nonfunctional_case", () => generateCases(true));
/** 先恢复工作流状态，再按产物及其选择条件填充页面，进入页面本身不启动模型。 */
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

onMounted(restoreWorkflow);
/** 用户确认后清空本次用例展示和会话步骤，不发送服务端产物删除请求。 */
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
