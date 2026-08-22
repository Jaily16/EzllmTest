<template>
  <div class="common-layout" style="min-width: 500px">
    <el-container>
      <el-header style="position: sticky; top: 0; z-index: 999">
        <el-image
          style="width: 50px; height: 50px; margin-top: 5px"
          :src="require('@/assets/static/image/ezlogo.png')"
          fit="fill"
        />
        <div class="en_name">EzllmTest</div>
        <el-divider style="background-color: white; margin-top: 26px" direction="vertical" />
        <div class="page_name">创建新项目</div>
      </el-header>
      <el-main>
        <el-alert
          v-if="project_id"
          :title="`已恢复项目 ${project_id}：${projectSetupState.message || '可继续上传资料'}`"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 20px"
        >
          <template #default>
            <el-button size="small" @click="discardRestoredProject">放弃恢复并创建新项目</el-button>
          </template>
        </el-alert>

        <div class="input_name_container">
          <el-icon size="24px" style="margin-top: 4px; margin-right: 5px"><Postcard /></el-icon>
          <div class="info">项目名称</div>
          <el-divider style="margin-top: 9px" direction="vertical" />
          <el-input
            v-model="input_name"
            style="width: 350px; margin-left: 20px"
            placeholder="请输入项目名称(项目名称不超过50个字)"
            maxlength="50"
            show-word-limit
            :suffix-icon="Memo"
            clearable
            :disabled="Boolean(project_id)"
          />
          <RouterLink to="/">
            <el-button type="info" size="large" style="width: 120px; position: absolute; right: 15px" :icon="Back">
              返回登入页面
            </el-button>
          </RouterLink>
        </div>

        <el-divider />
        <div class="input_name_container">
          <el-icon size="24px" style="margin-top: 4px; margin-right: 5px"><Collection /></el-icon>
          <div class="info">测试知识库</div>
        </div>
        <el-row><span style="font-size: small">(请勿传入与软件测试知识库无关的内容,否则会影响LLM正确生成结果)</span></el-row>
        <el-divider border-style="dashed">请上传希望LLM学习的软件测试相关知识库</el-divider>
        <el-upload
          class="upload_knowledge"
          v-model:file-list="fileListKnowledge"
          drag
          accept=".txt, .docx, .doc, .pdf, .md"
          multiple
          show-file-list
          :http-request="func"
          :before-upload="handleBeforeUploadKnowledge"
          :before-remove="beforeRemove"
          :disabled="projectSetupState.groups.knowledge === 'completed'"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">将文件拖拽到到此处或 <em>点击上传</em></div>
          <template #tip><div class="el-upload__tip">请上传(.txt/.pdf/.md/.docx/.doc)格式的文档,单个文件大小不得超过50MB</div></template>
        </el-upload>

        <el-divider />
        <div class="input_name_container">
          <el-icon size="24px" style="margin-top: 4px; margin-right: 5px"><DocumentAdd /></el-icon>
          <div class="info">业务文档-需求文档</div>
        </div>
        <el-row><span style="font-size: small">(请上传业务需求相关文档,例如需求文档、需求分析文档等)</span></el-row>
        <el-divider border-style="dashed">请上传需要进行分析的所有业务需求文档</el-divider>
        <el-upload
          class="upload_testdoc"
          v-model:file-list="fileListRequirementTestDoc"
          drag
          accept=".txt, .docx, .doc, .pdf, .md"
          multiple
          show-file-list
          :http-request="func"
          :before-upload="handleBeforeUploadRequirementTestdoc"
          :before-remove="beforeRemove"
          :disabled="projectSetupState.groups.requirements === 'completed'"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">将文件拖拽到到此处或 <em>点击上传</em></div>
          <template #tip><div class="el-upload__tip">请上传(.txt/.pdf/.md/.docx/.doc)格式的文档,单个文件大小不得超过10MB</div></template>
        </el-upload>

        <el-divider />
        <div class="input_name_container">
          <el-icon size="24px" style="margin-top: 4px; margin-right: 5px"><DocumentAdd /></el-icon>
          <div class="info">业务文档-开发设计文档</div>
        </div>
        <el-row><span style="font-size: small">(请上传业务开发设计相关文档,例如概要设计文档、详细设计文档等)</span></el-row>
        <el-divider border-style="dashed">请上传需要进行分析的所有业务开发设计文档</el-divider>
        <el-upload
          class="upload_testdoc"
          v-model:file-list="fileListDesignTestDoc"
          drag
          accept=".txt, .docx, .doc, .pdf, .md"
          multiple
          show-file-list
          :http-request="func"
          :before-upload="handleBeforeUploadDesignTestdoc"
          :before-remove="beforeRemove"
          :disabled="projectSetupState.groups.design === 'completed'"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">将文件拖拽到到此处或 <em>点击上传</em></div>
          <template #tip><div class="el-upload__tip">请上传(.txt/.pdf/.md/.docx/.doc)格式的文档,单个文件大小不得超过10MB</div></template>
        </el-upload>

        <el-divider />
        <el-button
          type="success"
          size="large"
          style="width: 140px; position: absolute; right: 15px"
          :icon="Cpu"
          :loading="setupRequestActive"
          :disabled="setupRequestActive"
          @click="createProject"
        >{{ createButtonText }}</el-button>
        <el-divider style="margin-top: 80px" border-style="dotted" />
      </el-main>
    </el-container>

    <el-dialog
      v-model="centerDialogVisible"
      width="760"
      :show-close="!setupRequestActive"
      :close-on-click-modal="false"
      align-center
    >
      <el-row style="min-width: 500px">
        <span class="cn_name" style="font-size: medium">基于知识库和业务文档信息创建项目</span>
      </el-row>
      <el-steps :active="activeStep" finish-status="success" align-center style="margin: 28px 0">
        <el-step title="生成项目id" :status="project_id ? 'finish' : 'wait'" />
        <el-step title="测试知识库" :status="stepStatus(projectSetupState.groups.knowledge)" />
        <el-step title="需求文档" :status="stepStatus(projectSetupState.groups.requirements)" />
        <el-step title="设计文档" :status="stepStatus(projectSetupState.groups.design)" />
        <el-step title="确认资料" :status="finalizeStepStatus" />
      </el-steps>
      <el-row style="min-width: 500px"><span class="cn_name" style="font-size: small">{{ createInfo }}</span></el-row>
      <el-row v-if="project_id" style="min-width: 500px; margin-top: 18px">
        <span class="cn_name" style="color: #c45656; font-size: small">请复制并妥善保存项目id：</span>
      </el-row>
      <el-row v-if="project_id" style="min-width: 500px; margin-top: 8px">
        <el-input v-model="project_id" style="width: 230px" readonly />
        <el-button type="success" style="margin-left: 10px" :icon="DocumentCopy" @click="copyId">复制项目id</el-button>
      </el-row>
      <template #footer>
        <RouterLink to="/"><el-button type="info">返回登入页面</el-button></RouterLink>
        <el-button v-if="hasFailure" type="warning" @click="centerDialogVisible = false">返回修改上传资料</el-button>
        <el-button
          v-if="canContinueToPlan"
          style="margin-left: 10px"
          type="success"
          @click="goToPlan"
        >开始分析业务和生成测试计划</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, onMounted, ref } from "vue";
