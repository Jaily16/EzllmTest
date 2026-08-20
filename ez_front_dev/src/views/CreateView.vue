<template>
  <div class="common-layout" style="min-width: 500px">
    <el-container>
      <el-header style="position: sticky; top: 0; z-index: 999">
        <el-image style="width: 50px; height: 50px; margin-top: 5px" :src="require('@/assets/static/image/ezlogo.png')"
          fit="fill" />
        <div class="en_name">EzllmTest</div>
        <el-divider style="background-color: white; margin-top: 26px" direction="vertical" />
        <div class="page_name">创建新项目</div>
      </el-header>
      <el-main>
        <div class="input_name_container">
          <el-icon size="24px" style="margin-top: 4px; margin-right: 5px">
            <Postcard />
          </el-icon>
          <div class="info">项目名称</div>
          <el-divider style="margin-top: 9px" direction="vertical" />
          <el-input v-model="input_name" style="width: 350px; margin-left: 20px" placeholder="请输入项目名称(项目名称不超过50个字)"
            maxlength="50" show-word-limit :suffix-icon="Memo" clearable />
          <RouterLink to="/"><el-button type="info" size="large" style="width: 120px; position: absolute; right: 15px"
              :icon="Back">返回登入页面</el-button></RouterLink>
        </div>
        <el-divider />
        <div class="input_name_container">
          <el-icon size="24px" style="margin-top: 4px; margin-right: 5px">
            <Collection />
          </el-icon>
          <div class="info">测试知识库</div>
        </div>
        <el-row>
          <span style="font-size: small;">(请勿传入与软件测试知识库无关的内容,否则会影响LLM正确生成结果)</span>
        </el-row>
        <el-divider border-style="dashed">请上传希望LLM学习的软件测试相关知识库</el-divider>
        <el-upload class="upload_knowledge" v-model:file-list="fileListKnowledge" drag
          accept=".txt, .docx, .doc, .pdf, .md" multiple show-file-list :http-request="func"
          :before-upload="handleBeforeUploadKnowledge" :before-remove="beforeRemove">
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            将文件拖拽到到此处或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              请上传(.txt/.pdf/.md/.docx/.doc)格式的文档,单个文件大小不得超过50MB
            </div>
          </template>
        </el-upload>
        <el-divider />
        <div class="input_name_container">
          <el-icon size="24px" style="margin-top: 4px; margin-right: 5px">
            <DocumentAdd />
          </el-icon>
          <div class="info">业务文档-需求文档</div>
        </div>
        <el-row>
          <span style="font-size: small;">(请上传业务需求相关文档,例如需求文档、需求分析文档等)</span>
        </el-row>
        <el-divider border-style="dashed">请上传需要进行分析的所有业务需求文档</el-divider>
        <el-upload class="upload_testdoc" v-model:file-list="fileListRequirementTestDoc" drag accept=".txt, .docx, .doc, .pdf, .md"
          multiple show-file-list :http-request="func" :before-upload="handleBeforeUploadRequirementTestdoc"
          :before-remove="beforeRemove">
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            将文件拖拽到到此处或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              请上传(.txt/.pdf/.md/.docx/.doc)格式的文档,单个文件大小不得超过10MB
            </div>
          </template>
        </el-upload>
        <el-divider />
        <div class="input_name_container">
          <el-icon size="24px" style="margin-top: 4px; margin-right: 5px">
            <DocumentAdd />
          </el-icon>
          <div class="info">业务文档-开发设计文档</div>
        </div>
        <el-row>
          <span style="font-size: small;">(请上传业务开发设计相关文档,例如概要设计文档、详细设计文档等)</span>
        </el-row>
        <el-divider border-style="dashed">请上传需要进行分析的所有业务开发设计文档</el-divider>
        <el-upload class="upload_testdoc" v-model:file-list="fileListDesignTestDoc" drag accept=".txt, .docx, .doc, .pdf, .md"
          multiple show-file-list :http-request="func" :before-upload="handleBeforeUploadDesignTestdoc"
          :before-remove="beforeRemove">
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            将文件拖拽到到此处或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              请上传(.txt/.pdf/.md/.docx/.doc)格式的文档,单个文件大小不得超过10MB
            </div>
          </template>
        </el-upload>
        <el-divider />
        <el-button type="success" size="large" style="width: 120px; position: absolute; right: 15px" :icon="Cpu"
          @click="createProject">创建</el-button>
        <el-divider style="margin-top: 80px" border-style="dotted" />
      </el-main>
    </el-container>
    <el-dialog v-model="centerDialogVisible" width="700" :show-close="false" align-center>
      <el-row style="min-width: 500px">
        <span class="cn_name" style="font-size: medium">基于知识库和业务文档信息创建项目</span>
      </el-row>
      <el-row style="min-width: 500px">
        <el-progress style="left: 50%; margin-top: 15px; margin-left: -63px" type="circle" :percentage="percentage"
          :status="status" />
      </el-row>
      <el-row v-model="createInfo" style="min-width: 500px">
        <span class="cn_name" style="font-size: small">{{ createInfo }}</span>
      </el-row>
      <el-row v-if="createFinished" style="min-width: 500px">
        <span class="cn_name" style="color: #c45656; font-size: small">
          以下是平台为您生成的项目id,请复制保存!</span>
      </el-row>
      <el-row v-if="createFinished" style="min-width: 500px">
        <el-input v-model="project_id" style="width: 230px" readonly />
        <el-button type="success" style="margin-left: 10px;" :icon="DocumentCopy" @click="copyId">复制项目id</el-button>
      </el-row>
      <template #footer>
        <RouterLink to="/">
          <el-button v-if="errorButton" type="danger">返回登入页面</el-button>
        </RouterLink>
        <RouterLink to="/">
          <el-button v-if="createFinished" type="info">返回登入页面</el-button>
        </RouterLink>
        <RouterLink to="/plan">
          <el-button v-if="createFinished" style="margin-left: 10px;" type="success">开始分析业务和生成测试计划</el-button>
        </RouterLink>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, getCurrentInstance } from "vue";
