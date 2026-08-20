<template>
  <el-row>
    <span style="margin-top: 5px" class="cn_name">请选择用于分析业务和生成测试计划的大语言模型</span>
  </el-row>
  <el-row>
    <el-segmented
      v-model="llm"
      style="margin-top: 5px"
      :options="options"
      size="large"
      :disabled="isRunning"
    />
  </el-row>
  <el-row>
    <el-button
      v-if="!completed"
      style="margin-top: 10px; width: 180px"
      type="success"
      :icon="Right"
      :disabled="isRunning"
      plain
      round
      @click="startTestPlan"
    >
      开始分析业务和生成测试计划
    </el-button>
  </el-row>

  <LlmExecutionPanel
    :visible="hasActivity"
    :running="isRunning"
    :completed="completed"
    :cancelled="cancelled"
    :saved="saved"
    :from-cache="fromCache"
    :progress="progress"
    :meta="meta"
    :reasoning-sections="reasoningSections"
    :usage="usage"
    :usage-received="usageReceived"
    :error="streamError"
    @cancel="cancelTestPlan"
  />

  <el-divider v-if="summary" />
  <el-row v-if="summary">
    <span class="cn_name" style="color: #06b009">业务文档的初步分析与总结</span>
  </el-row>
  <el-row v-if="summary" style="margin-top: 10px">
    <el-input
      v-model="summary"
      style="width: 99%"
      :autosize="{ minRows: 4, maxRows: 35 }"
      type="textarea"
      readonly
    />
  </el-row>
  <el-divider v-if="answer" />
  <el-row v-if="answer">
    <span class="cn_name" style="color: #06b009">LLM 对该软件业务的测试计划建议如下</span>
  </el-row>
  <el-row v-if="answer" style="margin-top: 10px">
    <el-input
      v-model="answer"
      style="width: 99%"
      :autosize="{ minRows: 4, maxRows: 50 }"
      type="textarea"
      readonly
    />
  </el-row>
  <el-alert
    v-if="completed && ready"
    style="margin-top: 12px; width: 99%"
    title="测试菜单已生成并保存，左侧测试菜单和手动测试类型现已解锁"
    type="success"
    :closable="false"
    show-icon
  />
  <el-row v-if="completed && answer && !isRunning">
    <el-button
      style="margin-top: 10px; width: 180px"
      type="info"
      :icon="Right"
      plain
      round
      @click="restartTestPlan"
    >
      重新分析业务和生成测试计划
    </el-button>
  </el-row>
  <span class="cn_name">注意该测试计划只是整体建议，具体测试用例请在平台中选择相应模块进行生成</span>
  <el-divider v-if="answer" border-style="dotted" />
</template>

<script lang="ts" setup>
import { getCurrentInstance, onMounted, ref } from "vue";
import { Right } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import LlmExecutionPanel from "@/components/LlmExecutionPanel.vue";
import { useLlmStream } from "@/composables/useLlmStream";
import { DEFAULT_MODEL, MODEL_OPTIONS } from "@/config/models";
import {
  analysisReady,
  analysisStatusLoaded,
  loadProjectAnalysisStatus,
  setProjectAnalysisReady,
} from "@/state/projectAnalysis";

const instance = getCurrentInstance();
if (instance === null) {
  ElMessage({ message: "平台出现了一些问题，无法获取关键信息", type: "error" });
}
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");

const llm = ref(DEFAULT_MODEL);
const options = MODEL_OPTIONS;
const {
  isRunning,
  completed,
  cancelled,
  saved,
  fromCache,
  ready,
  summary,
  menu,
  answer,
  reasoningSections,
  usage,
  usageReceived,
  error: streamError,
  progress,
  meta,
  hasActivity,
  start,
  cancel,
} = useLlmStream(requestUrl);

const runTestPlan = async (regenerate: boolean) => {
  const succeeded = await start("/project/llm/plan/stream", {
    pid: projectId,
    llm_name: llm.value,
    regenerate,
  });
  if (succeeded) {
    if (ready.value) {
      setProjectAnalysisReady(menu.value);
      if (instance) instance.appContext.config.globalProperties.$test_menu = menu.value;
    }
    ElMessage({
      message: fromCache.value
        ? "已读取保存的业务分析、测试计划和测试菜单"
        : "业务分析、测试计划和测试菜单已生成并保存",
      type: "success",
    });
  } else if (streamError.value) {
    ElMessage({
      message: `业务分析与测试计划生成失败：${streamError.value.message}`,
      type: "error",
    });
  }
};

const startTestPlan = () => runTestPlan(false);
const restartTestPlan = () => runTestPlan(true);
const cancelTestPlan = () => {
  cancel();
  ElMessage({ message: "已取消生成，本次结果不会保存", type: "warning" });
};

onMounted(async () => {
  try {
    if (!analysisStatusLoaded.value) {
      await loadProjectAnalysisStatus(requestUrl, projectId);
    }
    if (analysisReady.value) await runTestPlan(false);
  } catch {
    // A missing bundle is the normal state for a newly created project.
  }
});
</script>