import { Memo, Cpu, Back, DocumentCopy } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadProps, UploadUserFile } from "element-plus";
import useClipboard from "vue-clipboard3";
import axios from "axios";
import { useRouter } from "vue-router";
import { resetProjectAnalysisState } from "@/state/projectAnalysis";
import {
  beginProjectSetup,
  finalizeProjectSetup,
  loadProjectSetupStatus,
  markSetupGroup,
  projectSetupState,
  resetProjectSetupState,
  restoreProjectSetupState,
  setupRequestActive,
} from "@/state/projectSetup";
import type { SetupGroup, SetupStepState } from "@/state/projectSetup";

const instance = getCurrentInstance();
const router = useRouter();
const requestUrl = String(
  instance?.appContext.config.globalProperties.$requestUrl || ""
);
const input_name = ref("");
const fileListKnowledge = ref<UploadUserFile[]>([]);
const fileListRequirementTestDoc = ref<UploadUserFile[]>([]);
const fileListDesignTestDoc = ref<UploadUserFile[]>([]);
const project_id = ref("");
const centerDialogVisible = ref(false);
const createInfo = ref("正在初始化项目资料");
const { toClipboard } = useClipboard();
let fileUploadFault = false;

const canContinueToPlan = computed(
  () => projectSetupState.stage === "setup_complete"
);
const hasFailure = computed(() =>
  Object.values(projectSetupState.groups).some((state) => state === "failed")
);
const createButtonText = computed(() =>
  project_id.value ? "继续/重试" : "创建"
);
const activeStep = computed(() => {
  if (projectSetupState.stage === "setup_complete") return 5;
  const completedGroups = Object.values(projectSetupState.groups).filter(
    (state) => state === "completed"
  ).length;
  return (project_id.value ? 1 : 0) + completedGroups;
});
const finalizeStepStatus = computed(() => {
  if (projectSetupState.stage === "setup_complete") return "finish";
  return setupRequestActive.value && activeStep.value >= 4 ? "process" : "wait";
});