import { Memo, Cpu, Back, DocumentCopy } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadProps, UploadUserFile } from "element-plus";
import useClipboard from 'vue-clipboard3'
import axios from "axios";
import { resetProjectAnalysisState } from "@/state/projectAnalysis";

const instance = getCurrentInstance();
const requestUrl = instance?.appContext.config.globalProperties.$requestUrl;
const input_name = ref("");
const fileListKnowledge = ref<UploadUserFile[]>([])
const fileListRequirementTestDoc = ref<UploadUserFile[]>([])
const fileListDesignTestDoc = ref<UploadUserFile[]>([])
const project_id = ref("");
const centerDialogVisible = ref(false);
const percentage = ref(0);
const createFinished = ref(false);
const status = ref("");
const createInfo = ref("正在初始化");
const { toClipboard } = useClipboard()

const errorButton = ref(false);

const copyId = async () => {
  try {
    await toClipboard(project_id.value)
    ElMessage.success('已复制项目id');
  } catch {
    ElMessage.warning('项目id复制失败');
  }
}
// 用于记录是否为文件上传的用户性错误
let fileUploadFault = false;

const appendRawFile = (formData: FormData, file: UploadUserFile): boolean => {
  if (!file.raw) {
    ElMessage({ message: "上传文件内容不可用，请重新选择文件", type: "error" });
    return false;
  }
  formData.append("file", file.raw);
  return true;
};

const func = () => undefined;

const handleBeforeUploadKnowledge: UploadProps["beforeUpload"] = (file) => {
  //检查传输的文档大小是否满足约束
  if (file.size != undefined) {
    let fileSize = Number(file.size / 1024 / 1024);
    if (fileSize > 50) {
      fileUploadFault = true;
      ElMessage({
        message: "您上传的知识库单个文件大小超过50MB,请重新上传",
        type: "warning",
      });
      return false;
    }
  } else {
    ElMessage({ message: "文件上传系统出现了一些问题", type: "error" });
    return false;
  }

  //需要检查是否有重名文档的
  for (let i = 0; i < fileListKnowledge.value.length; i++) {
    if (file.name == fileListKnowledge.value[i].name) {
      fileUploadFault = true;
      ElMessage({ message: "请勿重复上传知识库文件", type: "warning" });
      return false;
    }
  }
};

