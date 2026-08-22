<template>
  <WorkflowStepper :steps="workflowSteps" :active-operation="activeOperation" />
  <el-alert v-if="staleWarning('functional_info')" :title="staleWarning('functional_info')" type="warning" show-icon :closable="false" />
  <el-row><span class="cn_name">请选择本页使用的大语言模型</span></el-row>
  <el-row>
    <el-segmented v-model="llm" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" />
  </el-row>
  <el-row>
    <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning || !canRunStep('functional_info')" plain round @click="analyzeUseCases(false)">
      {{ hasSavedResult("functional_info") ? "继续系统功能性测试分析" : "开始系统功能性测试分析" }}
    </el-button>
    <el-button v-if="hasSavedResult('functional_info')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateAnalysis">
      重新生成系统功能性测试分析
    </el-button>
  </el-row>
  <LlmWorkflowExecution v-if="activeOperation === 'functional_info'" v-bind="executionProps" @cancel="cancel" />

  <template v-if="showAnalysis">
    <el-row><span class="cn_name">LLM从业务需求文档中找到的全部用例内容</span></el-row>
    <el-row class="result-row">
      <el-input v-model="useCasesInfo" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly />
    </el-row>
    <el-row class="result-row"><span class="cn_name">请选择要进行功能性测试的用例</span></el-row>
    <el-row class="result-row">
      <el-select v-model="useCaseName" placeholder="请选择用例" style="width: 260px">
        <el-option v-for="useCase in useCases" :key="useCase" :label="useCase" :value="useCase" />
      </el-select>
    </el-row>
    <el-row class="result-row"><span class="cn_name">请选择生成格式</span></el-row>
    <el-row class="result-row">
      <el-radio-group v-model="outputFormat">
        <el-radio-button v-for="(format, index) in outputFormats" :key="format" :label="format" :value="index" />
      </el-radio-group>
    </el-row>
    <el-row>
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning || !canRunStep('functional_case')" plain round @click="generateCases(false)">
        {{ hasSavedResult("functional_case") ? "继续查看功能性测试用例" : "生成功能性测试用例" }}
      </el-button>
      <el-button v-if="hasSavedResult('functional_case')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateCases">
        重新生成功能性测试用例
      </el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'functional_case'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="showCases">
    <el-alert v-if="staleWarning('functional_case')" :title="staleWarning('functional_case')" type="warning" show-icon :closable="false" />
    <el-divider />
    <el-row><span class="cn_name">知识库中的系统功能性测试知识</span></el-row>
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
const knowledge = ref("");
const testCases = ref("");
const testWorkflow = useTestWorkflow({
  baseUrl: requestUrl,
  pid: projectId,
  steps: [
    { operation: "functional_info", label: "功能需求分析", artifactKey: "functional_info" },
    { operation: "functional_case", label: "功能测试用例", artifactKey: "functional_case", dependsOn: ["functional_info"], selectionFields: ["test_type", "output_type", "use_case_name"], persistResult: false },
  ],
});
const {
  steps: workflowSteps, hydrateWorkflow, canRunStep, regenerateStep,
  resetStep, resultFor, selectionFor, hasSavedResult, staleWarning,
} = testWorkflow;
const { isRunning, result, error, activeOperation, executionProps, runWorkflow, cancel, resetStream } =
  useLlmWorkflow(requestUrl, projectId, testWorkflow);

const analyzeUseCases = async (regenerate = false): Promise<boolean> => {
  const succeeded = await runWorkflow("functional_info", llm.value, {}, {
    answerTitle: "系统功能性需求分析（流式输出）",
    successTitle: "系统功能性需求分析已完成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded) {
    const value = result.value as FunctionalAnalysisResult;
    useCasesInfo.value = value.text_info;
    useCases.value = value.list_info.use_case_list;
    showAnalysis.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
  return succeeded;
};

const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("functional_case")) {
    ElMessage.warning("请先完成有效的功能需求分析");
    return false;
  }
  if (!useCaseName.value) {
    ElMessage.warning("请先选择要测试的用例（故事）");
    return false;
  }
  const succeeded = await runWorkflow("functional_case", llm.value, {
    info: useCasesInfo.value,
    test_type: 1,
    output_type: outputFormat.value,
    use_case_name: useCaseName.value,
  }, {
    answerTitle: "系统功能性测试用例（流式输出）",
    successTitle: "系统功能性测试用例已生成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded) {
    const value = result.value as FunctionalCaseResult;
    knowledge.value = value.functional_test_knowledge;
    testCases.value = value.test_cases;
    showCases.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
  return succeeded;
};

const regenerateAnalysis = () =>
  regenerateStep("functional_info", () => analyzeUseCases(true));
const regenerateCases = () =>
  regenerateStep("functional_case", () => generateCases(true));

onMounted(async () => {
  await hydrateWorkflow();
  const savedInfo = resultFor<FunctionalAnalysisResult>("functional_info");
  const savedCases = resultFor<FunctionalCaseResult>("functional_case");
  const savedSelection = selectionFor("functional_case");
  if (savedInfo) {
    useCasesInfo.value = savedInfo.text_info;
    useCases.value = savedInfo.list_info.use_case_list;
    showAnalysis.value = true;
  }
  if (typeof savedSelection.use_case_name === "string") useCaseName.value = savedSelection.use_case_name;
  if (typeof savedSelection.output_type === "number") outputFormat.value = savedSelection.output_type;
  if (savedCases) {
    knowledge.value = savedCases.functional_test_knowledge;
    testCases.value = savedCases.test_cases;
    showCases.value = true;
  }
});

const reset = () => {
  resetStream();
  showCases.value = false;
  knowledge.value = "";
  testCases.value = "";
  resetStep("functional_case");
};
</script>

<style scoped>
.action-button { min-width: 190px; margin-top: 10px; }
.result-row { margin-top: 10px; }
.result-input { width: 99%; }
.cn_name { font-family: "Ali"; }
.result-title { margin-top: 10px; color: #06b009; font-family: "Ali"; }
</style>
