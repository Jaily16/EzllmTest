<template>
  <el-row><span class="cn_name">请选择本页使用的大语言模型</span></el-row>
  <el-row><el-segmented v-model="llm" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" /></el-row>
  <el-row><span class="hint">建议先完成单元测试分析；若尚未完成，系统将在本次工作流中自动补充。</span></el-row>
  <el-row>
    <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning" plain round @click="analyzeMenu">开始集成测试分析</el-button>
  </el-row>
  <LlmWorkflowExecution v-if="activeOperation === 'integration_menu'" v-bind="executionProps" @cancel="cancel" />

  <template v-if="menuResult">
    <el-row class="result-row"><span class="cn_name">根据 LLM 分析，请选择要进行的集成测试类型</span></el-row>
    <el-row class="result-row">
      <el-radio-group v-model="integrationType" @change="selectIntegrationType">
        <el-radio-button v-for="type in availableTypes" :key="type" :label="type" :value="type" />
      </el-radio-group>
    </el-row>
    <el-row v-if="needsUnit" class="result-row"><span class="cn_name">请选择要进行集成测试的单元</span></el-row>
    <el-row v-if="needsUnit" class="result-row">
      <el-select v-model="integrationUnit" placeholder="请选择集成测试单元" style="width: 320px">
        <el-option v-for="item in integrationUnits" :key="item" :label="item" :value="item" />
      </el-select>
    </el-row>
    <el-row v-if="integrationType">
      <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning" plain round @click="analyzeIntegration">利用 LLM 进一步分析</el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'integration_info'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="integrationInfo">
    <el-divider />
    <el-row><span class="cn_name">LLM 从业务文档中找出的集成测试对象相关内容</span></el-row>
    <el-row class="result-row"><el-input v-model="integrationInfo" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly /></el-row>
    <el-row class="result-row"><span class="cn_name">请选择集成测试策略</span></el-row>
    <el-row class="result-row">
      <el-radio-group v-model="strategyIndex">
        <el-radio-button v-for="(item, index) in strategies" :key="item" :label="item" :value="index" />
      </el-radio-group>
    </el-row>
    <el-row class="result-row"><span class="cn_name">请选择测试用例输出格式</span></el-row>
    <el-row class="result-row">
      <el-radio-group v-model="outputFormat">
        <el-radio-button v-for="(format, index) in outputFormats" :key="format" :label="format" :value="index" />
      </el-radio-group>
    </el-row>
    <el-row>
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning" plain round @click="generateCases">生成集成测试用例</el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'integration_case'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="caseResult">
    <el-divider />
    <el-row><span class="cn_name">知识库中的集成测试知识</span></el-row>
    <el-row class="result-row"><el-input v-model="caseResult.integration_test_knowledge" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly /></el-row>
    <el-row class="result-row"><span class="cn_name">知识库中的所选集成策略知识</span></el-row>
    <el-row class="result-row"><el-input v-model="caseResult.integration_strategy_knowledge" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly /></el-row>
    <el-row class="result-row"><span class="cn_name">知识库中的静态黑盒测试知识</span></el-row>
    <el-row class="result-row"><el-input v-model="caseResult.static_blackbox_knowledge" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly /></el-row>
    <el-row><span class="result-title">LLM 生成的测试用例如下</span></el-row>
    <el-row class="result-row"><el-input v-model="caseResult.test_cases" class="result-input" :autosize="{ minRows: 2, maxRows: 50 }" type="textarea" readonly /></el-row>
    <el-button type="info" @click="resetCases">重置</el-button>
  </template>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, ref } from "vue";
import { Right } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import LlmWorkflowExecution from "@/components/LlmWorkflowExecution.vue";
import { useLlmWorkflow } from "@/composables/useLlmWorkflow";
import { DEFAULT_MODEL, MODEL_OPTIONS } from "@/config/models";

interface IntegrationMenu {
  subsystem_integration_test: boolean;
  subsystem_integration_menu: { subsystem_test: boolean; subsystem_list: string[] };
  module_integration_menu: { module_test: boolean; module_list: string[] };
  class_integration_menu: { class_test: boolean; class_list: string[] };
}
interface IntegrationCaseResult {
  integration_test_knowledge: string;
  static_blackbox_knowledge: string;
  integration_strategy_knowledge: string;
  test_cases: string;
}