const handleBeforeUploadRequirementTestdoc: UploadProps["beforeUpload"] = (file) => {
  //检查传输的文档大小是否满足约束
  if (file.size != undefined) {
    let fileSize = Number(file.size / 1024 / 1024);
    if (fileSize > 10) {
      fileUploadFault = true;
      ElMessage({
        message: "您上传的业务文档单个文件大小超过10MB,请重新上传",
        type: "warning",
      });
      return false;
    }
  } else {
    ElMessage({ message: "文件上传系统出现了一些问题", type: "error" });
    return false;
  }

  //需要检查是否有重名文档的
  for (let i = 0; i < fileListRequirementTestDoc.value.length; i++) {
    if (file.name == fileListRequirementTestDoc.value[i].name) {
      fileUploadFault = true;
      ElMessage({ message: "请勿重复上传业务需求文档", type: "warning" });
      return false;
    }
  }
};

const handleBeforeUploadDesignTestdoc: UploadProps["beforeUpload"] = (file) => {
  //检查传输的文档大小是否满足约束
  if (file.size != undefined) {
    let fileSize = Number(file.size / 1024 / 1024);
    if (fileSize > 10) {
      fileUploadFault = true;
      ElMessage({
        message: "您上传的业务文档单个文件大小超过10MB,请重新上传",
        type: "warning",
      });
      return false;
    }
  } else {
    ElMessage({ message: "文件上传系统出现了一些问题", type: "error" });
    return false;
  }

  //需要检查是否有重名文档的
  for (let i = 0; i < fileListDesignTestDoc.value.length; i++) {
    if (file.name == fileListDesignTestDoc.value[i].name) {
      fileUploadFault = true;
      ElMessage({ message: "请勿重复上传业务开发设计文档", type: "warning" });
      return false;
    }
  }
};

const beforeRemove: UploadProps["beforeRemove"] = (uploadFile) => {
  if (fileUploadFault) {
    fileUploadFault = false;
    return true;
  }
  return ElMessageBox.confirm(
    `您确定删除文档 ${uploadFile.name} 吗?`,
    "Warning",
    {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning",
    }
  ).then(
    () => true,
    () => false
  );
};

const register = async () => {
  await axios({
    method: "post",
    url: requestUrl + "/project/add/" + input_name.value,
  })
    .then(function (response) {
      if (response.data.data != false) {
        project_id.value = response.data.data;
      } else {
        ElMessage({ message: response.data.reason, type: "error" });
        return false
      }
    })
    .catch(function () {
      ElMessage({ message: "项目创建请求失败", type: "error" });
      return false
    });
  return true
};

const submitUploadKnowledge = async () => {
  for (let i = 0; i < fileListKnowledge.value.length; i++) {
    let formData = new FormData();
    if (!appendRawFile(formData, fileListKnowledge.value[i])) return false;
    await axios({
      method: "post",
      url: requestUrl + "/uploadFile/" + project_id.value + "/1",
      data: formData,
    })
      .then(function (response) {
        if (response.data.data == false) {
          ElMessage({ message: response.data.reason, type: "error" });
          return false
        }
      })
      .catch(function () {
        ElMessage({ message: "知识库文件上传请求失败", type: "error" });
        return false
      });
  }
  return true
};

const submitUploadRequirementTestdoc = async () => {
  for (let i = 0; i < fileListRequirementTestDoc.value.length; i++) {
    let formData = new FormData();
    if (!appendRawFile(formData, fileListRequirementTestDoc.value[i])) return false;
    await axios({
      method: "post",
      url: requestUrl + "/uploadFile/" + project_id.value + "/2",
      data: formData,
    })
      .then(function (response) {
        if (response.data.data == false) {
          ElMessage({ message: response.data.reason, type: "error" });
          return false
        }
      })
      .catch(function () {
        ElMessage({ message: "需求文档上传请求失败", type: "error" });
        return false
      });
  }
  return true
};

