<template>
  <WorkflowStepper :steps="workflowSteps" :active-operation="activeOperation" />
  <el-alert v-if="staleWarning('ui_info')" :title="staleWarning('ui_info')" type="warning" show-icon :closable="false" />
  <el-row><span class="cn_name">请选择本页使用的大语言模型</span></el-row>
  <el-row>
    <el-segmented v-model="llm" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" />
  </el-row>
  <el-row>
    <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning || !canRunStep('ui_info')" plain round @click="analyzeUi(false)">
      {{ hasSavedResult("ui_info") ? "继续前端 UI 测试分析" : "开始前端 UI 测试分析" }}
    </el-button>
    <el-button v-if="hasSavedResult('ui_info')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateAnalysis">
      重新生成前端 UI 测试分析
    </el-button>
  </el-row>
  <LlmWorkflowExecution v-if="activeOperation === 'ui_info'" v-bind="executionProps" @cancel="cancel" />

  <template v-if="showAnalysis">
    <el-row><span class="cn_name">LLM从业务文档中找到的前端 UI 设计内容</span></el-row>
    <el-row class="result-row">
      <el-input v-model="uiInfo" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly />
    </el-row>
    <el-row>
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning || !canRunStep('ui_case')" plain round @click="generateCases(false)">
        {{ hasSavedResult("ui_case") ? "继续查看前端 UI 测试用例" : "生成前端 UI 测试用例" }}
      </el-button>
      <el-button v-if="hasSavedResult('ui_case')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateCases">
        重新生成测试用例
      </el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'ui_case'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="showCases">
    <el-alert v-if="staleWarning('ui_case')" :title="staleWarning('ui_case')" type="warning" show-icon :closable="false" />
    <el-divider />
    <el-row><span class="cn_name">知识库中的前端 UI 测试知识</span></el-row>
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
  steps: workflowSteps, hydrateWorkflow, canRunStep, regenerateStep,
  resetStep, resultFor, hasSavedResult, staleWarning,
} = testWorkflow;
const { isRunning, result, error, activeOperation, executionProps, runWorkflow, cancel, resetStream } =
  useLlmWorkflow(requestUrl, projectId, testWorkflow);

const analyzeUi = async (regenerate = false): Promise<boolean> => {
  const succeeded = await runWorkflow("ui_info", llm.value, {}, {
    answerTitle: "前端 UI 设计分析（流式输出）",
    successTitle: "前端 UI 设计分析已完成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded && typeof result.value === "string") {
    uiInfo.value = result.value;
    showAnalysis.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
  return succeeded;
};

const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("ui_case")) {
    ElMessage.warning("请先完成有效的 UI 设计分析");
    return false;
  }
  const succeeded = await runWorkflow("ui_case", llm.value, { info: uiInfo.value }, {
    answerTitle: "前端 UI 测试用例（流式输出）",
    successTitle: "前端 UI 测试用例已生成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded) {
    const value = result.value as UiCaseResult;
    knowledge.value = value.ui_test_knowledge;
    testCases.value = value.test_cases;
    showCases.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
  return succeeded;
};

const regenerateAnalysis = () =>
  regenerateStep("ui_info", () => analyzeUi(true));
const regenerateCases = () =>
  regenerateStep("ui_case", () => generateCases(true));

onMounted(async () => {
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
});

const reset = () => {
  resetStream();
  showCases.value = false;
  knowledge.value = "";
  testCases.value = "";
  resetStep("ui_case");
};
</script>

<style scoped>
.action-button { width: 190px; margin-top: 10px; }
.result-row { margin-top: 10px; }
.result-input { width: 99%; }
.cn_name { font-family: "Ali"; }
.result-title { margin-top: 10px; color: #06b009; font-family: "Ali"; }
</style>
