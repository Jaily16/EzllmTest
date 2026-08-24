<template>
  <!-- WorkflowStepper 由共享 scaffold 呈现。 -->
  <TestWorkspaceScaffold eyebrow="UNIT TESTING" title="单元测试" description="按范围识别、待测单元分析和用例生成三个阶段恢复结果并继续工作。" :steps="workflowSteps" :active-operation="activeOperation" :hydrating="hydrating" :hydration-error="hydrationError">
    <template #hydration-actions><el-button :disabled="hydrating" @click="restoreWorkflow">重新读取</el-button></template>

    <WorkspaceSection title="1. 单元测试范围" description="识别子系统、模块、类和函数，并保留完整 qualified reference。" :busy="activeOperation === 'unit_menu' && isRunning">
      <el-alert v-if="staleWarning('unit_menu')" :title="staleWarning('unit_menu')" type="warning" show-icon :closable="false" />
      <ModelSelector v-model="menuModel" :options="MODEL_OPTIONS" :disabled="isRunning" label="范围识别使用的大语言模型" />
      <WorkflowActionBar aria-label="单元测试范围操作">
        <el-button v-if="!menuResult && !staleWithoutContent('unit_menu')" type="primary" :icon="Right" :disabled="isRunning || !canRunStep('unit_menu')" round @click="analyzeMenu(false)">{{ needsResultRecovery("unit_menu") ? "恢复匹配的已保存结果" : "开始单元测试范围分析" }}</el-button>
        <el-button v-if="hasSavedResult('unit_menu')" type="warning" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateMenu">重新生成单元测试范围</el-button>
      </WorkflowActionBar>
      <p v-if="needsResultRecovery('unit_menu')" class="recovery-note">恢复会按当前模型与输入查找已保存结果；匹配时直接恢复，不匹配时会开始新的分析。</p>
      <LlmWorkflowExecution v-if="activeOperation === 'unit_menu'" v-bind="executionProps" @cancel="cancel" />
    </WorkspaceSection>

    <el-alert v-if="menuRegenerating" title="正在重新生成单元测试范围" description="上一轮的单元选择和下游结果已暂时隐藏；成功后显示新结果，失败或取消后恢复原结果。" type="warning" show-icon :closable="false" />
    <WorkspaceSection v-else-if="menuResult" title="2. 待测单元分析" description="先选择单元类型，再通过完整限定名确认具体目标。" :busy="activeOperation === 'unit_info' && isRunning">
      <el-alert v-if="unitInfoWarning" :title="unitInfoWarning" type="warning" show-icon :closable="false" />
      <TestFieldGroup legend="单元测试类型" field-id="unit-type" required><el-radio-group v-model="unitType" aria-required="true" @change="generateUnits"><el-radio-button v-for="type in unitTypes" :key="type" :label="type" :value="type" /></el-radio-group></TestFieldGroup>
      <TestTargetSelector v-if="unitType" v-model="unit" :options="units" label="待测单元" field-id="unit-target" description="同名目标使用 qualified name 与来源文件区分；请求始终提交完整原始值。" placeholder="请选择单元" required @update:model-value="markUnitInfoStale">
        <template #options><el-option v-for="item in units" :key="item.value" :label="item.label" :value="item.value" /></template>
      </TestTargetSelector>
      <ModelSelector v-if="unitType" v-model="analysisModel" :options="MODEL_OPTIONS" :disabled="isRunning" label="待测单元分析使用的大语言模型" />
      <WorkflowActionBar v-if="unitType" aria-label="待测单元分析操作">
        <el-button v-if="!unitInfoResultVisible" type="primary" :icon="Right" :disabled="isRunning || !unit || !canRunStep('unit_info')" round @click="analyzeUnit(false)">{{ needsResultRecovery("unit_info") ? "恢复匹配的已保存结果" : "分析所选单元" }}</el-button>
        <el-button v-if="unitInfoResultVisible" type="warning" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateUnit">重新生成待测单元分析</el-button>
      </WorkflowActionBar>
      <p v-if="needsResultRecovery('unit_info')" class="recovery-note">请选择与原结果一致的目标和模型以优先命中缓存；不匹配时可能执行新分析。</p>
      <template v-if="unitInfoExecutionVisible">
        <LlmWorkflowExecution v-if="activeOperation === 'unit_info'" v-bind="executionProps" @cancel="cancel" />
      </template>
      <ResultContainer v-if="visibleUnitInfoResult" title="业务资料中的待测单元内容" :status="unitInfoWarning ? 'stale' : 'default'" retention="persistent"><TestResultText :text="visibleUnitInfoResult.unit_info" /></ResultContainer>
    </WorkspaceSection>

    <template v-if="unitInfoResult && !menuRegenerating">
    <WorkspaceSection v-if="visibleUnitInfoResult" title="3. 单元测试用例" description="选择可用方法和输出格式后生成当前页面结果。" :busy="activeOperation === 'unit_case' && isRunning">
      <el-alert v-if="caseWarning" :title="caseWarning" type="warning" show-icon :closable="false" />
      <TestFieldGroup legend="单元测试方法" field-id="unit-method" required><el-radio-group v-model="methodIndex" aria-required="true" @change="markCaseStale"><el-radio-button v-for="item in availableMethods" :key="item.index" :label="item.label" :value="item.index" /></el-radio-group></TestFieldGroup>
      <TestFieldGroup legend="测试用例输出格式" field-id="unit-output-format"><el-radio-group v-model="outputFormat" @change="markCaseStale"><el-radio-button v-for="(format, index) in outputFormats" :key="format" :label="format" :value="index" /></el-radio-group></TestFieldGroup>
      <TestRetentionNotice retention="session-only" />
      <ModelSelector v-model="caseModel" :options="MODEL_OPTIONS" :disabled="isRunning" label="测试用例生成使用的大语言模型" />
      <WorkflowActionBar aria-label="单元测试用例操作">
        <el-button v-if="!caseResultVisible" type="primary" :icon="Right" :disabled="isRunning || methodIndex < 0 || !canRunStep('unit_case')" round @click="generateCases(false)">生成单元测试用例</el-button>
        <el-button v-if="caseResultVisible" type="warning" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateCases">重新生成单元测试用例</el-button>
      </WorkflowActionBar>
      <span class="recovery-copy">恢复匹配的已保存结果仅适用于持久化步骤；本阶段结果不会跨页面恢复。</span>
      <template v-if="caseExecutionVisible">
        <LlmWorkflowExecution v-if="activeOperation === 'unit_case'" v-bind="executionProps" @cancel="cancel" />
      </template>
      <template v-if="caseResult && !menuRegenerating">
      <div v-if="visibleCaseResult && !menuRegenerating" class="test-results">
        <ResultContainer title="知识库中的单元测试知识" :status="caseWarning ? 'stale' : 'default'" retention="session-only"><TestResultText :text="visibleCaseResult.unit_test_knowledge" /></ResultContainer>
        <ResultContainer title="知识库中的所选测试方法知识" :status="caseWarning ? 'stale' : 'default'" retention="session-only"><TestResultText :text="visibleCaseResult.unit_method_knowledge" /></ResultContainer>
        <ResultContainer title="模型生成的单元测试用例" :status="caseWarning ? 'stale' : 'default'" retention="session-only"><TestResultText :text="visibleCaseResult.test_cases" /></ResultContainer>
        <WorkflowActionBar aria-label="单元测试结果操作"><el-button type="info" plain @click="resetCases">清空当前页面结果</el-button></WorkflowActionBar>
      </div>
      </template>
    </WorkspaceSection>
    </template>
  </TestWorkspaceScaffold>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, onMounted, ref } from "vue";
