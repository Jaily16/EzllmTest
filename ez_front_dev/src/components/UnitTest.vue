<template>
  <el-row><span class="cn_name">请选择用于单元测试初步分析的大语言模型</span></el-row>
  <el-row><el-segmented v-model="menuModel" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" /></el-row>
  <el-row>
    <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning" plain round @click="analyzeMenu(false)">
      {{ menuResult ? "继续单元测试分析" : "开始单元测试分析" }}
    </el-button>
    <el-button v-if="menuResult" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="analyzeMenu(true)">
      重新进行单元测试分析
    </el-button>
  </el-row>
  <LlmWorkflowExecution v-if="activeOperation === 'unit_menu'" v-bind="executionProps" @cancel="cancel" />

  <template v-if="menuResult">
    <el-row class="result-row"><span class="cn_name">根据 LLM 分析，您的业务适合以下单元测试类型，请选择测试类型</span></el-row>
    <el-row class="result-row">
      <el-radio-group v-model="unitType" @change="generateUnits">
        <el-radio-button v-for="type in unitTypes" :key="type" :label="type" :value="type" />
      </el-radio-group>
    </el-row>
    <el-row v-if="unitType" class="result-row"><span class="cn_name">请选择要进行测试的单元</span></el-row>
    <el-row v-if="unitType" class="result-row">
      <el-select v-model="unit" placeholder="请选择单元" style="width: 300px">
        <el-option v-for="item in units" :key="item" :label="item" :value="item" />
      </el-select>
    </el-row>
    <el-row v-if="unitType" class="result-row"><span class="cn_name">请选择用于进一步分析的大语言模型</span></el-row>
    <el-row v-if="unitType"><el-segmented v-model="analysisModel" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" /></el-row>
    <el-row v-if="unitType">
      <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning" plain round @click="analyzeUnit">利用 LLM 进一步分析</el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'unit_info'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="unitInfoResult">
    <el-divider />
    <el-row><span class="cn_name">LLM 从业务开发设计文档中找出的待测试单元相关内容</span></el-row>
    <el-row class="result-row"><el-input v-model="unitInfoResult.unit_info" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly /></el-row>
    <el-row class="result-row"><span class="cn_name">请选择测试方法</span></el-row>
    <el-row class="result-row">
      <el-radio-group v-model="methodIndex">
        <el-radio-button v-for="item in availableMethods" :key="item.index" :label="item.label" :value="item.index" />
      </el-radio-group>
    </el-row>
    <el-row class="result-row"><span class="cn_name">请选择测试用例输出格式</span></el-row>
    <el-row class="result-row">
      <el-radio-group v-model="outputFormat">
        <el-radio-button v-for="(format, index) in outputFormats" :key="format" :label="format" :value="index" />
      </el-radio-group>
    </el-row>
    <el-row class="result-row"><span class="cn_name">请选择用于生成测试用例的大语言模型</span></el-row>
    <el-row><el-segmented v-model="caseModel" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" /></el-row>
    <el-row>
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning" plain round @click="generateCases">生成单元测试用例</el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'unit_case'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="caseResult">
    <el-divider />
    <el-row><span class="cn_name">知识库中的单元测试知识</span></el-row>
    <el-row class="result-row"><el-input v-model="caseResult.unit_test_knowledge" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly /></el-row>
    <el-row class="result-row"><span class="cn_name">知识库中的所选测试方法知识</span></el-row>
    <el-row class="result-row"><el-input v-model="caseResult.unit_method_knowledge" class="result-input" :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" readonly /></el-row>
    <el-row><span class="result-title">LLM 生成的测试用例如下</span></el-row>
    <el-row class="result-row"><el-input v-model="caseResult.test_cases" class="result-input" :autosize="{ minRows: 2, maxRows: 50 }" type="textarea" readonly /></el-row>
    <el-button type="info" @click="resetCases">重置</el-button>
  </template>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, ref } from "vue";
import { Refresh, Right } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import LlmWorkflowExecution from "@/components/LlmWorkflowExecution.vue";
import { useLlmWorkflow } from "@/composables/useLlmWorkflow";
import { DEFAULT_MODEL, MODEL_OPTIONS } from "@/config/models";

interface UnitTestMenu {
  subsystem_menu: { subsystem_test: boolean; subsystem_list: string[] };
  module_menu: { module_test: boolean; module_list: string[] };
  class_menu: { class_test: boolean; class_list: string[] };
  function_menu: { function_test: boolean; function_list: string[] };
}
interface UnitMenuResult { text_info: string; list_info: UnitTestMenu }
interface UnitInfoResult { unit_info: string; test_type: { black_box: boolean; white_box: boolean } }
interface UnitCaseResult { unit_test_knowledge: string; unit_method_knowledge: string; test_cases: string }

