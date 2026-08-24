<template>
  <OnboardingShell
    eyebrow="项目入口"
    title="进入 EzllmTest"
    description="打开已有项目可继续资料恢复、业务分析和测试计划；创建新项目则从文档引导开始。"
  >
    <section v-if="hasRecovery" class="recovery-card" aria-labelledby="recovery-title">
      <div class="recovery-card__header">
        <div>
          <h2 id="recovery-title">继续上次项目</h2>
          <p>{{ recoveryDescription }}</p>
        </div>
        <span>{{ recoveryStatus }}</span>
      </div>
      <ProjectIdDisplay
        :pid="projectSetupState.pid"
        title-id="recovery-project-id-title"
        compact
      />
      <WorkflowActionBar aria-label="上次项目操作">
        <el-button type="primary" :disabled="loginPending" @click="continueRecovery">
          {{ recoveryActionLabel }}
        </el-button>
      </WorkflowActionBar>
    </section>

    <form class="open-project" novalidate @submit.prevent="login">
      <h2>打开已有项目</h2>
      <p>
        输入创建时保存的 21 位项目 ID。验证完成后，未完成资料会进入恢复页；已完成项目进入测试计划。
      </p>
      <label for="existing-project-id">项目 ID</label>
      <el-input
        id="existing-project-id"
        v-model="inputPid"
        maxlength="21"
        autocomplete="off"
        clearable
        :disabled="loginPending"
        :aria-invalid="Boolean(loginError)"
        aria-describedby="project-id-hint"
        placeholder="例如：Ez1234567890123456789"
      />
      <p id="project-id-hint" class="field-hint">格式为 Ez 加 19 位数字。</p>

      <FeedbackState
        v-if="loginPending"
        kind="loading"
        title="正在读取项目状态"
        description="只读取项目和资料状态，不会启动模型分析。"
        compact
      />
      <FeedbackState
        v-else-if="loginError"
        kind="error"
        title="项目打开失败"
        :description="loginError"
        compact
      />

      <WorkflowActionBar aria-label="打开已有项目">
        <el-button
          native-type="submit"
          type="primary"
          :loading="loginPending"
          :disabled="loginPending"
        >
          打开已有项目
        </el-button>
      </WorkflowActionBar>
      <p class="flow-note">打开后可继续开始分析业务和生成测试计划，生成动作仍需由你明确触发。</p>
    </form>

    <template #secondary>
      <section class="create-entry" aria-labelledby="create-entry-title">
        <p class="create-entry__eyebrow">首次使用</p>
        <h2 id="create-entry-title">创建新项目</h2>
        <p>为项目命名并分别上传测试知识库、业务需求和开发设计文档。</p>
        <ul>
          <li>创建前确认文件数量</li>
          <li>逐文件显示真实上传进度</li>
          <li>失败后复用已经成功的文件</li>
        </ul>
        <el-button
          type="primary"
          plain
          :disabled="loginPending"
          @click="startNewProject"
        >
          创建新项目
        </el-button>
      </section>
    </template>
  </OnboardingShell>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, onBeforeUnmount, ref } from "vue";
import axios from "axios";
import { useRouter } from "vue-router";
import OnboardingShell from "@/components/onboarding/OnboardingShell.vue";
import ProjectIdDisplay from "@/components/onboarding/ProjectIdDisplay.vue";
import FeedbackState from "@/components/workspace/FeedbackState.vue";
import WorkflowActionBar from "@/components/workspace/WorkflowActionBar.vue";
import { resetProjectAnalysisState } from "@/state/projectAnalysis";
import {
  applyProjectSetupStatus,
  fetchProjectSetupStatus,
  projectSetupState,
  resetProjectSetupState,
  restoreProjectSetupState,
} from "@/state/projectSetup";
import {
  confirmRecoveryDiscard,
  confirmRecoverySwitch,
} from "@/ui/confirmations";

const PROJECT_ID_PATTERN = /^Ez\d{19}$/;
const inputPid = ref("");
const loginPending = ref(false);
const loginError = ref("");
const instance = getCurrentInstance();
const router = useRouter();
const requestUrl = String(
  instance?.appContext.config.globalProperties.$requestUrl || ""
);
let loginController: AbortController | null = null;

if (instance !== null) {
  instance.appContext.config.globalProperties.$test_menu = null;
  instance.appContext.config.globalProperties.$unit_menu_result = null;
  instance.appContext.config.globalProperties.$integration_menu_result = null;
  instance.appContext.config.globalProperties.$id = null;
  resetProjectAnalysisState();
}

restoreProjectSetupState();

const hasRecovery = computed(() => Boolean(projectSetupState.pid));
const recoveryComplete = computed(
  () => projectSetupState.stage === "setup_complete"
);
const recoveryStatus = computed(() =>
  recoveryComplete.value ? "资料已确认" : "资料未完成"
);
const recoveryActionLabel = computed(() =>
  recoveryComplete.value ? "验证并打开项目" : "继续上传资料"
);
const recoveryDescription = computed(() =>
  recoveryComplete.value
    ? "本机保存了一个已完成项目。打开前会重新读取服务器状态。"
    : "本机保存了未完成的资料进度，可继续上传且不会重复发送已成功文件。"
);

