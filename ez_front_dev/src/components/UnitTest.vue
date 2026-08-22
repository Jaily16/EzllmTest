<template>
  <WorkflowStepper :steps="workflowSteps" :active-operation="activeOperation" />
  <el-alert v-if="staleWarning('unit_menu')" :title="staleWarning('unit_menu')" type="warning" show-icon :closable="false" />
  <el-row><span class="cn_name">请选择用于单元测试初步分析的大语言模型</span></el-row>
  <el-row><el-segmented v-model="menuModel" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" /></el-row>
  <el-row>
    <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning || !canRunStep('unit_menu')" plain round @click="analyzeMenu(false)">
      {{ hasSavedResult("unit_menu") ? "继续单元测试分析" : "开始单元测试分析" }}
    </el-button>
    <el-button v-if="hasSavedResult('unit_menu')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateMenu">
      重新生成单元测试分析
    </el-button>
  </el-row>
  <LlmWorkflowExecution v-if="activeOperation === 'unit_menu'" v-bind="executionProps" @cancel="cancel" />

  <el-alert
    v-if="menuRegenerating"
    class="result-row"
    title="正在重新生成单元测试范围"
    description="上一轮的单元选择和下游结果已暂时隐藏；成功后显示新结果，失败或取消后恢复原结果。"
    type="warning"
    show-icon
    :closable="false"
  />

  <template v-else-if="menuResult">
    <el-alert v-if="staleWarning('unit_info')" :title="staleWarning('unit_info')" type="warning" show-icon :closable="false" />
    <el-row class="result-row"><span class="cn_name">根据 LLM 分析，您的业务适合以下单元测试类型，请选择测试类型</span></el-row>
    <el-row class="result-row">
      <el-radio-group v-model="unitType" @change="generateUnits">
        <el-radio-button v-for="type in unitTypes" :key="type" :label="type" :value="type" />
      </el-radio-group>
    </el-row>
    <el-row v-if="unitType" class="result-row"><span class="cn_name">请选择要进行测试的单元</span></el-row>
    <el-row v-if="unitType" class="result-row">
      <el-select v-model="unit" placeholder="请选择单元" style="width: 620px" filterable>
        <el-option v-for="item in units" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
    </el-row>
    <el-row v-if="unitType" class="result-row"><span class="cn_name">请选择用于进一步分析的大语言模型</span></el-row>
    <el-row v-if="unitType"><el-segmented v-model="analysisModel" :options="MODEL_OPTIONS" size="large" :disabled="isRunning" /></el-row>
    <el-row v-if="unitType">
      <el-button class="action-button" type="primary" :icon="Right" :disabled="isRunning || !canRunStep('unit_info')" plain round @click="analyzeUnit(false)">
        {{ hasSavedResult("unit_info") ? "继续单元进一步分析" : "利用 LLM 进一步分析" }}
      </el-button>
      <el-button v-if="hasSavedResult('unit_info')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateUnit">
        重新生成单元进一步分析
      </el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'unit_info'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="unitInfoResult && !menuRegenerating">
    <el-alert v-if="staleWarning('unit_case')" :title="staleWarning('unit_case')" type="warning" show-icon :closable="false" />
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
      <el-button class="action-button" type="success" :icon="Right" :disabled="isRunning || !canRunStep('unit_case')" plain round @click="generateCases(false)">
        {{ hasSavedResult("unit_case") ? "继续查看单元测试用例" : "生成单元测试用例" }}
      </el-button>
      <el-button v-if="hasSavedResult('unit_case')" class="action-button" type="info" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateCases">
        重新生成单元测试用例
      </el-button>
    </el-row>
    <LlmWorkflowExecution v-if="activeOperation === 'unit_case'" v-bind="executionProps" @cancel="cancel" />
  </template>

  <template v-if="caseResult && !menuRegenerating">
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
import { computed, getCurrentInstance, onMounted, ref } from "vue";
import { Refresh, Right } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import LlmWorkflowExecution from "@/components/LlmWorkflowExecution.vue";
import WorkflowStepper from "@/components/WorkflowStepper.vue";
import { useLlmWorkflow } from "@/composables/useLlmWorkflow";
import { useTestWorkflow } from "@/composables/useTestWorkflow";
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
interface UnitOption { value: string; label: string }