import { Refresh, Right } from "@element-plus/icons-vue";
import { ElMessage } from "@/plugins/elementPlus";
import "@/components/workspace/FeedbackState.vue";
import LlmWorkflowExecution from "@/components/LlmWorkflowExecution.vue";
import ModelSelector from "@/components/workspace/ModelSelector.vue";
import ResultContainer from "@/components/workspace/ResultContainer.vue";
import TestFieldGroup from "@/components/testing/TestFieldGroup.vue";
import TestResultText from "@/components/testing/TestResultText.vue";
import TestRetentionNotice from "@/components/testing/TestRetentionNotice.vue";
import TestTargetSelector from "@/components/testing/TestTargetSelector.vue";
import TestWorkspaceScaffold from "@/components/testing/TestWorkspaceScaffold.vue";
import WorkflowActionBar from "@/components/workspace/WorkflowActionBar.vue";
import WorkspaceSection from "@/components/workspace/WorkspaceSection.vue";
import { useLlmWorkflow } from "@/composables/useLlmWorkflow";
import { useTestWorkflow } from "@/composables/useTestWorkflow";
import { DEFAULT_MODEL, MODEL_OPTIONS } from "@/config/models";
import { confirmSessionOnlyResultReset } from "@/ui/confirmations";
import { parseQualifiedReference } from "@/ui/qualifiedReferences";

