<template>
  <OnboardingShell
    wide
    eyebrow="项目资料"
    title="创建或恢复项目"
    description="三个文档组按顺序上传；成功文件会立即记录，失败重试不会重复发送。资料确认后也不会自动启动模型分析。"
  >
    <WorkflowActionBar aria-label="创建流程导航" class="create-navigation">
      <el-button :disabled="setupRequestActive" @click="requestExit"> 返回项目入口 </el-button>
      <el-button
        v-if="projectId"
        type="warning"
        plain
        :disabled="setupRequestActive"
        @click="discardRestoredProject"
      >
        清除本机恢复并创建其他项目
      </el-button>
    </WorkflowActionBar>

    <FeedbackState
      v-if="restoreLoading"
      kind="loading"
      title="正在恢复项目资料状态"
      description="只读取已上传文件，不会上传新文件或启动模型。"
      skeleton="form"
      compact
    />
    <FeedbackState
      v-else-if="restoreError"
      kind="error"
      title="项目资料状态恢复失败"
      :description="restoreError"
      compact
    >
      <template #actions>
        <el-button type="primary" plain @click="retryRestore">重新读取状态</el-button>
      </template>
    </FeedbackState>

    <form class="create-form" novalidate @submit.prevent="createProject">
      <section v-if="!projectId" class="project-identity" aria-labelledby="project-name-title">
        <div>
          <h2 id="project-name-title">项目名称</h2>
          <p>创建后名称不可在本流程修改；请使用便于团队识别的名称。</p>
        </div>
        <label for="project-name">名称</label>
        <el-input
          id="project-name"
          v-model="inputName"
          maxlength="80"
          show-word-limit
          :disabled="Boolean(projectId) || setupRequestActive"
          :aria-invalid="Boolean(projectNameError)"
          placeholder="例如：订单服务回归测试"
        />
        <p v-if="projectNameError" class="field-error" role="alert">
          {{ projectNameError }}
        </p>
      </section>

      <ProjectIdDisplay v-if="projectId" :pid="projectId" title-id="setup-project-id-title" />

      <div class="document-groups">
        <DocumentUploadGroup
          v-model="fileListKnowledge"
          group-id="knowledge-documents"
          title="1. 测试知识库"
          description="上传测试理论、规范、最佳实践等辅助知识。至少需要一个文件。"
          :max-size-mb="50"
          :status="projectSetupState.groups.knowledge"
          :stored-files="projectSetupState.documentFiles.knowledge"
          :disabled="projectSetupState.groups.knowledge === 'completed'"
          :busy="setupRequestActive"
          :progress="progressFor('knowledge')"
          :error="groupErrors.knowledge"
          :before-upload="handleBeforeUploadKnowledge"
          :before-remove="beforeRemove"
        />
        <DocumentUploadGroup
          v-model="fileListRequirementTestDoc"
          group-id="requirements-documents"
          title="2. 业务需求文档"
          description="上传需求规格、用户故事、业务流程等待验证资料。至少需要一个文件。"
          :max-size-mb="10"
          :status="projectSetupState.groups.requirements"
          :stored-files="projectSetupState.documentFiles.requirements"
          :disabled="projectSetupState.groups.requirements === 'completed'"
          :busy="setupRequestActive"
          :progress="progressFor('requirements')"
          :error="groupErrors.requirements"
          :before-upload="handleBeforeUploadRequirementTestdoc"
          :before-remove="beforeRemove"
        />
        <DocumentUploadGroup
          v-model="fileListDesignTestDoc"
          group-id="design-documents"
          title="3. 开发设计文档"
          description="上传概要设计、详细设计、接口或数据设计等资料。至少需要一个文件。"
          :max-size-mb="10"
          :status="projectSetupState.groups.design"
          :stored-files="projectSetupState.documentFiles.design"
          :disabled="projectSetupState.groups.design === 'completed'"
          :busy="setupRequestActive"
          :progress="progressFor('design')"
          :error="groupErrors.design"
          :before-upload="handleBeforeUploadDesignTestdoc"
          :before-remove="beforeRemove"
        />
      </div>

      <FeedbackState
        v-if="setupRequestActive"
        kind="loading"
        :title="createInfo"
        description="请保持页面打开。此阶段不会调用模型或 embedding。"
        compact
      />
      <FeedbackState
        v-else-if="workflowError"
        kind="error"
        title="项目资料尚未完成"
        :description="workflowError"
        compact
      />

      <WorkflowActionBar aria-label="项目创建与恢复操作" class="create-actions">
        <el-button
          v-if="!canContinueToPlan"
          native-type="submit"
          type="primary"
          size="large"
          :loading="setupRequestActive"
          :disabled="setupRequestActive"
        >
          {{ createButtonText }}
        </el-button>
        <el-button
          v-else
          type="primary"
          size="large"
          :disabled="setupRequestActive"
          @click="goToPlan"
        >
          前往测试计划
        </el-button>
      </WorkflowActionBar>
    </form>

    <el-dialog
      v-model="centerDialogVisible"
      class="setup-dialog"
      width="min(840px, calc(100vw - 32px))"
      :show-close="!setupRequestActive"
      :close-on-click-modal="false"
      :close-on-press-escape="!setupRequestActive"
      align-center
      aria-label="项目资料进度"
    >
      <div class="setup-dialog__grid">
        <el-steps
          :active="activeStep"
          direction="vertical"
          finish-status="success"
          class="setup-dialog__steps"
        >
          <el-step title="生成项目 ID" :status="projectId ? 'finish' : 'wait'" />
          <el-step title="测试知识库" :status="stepStatus(projectSetupState.groups.knowledge)" />
          <el-step title="业务需求" :status="stepStatus(projectSetupState.groups.requirements)" />
          <el-step title="开发设计" :status="stepStatus(projectSetupState.groups.design)" />
          <el-step title="确认资料" :status="finalizeStepStatus" />
        </el-steps>
        <div class="setup-dialog__details">
          <h2>项目资料进度</h2>
          <p aria-live="polite">{{ createInfo }}</p>
          <ProjectIdDisplay
            v-if="projectId"
            :pid="projectId"
            title-id="dialog-project-id-title"
            compact
          />
          <ul v-if="projectId" class="setup-dialog__summary">
            <li v-for="group in setupGroups" :key="group">
              {{ groupLabels[group] }}：{{ projectSetupState.documentCounts[group] }} 个已上传
            </li>
          </ul>
          <FeedbackState
            v-if="workflowError"
            kind="error"
            title="需要处理后继续"
            :description="workflowError"
            compact
          />
          <FeedbackState
            v-else-if="canContinueToPlan"
            kind="empty"
            title="项目资料已确认，尚未开始模型分析"
            description="你可以保存项目 ID 后显式进入测试计划。"
            compact
          />
        </div>
      </div>
      <template #footer>
        <WorkflowActionBar aria-label="项目资料进度操作">
          <el-button :disabled="setupRequestActive" @click="requestExit"> 返回项目入口 </el-button>
          <el-button
            v-if="hasFailure"
            type="warning"
            :disabled="setupRequestActive"
            @click="centerDialogVisible = false"
          >
            返回检查待上传文件
          </el-button>
          <el-button
            v-if="canContinueToPlan"
            type="primary"
            :disabled="setupRequestActive"
            @click="goToPlan"
          >
            前往测试计划
          </el-button>
        </WorkflowActionBar>
      </template>
    </el-dialog>
  </OnboardingShell>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import axios from "axios";