const UNIT_REFERENCE_SEPARATOR = " ｜ ";
const parseUnitOption = (value: string): UnitOption => {
  const parts = value.split(UNIT_REFERENCE_SEPARATOR).map((item) => item.trim());
  if (parts.length < 2) return { value, label: value };
  const [displayName, qualifiedName, sourceHint] = parts;
  const sourceLabel = sourceHint ? `（来源：${sourceHint}）` : "";
  return {
    value,
    label: `${displayName} — ${qualifiedName}${sourceLabel}`,
  };
};

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
const testWorkflow = useTestWorkflow({
  baseUrl: requestUrl,
  pid: projectId,
  steps: [
    { operation: "unit_menu", label: "单元测试范围", artifactKey: "unit_menu" },
    { operation: "unit_info", label: "待测单元分析", artifactKey: "unit_info", dependsOn: ["unit_menu"], selectionFields: ["unit_type", "unit"] },
    { operation: "unit_case", label: "单元测试用例", artifactKey: "unit_case", dependsOn: ["unit_info"], selectionFields: ["method_type", "static_method", "unit_type", "unit", "output_type"], persistResult: false },
  ],
});
const {
  steps: workflowSteps, hydrateWorkflow, canRunStep, regenerateStep,
  markDependentsStale, resetStep, resultFor, selectionFor,
  hasSavedResult, staleWarning,
} = testWorkflow;
const { isRunning, result, error, activeOperation, executionProps, runWorkflow, cancel, resetStream } =
  useLlmWorkflow(requestUrl, projectId, testWorkflow);
const menuRegenerationRequested = ref(false);
const menuRegenerating = computed(
  () => menuRegenerationRequested.value && isRunning.value && activeOperation.value === "unit_menu"
);

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
  let values: string[] = [];
  if (unitType.value === "子系统单元测试") values = menu.subsystem_menu.subsystem_list;
  else if (unitType.value === "模块单元测试") values = menu.module_menu.module_list;
  else if (unitType.value === "类单元测试") values = menu.class_menu.class_list;
  else if (unitType.value === "函数单元测试") values = menu.function_menu.function_list;
  return Array.from(new Set(values)).map(parseUnitOption);
});

const selectedUnitLabel = computed(
  () => units.value.find((item) => item.value === unit.value)?.label ?? unit.value
);

const availableMethods = computed(() => {
  const methods: Array<{ index: number; label: string }> = [];
  if (unitInfoResult.value?.test_type.black_box) methods.push({ index: 0, label: methodLabels[0] });
  if (unitInfoResult.value?.test_type.white_box) methods.push({ index: 1, label: methodLabels[1] });
  return methods;
});

const analyzeMenu = async (regenerate: boolean): Promise<boolean> => {
  const succeeded = await runWorkflow("unit_menu", menuModel.value, {}, {
    answerTitle: "单元测试业务分析（流式输出）",
    successTitle: "单元测试业务分析已完成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded) {
    const value = result.value as UnitMenuResult;
    menuResult.value = value.list_info;
    if (instance) {
      instance.appContext.config.globalProperties.$unit_menu_result = value.list_info;
      instance.appContext.config.globalProperties.$unit_types_list = unitTypes.value;
    }
  } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};

const generateUnits = () => {
  unit.value = "";
  markDependentsStale("unit_menu");
};

const analyzeUnit = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("unit_info")) {
    ElMessage.warning("请先完成有效的单元测试范围分析");
    return false;
  }
  if (!unit.value) {
    ElMessage.warning("请先选择要测试的单元");
    return false;
  }
  const succeeded = await runWorkflow("unit_info", analysisModel.value, {
    unit_type: unitType.value,
    unit: unit.value,
  }, {
    answerTitle: `单元 ${selectedUnitLabel.value} 业务分析（流式输出）`,
    successTitle: "单元测试进一步分析已完成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded) {
    unitInfoResult.value = result.value as UnitInfoResult;
    methodIndex.value = -1;
  } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};