interface UnitTestMenu {
  subsystem_menu: { subsystem_test: boolean; subsystem_list: string[] };
  module_menu: { module_test: boolean; module_list: string[] };
  class_menu: { class_test: boolean; class_list: string[] };
  function_menu: { function_test: boolean; function_list: string[] };
}
interface UnitMenuResult { text_info: string; list_info: UnitTestMenu }
interface UnitInfoResult { unit_info: string; test_type: { black_box: boolean; white_box: boolean } }
interface UnitCaseResult { unit_test_knowledge: string; unit_method_knowledge: string; test_cases: string }
interface UnitOption { value: string; label: string; detail: string }
const parseUnitOption = (value: string): UnitOption => { const reference = parseQualifiedReference(value); return { value: reference.value, label: reference.label, detail: reference.detail }; };

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
const testWorkflow = useTestWorkflow({ baseUrl: requestUrl, pid: projectId, steps: [
  { operation: "unit_menu", label: "单元测试范围", artifactKey: "unit_menu" },
  { operation: "unit_info", label: "待测单元分析", artifactKey: "unit_info", dependsOn: ["unit_menu"], selectionFields: ["unit_type", "unit"] },
  { operation: "unit_case", label: "单元测试用例", artifactKey: "unit_case", dependsOn: ["unit_info"], selectionFields: ["method_type", "static_method", "unit_type", "unit", "output_type"], persistResult: false },
] });
const { steps: workflowSteps, hydrating, hydrationError, hydrateWorkflow, canRunStep, regenerateStep, reconcileStepSelection, resetStep, resultFor, selectionFor, selectionsMatch, hasSavedResult, hasVisibleResultFor, needsResultRecovery, staleWarning } = testWorkflow;
const { isRunning, result, error, activeOperation, activeSelection, executionProps, runWorkflow, cancel, resetStream } = useLlmWorkflow(requestUrl, projectId, testWorkflow);
const menuRegenerationRequested = ref(false);
const menuRegenerating = computed(() => menuRegenerationRequested.value && isRunning.value && activeOperation.value === "unit_menu");
const staleWithoutContent = (operation: string) => workflowSteps.value.some((step) => step.operation === operation && step.state === "stale" && step.result === null);