import type { UploadProps, UploadRawFile, UploadUserFile } from "element-plus";
import { ElMessage } from "@/shared/plugins/elementPlus";
import { onBeforeRouteLeave, useRouter } from "vue-router";
import OnboardingShell from "@/features/onboarding/components/OnboardingShell.vue";
import ProjectIdDisplay from "@/features/onboarding/components/ProjectIdDisplay.vue";
import DocumentUploadGroup from "@/features/onboarding/components/DocumentUploadGroup.vue";
import FeedbackState from "@/shared/components/FeedbackState.vue";
import WorkflowActionBar from "@/shared/components/WorkflowActionBar.vue";
import { resetProjectAnalysisState } from "@/features/planning/state/projectAnalysis";
import {
  beginProjectSetup,
  loadProjectSetupStatus,
  finalizeProjectSetup,
  isUploadedDocument,
  markSetupGroup,
  normalizeUploadedDocumentName,
  projectSetupState,
  recordUploadedDocument,
  resetProjectSetupState,
  restoreProjectSetupState,
  setupRequestActive,
} from "@/features/onboarding/state/projectSetup";
import type { SetupGroup, SetupStepState } from "@/features/onboarding/state/projectSetup";
import {
  confirmPendingFileRemoval,
  confirmProjectCreation,
  confirmProjectSetupExit,
  confirmRecoveryDiscard,
} from "@/shared/ui/confirmations";