const submitUploadDesignTestdoc = async () => {
  for (let i = 0; i < fileListDesignTestDoc.value.length; i++) {
    let formData = new FormData();
    if (!appendRawFile(formData, fileListDesignTestDoc.value[i])) return false;
    await axios({
      method: "post",
      url: requestUrl + "/uploadFile/" + project_id.value + "/3",
      data: formData,
    })
      .then(function (response) {
        if (response.data.data == false) {
          ElMessage({ message: response.data.reason, type: "error" });
          return false
        }
      })
      .catch(function () {
        ElMessage({ message: "设计文档上传请求失败", type: "error" });
        return false
      });
  }
  return true
};

const analyzeProjectType = async () => {
  await axios({
    method: "get",
    url: requestUrl + "/project/type/" + project_id.value,
  })
    .then(function (response) {
      if (response.data.data == false) {
        ElMessage({ message: response.data.reason, type: "error" });
        return false
      }
      else {
        if (instance != null) {
            instance.appContext.config.globalProperties.$id = project_id.value
            instance.appContext.config.globalProperties.$unit_menu_result = null
          }
      }
    })
    .catch(function () {
      ElMessage({ message: "项目类型分析请求失败", type: "error" });
      return false
    });
  return true
}

const createProject = async () => {
  // 检查输入的名称是否为空
  if (input_name.value == "") {
    ElMessage({ message: "项目名称不能为空,请输入项目名称", type: "error" });
    return false;
  }
  // 检查输入的知识库是否为空
  if (fileListKnowledge.value.length == 0) {
    ElMessage({
      message: "项目知识库不建议为空,请至少上传一个知识库文件",
      type: "warning",
    });
    return false;
  }
  // 检查输入的业务需求文档是否为空
  if (fileListRequirementTestDoc.value.length == 0) {
    ElMessage({
      message: "项目的业务需求文档不能为空,请上传业务文档",
      type: "error",
    });
    return false;
  }
  // 检查输入的业务开发设计文档是否为空
  if (fileListDesignTestDoc.value.length == 0) {
    ElMessage({
      message: "项目的业务开发设计文档不能为空,请上传业务文档",
      type: "error",
    });
    return false;
  }
  resetProjectAnalysisState()
  centerDialogVisible.value = true;
  var register_result = await register();
  if (register_result) {
    percentage.value = 20;
    createInfo.value = "项目id已生成,开始上传知识库文件";
  } else {
    status.value = "exception";
    createInfo.value = "抱歉,平台出现了一点问题,项目创建失败";
    errorButton.value = true;
    return false;
  }
  var knowledge_result = await submitUploadKnowledge()
  if (knowledge_result) {
    percentage.value = 40;
    createInfo.value = "项目知识库上传完成,开始上传业务文档";
  } else {
    status.value = "exception";
    createInfo.value = "抱歉,平台出现了一点问题,项目创建失败";
    errorButton.value = true;
    return false;
  }
  var testdoc_result_requirement = await submitUploadRequirementTestdoc()
  if (testdoc_result_requirement) {
    percentage.value = 60;
    createInfo.value = "项目业务需求文档上传完成,对业务文档进行初步分析";
  } else {
    status.value = "exception";
    createInfo.value = "抱歉,平台出现了一点问题,项目创建失败";
    errorButton.value = true;
    return false;
  }
  var testdoc_result_design = await submitUploadDesignTestdoc()
  if (testdoc_result_design) {
    percentage.value = 80;
    createInfo.value = "项目业务开发设计文档上传完成,对业务文档进行初步分析";
  } else {
    status.value = "exception";
    createInfo.value = "抱歉,平台出现了一点问题,项目创建失败";
    errorButton.value = true;
    return false;
  }
  var type_result = await analyzeProjectType()
  if (type_result) {
    percentage.value = 100
    createInfo.value = "项目创建成功";
    status.value = "success";
    createFinished.value = true
    
  } else {
    status.value = "exception";
    createInfo.value = "抱歉,平台出现了一点问题,项目创建失败";
    errorButton.value = true;
    return false;
  }
}

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
