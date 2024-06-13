<template>
  <el-row>
    <el-button style="width: 180px;" type="primary" :icon="Right" @click="get_nfunctional_info" plain
      round>开始系统非功能性测试分析</el-button>
  </el-row>
  <el-row v-loading="loading1" element-loading-text="LLM正在进行系统非功能性测试相关分析,请耐心等待"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 99%; z-index: 900" />
  <el-row v-if="show1">
    <span class="cn_name">LLM从知识库中找到有关系统中非功能性需求的相关内容</span>
  </el-row>
  <el-row v-if="show1" style="margin-top: 10px;">
    <el-input v-model="nfunctional_info" style="width: 99%; margin-top: 10px;" :autosize="{ minRows: 2, maxRows: 20 }"
      type="textarea" disabled />
  </el-row>
  <el-row v-if="show1" style="margin-top: 10px;">
    <span class="cn_name">请选择要进行的非功能性测试类型</span>
  </el-row>
  <el-row style="margin-top: 10px;">
    <el-select v-if="show1" v-model="method_name" placeholder="Select" style="width: 260px">
      <el-option v-for="(method, index) in methods" :key="index" :labal="method" :value="method" />
    </el-select>
  </el-row>
  <el-row v-if="show1">
    <el-button style="margin-top: 20px; width: 180px;" type="success" :icon="Right" @click="startNFunctionalTest" plain
      round>生成相应的测试用例</el-button>
  </el-row>
  <el-divider v-if="show1" />
  <el-row v-loading="loading2" element-loading-text="LLM正在综合知识库内容进行系统非功能性测试分析"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 99%; z-index: 902" />
  <el-row v-model="method_name" v-if="show2">
    <span class="cn_name">LLM结合知识库查找有关{{ method_name }}的内容...</span>
  </el-row>
  <el-row v-if="show2" style="margin-top: 10px;">
    <el-input v-model="knowledge" style="width: 99%;"
      :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" disabled />
  </el-row>
  <el-row v-if="show2">
    <span class="cn_name" style="margin-top: 10px; color: #06B009;">LLM生成的测试用例如下</span>
  </el-row>
  <el-row v-if="show2" style="margin-top: 10px;">
    <el-input v-model="cases" style="width: 99%;" :autosize="{ minRows: 2, maxRows: 50 }" type="textarea" readonly />
  </el-row>
  <el-divider v-if="show2" border-style="dotted" />
  <el-row v-if="show2">
    <el-button style="width: 120px;" type="info" @click="reset">重置</el-button>
  </el-row>
</template>

<script lang="ts" setup>
import { ref, getCurrentInstance, reactive } from "vue";
import { Right } from '@element-plus/icons-vue'
import { ElMessage } from "element-plus";
import axios from "axios";

const instance = getCurrentInstance()
if (instance == null) {
  ElMessage({ message: "平台出现了一些问题,无法获取关键信息", type: "error" });
}
const requestUrl = instance?.appContext.config.globalProperties.$requestUrl;
const project_id = instance?.appContext.config.globalProperties.$id;

const loading1 = ref(false)
const loading2 = ref(false)
const show1 = ref(false)
const show2 = ref(false)
const method_name = ref('')

let methods = ref()
const nfunctional_info = ref('')
const knowledge = ref('')
const cases = ref('')

const get_nfunctional_info = () => {
  show1.value = false
  loading1.value = true
  methods = ref()
  axios.get(requestUrl + "/project/llm/nfunctional/info/" + project_id).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      return
    }
    else {
      nfunctional_info.value = resp.data.data.nonfunctional_info
      methods.value = resp.data.data.list.method_list
      loading1.value = false
      show1.value = true
    }
  });
}

const startNFunctionalTest = (type: number) => {
  show2.value = false
  loading2.value = true
  knowledge.value = ''
  cases.value = ''
  if(method_name.value == ''){
      loading2.value = false
      ElMessage({ message: "请先选择测试类型", type: "warning" });
      return
    }
  axios.post(requestUrl + "/project/llm/nfunctional/case", {
    pid: project_id,
    info: nfunctional_info.value,
    method_name: method_name.value
  }).then((resp) => {
    if(resp.data.data == false){
      ElMessage({ message: resp.data.reason, type: "error" });
      return
    }else{
      knowledge.value = resp.data.data.nonfunctional_test_knowledge
      cases.value = resp.data.data.test_cases
      loading2.value = false
      show2.value = true
    }
  });
}

const reset = () => {
  show2.value = false
  knowledge.value = ''
  cases.value = ''
}

</script>