interface ActiveUpload {
  group: SetupGroup;
  fileName: string;
  current: number;
  total: number;
}

const setupGroups: SetupGroup[] = ["knowledge", "requirements", "design"];
const allowedExtensions = ["txt", "pdf", "md", "doc", "docx"];
const INVALID_PROJECT_NAME_PATH = /[/\\]/;
/**
 * 判断是否存在控件 character，并保持现有状态与错误处理语义。
 */
const hasControlCharacter = (value: string): boolean =>
  Array.from(value).some((character) => {
    const code = character.charCodeAt(0);
    return code <= 31 || code === 127;
  });
const groupLabels: Record<SetupGroup, string> = {
  knowledge: "测试知识库",
  requirements: "业务需求文档",
  design: "开发设计文档",
};

const instance = getCurrentInstance();
const router = useRouter();
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const inputName = ref("");
const fileListKnowledge = ref<UploadUserFile[]>([]);
const fileListRequirementTestDoc = ref<UploadUserFile[]>([]);
const fileListDesignTestDoc = ref<UploadUserFile[]>([]);
const projectId = ref("");
const projectNameError = ref("");
const workflowError = ref("");
const restoreError = ref("");
const restoreLoading = ref(false);
const centerDialogVisible = ref(false);
const createInfo = ref("请检查项目名称和三个文档组");
const activeUpload = ref<ActiveUpload | null>(null);
const invalidFileUids = new Set<number>();
const groupErrors = reactive<Record<SetupGroup, string>>({
  knowledge: "",
  requirements: "",
  design: "",
});

/**
 * 派生用于界面展示或请求判断的can continue计划。
 */
const canContinueToPlan = computed(() => projectSetupState.stage === "setup_complete");
/**
 * 派生用于界面展示或请求判断的has失败状态。
 */
const hasFailure = computed(() =>
  Object.values(projectSetupState.groups).some((state) => state === "failed"),
);
/**
 * 派生用于界面展示或请求判断的create button文本。
 */
const createButtonText = computed(() =>
  projectId.value ? "继续上传未完成资料" : "确认创建并上传",
);
/**
 * 派生用于界面展示或请求判断的当前活动步骤。
 */
const activeStep = computed(() => {
  if (projectSetupState.stage === "setup_complete") return 5;
  return (
    (projectId.value ? 1 : 0) +
    Object.values(projectSetupState.groups).filter((state) => state === "completed").length
  );
});
/**
 * 派生用于界面展示或请求判断的finalize步骤状态。
 */
const finalizeStepStatus = computed(() => {
  if (projectSetupState.stage === "setup_complete") return "finish";
  return setupRequestActive.value && activeStep.value >= 4 ? "process" : "wait";
});

/**
 * 处理步骤状态，并保持现有输入输出约定。
 */
