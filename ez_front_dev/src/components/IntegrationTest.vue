<template>
  <!-- WorkflowStepper 由共享 scaffold 呈现。 -->
  <TestWorkspaceScaffold eyebrow="INTEGRATION TESTING" title="集成测试" description="按范围识别、集成对象分析和用例生成三个阶段恢复结果并继续工作。" :steps="workflowSteps" :active-operation="activeOperation" :hydrating="hydrating" :hydration-error="hydrationError">
    <template #hydration-actions><el-button :disabled="hydrating" @click="restoreWorkflow">重新读取</el-button></template>
    <WorkspaceSection title="1. 集成测试范围" description="识别系统、子系统、模块和类级集成范围。" :busy="activeOperation === 'integration_menu' && isRunning">
      <el-alert v-if="staleWarning('integration_menu')" :title="staleWarning('integration_menu')" type="warning" show-icon :closable="false" />
      <p class="stage-hint">建议先完成单元测试分析；若尚未完成，现有工作流会按既定后端逻辑补充。</p>
      <ModelSelector v-model="llm" :options="MODEL_OPTIONS" :disabled="isRunning" label="本阶段使用的大语言模型" description="当前页面各阶段共用此模型。" />
      <WorkflowActionBar aria-label="集成测试范围操作">
        <el-button v-if="!menuResult && !staleWithoutContent('integration_menu')" type="primary" :icon="Right" :disabled="isRunning || !canRunStep('integration_menu')" round @click="analyzeMenu(false)">{{ needsResultRecovery("integration_menu") ? "恢复匹配的已保存结果" : "开始集成测试范围分析" }}</el-button>
        <el-button v-if="hasSavedResult('integration_menu')" type="warning" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateMenu">重新生成集成测试范围</el-button>
      </WorkflowActionBar>
      <p v-if="needsResultRecovery('integration_menu')" class="recovery-note">恢复会按当前模型与输入查找已保存结果；匹配时直接恢复，不匹配时会开始新的分析。</p>
      <LlmWorkflowExecution v-if="activeOperation === 'integration_menu'" v-bind="executionProps" @cancel="cancel" />
    </WorkspaceSection>

    <el-alert v-if="menuRegenerating" title="正在重新生成集成测试范围" description="旧的对象选择与下游结果暂时隐藏；成功后采用新范围，失败或取消后恢复原结果。" type="warning" show-icon :closable="false" />
    <WorkspaceSection v-else-if="menuResult" title="2. 集成对象分析" description="选择集成层级；需要具体对象时使用完整后端名称。" :busy="activeOperation === 'integration_info' && isRunning">
      <el-alert v-if="integrationInfoWarning" :title="integrationInfoWarning" type="warning" show-icon :closable="false" />
      <TestFieldGroup legend="集成测试类型" field-id="integration-type" required><el-radio-group v-model="integrationType" aria-required="true" @change="selectIntegrationType"><el-radio-button v-for="type in availableTypes" :key="type" :label="type" :value="type" /></el-radio-group></TestFieldGroup>
      <TestTargetSelector v-if="needsUnit" v-model="integrationUnit" :options="integrationUnitOptions" label="集成测试对象" field-id="integration-target" description="保留后端返回的完整对象名称；改变目标会使已有对象分析和用例过期。" placeholder="请选择集成测试对象" required @update:model-value="markIntegrationInfoStale" />
      <ModelSelector v-if="integrationType" v-model="llm" :options="MODEL_OPTIONS" :disabled="isRunning" label="本阶段使用的大语言模型" />
      <WorkflowActionBar v-if="integrationType" aria-label="集成对象分析操作">
        <el-button v-if="!integrationInfoResultVisible" type="primary" :icon="Right" :disabled="isRunning || (needsUnit && !integrationUnit) || !canRunStep('integration_info')" round @click="analyzeIntegration(false)">{{ needsResultRecovery("integration_info") ? "恢复匹配的已保存结果" : "分析集成测试对象" }}</el-button>
        <el-button v-if="integrationInfoResultVisible" type="warning" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateIntegration">重新生成集成对象分析</el-button>
      </WorkflowActionBar>
      <p v-if="needsResultRecovery('integration_info')" class="recovery-note">请选择与原结果一致的类型、对象和模型以优先命中缓存；不匹配时可能执行新分析。</p>
      <template v-if="integrationInfoExecutionVisible">
        <LlmWorkflowExecution v-if="activeOperation === 'integration_info'" v-bind="executionProps" @cancel="cancel" />
      </template>
      <ResultContainer v-if="visibleIntegrationInfo" title="业务资料中的集成对象内容" :status="integrationInfoWarning ? 'stale' : 'default'" retention="persistent"><TestResultText :text="visibleIntegrationInfo" /></ResultContainer>
    </WorkspaceSection>

    <WorkspaceSection v-if="visibleIntegrationInfo && !menuRegenerating" title="3. 集成测试用例" description="选择集成策略和输出格式后生成当前页面结果。" :busy="activeOperation === 'integration_case' && isRunning">
      <el-alert v-if="caseWarning" :title="caseWarning" type="warning" show-icon :closable="false" />
      <TestFieldGroup legend="集成测试策略" field-id="integration-strategy" required><el-radio-group v-model="strategyIndex" aria-required="true" @change="markCaseStale"><el-radio-button v-for="(item, index) in strategies" :key="item" :label="item" :value="index" /></el-radio-group></TestFieldGroup>
      <TestFieldGroup legend="测试用例输出格式" field-id="integration-output-format"><el-radio-group v-model="outputFormat" @change="markCaseStale"><el-radio-button v-for="(format, index) in outputFormats" :key="format" :label="format" :value="index" /></el-radio-group></TestFieldGroup>
      <TestRetentionNotice retention="session-only" />
      <ModelSelector v-model="llm" :options="MODEL_OPTIONS" :disabled="isRunning" label="本阶段使用的大语言模型" />
      <WorkflowActionBar aria-label="集成测试用例操作">
        <el-button v-if="!caseResultVisible" type="primary" :icon="Right" :disabled="isRunning || strategyIndex < 0 || !canRunStep('integration_case')" round @click="generateCases(false)">生成集成测试用例</el-button>
        <el-button v-if="caseResultVisible" type="warning" :icon="Refresh" :disabled="isRunning" plain round @click="regenerateCases">重新生成集成测试用例</el-button>
      </WorkflowActionBar>
      <span class="recovery-copy">恢复匹配的已保存结果仅适用于持久化步骤；本阶段结果不会跨页面恢复。</span>
      <template v-if="caseExecutionVisible">
        <LlmWorkflowExecution v-if="activeOperation === 'integration_case'" v-bind="executionProps" @cancel="cancel" />
      </template>
      <div v-if="visibleCaseResult && !menuRegenerating" class="test-results">
        <ResultContainer title="知识库中的集成测试知识" :status="caseWarning ? 'stale' : 'default'" retention="session-only"><TestResultText :text="visibleCaseResult.integration_test_knowledge" /></ResultContainer>
        <ResultContainer title="知识库中的所选集成策略知识" :status="caseWarning ? 'stale' : 'default'" retention="session-only"><TestResultText :text="visibleCaseResult.integration_strategy_knowledge" /></ResultContainer>
        <ResultContainer title="知识库中的静态黑盒测试知识" :status="caseWarning ? 'stale' : 'default'" retention="session-only"><TestResultText :text="visibleCaseResult.static_blackbox_knowledge" /></ResultContainer>
        <ResultContainer title="模型生成的集成测试用例" :status="caseWarning ? 'stale' : 'default'" retention="session-only"><TestResultText :text="visibleCaseResult.test_cases" /></ResultContainer>
        <WorkflowActionBar aria-label="集成测试结果操作"><el-button type="info" plain @click="resetCases">清空当前页面结果</el-button></WorkflowActionBar>
      </div>
    </WorkspaceSection>
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