const stepStatus = (state: SetupStepState): "wait" | "process" | "finish" | "error" => {
  if (state === "completed") return "finish";
  if (state === "running") return "process";
  if (state === "failed") return "error";
  return "wait";
};

const syncGlobalProjectId = (): void => {
  if (instance !== null) {
    instance.appContext.config.globalProperties.$id = project_id.value || null;
    instance.appContext.config.globalProperties.$unit_menu_result = null;
  }
};

const copyId = async (): Promise<void> => {
  try {
    await toClipboard(project_id.value);
    ElMessage.success("已复制项目id");
  } catch {
    ElMessage.warning("项目id复制失败");
  }
};

const appendRawFile = (formData: FormData, file: UploadUserFile): boolean => {
  if (!file.raw) {
    ElMessage({ message: "上传文件内容不可用，请重新选择文件", type: "error" });
    return false;
  }
  formData.append("file", file.raw);
  return true;
};

const func = () => undefined;

const validateFile = (
  file: { name: string; size: number },
  files: UploadUserFile[],
  maxSizeMb: number,
  duplicateMessage: string
): boolean => {
  const fileSize = Number(file.size / 1024 / 1024);
  if (fileSize > maxSizeMb) {
    fileUploadFault = true;
    ElMessage({
      message: `您上传的文档单个文件大小超过${maxSizeMb}MB,请重新上传`,
      type: "warning",
    });
    return false;
  }
  if (files.some((selected) => selected.name === file.name)) {
    fileUploadFault = true;
    ElMessage({ message: duplicateMessage, type: "warning" });
    return false;
  }
  return true;
};

const handleBeforeUploadKnowledge: UploadProps["beforeUpload"] = (file) =>
  validateFile(file, fileListKnowledge.value, 50, "请勿重复上传知识库文件");

const handleBeforeUploadRequirementTestdoc: UploadProps["beforeUpload"] = (file) =>
  validateFile(
    file,
    fileListRequirementTestDoc.value,
    10,
    "请勿重复上传业务需求文档"
  );

const handleBeforeUploadDesignTestdoc: UploadProps["beforeUpload"] = (file) =>
  validateFile(
    file,
    fileListDesignTestDoc.value,
    10,
    "请勿重复上传业务开发设计文档"
  );

const beforeRemove: UploadProps["beforeRemove"] = (uploadFile) => {
  if (fileUploadFault) {
    fileUploadFault = false;
    return true;
  }
  return ElMessageBox.confirm(`您确定删除文档 ${uploadFile.name} 吗?`, "Warning", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning",
  }).then(
    () => true,
    () => false
  );
};

const registerProject = async (): Promise<boolean> => {
  try {
    const response = await axios.post(
      `${requestUrl}/project/add/${encodeURIComponent(input_name.value)}`
    );
    if (!response.data?.data) {
      throw new Error(String(response.data?.reason || "项目创建失败"));
    }
    project_id.value = String(response.data.data);
    beginProjectSetup(project_id.value);
    syncGlobalProjectId();
    createInfo.value = "项目id已生成，开始上传项目资料";
    return true;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "项目创建请求失败";
    createInfo.value = message;
    ElMessage({ message, type: "error" });
    return false;
  }
};

const groupLabels: Record<SetupGroup, string> = {
  knowledge: "测试知识库",
  requirements: "业务需求文档",
  design: "开发设计文档",
};

const uploadGroup = async (
  group: SetupGroup,
  doctype: number,
  files: UploadUserFile[]
): Promise<boolean> => {
  if (projectSetupState.groups[group] === "completed") return true;
  markSetupGroup(group, "running");
  createInfo.value = `正在上传${groupLabels[group]}`;
  try {
    for (const file of files) {
      const formData = new FormData();
      if (!appendRawFile(formData, file)) throw new Error("上传文件内容不可用");
      const response = await axios.post(
        `${requestUrl}/uploadFile/${encodeURIComponent(project_id.value)}/${doctype}`,
        formData
      );
      if (response.data?.data === false) {
        throw new Error(String(response.data?.reason || `${groupLabels[group]}上传失败`));
      }
    }
    markSetupGroup(group, "completed");
    createInfo.value = `${groupLabels[group]}上传完成`;
    return true;
  } catch (caught) {
    markSetupGroup(group, "failed");
    const message = caught instanceof Error ? caught.message : `${groupLabels[group]}上传请求失败`;
    createInfo.value = message;
    ElMessage({ message, type: "error" });
    return false;
  }
};