const stepStatus = (state: SetupStepState): "wait" | "process" | "finish" | "error" => {
  if (state === "completed") return "finish";
  if (state === "running") return "process";
  if (state === "failed") return "error";
  return "wait";
};

/**
 * 处理progress for，并保持现有输入输出约定。
 */
const progressFor = (group: SetupGroup): ActiveUpload | undefined =>
  activeUpload.value?.group === group ? activeUpload.value : undefined;

/**
 * 同步global项目 ID，并保持现有状态与错误处理语义。
 */
const syncGlobalProjectId = (): void => {
  if (instance !== null) {
    instance.appContext.config.globalProperties.$id = projectId.value || null;
    instance.appContext.config.globalProperties.$unit_menu_result = null;
  }
};

/**
 * 处理错误消息，并保持现有输入输出约定。
 *
 * @param caught 沿用当前 TypeScript 类型约束的输入。
 * @param fallback 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
 */
const errorMessage = (caught: unknown, fallback: string): string => {
  if (axios.isAxiosError(caught)) {
    return String(caught.response?.data?.reason || caught.message || fallback);
  }
  return caught instanceof Error ? caught.message : fallback;
};

/**
 * 处理文件 for分组，并保持现有输入输出约定。
 */
const filesForGroup = (group: SetupGroup): UploadUserFile[] => {
  if (group === "knowledge") return fileListKnowledge.value;
  if (group === "requirements") return fileListRequirementTestDoc.value;
  return fileListDesignTestDoc.value;
};

/**
 * 设置文件 for分组，并保持现有状态与错误处理语义。
 */
const setFilesForGroup = (group: SetupGroup, files: UploadUserFile[]): void => {
  if (group === "knowledge") fileListKnowledge.value = files;
  else if (group === "requirements") fileListRequirementTestDoc.value = files;
  else fileListDesignTestDoc.value = files;
};

/**
 * 校验文件，并保持现有状态与错误处理语义。
 *
 * @param group 沿用当前 TypeScript 类型约束的输入。
 * @param file 沿用当前 TypeScript 类型约束的输入。
 * @param maxSizeMb 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const validateFile = (group: SetupGroup, file: UploadRawFile, maxSizeMb: number): boolean => {
  const extension = file.name.includes(".")
    ? file.name.split(".").pop()?.toLocaleLowerCase() || ""
    : "";
  let message = "";
  if (!allowedExtensions.includes(extension)) {
    message = `${groupLabels[group]}仅支持 txt、pdf、md、doc、docx 文件`;
  } else if (file.size / 1024 / 1024 > maxSizeMb) {
    message = `${file.name} 超过单个文件 ${maxSizeMb}MB 的限制`;
  } else {
    const normalized = normalizeUploadedDocumentName(file.name);
    const duplicateLocal = filesForGroup(group).some(
      (selected) =>
        selected.uid !== file.uid &&
        normalizeUploadedDocumentName(selected.name).toLocaleLowerCase() ===
          normalized.toLocaleLowerCase(),
    );
    if (duplicateLocal || isUploadedDocument(group, normalized)) {
      message = `${file.name} 与本组已选择或已上传文件重名`;
    }
  }

  if (!message) {
    groupErrors[group] = "";
    return true;
  }
  invalidFileUids.add(file.uid);
  groupErrors[group] = message;
  ElMessage.warning(message);
  return false;
};

/**
 * 处理前置上传 knowledge，并保持现有状态与错误处理语义。
 */
const handleBeforeUploadKnowledge: UploadProps["beforeUpload"] = (file) =>
  validateFile("knowledge", file, 50);
/**
 * 处理前置上传 requirement testdoc，并保持现有状态与错误处理语义。
 */
const handleBeforeUploadRequirementTestdoc: UploadProps["beforeUpload"] = (file) =>
  validateFile("requirements", file, 10);
/**
 * 处理前置上传 design testdoc，并保持现有状态与错误处理语义。
 */
const handleBeforeUploadDesignTestdoc: UploadProps["beforeUpload"] = (file) =>
  validateFile("design", file, 10);