interface IntegrationMenu {
  subsystem_integration_test: boolean;
  subsystem_integration_menu: { subsystem_test: boolean; subsystem_list: string[] };
  module_integration_menu: { module_test: boolean; module_list: string[] };
  class_integration_menu: { class_test: boolean; class_list: string[] };
}
interface IntegrationCaseResult { integration_test_knowledge: string; static_blackbox_knowledge: string; integration_strategy_knowledge: string; test_cases: string }
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
const strategies = ["大爆炸集成(Big Bang Integration)", "自顶向下集成(Top-Down Integration)", "自底向上集成(Bottom-up Integration)", "三明治集成(Sandwich Integration)"];
const outputFormats = [".txt(文字形式)", ".md(表格形式)", ".xml", ".csv"];
const testWorkflow = useTestWorkflow({ baseUrl: requestUrl, pid: projectId, steps: [
  { operation: "integration_menu", label: "集成测试范围", artifactKey: "integration_menu" },
  { operation: "integration_info", label: "集成对象分析", artifactKey: "integration_info", dependsOn: ["integration_menu"], selectionFields: ["integration_type", "name"] },
  { operation: "integration_case", label: "集成测试用例", artifactKey: "integration_case", dependsOn: ["integration_info"], selectionFields: ["strategy_type", "strategy", "integration_object", "output_type"], persistResult: false },
] });
const { steps: workflowSteps, hydrating, hydrationError, hydrateWorkflow, canRunStep, regenerateStep, reconcileStepSelection, resetStep, resultFor, selectionFor, selectionsMatch, hasSavedResult, hasVisibleResultFor, needsResultRecovery, staleWarning } = testWorkflow;
const { isRunning, result, error, activeOperation, activeSelection, executionProps, runWorkflow, cancel, resetStream } = useLlmWorkflow(requestUrl, projectId, testWorkflow);
const menuRegenerationRequested = ref(false);
const menuRegenerating = computed(() => menuRegenerationRequested.value && isRunning.value && activeOperation.value === "integration_menu");
const staleWithoutContent = (operation: string) => workflowSteps.value.some((step) => step.operation === operation && step.state === "stale" && step.result === null);
const availableTypes = computed(() => {
  const menu = menuResult.value; if (!menu) return [];
  const values: string[] = [menu.subsystem_integration_test ? allTypes[1] : allTypes[0]];
  if (menu.subsystem_integration_menu.subsystem_test && menu.subsystem_integration_menu.subsystem_list.length) values.push(allTypes[2]);
  if (menu.module_integration_menu.module_test && menu.module_integration_menu.module_list.length) values.push(allTypes[3]);
  if (menu.class_integration_menu.class_test && menu.class_integration_menu.class_list.length) values.push(allTypes[4]);
  return values;
});
const integrationTypeIndex = computed(() => allTypes.indexOf(integrationType.value));
const needsUnit = computed(() => integrationTypeIndex.value >= 2);
const integrationUnits = computed(() => {
  const menu = menuResult.value; if (!menu) return [];
  if (integrationTypeIndex.value === 2) return menu.subsystem_integration_menu.subsystem_list;
  if (integrationTypeIndex.value === 3) return menu.module_integration_menu.module_list;
  if (integrationTypeIndex.value === 4) return menu.class_integration_menu.class_list;
  return [];
});
const integrationUnitOptions = computed(() => integrationUnits.value.map((value) => ({ value, label: value })));
const currentIntegrationInfoSelection = computed(() => ({
  integration_type: integrationTypeIndex.value,
  name: needsUnit.value ? integrationUnit.value : "",
}));
const integrationInfoResultVisible = computed(() => hasVisibleResultFor("integration_info", currentIntegrationInfoSelection.value));
const visibleIntegrationInfo = computed(() => integrationInfoResultVisible.value ? integrationInfo.value : "");
const integrationInfoExecutionVisible = computed(() => activeOperation.value === "integration_info" &&
  (isRunning.value || selectionsMatch("integration_info", activeSelection.value, currentIntegrationInfoSelection.value)));