const unitTypes = computed(() => {
  if (!menuResult.value) return [];
  const menu = menuResult.value; const values: string[] = [];
  if (menu.subsystem_menu.subsystem_test || menu.subsystem_menu.subsystem_list.length) values.push("子系统单元测试");
  if (menu.module_menu.module_test || menu.module_menu.module_list.length) values.push("模块单元测试");
  if (menu.class_menu.class_test || menu.class_menu.class_list.length) values.push("类单元测试");
  if (menu.function_menu.function_test || menu.function_menu.function_list.length) values.push("函数单元测试");
  return values;
});
const units = computed(() => {
  const menu = menuResult.value; if (!menu) return [];
  let values: string[] = [];
  if (unitType.value === "子系统单元测试") values = menu.subsystem_menu.subsystem_list;
  else if (unitType.value === "模块单元测试") values = menu.module_menu.module_list;
  else if (unitType.value === "类单元测试") values = menu.class_menu.class_list;
  else if (unitType.value === "函数单元测试") values = menu.function_menu.function_list;
  return Array.from(new Set(values)).map(parseUnitOption);
});
const selectedUnitLabel = computed(() => units.value.find((item) => item.value === unit.value)?.label ?? unit.value);
const currentUnitInfoSelection = computed(() => ({ unit_type: unitType.value, unit: unit.value }));
const unitInfoResultVisible = computed(() => hasVisibleResultFor("unit_info", currentUnitInfoSelection.value));
const visibleUnitInfoResult = computed(() => unitInfoResultVisible.value ? unitInfoResult.value : null);
const unitInfoExecutionVisible = computed(() => activeOperation.value === "unit_info" &&
  (isRunning.value || selectionsMatch("unit_info", activeSelection.value, currentUnitInfoSelection.value)));
const currentUnitCaseSelection = computed(() => ({
  method_type: methodIndex.value + 1,
  static_method: methodIndex.value >= 0 ? methodLabels[methodIndex.value] : undefined,
  unit_type: unitType.value,
  unit: unit.value,
  output_type: outputFormat.value,
}));
const caseResultVisible = computed(() => hasVisibleResultFor("unit_case", currentUnitCaseSelection.value));
const visibleCaseResult = computed(() => caseResultVisible.value ? caseResult.value : null);
const caseExecutionVisible = computed(() => activeOperation.value === "unit_case" &&
  (isRunning.value || selectionsMatch("unit_case", activeSelection.value, currentUnitCaseSelection.value)));
const unitInfoWarning = computed(() => unitInfoResultVisible.value ? staleWarning("unit_info") : "");
const caseWarning = computed(() => caseResultVisible.value ? staleWarning("unit_case") : "");
const availableMethods = computed(() => {
  const methods: Array<{ index: number; label: string }> = [];
  if (visibleUnitInfoResult.value?.test_type.black_box) methods.push({ index: 0, label: methodLabels[0] });
  if (visibleUnitInfoResult.value?.test_type.white_box) methods.push({ index: 1, label: methodLabels[1] });
  return methods;
});

const analyzeMenu = async (regenerate: boolean): Promise<boolean> => {
  const succeeded = await runWorkflow("unit_menu", menuModel.value, {}, { answerTitle: "单元测试业务分析（流式输出）", successTitle: "单元测试业务分析已完成", regenerate, keepPreviousOnFailure: true });
  if (succeeded) { const value = result.value as UnitMenuResult; menuResult.value = value.list_info; if (instance) { instance.appContext.config.globalProperties.$unit_menu_result = value.list_info; instance.appContext.config.globalProperties.$unit_types_list = unitTypes.value; } } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
const generateUnits = () => { unit.value = ""; reconcileStepSelection("unit_info", currentUnitInfoSelection.value); };
const markUnitInfoStale = () => reconcileStepSelection("unit_info", currentUnitInfoSelection.value);
const markCaseStale = () => reconcileStepSelection("unit_case", currentUnitCaseSelection.value, false);
const analyzeUnit = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("unit_info")) { ElMessage.warning("请先完成有效的单元测试范围分析"); return false; }
  if (!unit.value) { ElMessage.warning("请先选择要测试的单元"); return false; }
  const succeeded = await runWorkflow("unit_info", analysisModel.value, { unit_type: unitType.value, unit: unit.value }, { answerTitle: `单元 ${selectedUnitLabel.value} 业务分析（流式输出）`, successTitle: "单元测试进一步分析已完成", regenerate, keepPreviousOnFailure: true });
  if (succeeded) { unitInfoResult.value = result.value as UnitInfoResult; methodIndex.value = -1; } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("unit_case")) { ElMessage.warning("请先完成有效的待测单元分析"); return false; }
  if (!visibleUnitInfoResult.value || methodIndex.value < 0) { ElMessage.warning("请先选择单元测试方法"); return false; }
  const succeeded = await runWorkflow("unit_case", caseModel.value, { method_type: methodIndex.value + 1, static_method: methodLabels[methodIndex.value], unit_type: unitType.value, unit: unit.value, unit_info: visibleUnitInfoResult.value.unit_info, output_type: outputFormat.value }, { answerTitle: "单元测试用例（流式输出）", successTitle: "单元测试用例已生成", regenerate, keepPreviousOnFailure: true });
  if (succeeded) caseResult.value = result.value as UnitCaseResult; else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
