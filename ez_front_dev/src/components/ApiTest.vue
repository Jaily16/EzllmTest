<template>
  <el-row>
    <el-button style="width: 180px;" type="primary" :icon="Right" @click="get_apis_info" plain
      round>开始api接口测试分析</el-button>
  </el-row>
  <el-row v-loading="loading1" element-loading-text="LLM正在进行api接口测试相关分析,请耐心等待"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 99%; z-index: 900" />
  <el-row v-if="show1">
    <span class="cn_name">LLM从知识库中找到有关系统中所有api的的相关内容</span>
  </el-row>
  <el-row v-if="show1" style="margin-top: 10px;">
    <el-input v-model="apis_info" style="width: 99%; margin-top: 10px;" :autosize="{ minRows: 2, maxRows: 20 }"
      type="textarea" disabled />
  </el-row>
  <el-row v-if="show1" style="margin-top: 10px;">
    <span class="cn_name">您可以选择项目中的某个api生成测试用例,LLM分析出的项目中的所有api接口如下</span>
  </el-row>
  <el-row style="margin-top: 10px;">
    <el-select v-if="show1" v-model="api_name" placeholder="Select" style="width: 260px">
      <el-option v-for="(api, index) in apis" :key="index" :labal="api" :value="api" />
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
    <el-button style="margin-top: 20px; width: 180px;" type="success" :icon="Right" @click="startApiTest(0)" plain
      round>全部api接口测试用例</el-button>
    <el-button style="margin-top: 20px; width: 180px;" type="success" :icon="Right" @click="startApiTest(1)" plain
      round>生成api接口测试用例</el-button>
  </el-row>
  <el-divider v-if="show1" />
  <el-row v-loading="loading2" element-loading-text="LLM正在综合知识库内容进行api测试分析测试分析"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 99%; z-index: 902" />
  <el-row v-if="show2">
    <span class="cn_name">LLM结合知识库查找有关api测接口测试的内容...</span>
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
const apis_info = ref('')

const api_name = ref('')
let apis = ref()
const knowledge = ref('')
const cases = ref('')

const get_apis_info = () => {
  show1.value = false
  loading1.value = true
  apis = ref()
  axios.get(requestUrl + "/project/llm/api/info/" + project_id).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      return
    }
    else {
      apis_info.value = resp.data.data.apis_info
      apis.value = resp.data.data.list.api_list
      loading1.value = false
      show1.value = true
    }
  });
}

const startApiTest = (type: number) => {
  show2.value = false
  loading2.value = true
  knowledge.value = ''
  cases.value = ''
  let name = ''
  if(type){
    if(api_name.value == ''){
      loading2.value = false
      ElMessage({ message: "请先选择要测试的api接口", type: "warning" });
      return
    }
    else{
      name = api_name.value
    }
  }
  axios.post(requestUrl + "/project/llm/api/case", {
    pid: project_id,
    info: apis_info.value,
    test_type: type,
    output_type: output_format.value,
    api_name: name
  }).then((resp) => {
    if(resp.data.data == false){
      ElMessage({ message: resp.data.reason, type: "error" });
      return
    }else{
      knowledge.value = resp.data.data.api_test_knowledge
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