const currentIntegrationObject = computed(() => integrationTypeIndex.value === 0
  ? "业务中的整个系统"
  : integrationTypeIndex.value === 1
    ? "业务中的由多个子系统构成的整体系统"
    : integrationUnit.value);
const currentIntegrationCaseSelection = computed(() => ({
  strategy_type: strategyIndex.value,
  strategy: strategyIndex.value >= 0 ? strategies[strategyIndex.value] : undefined,
  integration_object: currentIntegrationObject.value,
  output_type: outputFormat.value,
}));
const caseResultVisible = computed(() => hasVisibleResultFor("integration_case", currentIntegrationCaseSelection.value));
const visibleCaseResult = computed(() => caseResultVisible.value ? caseResult.value : null);
const caseExecutionVisible = computed(() => activeOperation.value === "integration_case" &&
  (isRunning.value || selectionsMatch("integration_case", activeSelection.value, currentIntegrationCaseSelection.value)));
const integrationInfoWarning = computed(() => integrationInfoResultVisible.value ? staleWarning("integration_info") : "");
const caseWarning = computed(() => caseResultVisible.value ? staleWarning("integration_case") : "");
const analyzeMenu = async (regenerate = false): Promise<boolean> => {
  const succeeded = await runWorkflow("integration_menu", llm.value, {}, { answerTitle: "集成测试类型分析（流式输出）", successTitle: "集成测试类型分析已完成", regenerate, keepPreviousOnFailure: true });
  if (succeeded) menuResult.value = result.value as IntegrationMenu; else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
const selectIntegrationType = () => { integrationUnit.value = ""; reconcileStepSelection("integration_info", currentIntegrationInfoSelection.value); };
const markIntegrationInfoStale = () => reconcileStepSelection("integration_info", currentIntegrationInfoSelection.value);
const markCaseStale = () => reconcileStepSelection("integration_case", currentIntegrationCaseSelection.value, false);
const analyzeIntegration = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("integration_info")) { ElMessage.warning("请先完成有效的集成测试范围分析"); return false; }
  if (integrationTypeIndex.value < 0) { ElMessage.warning("请先选择集成测试类型"); return false; }
  if (needsUnit.value && !integrationUnit.value) { ElMessage.warning("请先选择要进行集成测试的对象"); return false; }
  const succeeded = await runWorkflow("integration_info", llm.value, { integration_type: integrationTypeIndex.value, name: needsUnit.value ? integrationUnit.value : "" }, { answerTitle: "集成测试对象分析（流式输出）", successTitle: "集成测试对象分析已完成", regenerate, keepPreviousOnFailure: true });
  if (succeeded) { integrationInfo.value = String(result.value || ""); strategyIndex.value = -1; } else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