const instance = getCurrentInstance();
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");
const llm = ref(DEFAULT_MODEL);
const menuResult = ref<IntegrationMenu | null>(null);
const integrationType = ref("");
const integrationUnit = ref("");
const integrationInfo = ref("");
const strategyIndex = ref(-1);
const outputFormat = ref(0);
const caseResult = ref<IntegrationCaseResult | null>(null);
const allTypes = ["系统集成测试", "子系统间集成测试", "子系统内集成测试", "模块内集成测试", "类(class)内集成测试"];
const strategies = [
  "大爆炸集成(Big Bang Integration)",
  "自顶向下集成(Top-Down Integration)",
  "自底向上集成(Bottom-up Integration)",
  "三明治集成(Sandwich Integration)",
];
const outputFormats = [".txt(文字形式)", ".md(表格形式)", ".xml", ".csv"];
const { isRunning, result, error, activeOperation, executionProps, runWorkflow, cancel, resetStream } = useLlmWorkflow(requestUrl, projectId);

const availableTypes = computed(() => {
  const menu = menuResult.value;
  if (!menu) return [];
  const values: string[] = [menu.subsystem_integration_test ? allTypes[1] : allTypes[0]];
  if (menu.subsystem_integration_menu.subsystem_test && menu.subsystem_integration_menu.subsystem_list.length) values.push(allTypes[2]);
  if (menu.module_integration_menu.module_test && menu.module_integration_menu.module_list.length) values.push(allTypes[3]);
  if (menu.class_integration_menu.class_test && menu.class_integration_menu.class_list.length) values.push(allTypes[4]);
  return values;
});

const integrationTypeIndex = computed(() => allTypes.indexOf(integrationType.value));
const needsUnit = computed(() => integrationTypeIndex.value >= 2);
const integrationUnits = computed(() => {
  const menu = menuResult.value;
  if (!menu) return [];
  if (integrationTypeIndex.value === 2) return menu.subsystem_integration_menu.subsystem_list;
  if (integrationTypeIndex.value === 3) return menu.module_integration_menu.module_list;
  if (integrationTypeIndex.value === 4) return menu.class_integration_menu.class_list;
  return [];
});

const analyzeMenu = async () => {
  integrationType.value = "";
  integrationUnit.value = "";
  integrationInfo.value = "";
  caseResult.value = null;
  const succeeded = await runWorkflow("integration_menu", llm.value, {}, {
    answerTitle: "集成测试类型分析（流式输出）",
    successTitle: "集成测试类型分析已完成",
  });
  if (succeeded) menuResult.value = result.value as IntegrationMenu;
  else if (error.value) ElMessage.error(error.value.message);
};

const selectIntegrationType = () => {
  integrationUnit.value = "";
  integrationInfo.value = "";
  caseResult.value = null;
};

const analyzeIntegration = async () => {
  if (integrationTypeIndex.value < 0) {
    ElMessage.warning("请先选择集成测试类型");
    return;
  }
  if (needsUnit.value && !integrationUnit.value) {
    ElMessage.warning("请先选择要进行集成测试的单元");
    return;
  }
  integrationInfo.value = "";
  caseResult.value = null;
  const succeeded = await runWorkflow("integration_info", llm.value, {
    integration_type: integrationTypeIndex.value,
    name: needsUnit.value ? integrationUnit.value : "",
  }, {
    answerTitle: "集成测试对象分析（流式输出）",
    successTitle: "集成测试对象分析已完成",
  });
  if (succeeded) {
    integrationInfo.value = String(result.value || "");
    strategyIndex.value = -1;
  } else if (error.value) ElMessage.error(error.value.message);
};

const generateCases = async () => {
  if (strategyIndex.value < 0) {
    ElMessage.warning("请先选择集成测试策略");
    return;
  }
  const integrationObject = integrationTypeIndex.value === 0
    ? "业务中的整个系统"
    : integrationTypeIndex.value === 1
      ? "业务中的由多个子系统构成的整体系统"
      : integrationUnit.value;
  caseResult.value = null;
  const succeeded = await runWorkflow("integration_case", llm.value, {
    strategy_type: strategyIndex.value,
    strategy: strategies[strategyIndex.value],
    integration_object: integrationObject,
    integration_object_info: integrationInfo.value,
    output_type: outputFormat.value,
  }, {
    answerTitle: "集成测试用例（流式输出）",
    successTitle: "集成测试用例已生成",
  });
  if (succeeded) caseResult.value = result.value as IntegrationCaseResult;
  else if (error.value) ElMessage.error(error.value.message);
};

const resetCases = () => {
  resetStream();
  caseResult.value = null;
  strategyIndex.value = -1;
  outputFormat.value = 0;
};
</script>

<style scoped>
.action-button { min-width: 190px; margin-top: 10px; }
.result-row { margin-top: 10px; }
.result-input { width: 99%; }
.cn_name { font-family: "Ali"; }
.hint { margin-top: 8px; color: #909399; }
.result-title { margin-top: 10px; color: #06b009; font-family: "Ali"; }
</style>
