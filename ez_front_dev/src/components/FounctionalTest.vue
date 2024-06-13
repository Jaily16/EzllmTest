<template>
  <el-row>
    <el-button style="width: 180px;" type="primary" :icon="Right" @click="get_use_cases_info" plain
      round>开始系统功能性测试分析</el-button>
  </el-row>
  <el-row v-loading="loading1" element-loading-text="LLM正在进行系统功能性测试相关分析,请耐心等待"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 99%; z-index: 900" />
  <el-row v-if="show1">
    <span class="cn_name">LLM从知识库中找到有关系统中所有用例的相关内容</span>
  </el-row>
  <el-row v-if="show1" style="margin-top: 10px;">
    <el-input v-model="use_cases_info" style="width: 99%; margin-top: 10px;" :autosize="{ minRows: 2, maxRows: 20 }"
      type="textarea" disabled />
  </el-row>
  <el-row v-if="show1" style="margin-top: 10px;">
    <span class="cn_name">您可以选择项目中的某个用例进行功能性测试分析,LLM分析出的项目中的所有用例如下</span>
  </el-row>
  <el-row style="margin-top: 10px;">
    <el-select v-if="show1" v-model="use_case_name" placeholder="Select" style="width: 260px">
      <el-option v-for="(uc, index) in use_cases" :key="index" :labal="uc" :value="uc" />
    </el-select>
  </el-row>
  <el-row v-if="show1" style="margin-top: 10px;">
    <span class="cn_name">请选择生成的测试用例的输出格式</span>
  </el-row>
  <el-row v-if="show1" style="margin-top: 10px;">
    <el-radio-group v-model="output_format">
      <el-radio-button v-for="(format, index) in output_formats" :key="index" :label="format" :value="index" />
    </el-radio-group>
  </el-row>
  <el-row v-if="show1">
    <el-button style="margin-top: 20px; width: 180px;" type="success" :icon="Right" @click="startFunctionalTest(1)" plain
      round>生成功能性测试用例</el-button>
  </el-row>
  <el-divider v-if="show1" />
  <el-row v-loading="loading2" element-loading-text="LLM正在综合知识库内容进行系统功能性测试分析"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 99%; z-index: 902" />
  <el-row v-if="show2">
    <span class="cn_name">LLM结合知识库查找有关系统功能性测试的内容...</span>
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
const output_format = ref(0)
const output_formats = ref(['.txt(文字形式)', '.md(表格形式)', '.xml', '.csv'])
const use_cases_info = ref('')

const use_case_name = ref('')
let use_cases = ref()
const knowledge = ref('')
const cases = ref('')

const get_use_cases_info = () => {
  show1.value = false
  loading1.value = true
  use_cases = ref()
  axios.get(requestUrl + "/project/llm/functional/info/" + project_id).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      return
    }
    else {
      use_cases_info.value = resp.data.data.text_info
      use_cases.value = resp.data.data.list_info.use_case_list
      loading1.value = false
      show1.value = true
    }
  });
}

const startFunctionalTest = (type: number) => {
  show2.value = false
  loading2.value = true
  knowledge.value = ''
  cases.value = ''
  let name = ''
  if(type){
    if(use_case_name.value == ''){
      loading2.value = false
      ElMessage({ message: "请先选择要测试的用例(故事)", type: "warning" });
      return
    }
    else{
      name = use_case_name.value
    }
  }
  axios.post(requestUrl + "/project/llm/functional/case", {
    pid: project_id,
    info: use_cases_info.value,
    test_type: type,
    output_type: output_format.value,
    use_case_name: name
  }).then((resp) => {
    if(resp.data.data == false){
      ElMessage({ message: resp.data.reason, type: "error" });
      return
    }else{
      knowledge.value = resp.data.data.functional_test_knowledge
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

