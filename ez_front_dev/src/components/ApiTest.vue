<template>
  <el-row><span class="cn_name">请选择本页使用的大语言模型</span></el-row>
  <el-row>
    <el-segmented v-model="llm" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" />
  </el-row>
  <el-row>
    <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning" plain round @click="analyzeApis">
      开始api接口测试分析
    </el-button>
  </el-row>
  <LlmWorkflowExecution v-if="activeOperation === 'api_info'" v-bind="executionProps" @cancel="cancel" />

  <template v-if="showAnalysis">
    <el-row><span class="cn_name">LLM从业务文档中找到的所有 API 接口内容</span></el-row>
    <el-row class="result-row">
      <el-input v-model="apisInfo" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly />
    </el-row>
    <el-row class="result-row"><span class="cn_name">可选择某个 API，或为全部 API 生成测试用例</span></el-row>
    <el-row class="result-row">
      <el-select v-model="apiName" placeholder="请选择 API" style="width: 260px">
        <el-option v-for="api in apis" :key="api" :label="api" :value="api" />
      </el-select>
    </el-row>
    <el-row class="result-row"><span class="cn_name">请选择生成格式</span></el-row>
    <el-row class="result-row">
      <el-radio-group v-model="outputFormat">
        <el-radio-button v-for="(format, index) in outputFormats" :key="format" :label="format" :value="index" />
      </el-radio-group>
    </el-row>
    <el-row>
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning" plain round @click="generateCases(0)">
        全部api接口测试用例
      </el-button>
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning" plain round @click="generateCases(1)">
        生成所选api测试用例
      </el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'api_case'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="showCases">
    <el-divider />
    <el-row><span class="cn_name">知识库中的 API 接口测试知识</span></el-row>
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

interface ApiAnalysisResult {
  apis_info: string;
  list: { api_list: string[] };
}
interface ApiCaseResult {
  api_test_knowledge: string;
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
const apisInfo = ref("");
const apiName = ref("");
const apis = ref<string[]>([]);
const knowledge = ref("");
const testCases = ref("");
const { isRunning, result, error, activeOperation, executionProps, runWorkflow, cancel, resetStream } =
  useLlmWorkflow(requestUrl, projectId);

const analyzeApis = async () => {
  showAnalysis.value = false;
  const succeeded = await runWorkflow("api_info", llm.value, {}, {
    answerTitle: "API 接口分析（流式输出）",
    successTitle: "API 接口分析已完成",
  });
  if (succeeded) {
    const value = result.value as ApiAnalysisResult;
    apisInfo.value = value.apis_info;
    apis.value = value.list.api_list;
    showAnalysis.value = true;
  } else if (error.value) {
    ElMessage.error(error.value.message);
  }
};

const generateCases = async (testType: number) => {
  if (testType === 1 && !apiName.value) {
    ElMessage.warning("请先选择要测试的 API 接口");
    return;
  }
  showCases.value = false;
  const succeeded = await runWorkflow("api_case", llm.value, {
    info: apisInfo.value,
    test_type: testType,
    output_type: outputFormat.value,
    api_name: testType === 1 ? apiName.value : "",
  }, {
    answerTitle: "API 接口测试用例（流式输出）",
    successTitle: "API 接口测试用例已生成",
  });
  if (succeeded) {
    const value = result.value as ApiCaseResult;
    knowledge.value = value.api_test_knowledge;
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
.action-button { min-width: 190px; margin-top: 10px; margin-right: 10px; }
.result-row { margin-top: 10px; }
.result-input { width: 99%; }
.cn_name { font-family: "Ali"; }
.result-title { margin-top: 10px; color: #06b009; font-family: "Ali"; }
</style>
