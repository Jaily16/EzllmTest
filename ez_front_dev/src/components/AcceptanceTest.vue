<template>
  <WorkflowStepper :steps="workflowSteps" :active-operation="activeOperation" />
  <el-alert v-if="staleWarning('acceptance_info')" :title="staleWarning('acceptance_info')" type="warning" show-icon :closable="false" />
  <el-row><span class="cn_name">请选择本页使用的大语言模型</span></el-row>
  <el-row>
    <el-segmented v-model="llm" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" />
  </el-row>
  <el-row>
    <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning || !canRunStep('acceptance_info')" plain round @click="analyzeRequirements(false)">
      {{ hasSavedResult("acceptance_info") ? "继续验收测试分析" : "开始验收测试分析" }}
    </el-button>
    <el-button v-if="hasSavedResult('acceptance_info')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateAnalysis">
      重新生成验收测试分析
    </el-button>
  </el-row>
  <LlmWorkflowExecution v-if="activeOperation === 'acceptance_info'" v-bind="executionProps" @cancel="cancel" />

  <template v-if="showAnalysis">
    <el-row><span class="cn_name">LLM从业务需求文档中找到的验收测试相关内容</span></el-row>
    <el-row class="result-row">
      <el-input v-model="requirementInfo" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly />
    </el-row>
    <el-row>
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning || !canRunStep('acceptance_case')" plain round @click="generateCases(false)">
        {{ hasSavedResult("acceptance_case") ? "继续查看验收测试用例" : "生成验收测试用例" }}
      </el-button>
      <el-button v-if="hasSavedResult('acceptance_case')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateCases">
        重新生成测试用例
      </el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'acceptance_case'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="showCases">
    <el-alert v-if="staleWarning('acceptance_case')" :title="staleWarning('acceptance_case')" type="warning" show-icon :closable="false" />
    <el-divider />
    <el-row><span class="cn_name">知识库中的验收测试知识</span></el-row>
    <el-row class="result-row">
      <el-input v-model="knowledge" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly />
    </el-row>
    <el-row><span class="result-title">LLM生成的测试用例如下</span></el-row>
    <el-row class="result-row">
      <el-input v-model="testCases" class="result-input" :autosize="{ minRows: 2, maxRows: 50 }" type="textarea" readonly />
    </el-row>
    <el-button type="info" @click="reset">重置</el-button>
  </template>
</template>

<script lang="ts" setup>
import { getCurrentInstance, onMounted, ref } from "vue";
import { Refresh, Right } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import LlmWorkflowExecution from "@/components/LlmWorkflowExecution.vue";
import WorkflowStepper from "@/components/WorkflowStepper.vue";
import { useLlmWorkflow } from "@/composables/useLlmWorkflow";
import { useTestWorkflow } from "@/composables/useTestWorkflow";
import { DEFAULT_MODEL, MODEL_OPTIONS } from "@/config/models";

interface AcceptanceCaseResult {
  acceptance_test_knowledge: string;
  test_cases: string;
}

const instance = getCurrentInstance();
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");
const llm = ref(DEFAULT_MODEL);
const showAnalysis = ref(false);
const showCases = ref(false);
const requirementInfo = ref("");
const knowledge = ref("");
const testCases = ref("");
const testWorkflow = useTestWorkflow({
  baseUrl: requestUrl,
  pid: projectId,
  steps: [
    { operation: "acceptance_info", label: "验收需求分析", artifactKey: "acceptance_info" },
    { operation: "acceptance_case", label: "验收测试用例", artifactKey: "acceptance_case", dependsOn: ["acceptance_info"] },
  ],
});
const {
  steps: workflowSteps, hydrateWorkflow, canRunStep, regenerateStep,
  resetStep, resultFor, hasSavedResult, staleWarning,
} = testWorkflow;
const { isRunning, result, error, activeOperation, executionProps, runWorkflow, cancel, resetStream } =
  useLlmWorkflow(requestUrl, projectId, testWorkflow);

const analyzeRequirements = async (regenerate = false): Promise<boolean> => {
  const succeeded = await runWorkflow("acceptance_info", llm.value, {}, {
    answerTitle: "验收测试需求分析（流式输出）",
    successTitle: "验收测试需求分析已完成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded && typeof result.value === "string") {
    requirementInfo.value = result.value;
    showAnalysis.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
  return succeeded;
};

const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("acceptance_case")) {
    ElMessage.warning("请先完成有效的验收需求分析");
    return false;
  }
  const succeeded = await runWorkflow("acceptance_case", llm.value, { info: requirementInfo.value }, {
    answerTitle: "验收测试用例（流式输出）",
    successTitle: "验收测试用例已生成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded) {
    const value = result.value as AcceptanceCaseResult;
    knowledge.value = value.acceptance_test_knowledge;
    testCases.value = value.test_cases;
    showCases.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
  return succeeded;
};

const regenerateAnalysis = () =>
  regenerateStep("acceptance_info", () => analyzeRequirements(true));
const regenerateCases = () =>
  regenerateStep("acceptance_case", () => generateCases(true));

onMounted(async () => {
  await hydrateWorkflow();
  const savedInfo = resultFor<string>("acceptance_info");
  const savedCases = resultFor<AcceptanceCaseResult>("acceptance_case");
  if (savedInfo) {
    requirementInfo.value = savedInfo;
    showAnalysis.value = true;
  }
  if (savedCases) {
    knowledge.value = savedCases.acceptance_test_knowledge;
    testCases.value = savedCases.test_cases;
    showCases.value = true;
  }
});

const reset = () => {
  resetStream();
  showCases.value = false;
  knowledge.value = "";
  testCases.value = "";
  resetStep("acceptance_case");
};
</script>

<style scoped>
.action-button { width: 190px; margin-top: 10px; }
.result-row { margin-top: 10px; }
.result-input { width: 99%; }
.cn_name { font-family: "Ali"; }
.result-title { margin-top: 10px; color: #06b009; font-family: "Ali"; }
</style>