/**
 * 处理前置 remove，并保持现有输入输出约定。
 *
 * @param uploadFile 沿用当前 TypeScript 类型约束的输入。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
 */
const beforeRemove: UploadProps["beforeRemove"] = async (uploadFile) => {
  if (invalidFileUids.delete(uploadFile.uid)) return true;
  if (setupRequestActive.value) return false;
  return confirmPendingFileRemoval(uploadFile.name);
};

/**
 * 校验项目名称，并保持现有状态与错误处理语义。
 */
const validateProjectName = (): boolean => {
  inputName.value = inputName.value.trim();
  if (!inputName.value) projectNameError.value = "请输入项目名称。";
  else if (inputName.value.length > 80) projectNameError.value = "项目名称不能超过 80 个字符。";
  else if (
    INVALID_PROJECT_NAME_PATH.test(inputName.value) ||
    hasControlCharacter(inputName.value)
  ) {
    projectNameError.value = "项目名称不能包含斜杠或控制字符。";
  } else projectNameError.value = "";
  return !projectNameError.value;
};

/**
 * 处理pending分组 has文件，并保持现有输入输出约定。
 */
const pendingGroupHasFiles = (group: SetupGroup): boolean => {
  if (projectSetupState.groups[group] === "completed") return true;
  const pending = filesForGroup(group).filter((file) => !isUploadedDocument(group, file.name));
  if (pending.length > 0) return true;
  if (projectSetupState.documentCounts[group] > 0) {
    markSetupGroup(group, "completed");
    return true;
  }
  groupErrors[group] = `请至少选择一个${groupLabels[group]}文件`;
  return false;
};

/**
 * 校验初始化输入，并保持现有状态与错误处理语义。
 */
const validateSetupInput = (): boolean => {
  workflowError.value = "";
  const nameValid = projectId.value ? true : validateProjectName();
  const groupsValid = setupGroups.map(pendingGroupHasFiles).every(Boolean);
  if (!nameValid || !groupsValid) {
    workflowError.value = "请修正项目名称并补齐三个必需文档组。";
  }
  return nameValid && groupsValid;
};

/**
 * 处理register项目，并保持现有输入输出约定。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
 */
const registerProject = async (): Promise<boolean> => {
  try {
    createInfo.value = "正在创建项目并生成项目 ID";
    const response = await axios.post(
      `${requestUrl}/project/add/${encodeURIComponent(inputName.value)}`,
    );
    if (!response.data?.data) {
      throw new Error(String(response.data?.reason || "项目创建失败"));
    }
    projectId.value = String(response.data.data);
    beginProjectSetup(projectId.value);
    syncGlobalProjectId();
    createInfo.value = "项目 ID 已生成，准备上传项目资料";
    return true;
  } catch (caught) {
    workflowError.value = errorMessage(caught, "项目创建请求失败");
    createInfo.value = workflowError.value;
    return false;
  }
};

/**
 * 移除pending文件，并保持现有状态与错误处理语义。
 */
const removePendingFile = (group: SetupGroup, uid: number): void => {
  setFilesForGroup(
    group,
    filesForGroup(group).filter((file) => file.uid !== uid),
  );
};

/**
 * 处理上传分组，并保持现有输入输出约定。
 *
 * @param group 沿用当前 TypeScript 类型约束的输入。
 * @param doctype 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
 */
