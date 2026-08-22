<template>
  <WorkflowStepper :steps="workflowSteps" :active-operation="activeOperation" />
  <el-alert v-if="staleWarning('db_info')" :title="staleWarning('db_info')" type="warning" show-icon :closable="false" />
  <el-row><span class="cn_name">请选择本页使用的大语言模型</span></el-row>
  <el-row>
    <el-segmented v-model="llm" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" />
  </el-row>
  <el-row>
    <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning || !canRunStep('db_info')" plain round @click="analyzeDatabase(false)">
      {{ hasSavedResult("db_info") ? "继续数据库测试分析" : "开始数据库测试分析" }}
    </el-button>
    <el-button v-if="hasSavedResult('db_info')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateAnalysis">
      重新生成数据库测试分析
    </el-button>
  </el-row>
  <LlmWorkflowExecution v-if="activeOperation === 'db_info'" v-bind="executionProps" @cancel="cancel" />

  <template v-if="showAnalysis">
    <el-row><span class="cn_name">LLM从业务文档中找到的数据库设计内容</span></el-row>
    <el-row class="result-row">
      <el-input v-model="databaseInfo" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly />
    </el-row>
    <el-row>
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning || !canRunStep('db_case')" plain round @click="generateCases(false)">
        {{ hasSavedResult("db_case") ? "继续查看数据库测试用例" : "生成数据库测试用例" }}
      </el-button>
      <el-button v-if="hasSavedResult('db_case')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateCases">
        重新生成测试用例
      </el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'db_case'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="showCases">
    <el-alert v-if="staleWarning('db_case')" :title="staleWarning('db_case')" type="warning" show-icon :closable="false" />
    <el-divider />
    <el-row><span class="cn_name">知识库中的数据库测试知识</span></el-row>
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
const databaseInfo = ref("");
const knowledge = ref("");
const testCases = ref("");
const testWorkflow = useTestWorkflow({
  baseUrl: requestUrl,
  pid: projectId,
  steps: [
    { operation: "db_info", label: "数据库设计分析", artifactKey: "db_info" },
    { operation: "db_case", label: "数据库测试用例", artifactKey: "db_case", dependsOn: ["db_info"] },
  ],
});
const {
  steps: workflowSteps, hydrateWorkflow, canRunStep, regenerateStep,
  resetStep, resultFor, hasSavedResult, staleWarning,
} = testWorkflow;
const { isRunning, result, error, activeOperation, executionProps, runWorkflow, cancel, resetStream } =
  useLlmWorkflow(requestUrl, projectId, testWorkflow);

const analyzeDatabase = async (regenerate = false): Promise<boolean> => {
  const succeeded = await runWorkflow("db_info", llm.value, {}, {
    answerTitle: "数据库设计分析（流式输出）",
    successTitle: "数据库设计分析已完成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded && typeof result.value === "string") {
    databaseInfo.value = result.value;
    showAnalysis.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
  return succeeded;
};

const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("db_case")) {
    ElMessage.warning("请先完成有效的数据库设计分析");
    return false;
  }
  const succeeded = await runWorkflow("db_case", llm.value, { info: databaseInfo.value }, {
    answerTitle: "数据库测试用例（流式输出）",
    successTitle: "数据库测试用例已生成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded) {
    const value = result.value as DatabaseCaseResult;
    knowledge.value = value.db_test_knowledge;
    testCases.value = value.test_cases;
    showCases.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
  return succeeded;
};

const regenerateAnalysis = () =>
  regenerateStep("db_info", () => analyzeDatabase(true));
const regenerateCases = () =>
  regenerateStep("db_case", () => generateCases(true));

onMounted(async () => {
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
});

const reset = () => {
  resetStream();
  showCases.value = false;
  knowledge.value = "";
  testCases.value = "";
  resetStep("db_case");
};
</script>

<style scoped>
.action-button { width: 190px; margin-top: 10px; }
.result-row { margin-top: 10px; }
.result-input { width: 99%; }
.cn_name { font-family: "Ali"; }
.result-title { margin-top: 10px; color: #06b009; font-family: "Ali"; }
</style>
