<template>
  <el-row>
    <span style="margin-top: 5px;" class="cn_name">
      请选择用于进行生成测试计划的大语言模型
    </span>
  </el-row>
  <el-row>
    <el-segmented style="margin-top: 5px;" v-model="llm" :options="options" size="large" />
  </el-row>
  <el-row>
    <el-button style="margin-top: 10px; width: 180px;" type="success" :icon="Right" @click="startTestPlan" plain
      round>生成测试计划</el-button>
  </el-row>
  <el-divider v-if="show1"/>
  <el-row v-loading="loading1" element-loading-text="LLM正在生成测试计划"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 99%; z-index: 902" />
  <el-row v-if="show1">
    <span class="cn_name" style="color: #06B009;">LLM对该软件业务的测试计划建议如下</span>
  </el-row>
  <el-row v-if="show1" style="margin-top: 10px;">
    <el-input v-model="plan" style="width: 99%;" :autosize="{ minRows: 2, maxRows: 50 }" type="textarea" readonly />
  </el-row>
  <el-row v-if="show1">
    <el-button style="margin-top: 10px; width: 180px;" type="info" :icon="Right" @click="restartTestPlan" plain
      round>重新生成测试计划</el-button>
  </el-row>
  <span class="cn_name">注意该测试计划只是整体建议,具体测试用例请在平台中选择响应模块进行用例的生成</span>
  <el-divider v-if="show1" border-style="dotted" />
</template>

<script lang="ts" setup>
import { ref, getCurrentInstance} from "vue";
import { Right } from '@element-plus/icons-vue'
import { ElMessage } from "element-plus";
import axios from "axios";

const instance = getCurrentInstance()
if (instance == null) {
  ElMessage({ message: "平台出现了一些问题,无法获取关键信息", type: "error" });
}
const requestUrl = instance?.appContext.config.globalProperties.$requestUrl;
const project_id = instance?.appContext.config.globalProperties.$id;

const llm = ref('GPT-3.5')
const options = [
{
    label: 'GPT-3.5',
    value: 'GPT-3.5',
  },
  {
    label: 'GPT-4.0',
    value: 'GPT-4.0',
  },
  {
    label: '文心一言',
    value: '文心一言',
    disabled: true,
  },
  {
    label: '通义千问',
    value: '通义千问',
    disabled: true,
  },
  {
    label: 'GLM-3',
    value: 'GLM-3',
  },
  {
    label: 'GLM-4',
    value: 'GLM-4',
  },
  {
    label: 'MoonShot',
    value: 'MoonShot',
    disabled: true,
  },
]

const loading1 = ref(false)
const show1 = ref(false)

const plan = ref('')

const startTestPlan = () => {
  show1.value = false
  loading1.value = true
  plan.value = ''
  axios.get(requestUrl + "/project/llm/plan/" + project_id + "/" + llm.value).then((resp) => {
    if(resp.data.data == false){
      ElMessage({ message: resp.data.reason, type: "error" });
      loading1.value = false
      return
    }else{
      plan.value = resp.data.data
      loading1.value = false
      show1.value = true
    }
  });
}

const restartTestPlan = () => {
  show1.value = false
  loading1.value = true
  plan.value = ''
  axios.put(requestUrl + "/project/llm/plan/update/" + project_id + "/" + llm.value).then((resp) => {
    if(resp.data.data == false){
      ElMessage({ message: resp.data.reason, type: "error" });
      loading1.value = false
      return
    }else{
      plan.value = resp.data.data
      loading1.value = false
      show1.value = true
    }
  });
}

</script>