const regenerateMenu = async () => { menuRegenerationRequested.value = true; try { return await regenerateStep("unit_menu", () => analyzeMenu(true)); } finally { menuRegenerationRequested.value = false; } };
const regenerateUnit = () => regenerateStep("unit_info", () => analyzeUnit(true));
const regenerateCases = () => regenerateStep("unit_case", () => generateCases(true));
const restoreUnitType = (savedUnit: string) => {
  const menu = menuResult.value; if (!menu || !savedUnit) return;
  if (menu.subsystem_menu.subsystem_list.includes(savedUnit)) unitType.value = "子系统单元测试";
  else if (menu.module_menu.module_list.includes(savedUnit)) unitType.value = "模块单元测试";
  else if (menu.class_menu.class_list.includes(savedUnit)) unitType.value = "类单元测试";
  else if (menu.function_menu.function_list.includes(savedUnit)) unitType.value = "函数单元测试";
};
const restoreWorkflow = async () => {
  await hydrateWorkflow();
  const savedMenu = resultFor<UnitMenuResult>("unit_menu"); const savedInfo = resultFor<UnitInfoResult>("unit_info"); const savedCases = resultFor<UnitCaseResult>("unit_case");
  const infoSelection = selectionFor("unit_info"); const caseSelection = selectionFor("unit_case");
  if (savedMenu) menuResult.value = savedMenu.list_info;
  const savedUnit = String(infoSelection.unit ?? caseSelection.unit ?? ""); const savedUnitType = String(infoSelection.unit_type ?? caseSelection.unit_type ?? "");
  if (unitTypes.value.includes(savedUnitType)) unitType.value = savedUnitType; else restoreUnitType(savedUnit);
  unit.value = savedUnit; if (savedInfo) unitInfoResult.value = savedInfo;
  if (typeof caseSelection.method_type === "number") methodIndex.value = caseSelection.method_type - 1;
  if (typeof caseSelection.output_type === "number") outputFormat.value = caseSelection.output_type;
  if (savedCases) caseResult.value = savedCases;
};
onMounted(restoreWorkflow);
const resetCases = async () => {
  if (!(await confirmSessionOnlyResultReset("单元测试用例"))) return;
  resetStream(); caseResult.value = null; methodIndex.value = -1; outputFormat.value = 0; resetStep("unit_case");
};
</script>

<style scoped>
.test-results { display: grid; min-width: 0; gap: var(--ez-space-4); margin-top: var(--ez-space-4); }
.recovery-note, .recovery-copy { display: block; max-width: var(--ez-reading-measure); margin: var(--ez-space-2) 0 0; color: var(--ez-color-text-muted); font-size: var(--ez-font-size-13); overflow-wrap: anywhere; }
</style>
