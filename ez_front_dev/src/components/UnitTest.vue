<template>
  <el-row>
    <span style="margin-top: 5px;" class="cn_name">
      请选择用于进行单元测试初步分析大语言模型
    </span>
  </el-row>
  <el-row>
    <el-segmented style="margin-top: 5px;" v-model="llm1" :options="options1" size="large" />
  </el-row>
  <el-row style="margin-top: 10px;">
    <el-button v-model="text" style="width: 180px;" type="primary" :icon="Right" plain round
      @click="getUnitTestMenu(false)">{{
        text }}</el-button>
    <el-button v-if="show6" style="width: 180px;" type="info" :icon="Right" plain round
      @click="getUnitTestMenu(true)">重新进行单元测试分析</el-button>
  </el-row>
  <el-row v-loading="loading1" element-loading-text="LLM正在进行单元测试相关分析,请耐心等待"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 99%; z-index: 900" />
  <el-row v-if="show1" style="margin-top: 10px;">
    <span class="cn_name">根据LLM分析,您的业务建议进行以下几种单元测试,请选择要进行测试的类型</span>
  </el-row>
  <el-row v-if="show1" style="margin-top: 10px;">
    <el-radio-group v-model="unit_type" @change="generateUnits">
      <el-radio-button v-for="(type, index) in unit_types_list" :key="index" :label="type" :value="type" />
    </el-radio-group>
  </el-row>
  <el-row v-if="unit_type != ''" style="margin-top: 10px;">
    <span class="cn_name">根据LLM进一步分析,为您智能划分了相应的单元,请选择要进行测试的单元</span>
  </el-row>
  <el-row v-if="unit_type != ''" style="margin-top: 10px;">
    <el-select v-model="unit" placeholder="Select" style="width: 260px">
      <el-option v-for="(unit, index) in units" :key="index" :labal="unit" :value="unit" />
    </el-select>
  </el-row>
  <el-row v-if="show2">
    <span style="margin-top: 5px;" class="cn_name">
      请选择用于进行单元测试进一步分析大语言模型
    </span>
  </el-row>
  <el-row v-if="show2">
    <el-segmented style="margin-top: 5px;" v-model="llm2" :options="options2" size="large" />
  </el-row>
  <el-row v-if="show2">
    <el-button style="margin-top: 10px; width: 180px;" type="primary" :icon="Right" @click="furtherAnalyze" plain
      round>利用LLM进一步分析</el-button>
  </el-row>
  <el-divider v-if="show2" />
  <el-row v-loading="loading2" element-loading-text="LLM正在进一步分析,请耐心等待" element-loading-background="rgba(255,255,255,1)"
    style="margin-top: 10px; width: 99%; z-index: 901" />
  <el-row v-if="show3">
    <span class="cn_name">LLM从知识库中找到有关待测试单元的相关内容</span>
  </el-row>
  <el-row v-if="show3" style="margin-top: 10px;">
    <el-input v-model="unit_info_result.unit_info" style="width: 99%; margin-top: 10px;"
      :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" disabled />
  </el-row>
  <el-row v-if="show3" style="margin-top: 10px;">
    <span class="cn_name">根据LLM分析,您的业务能采用以下方法进行测试,请选择您希望采用的测试方法</span>
  </el-row>
  <el-row v-if="show3" style="margin-top: 10px;">
    <el-radio-group v-model="method">
      <el-radio-button v-for="(method, index) in unit_methods_list" :key="index" :label="method" :value="index" />
    </el-radio-group>
  </el-row>
  <el-row v-if="show3" style="margin-top: 10px;">
    <span class="cn_name">请选择生成的测试用例的输出格式</span>
  </el-row>
  <el-row v-if="show3" style="margin-top: 10px;">
    <el-radio-group v-model="output_format">
      <el-radio-button v-for="(format, index) in output_formats" :key="index" :label="format" :value="index" />
    </el-radio-group>
  </el-row>
  <el-row v-if="show3">
    <span style="margin-top: 5px;" class="cn_name">
      请选择用于进行单元测试用例生成的大语言模型
    </span>
  </el-row>
  <el-row v-if="show3">
    <el-segmented style="margin-top: 5px;" v-model="llm3" :options="options3" size="large" />
  </el-row>
  <el-row v-if="show3">
    <el-button style="margin-top: 10px; width: 180px;" type="success" :icon="Right" @click="startUnitTest" plain
      round>生成测试用例</el-button>
  </el-row>
  <el-divider v-if="show3" />
  <el-row v-loading="loading3" element-loading-text="LLM正在综合知识库内容进行单元测试分析"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 99%; z-index: 902" />
  <el-row v-if="show4">
    <span class="cn_name">LLM结合知识库查找有关单元测试的内容...</span>
  </el-row>
  <el-row v-model="unit_knowledge_result" v-if="show4" style="margin-top: 10px;">
    <el-input v-model="unit_knowledge_result.unit_test_knowledge" style="width: 99%;"
      :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" disabled show-overflow-tooltip />
  </el-row>
  <el-row v-if="show4" style="margin-top: 10px;">
    <span class="cn_name">LLM将综合以下测试方法进行测试用例的生成...</span>
  </el-row>
  <el-row v-model="unit_knowledge_result" v-if="show4" style="margin-top: 10px;">
    <el-input v-model="unit_knowledge_result.unit_method_knowledge" style="width: 99%; "
      :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" disabled show-overflow-tooltip />
  </el-row>
  <el-divider v-if="show4" />
  <el-row v-loading="loading4" element-loading-text="LLM正在生成单元测试用例" element-loading-background="rgba(255,255,255,1)"
    style="margin-top: 10px; width: 99%; z-index: 902" />
  <el-row v-if="show5">
    <span class="cn_name" style="color: #06B009;">LLM生成的测试用例如下</span>
  </el-row>
  <el-row v-if="show5" style="margin-top: 10px;">
    <el-input v-model="test_cases" style="width: 99%;" :autosize="{ minRows: 2, maxRows: 50 }" type="textarea" readonly
      show-overflow-tooltip />
  </el-row>
  <el-divider v-if="show5" border-style="dotted" />
  <el-row v-if="show5">
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
const unit_menu_result = instance?.appContext.config.globalProperties.$unit_menu_result;