const instance = getCurrentInstance();
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");
const initialMenu = instance?.appContext.config.globalProperties.$unit_menu_result as UnitTestMenu | undefined;
const menuModel = ref(DEFAULT_MODEL);
const analysisModel = ref(DEFAULT_MODEL);
const caseModel = ref(DEFAULT_MODEL);
const menuResult = ref<UnitTestMenu | null>(initialMenu || null);
const unitInfoResult = ref<UnitInfoResult | null>(null);
const caseResult = ref<UnitCaseResult | null>(null);
const unitType = ref("");
const unit = ref("");
const methodIndex = ref(-1);
const outputFormat = ref(0);
const outputFormats = [".txt(文字形式)", ".md(表格形式)", ".xml", ".csv"];
const methodLabels = ["静态黑盒测试", "静态白盒测试"];
const { isRunning, result, error, activeOperation, executionProps, runWorkflow, cancel, resetStream } = useLlmWorkflow(requestUrl, projectId);

const unitTypes = computed(() => {
  if (!menuResult.value) return [];
  const menu = menuResult.value;
  const values: string[] = [];
  if (menu.subsystem_menu.subsystem_test || menu.subsystem_menu.subsystem_list.length) values.push("子系统单元测试");
  if (menu.module_menu.module_test || menu.module_menu.module_list.length) values.push("模块单元测试");
  if (menu.class_menu.class_test || menu.class_menu.class_list.length) values.push("类单元测试");
  if (menu.function_menu.function_test || menu.function_menu.function_list.length) values.push("函数单元测试");
  return values;
});

const units = computed(() => {
  const menu = menuResult.value;
  if (!menu) return [];
  if (unitType.value === "子系统单元测试") return menu.subsystem_menu.subsystem_list;
  if (unitType.value === "模块单元测试") return menu.module_menu.module_list;
  if (unitType.value === "类单元测试") return menu.class_menu.class_list;
  if (unitType.value === "函数单元测试") return menu.function_menu.function_list;
  return [];
});

const availableMethods = computed(() => {
  const methods: Array<{ index: number; label: string }> = [];
  if (unitInfoResult.value?.test_type.black_box) methods.push({ index: 0, label: methodLabels[0] });
  if (unitInfoResult.value?.test_type.white_box) methods.push({ index: 1, label: methodLabels[1] });
  return methods;
});

const analyzeMenu = async (regenerate: boolean) => {
  unitType.value = "";
  unit.value = "";
  unitInfoResult.value = null;
  caseResult.value = null;
  const succeeded = await runWorkflow("unit_menu", menuModel.value, {}, {
    answerTitle: "单元测试业务分析（流式输出）",
    successTitle: "单元测试业务分析已完成",
    regenerate,
  });
  if (succeeded) {
    const value = result.value as UnitMenuResult;
    menuResult.value = value.list_info;
    if (instance) {
      instance.appContext.config.globalProperties.$unit_menu_result = value.list_info;
      instance.appContext.config.globalProperties.$unit_types_list = unitTypes.value;
    }
  } else if (error.value) ElMessage.error(error.value.message);
};

const generateUnits = () => {
  unit.value = "";
  unitInfoResult.value = null;
  caseResult.value = null;
};

const analyzeUnit = async () => {
  if (!unit.value) {
    ElMessage.warning("请先选择要测试的单元");
    return;
  }
  unitInfoResult.value = null;
  caseResult.value = null;
  const succeeded = await runWorkflow("unit_info", analysisModel.value, { unit: unit.value }, {
    answerTitle: `单元 ${unit.value} 业务分析（流式输出）`,
    successTitle: "单元测试进一步分析已完成",
  });
  if (succeeded) {
    unitInfoResult.value = result.value as UnitInfoResult;
    methodIndex.value = -1;
  } else if (error.value) ElMessage.error(error.value.message);
};

const generateCases = async () => {
  if (!unitInfoResult.value || methodIndex.value < 0) {
    ElMessage.warning("请先选择单元测试方法");
    return;
  }
  caseResult.value = null;
  const succeeded = await runWorkflow("unit_case", caseModel.value, {
    method_type: methodIndex.value + 1,
    static_method: methodLabels[methodIndex.value],
    unit: unit.value,
    unit_info: unitInfoResult.value.unit_info,
    output_type: outputFormat.value,
  }, {
    answerTitle: "单元测试用例（流式输出）",
    successTitle: "单元测试用例已生成",
  });
  if (succeeded) caseResult.value = result.value as UnitCaseResult;
  else if (error.value) ElMessage.error(error.value.message);
};

const resetCases = () => {
  resetStream();
  caseResult.value = null;
  methodIndex.value = -1;
  outputFormat.value = 0;
};
</script>

<style scoped>
.action-button { min-width: 190px; margin-top: 10px; margin-right: 10px; }
.result-row { margin-top: 10px; }
.result-input { width: 99%; }
.cn_name { font-family: "Ali"; }
.result-title { margin-top: 10px; color: #06b009; font-family: "Ali"; }
</style>