const syncGlobalProjectId = (pid: string): void => {
  if (instance !== null) {
    instance.appContext.config.globalProperties.$id = pid;
  }
};

const errorMessage = (caught: unknown, fallback: string): string => {
  if (axios.isAxiosError(caught)) {
    return String(caught.response?.data?.reason || caught.message || fallback);
  }
  return caught instanceof Error ? caught.message : fallback;
};

const login = async (): Promise<void> => {
  if (loginPending.value) return;
  const normalizedPid = inputPid.value.trim();
  inputPid.value = normalizedPid;
  loginError.value = "";
  if (!PROJECT_ID_PATTERN.test(normalizedPid)) {
    loginError.value = "项目 ID 格式有误，应为 Ez 加 19 位数字。";
    return;
  }

  loginPending.value = true;
  const controller = new AbortController();
  loginController = controller;
  try {
    const loginResponse = await axios.get(
      `${requestUrl}/project/login/${encodeURIComponent(normalizedPid)}`,
      { signal: controller.signal }
    );
    if (loginResponse.data?.data === false) {
      throw new Error(String(loginResponse.data?.reason || "项目不存在"));
    }

    const status = await fetchProjectSetupStatus(
      requestUrl,
      normalizedPid,
      controller.signal
    );
    if (status.stage === "setup_complete") {
      syncGlobalProjectId(normalizedPid);
      await router.push({ name: "testMain" });
      return;
    }

    if (
      projectSetupState.pid &&
      projectSetupState.pid !== normalizedPid &&
      projectSetupState.stage !== "setup_complete" &&
      !(await confirmRecoverySwitch(projectSetupState.pid, normalizedPid))
    ) {
      return;
    }
    applyProjectSetupStatus(status);
    syncGlobalProjectId(normalizedPid);
    await router.push("/create");
  } catch (caught) {
    if (!axios.isCancel(caught)) {
      loginError.value = errorMessage(caught, "项目状态读取失败，请重试。");
    }
  } finally {
    if (loginController === controller) loginController = null;
    loginPending.value = false;
  }
};

const continueRecovery = async (): Promise<void> => {
  inputPid.value = projectSetupState.pid;
  if (recoveryComplete.value) {
    await login();
    return;
  }
  syncGlobalProjectId(projectSetupState.pid);
  await router.push("/create");
};

const startNewProject = async (): Promise<void> => {
  if (
    projectSetupState.pid &&
    !(await confirmRecoveryDiscard(projectSetupState.pid))
  ) {
    return;
  }
  if (projectSetupState.pid) resetProjectSetupState();
  await router.push("/create");
};

onBeforeUnmount(() => loginController?.abort());
</script>

<style scoped>
.recovery-card,
.open-project {
  min-width: 0;
}

.recovery-card {
  margin-bottom: var(--ez-space-8);
  padding-bottom: var(--ez-space-8);
  border-bottom: 1px solid var(--ez-color-border);
}

.recovery-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ez-space-4);
  margin-bottom: var(--ez-space-4);
}

.recovery-card__header span {
  flex: 0 0 auto;
  padding: var(--ez-space-1) var(--ez-space-2);
  border-radius: var(--ez-radius-pill);
  background: var(--ez-color-warning-bg);
  color: var(--ez-color-warning);
  font-size: var(--ez-font-size-12);
  font-weight: 700;
}

h2,
p,
li { overflow-wrap: anywhere; }

h2 {
  margin: 0;
  font-size: var(--ez-font-size-20);
  line-height: var(--ez-line-height-tight);
}

.recovery-card__header p,
.open-project > p,
.create-entry > p,
.flow-note,
.field-hint {
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
}

.recovery-card__header p,
.open-project > p,
.create-entry > p { margin: var(--ez-space-1) 0 0; }

.open-project label {
  display: block;
  margin: var(--ez-space-5, 20px) 0 var(--ez-space-2);
  font-weight: 700;
}

.field-hint {
  margin: var(--ez-space-1) 0 var(--ez-space-4);
  font-size: var(--ez-font-size-13);
}

.flow-note {
  margin: var(--ez-space-3) 0 0;
  font-size: var(--ez-font-size-13);
}

.create-entry__eyebrow {
  margin: 0 0 var(--ez-space-1);
  color: var(--ez-color-brand-600);
  font-size: var(--ez-font-size-13);
  font-weight: 700;
}

.create-entry ul {
  margin: var(--ez-space-4) 0;
  padding-left: var(--ez-space-6);
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
}

@media (max-width: 480px) {
  .recovery-card__header { flex-direction: column; }
  .create-entry :deep(.el-button) { width: 100%; }
}
</style>