const text = ref('开始单元测试分析')
const llm1 = ref('GPT-3.5')
const options1 = [
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
const test_cases = ref('')

const unit_type = ref('')

const unit_types = ref(['子系统单元测试', '模块单元测试', '类单元测试', '函数单元测试'])

const llm2 = ref('GPT-3.5')
const options2 = [
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
  },
  {
    label: '通义千问',
    value: '通义千问',
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
  },
]

const unit = ref('')

const units = ref()

const method = ref(-1)

const methods = ref(['静态黑盒测试', '静态白盒测试'])

const output_format = ref(0)

const output_formats = ref(['.txt(文字形式)', '.md(表格形式)', '.xml', '.csv'])

const llm3 = ref('GPT-3.5')
const options3 = [
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
  },
  {
    label: '通义千问',
    value: '通义千问',
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
  },
]

const loading1 = ref(false)
const loading2 = ref(false)
const loading3 = ref(false)
const loading4 = ref(false)
const show1 = ref(false)
const show2 = ref(false)
const show3 = ref(false)
const show4 = ref(false)
const show5 = ref(false)
const show6 = ref(false)
let unit_types_list: any = reactive([])
let unit_methods_list: any = reactive([])
const menu_result = ref()
const unit_info_result = ref()
const unit_knowledge_result = ref()

//如果之前有保存了信息直接读取，优化响应速度
if (unit_menu_result != null) {
  menu_result.value = unit_menu_result
  text.value = '继续进行单元测试'
  show6.value = true
  unit_types_list = reactive([])
  if (menu_result.value.subsystem_menu.subsystem_test || menu_result.value.subsystem_menu.subsystem_list.length) {
    unit_types_list.push(unit_types.value[0])
  }
  if (menu_result.value.module_menu.module_test) {
    unit_types_list.push(unit_types.value[1])
  }
  if (menu_result.value.class_menu.class_test) {
    unit_types_list.push(unit_types.value[2])
  }
  if (menu_result.value.function_menu.function_test) {
    unit_types_list.push(unit_types.value[3])
  }
  show1.value = true
  show2.value = true
}
else {
  axios.get(requestUrl + "/project/info/" + project_id + "/2").then((resp) => {
    if (resp.data.data != false) {
      show6.value = true
      text.value = '继续单元测试分析'
    }
  })
}