const pendingGroupHasFiles = (
  group: SetupGroup,
  files: UploadUserFile[]
): boolean => {
  if (projectSetupState.groups[group] === "completed") return true;
  if (files.length > 0) return true;
  ElMessage({ message: `请至少选择一个${groupLabels[group]}文件`, type: "warning" });
  return false;
};

const validateSetupInput = (): boolean => {
  if (!project_id.value && !input_name.value.trim()) {
    ElMessage({ message: "项目名称不能为空,请输入项目名称", type: "error" });
    return false;
  }
  return (
    pendingGroupHasFiles("knowledge", fileListKnowledge.value) &&
    pendingGroupHasFiles("requirements", fileListRequirementTestDoc.value) &&
    pendingGroupHasFiles("design", fileListDesignTestDoc.value)
  );
};

const createProject = async (): Promise<boolean> => {
  if (setupRequestActive.value || !validateSetupInput()) return false;
  setupRequestActive.value = true;
  centerDialogVisible.value = true;
  try {
    if (!project_id.value) {
      resetProjectAnalysisState();
      if (!(await registerProject())) return false;
    }
    const groups: Array<[SetupGroup, number, UploadUserFile[]]> = [
      ["knowledge", 1, fileListKnowledge.value],
      ["requirements", 2, fileListRequirementTestDoc.value],
      ["design", 3, fileListDesignTestDoc.value],
    ];
    for (const [group, doctype, files] of groups) {
      if (!(await uploadGroup(group, doctype, files))) return false;
    }

    createInfo.value = "正在核对项目资料";
    const remoteStatus = await loadProjectSetupStatus(requestUrl, project_id.value);
    const finalStatus =
      remoteStatus.stage === "setup_complete"
        ? remoteStatus
        : await finalizeProjectSetup(requestUrl, project_id.value);
    if (finalStatus.stage !== "setup_complete") {
      throw new Error(finalStatus.message || "项目资料尚未完成确认");
    }
    syncGlobalProjectId();
    createInfo.value = "项目创建成功，可以开始业务分析与测试计划生成";
    ElMessage({ message: "项目创建成功", type: "success" });
    return true;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "项目创建流程失败";
    createInfo.value = message;
    ElMessage({ message, type: "error" });
    return false;
  } finally {
    setupRequestActive.value = false;
  }
};

const discardRestoredProject = async (): Promise<void> => {
  try {
    await ElMessageBox.confirm(
      "这只会清除浏览器中的恢复状态，不会删除服务器上的项目或文档。是否继续？",
      "创建新项目",
      {
        confirmButtonText: "继续",
        cancelButtonText: "取消",
        type: "warning",
      }
    );
  } catch {
    return;
  }
  resetProjectSetupState();
  resetProjectAnalysisState();
  project_id.value = "";
  input_name.value = "";
  fileListKnowledge.value = [];
  fileListRequirementTestDoc.value = [];
  fileListDesignTestDoc.value = [];
  centerDialogVisible.value = false;
  syncGlobalProjectId();
};

const goToPlan = async (): Promise<void> => {
  if (!canContinueToPlan.value) return;
  syncGlobalProjectId();
  await router.push("/plan");
};

onMounted(async () => {
  if (!restoreProjectSetupState()) return;
  project_id.value = projectSetupState.pid;
  syncGlobalProjectId();
  try {
    const status = await loadProjectSetupStatus(requestUrl, project_id.value);
    createInfo.value = status.message;
    if (status.stage === "setup_complete") centerDialogVisible.value = true;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "项目资料状态恢复失败";
    ElMessage({ message, type: "warning" });
  }
});
</script>

<style scoped>
.el-header {
  background-color: #d1ffd3;
  display: flex;
}

.input_name_container {
  display: flex;
}

.en_name {
  font-family: "Quantify";
  font-size: 23px;
  margin-top: 20px;
  margin-left: 10px;
}

.page_name {
  font-family: "Ali";
  font-size: 23px;
  position: absolute;
  left: 45%;
  margin-top: 18px;
}

.info {
  font-family: "Ali";
  font-size: 22px;
}

.cn_name {
  font-family: "Ali";
}
</style>