const uploadGroup = async (group: SetupGroup, doctype: number): Promise<boolean> => {
  if (projectSetupState.groups[group] === "completed") return true;
  const pendingFiles = filesForGroup(group).filter((file) => !isUploadedDocument(group, file.name));
  if (!pendingFiles.length) {
    groupErrors[group] = `没有可上传的${groupLabels[group]}文件`;
    markSetupGroup(group, "failed");
    return false;
  }

  markSetupGroup(group, "running");
  groupErrors[group] = "";
  try {
    for (let index = 0; index < pendingFiles.length; index += 1) {
      const file = pendingFiles[index];
      activeUpload.value = {
        group,
        fileName: file.name,
        current: index + 1,
        total: pendingFiles.length,
      };
      createInfo.value = `正在上传${groupLabels[group]} ${index + 1}/${pendingFiles.length}：${file.name}`;
      if (!file.raw) throw new Error(`${file.name} 的本地文件内容不可用，请重新选择`);
      const formData = new FormData();
      formData.append("file", file.raw);
      const response = await axios.post(
        `${requestUrl}/uploadFile/${encodeURIComponent(projectId.value)}/${doctype}`,
        formData,
      );
      if (response.data?.data === false) {
        throw new Error(String(response.data?.reason || `${file.name} 上传失败`));
      }
      recordUploadedDocument(group, file.name);
      if (file.uid !== undefined) removePendingFile(group, file.uid);
    }
    markSetupGroup(group, "completed");
    createInfo.value = `${groupLabels[group]}上传完成`;
    return true;
  } catch (caught) {
    markSetupGroup(group, "failed");
    const detail = errorMessage(caught, `${groupLabels[group]}上传请求失败`);
    groupErrors[group] = `${groupLabels[group]}上传失败：${detail}。已成功文件将在重试时复用。`;
    workflowError.value = groupErrors[group];
    createInfo.value = groupErrors[group];
    return false;
  } finally {
    activeUpload.value = null;
  }
};

/**
 * 创建项目，并保持现有状态与错误处理语义。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const createProject = async (): Promise<boolean> => {
  if (setupRequestActive.value || !validateSetupInput()) return false;
  if (
    !projectId.value &&
    !(await confirmProjectCreation(inputName.value, {
      knowledge: fileListKnowledge.value.length,
      requirements: fileListRequirementTestDoc.value.length,
      design: fileListDesignTestDoc.value.length,
    }))
  ) {
    return false;
  }

  setupRequestActive.value = true;
  centerDialogVisible.value = true;
  workflowError.value = "";
  try {
    if (!projectId.value) {
      resetProjectAnalysisState();
      if (!(await registerProject())) return false;
    }
    const groups: Array<[SetupGroup, number]> = [
      ["knowledge", 1],
      ["requirements", 2],
      ["design", 3],
    ];
    for (const [group, doctype] of groups) {
      if (!(await uploadGroup(group, doctype))) return false;
    }

    createInfo.value = "正在核对项目资料（不会调用模型）";
    const remoteStatus = await loadProjectSetupStatus(requestUrl, projectId.value);
    const finalStatus =
      remoteStatus.stage === "setup_complete"
        ? remoteStatus
        : await finalizeProjectSetup(requestUrl, projectId.value);
    if (finalStatus.stage !== "setup_complete") {
      throw new Error(finalStatus.message || "项目资料尚未完成确认");
    }
    syncGlobalProjectId();
    createInfo.value = "项目资料已确认，尚未开始模型分析";
    ElMessage.success("项目资料已确认");
    return true;
  } catch (caught) {
    workflowError.value = errorMessage(caught, "项目创建流程失败");
    createInfo.value = workflowError.value;
    return false;
  } finally {
    setupRequestActive.value = false;
  }
};

/**
 * 处理retry restore，并保持现有输入输出约定。
 */
const retryRestore = async (): Promise<void> => {
  if (!projectId.value || restoreLoading.value) return;
  restoreLoading.value = true;
  restoreError.value = "";
  try {
    const status = await loadProjectSetupStatus(requestUrl, projectId.value);
    createInfo.value = status.message;
    if (status.stage === "setup_complete") centerDialogVisible.value = true;
  } catch (caught) {
    restoreError.value = errorMessage(caught, "项目资料状态恢复失败");
  } finally {
    restoreLoading.value = false;
  }
};