const getUnitTestMenu = (restart: boolean) => {
  unit_types_list = reactive([])
  unit_methods_list = reactive([])
  loading1.value = true
  show1.value = false
  show2.value = false
  show3.value = false
  show4.value = false
  show5.value = false
  unit_type.value = ''
  unit.value = ''
  method.value = -1
  output_format.value = 0
  let url = ''
  if (restart) {
    url = requestUrl + "/project/llm/unit/menu/update/" + project_id + "/" + llm1.value
  }
  else {
    url = requestUrl + "/project/llm/unit/menu/" + project_id + "/" + llm1.value
  }
  axios.get(url).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      loading1.value = false
      return
    } else {
      menu_result.value = resp.data.data.list_info
      if (menu_result.value.subsystem_menu.subsystem_test || menu_result.value.subsystem_menu.subsystem_list.length) {
        unit_types_list.push(unit_types.value[0])
      }
      if (menu_result.value.module_menu.module_test || menu_result.value.module_menu.module_list.length) {
        unit_types_list.push(unit_types.value[1])
      }
      if (menu_result.value.class_menu.class_test || menu_result.value.class_menu.class_list.length) {
        unit_types_list.push(unit_types.value[2])
      }
      if (menu_result.value.function_menu.function_test || menu_result.value.function_menu.function_list.length) {
        unit_types_list.push(unit_types.value[3])
      }
      if (instance != null) {
        instance.appContext.config.globalProperties.$unit_menu_result = menu_result.value
        instance.appContext.config.globalProperties.$unit_types_list = unit_types_list.value
      }
      loading1.value = false
      show1.value = true
    }
  });
}

const generateUnits = () => {
  unit.value = ''
  show2.value = true
  if (unit_type.value == unit_types.value[0]) {
    units.value = menu_result.value.subsystem_menu.subsystem_list
  }
  else if (unit_type.value == unit_types.value[1]) {
    units.value = menu_result.value.module_menu.module_list
  }
  else if (unit_type.value == unit_types.value[2]) {
    units.value = menu_result.value.class_menu.class_list
  }
  else {
    units.value = menu_result.value.function_menu.function_list
  }
}

const furtherAnalyze = () => {
  show3.value = false
  show4.value = false
  show5.value = false
  unit_methods_list = reactive([])
  method.value = -1
  output_format.value = 0
  if (unit.value == '') {
    ElMessage({ message: "请先选择要测试单元", type: "warning" });
    return
  }
  loading2.value = true
  axios.get(requestUrl + "/project/llm/unit/info/" + project_id + "/" + unit.value + "/" + llm2.value).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      loading2.value = false
      return
    } else {
      unit_info_result.value = resp.data.data
      if (unit_info_result.value.test_type.black_box) {
        unit_methods_list.push(methods.value[0])
      }
      if (unit_info_result.value.test_type.white_box) {
        unit_methods_list.push(methods.value[1])
      }
      if (unit_info_result.value.test_type.black_box == false && unit_info_result.value.test_type.white_box == false) {
        //处理分析的不对的情况
        ElMessage({ message: "LLM的分析可能出现了一些幻觉,请尝试重新进一步分析", type: "info" });
      }
      loading2.value = false
      show3.value = true
    }
  });
}

const generateTestCases = async () => {
  loading4.value = true
  let static_method = ''
  if (method.value == 0) {
    static_method = '静态黑盒测试'
  }
  else {
    static_method = '静态白盒测试'
  }
  await axios.post(requestUrl + "/project/llm/unit/case", {
    unit_test_knowledge: unit_knowledge_result.value.unit_test_knowledge,
    static_method: static_method,
    unit_test_method_knowledge: unit_knowledge_result.value.unit_method_knowledge,
    unit: unit.value,
    unit_info: unit_info_result.value.unit_info,
    output_type: output_format.value,
    llm_name: llm3.value
  }).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      loading4.value = false
      return
    }
    else {
      test_cases.value = resp.data.data
      show5.value = true
      loading4.value = false
    }
  });
}

const findKnowledge = async () => {
  let url = ''
  if (method.value == -1) {
    ElMessage({ message: "请先选择测试方法", type: "warning" });
    loading3.value = false
    return
  }
  if (method.value == 0) {
    url = requestUrl + "/project/llm/unit/knowledge/" + project_id + "/1"
  }
  else {
    url = requestUrl + "/project/llm/unit/knowledge/" + project_id + "/2"
  }
  await axios.get(url).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      loading3.value = false
      return
    }
    else {
      unit_knowledge_result.value = resp.data.data
      show4.value = true
      loading3.value = false
      generateTestCases()
    }
  });
}

const startUnitTest = async () => {
  loading3.value = true
  if (method.value == null) {
    ElMessage({ message: "请选择您希望采用哪种测试方法生成单元测试用例", type: "warning" });
    return
  }
  findKnowledge()
}

const reset = () => {
  show3.value = false
  show4.value = false
  show5.value = false
  method.value = -1
  test_cases.value = ''
  unit_methods_list = reactive([])
}
</script>

<style scoped>
.cn_name {
  font-family: "Ali";
}

.en_name {
  font-family: "Quantify";
}
</style>
