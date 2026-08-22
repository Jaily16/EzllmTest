<template>
  <WorkflowStepper :steps="workflowSteps" :active-operation="activeOperation" />
  <el-alert v-if="staleWarning('nonfunctional_info')" :title="staleWarning('nonfunctional_info')" type="warning" show-icon :closable="false" />
  <el-row><span class="cn_name">请选择本页使用的大语言模型</span></el-row>
  <el-row>
    <el-segmented v-model="llm" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" />
  </el-row>
  <el-row>
    <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning || !canRunStep('nonfunctional_info')" plain round @click="analyzeRequirements(false)">
      {{ hasSavedResult("nonfunctional_info") ? "继续系统非功能性测试分析" : "开始系统非功能性测试分析" }}
    </el-button>
    <el-button v-if="hasSavedResult('nonfunctional_info')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateAnalysis">
      重新生成非功能性测试分析
    </el-button>
  </el-row>
  <LlmWorkflowExecution v-if="activeOperation === 'nonfunctional_info'" v-bind="executionProps" @cancel="cancel" />

  <template v-if="showAnalysis">
    <el-row><span class="cn_name">LLM从业务需求文档中找到的非功能性需求</span></el-row>
    <el-row class="result-row">
      <el-input v-model="nonfunctionalInfo" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly />
    </el-row>
    <el-row class="result-row"><span class="cn_name">请选择非功能性测试类型</span></el-row>
    <el-row class="result-row">
      <el-select v-model="methodName" placeholder="请选择测试类型" style="width: 260px">
        <el-option v-for="method in methods" :key="method" :label="method" :value="method" />
      </el-select>
    </el-row>
    <el-row>
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning || !canRunStep('nonfunctional_case')" plain round @click="generateCases(false)">
        {{ hasSavedResult("nonfunctional_case") ? "继续查看相应测试用例" : "生成相应测试用例" }}
      </el-button>
      <el-button v-if="hasSavedResult('nonfunctional_case')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateCases">
        重新生成相应测试用例
      </el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'nonfunctional_case'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="showCases">
    <el-alert v-if="staleWarning('nonfunctional_case')" :title="staleWarning('nonfunctional_case')" type="warning" show-icon :closable="false" />
    <el-divider />
    <el-row><span class="cn_name">知识库中的 {{ methodName }} 知识</span></el-row>
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
const nonfunctionalInfo = ref("");
const knowledge = ref("");
const testCases = ref("");
const testWorkflow = useTestWorkflow({
  baseUrl: requestUrl,
  pid: projectId,
  steps: [
    { operation: "nonfunctional_info", label: "非功能需求分析", artifactKey: "nonfunctional_info" },
    { operation: "nonfunctional_case", label: "非功能测试用例", artifactKey: "nonfunctional_case", dependsOn: ["nonfunctional_info"], selectionFields: ["method_name"], persistResult: false },
  ],
});
const {
  steps: workflowSteps, hydrateWorkflow, canRunStep, regenerateStep,
  resetStep, resultFor, selectionFor, hasSavedResult, staleWarning,
} = testWorkflow;
const { isRunning, result, error, activeOperation, executionProps, runWorkflow, cancel, resetStream } =
  useLlmWorkflow(requestUrl, projectId, testWorkflow);

const analyzeRequirements = async (regenerate = false): Promise<boolean> => {
  const succeeded = await runWorkflow("nonfunctional_info", llm.value, {}, {
    answerTitle: "非功能性需求分析（流式输出）",
    successTitle: "非功能性需求分析已完成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded) {
    const value = result.value as NonfunctionalAnalysisResult;
    nonfunctionalInfo.value = value.nonfunctional_info;
    methods.value = value.list.method_list;
    showAnalysis.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
  return succeeded;
};

const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("nonfunctional_case")) {
    ElMessage.warning("请先完成有效的非功能需求分析");
    return false;
  }
  if (!methodName.value) {
    ElMessage.warning("请先选择非功能性测试类型");
    return false;
  }
  const succeeded = await runWorkflow("nonfunctional_case", llm.value, {
    info: nonfunctionalInfo.value,
    method_name: methodName.value,
  }, {
    answerTitle: methodName.value + "用例（流式输出）",
    successTitle: methodName.value + "用例已生成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded) {
    const value = result.value as NonfunctionalCaseResult;
    knowledge.value = value.nonfunctional_test_knowledge;
    testCases.value = value.test_cases;
    showCases.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
  return succeeded;
};

const regenerateAnalysis = () =>
  regenerateStep("nonfunctional_info", () => analyzeRequirements(true));
const regenerateCases = () =>
  regenerateStep("nonfunctional_case", () => generateCases(true));

onMounted(async () => {
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
});

const reset = () => {
  resetStream();
  showCases.value = false;
  knowledge.value = "";
  testCases.value = "";
  resetStep("nonfunctional_case");
};
</script>

<style scoped>
.action-button { min-width: 190px; margin-top: 10px; }
.result-row { margin-top: 10px; }
.result-input { width: 99%; }
.cn_name { font-family: "Ali"; }
.result-title { margin-top: 10px; color: #06b009; font-family: "Ali"; }
</style>