const generateCases = async (regenerate = false): Promise<boolean> => {
  if (!canRunStep("integration_case")) { ElMessage.warning("请先完成有效的集成对象分析"); return false; }
  if (strategyIndex.value < 0) { ElMessage.warning("请先选择集成测试策略"); return false; }
  if (!visibleIntegrationInfo.value) { ElMessage.warning("请先分析当前选择的集成对象"); return false; }
  const succeeded = await runWorkflow("integration_case", llm.value, { strategy_type: strategyIndex.value, strategy: strategies[strategyIndex.value], integration_object: currentIntegrationObject.value, integration_object_info: visibleIntegrationInfo.value, output_type: outputFormat.value }, { answerTitle: "集成测试用例（流式输出）", successTitle: "集成测试用例已生成", regenerate, keepPreviousOnFailure: true });
  if (succeeded) caseResult.value = result.value as IntegrationCaseResult; else if (error.value) ElMessage.error(error.value.message);
  return succeeded;
};
const regenerateMenu = async () => { menuRegenerationRequested.value = true; try { return await regenerateStep("integration_menu", () => analyzeMenu(true)); } finally { menuRegenerationRequested.value = false; } };
const regenerateIntegration = () => regenerateStep("integration_info", () => analyzeIntegration(true));
const regenerateCases = () => regenerateStep("integration_case", () => generateCases(true));
const restoreWorkflow = async () => {
  await hydrateWorkflow();
  const savedMenu = resultFor<IntegrationMenu>("integration_menu"); const savedInfo = resultFor<string>("integration_info"); const savedCases = resultFor<IntegrationCaseResult>("integration_case");
  const infoSelection = selectionFor("integration_info"); const caseSelection = selectionFor("integration_case");
  if (savedMenu) menuResult.value = savedMenu;
  if (typeof infoSelection.integration_type === "number") integrationType.value = allTypes[infoSelection.integration_type] ?? "";
  if (typeof infoSelection.name === "string") integrationUnit.value = infoSelection.name;
  if (savedInfo) integrationInfo.value = savedInfo;
  if (typeof caseSelection.strategy_type === "number") strategyIndex.value = caseSelection.strategy_type;
  if (typeof caseSelection.output_type === "number") outputFormat.value = caseSelection.output_type;
  if (savedCases) caseResult.value = savedCases;
};
onMounted(restoreWorkflow);
const resetCases = async () => {
  if (!(await confirmSessionOnlyResultReset("集成测试用例"))) return;
  resetStream(); caseResult.value = null; strategyIndex.value = -1; outputFormat.value = 0; resetStep("integration_case");
};
</script>

<style scoped>
.test-results { display: grid; min-width: 0; gap: var(--ez-space-4); margin-top: var(--ez-space-4); }
.recovery-note, .recovery-copy, .stage-hint { display: block; max-width: var(--ez-reading-measure); margin: var(--ez-space-2) 0 0; color: var(--ez-color-text-muted); font-size: var(--ez-font-size-13); overflow-wrap: anywhere; }
</style>