const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("unit_case")) {
    ElMessage.warning("请先完成有效的待测单元分析");
    return false;
  }
  if (!unitInfoResult.value || methodIndex.value < 0) {
    ElMessage.warning("请先选择单元测试方法");
    return false;
  }
  const succeeded = await runWorkflow("unit_case", caseModel.value, {
    method_type: methodIndex.value + 1,
    static_method: methodLabels[methodIndex.value],
    unit_type: unitType.value,
    unit: unit.value,
    unit_info: unitInfoResult.value.unit_info,
    output_type: outputFormat.value,
  }, {
    answerTitle: "单元测试用例（流式输出）",
    successTitle: "单元测试用例已生成",
    regenerate,
    keepPreviousOnFailure: true,
  });
  if (succeeded) caseResult.value = result.value as UnitCaseResult;
  else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};

const regenerateMenu = async () => {
  menuRegenerationRequested.value = true;
  try {
    return await regenerateStep("unit_menu", () => analyzeMenu(true));
  } finally {
    menuRegenerationRequested.value = false;
  }
};
const regenerateUnit = () =>
  regenerateStep("unit_info", () => analyzeUnit(true));
const regenerateCases = () =>
  regenerateStep("unit_case", () => generateCases(true));

const restoreUnitType = (savedUnit: string) => {
  const menu = menuResult.value;
  if (!menu || !savedUnit) return;
  if (menu.subsystem_menu.subsystem_list.includes(savedUnit)) unitType.value = "子系统单元测试";
  else if (menu.module_menu.module_list.includes(savedUnit)) unitType.value = "模块单元测试";
  else if (menu.class_menu.class_list.includes(savedUnit)) unitType.value = "类单元测试";
  else if (menu.function_menu.function_list.includes(savedUnit)) unitType.value = "函数单元测试";
};

onMounted(async () => {
  await hydrateWorkflow();
  const savedMenu = resultFor<UnitMenuResult>("unit_menu");
  const savedInfo = resultFor<UnitInfoResult>("unit_info");
  const savedCases = resultFor<UnitCaseResult>("unit_case");
  const infoSelection = selectionFor("unit_info");
  const caseSelection = selectionFor("unit_case");
  if (savedMenu) menuResult.value = savedMenu.list_info;
  const savedUnit = String(infoSelection.unit ?? caseSelection.unit ?? "");
  const savedUnitType = String(
    infoSelection.unit_type ?? caseSelection.unit_type ?? ""
  );
  if (unitTypes.value.includes(savedUnitType)) unitType.value = savedUnitType;
  else restoreUnitType(savedUnit);
  unit.value = savedUnit;
  if (savedInfo) unitInfoResult.value = savedInfo;
  if (typeof caseSelection.method_type === "number") methodIndex.value = caseSelection.method_type - 1;
  if (typeof caseSelection.output_type === "number") outputFormat.value = caseSelection.output_type;
  if (savedCases) caseResult.value = savedCases;
});

const resetCases = () => {
  resetStream();
  caseResult.value = null;
  methodIndex.value = -1;
  outputFormat.value = 0;
  resetStep("unit_case");
};
</script>

<style scoped>
.action-button { min-width: 190px; margin-top: 10px; margin-right: 10px; }
.result-row { margin-top: 10px; }
.result-input { width: 99%; }
.cn_name { font-family: "Ali"; }
.result-title { margin-top: 10px; color: #06b009; font-family: "Ali"; }
</style>
