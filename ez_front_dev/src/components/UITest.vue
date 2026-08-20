<template>
  <el-row><span class="cn_name">请选择本页使用的大语言模型</span></el-row>
  <el-row>
    <el-segmented v-model="llm" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" />
  </el-row>
  <el-row>
    <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning" plain round @click="analyzeUi">
      开始前端UI测试分析
    </el-button>
  </el-row>
  <LlmWorkflowExecution v-if="activeOperation === 'ui_info'" v-bind="executionProps" @cancel="cancel" />

  <template v-if="showAnalysis">
    <el-row><span class="cn_name">LLM从业务文档中找到的前端 UI 设计内容</span></el-row>
    <el-row class="result-row">
      <el-input v-model="uiInfo" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly />
    </el-row>
    <el-row>
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning" plain round @click="generateCases">
        生成前端UI测试用例
      </el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'ui_case'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="showCases">
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
import { getCurrentInstance, ref } from "vue";
import { Right } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import LlmWorkflowExecution from "@/components/LlmWorkflowExecution.vue";
import { useLlmWorkflow } from "@/composables/useLlmWorkflow";
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
const { isRunning, result, error, activeOperation, executionProps, runWorkflow, cancel, resetStream } =
  useLlmWorkflow(requestUrl, projectId);

const analyzeUi = async () => {
  showAnalysis.value = false;
  const succeeded = await runWorkflow("ui_info", llm.value, {}, {
    answerTitle: "前端 UI 设计分析（流式输出）",
    successTitle: "前端 UI 设计分析已完成",
  });
  if (succeeded && typeof result.value === "string") {
    uiInfo.value = result.value;
    showAnalysis.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
};

const generateCases = async () => {
  showCases.value = false;
  const succeeded = await runWorkflow("ui_case", llm.value, { info: uiInfo.value }, {
    answerTitle: "前端 UI 测试用例（流式输出）",
    successTitle: "前端 UI 测试用例已生成",
  });
  if (succeeded) {
    const value = result.value as UiCaseResult;
    knowledge.value = value.ui_test_knowledge;
    testCases.value = value.test_cases;
    showCases.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
};

const reset = () => {
  resetStream();
  showCases.value = false;
  knowledge.value = "";
  testCases.value = "";
};
</script>

<style scoped>
.action-button { width: 190px; margin-top: 10px; }
.result-row { margin-top: 10px; }
.result-input { width: 99%; }
.cn_name { font-family: "Ali"; }
.result-title { margin-top: 10px; color: #06b009; font-family: "Ali"; }
</style>