/**
 * 处理discard restored项目，并保持现有输入输出约定。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const discardRestoredProject = async (): Promise<void> => {
  if (!projectId.value || !(await confirmRecoveryDiscard(projectId.value))) return;
  resetProjectSetupState();
  resetProjectAnalysisState();
  projectId.value = "";
  inputName.value = "";
  fileListKnowledge.value = [];
  fileListRequirementTestDoc.value = [];
  fileListDesignTestDoc.value = [];
  setupGroups.forEach((group) => {
    groupErrors[group] = "";
  });
  workflowError.value = "";
  restoreError.value = "";
  centerDialogVisible.value = false;
  syncGlobalProjectId();
};

/**
 * 跳转到计划，并保持现有状态与错误处理语义。
 */
const goToPlan = async (): Promise<void> => {
  if (!canContinueToPlan.value) return;
  syncGlobalProjectId();
  await router.push("/plan");
};

/**
 * 处理请求 exit，并保持现有输入输出约定。
 */
const requestExit = async (): Promise<void> => {
  await router.push("/");
};

/**
 * 处理warn前置 unload，并保持现有输入输出约定。
 */
const warnBeforeUnload = (event: BeforeUnloadEvent): void => {
  if (!setupRequestActive.value) return;
  event.preventDefault();
  event.returnValue = "";
};

/**
 * 响应前置路由 leave，并保持现有状态与错误处理语义。
 */
onBeforeRouteLeave(async () => {
  if (setupRequestActive.value) {
    ElMessage.warning("当前上传或资料确认尚未结束，请等待完成后再离开。 ");
    return false;
  }
  if (projectId.value && !canContinueToPlan.value) {
    return confirmProjectSetupExit(projectId.value);
  }
  return true;
});

/**
 * 组件挂载后执行既有初始化或恢复流程。
 */
onMounted(async () => {
  window.addEventListener("beforeunload", warnBeforeUnload);
  if (!restoreProjectSetupState()) return;
  projectId.value = projectSetupState.pid;
  syncGlobalProjectId();
  await retryRestore();
});

/**
 * 组件卸载时释放事件监听、定时器或流式连接。
 */
onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", warnBeforeUnload);
});
</script>

<style scoped>
.create-navigation {
  margin-top: 0;
  margin-bottom: var(--ez-space-6);
}
.create-form,
.project-identity,
.document-groups {
  min-width: 0;
}

.create-form {
  display: grid;
  gap: var(--ez-space-6);
  max-width: var(--ez-content-default);
  margin: 0 auto;
}

.project-identity {
  padding: var(--ez-space-6);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-large);
  background: var(--ez-color-surface-subtle);
}

h2,
p {
  overflow-wrap: anywhere;
}
h2 {
  margin: 0;
  font-size: var(--ez-font-size-20);
  line-height: var(--ez-line-height-tight);
}
.project-identity > div p {
  margin: var(--ez-space-1) 0 0;
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
}
.project-identity label {
  display: block;
  margin: var(--ez-space-4) 0 var(--ez-space-2);
  font-weight: 700;
}
.field-error {
  margin: var(--ez-space-2) 0 0;
  color: var(--ez-color-danger);
}

.document-groups {
  display: grid;
  gap: var(--ez-space-6);
}
.create-actions {
  justify-content: flex-end;
  margin-top: 0;
}

.setup-dialog__grid {
  display: grid;
  grid-template-columns: minmax(180px, 0.65fr) minmax(0, 1.35fr);
  gap: var(--ez-space-8);
  min-width: 0;
}
.setup-dialog__steps {
  min-height: 320px;
}
.setup-dialog__details {
  min-width: 0;
}
.setup-dialog__details > p {
  margin: var(--ez-space-2) 0 var(--ez-space-4);
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
}
.setup-dialog__summary {
  margin: var(--ez-space-4) 0;
  padding-left: var(--ez-space-6);
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
}

@media (max-width: 767px) {
  .project-identity {
    padding: var(--ez-space-4);
  }
  .setup-dialog__grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .setup-dialog__steps {
    min-height: 300px;
  }
}
</style>
