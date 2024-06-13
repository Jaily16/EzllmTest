<template>
    <el-row>
        <span class="cn_name">(建议先完成单元测试分析)</span>
    </el-row>
    <el-row>
        <el-button style="width: 180px; margin-top: 10px;" type="primary" :icon="Right" plain round
            @click="getIntegrationTestMenu">开始集成测试分析</el-button>
    </el-row>
    <el-row v-loading="loading1" element-loading-text="LLM正在集成测试相关分析,请耐心等待" element-loading-background="rgba(255,255,255,1)"
        style="margin-top: 10px; width: 98%; z-index: 900" />
    <el-row v-if="show1" style="margin-top: 10px;">
        <span class="cn_name">根据LLM分析,您的业务建议进行以下几种集成测试,请选择要进行测试的类型</span>
    </el-row>
    <el-row v-if="show1" style="margin-top: 10px;">
        <el-radio-group v-model="integration_type" @change="generateIntegrations">
            <el-radio-button v-for="(type, index) in integration_types_list" :key="index" :label="type" :value="type" />
        </el-radio-group>
    </el-row>
    <el-row v-if="integration_type != '' && show2" style="margin-top: 10px;">
        <span class="cn_name">根据LLM进一步分析,为您智能划分了相应的集成测试单元,请选择要进行集成测试的单元</span>
    </el-row>
    <el-row v-if="integration_type != '' && show2" style="margin-top: 10px;">
        <el-select v-model="integration_unit" placeholder="Select" style="width: 260px">
            <el-option v-for="(integration, index) in integration_units" :key="index" :labal="integration"
                :value="integration" />
        </el-select>
    </el-row>
    <el-row v-if="show3">
        <el-button style="margin-top: 20px; width: 180px;" type="primary" :icon="Right" @click="furtherAnalyze" plain
            round>利用LLM进一步分析</el-button>
    </el-row>
    <el-divider v-if="show3" />
    <el-row v-loading="loading2" element-loading-text="LLM正在对集成测试进一步分析,请耐心等待"
        element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 98%; z-index: 901" />
    <el-row v-if="show4">
        <span class="cn_name">LLM从业务文档中找出的用于分析该集成测试的相关内容</span>
    </el-row>
    <el-row v-if="show4" style="margin-top: 10px;">
        <el-input v-model="integration_info" style="width: 99%; margin-top: 10px;" :autosize="{ minRows: 2, maxRows: 20 }"
            type="textarea" disabled />
    </el-row>
    <el-row v-if="show4" style="margin-top: 10px;">
        <span class="cn_name">根据LLM分析,您的业务能采用以下集成测试策略进行测试,请选择您希望采用集成测试策略</span>
    </el-row>
    <el-row v-if="show4" style="margin-top: 10px;">
        <el-radio-group v-model="strategy">
            <el-radio-button v-for="(method, index) in strategies" :key="index" :label="method" :value="index" />
        </el-radio-group>
    </el-row>
    <el-row v-if="show4" style="margin-top: 10px;">
        <span class="cn_name">请选择生成的测试用例的输出格式</span>
    </el-row>
    <el-row v-if="show4" style="margin-top: 10px;">
        <el-radio-group v-model="output_format">
            <el-radio-button v-for="(format, index) in output_formats" :key="index" :label="format" :value="index" />
        </el-radio-group>
    </el-row>
    <el-row v-if="show4">
        <el-button style="margin-top: 20px; width: 180px;" type="success" :icon="Right" @click="startIntegrationTest" plain round>生成测试用例</el-button>
    </el-row>
    <el-divider v-if="show5" />
    <el-row v-loading="loading3" element-loading-text="LLM正在综合知识库内容进行集成测试分析"
        element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 98%; z-index: 902" />
    <el-row v-if="show5">
        <span class="cn_name">LLM结合知识库查找有关集成测试的内容...</span>
    </el-row>
    <el-row v-model="integration_knowledge_result" v-if="show5" style="margin-top: 10px;">
        <el-input v-model="integration_knowledge_result.integration_test_knowledge" style="width: 99%;"
            :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" disabled />
    </el-row>
    <el-row v-if="show5" style="margin-top: 10px;">
        <span class="cn_name">LLM将采用以下集成测试策略进行测试用例的生成...</span>
    </el-row>
    <el-row v-model="integration_knowledge_result" v-if="show5" style="margin-top: 10px;">
        <el-input v-model="integration_knowledge_result.integration_strategy_knowledge" style="width: 99%; "
            :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" disabled />
    </el-row>
    <el-divider v-if="show5" />
    <el-row v-if="show5" style="margin-top: 10px;">
        <span class="cn_name">LLM将综合以下静态黑盒测试方法进行测试用例的生成...</span>
    </el-row>
    <el-row v-model="integration_knowledge_result" v-if="show5" style="margin-top: 10px;">
        <el-input v-model="integration_knowledge_result.static_blackbox_knowledge" style="width: 99%; "
            :autosize="{ minRows: 2, maxRows: 20 }" type="textarea" disabled />
    </el-row>
    <el-divider v-if="show5" />
    <el-row v-loading="loading4" element-loading-text="LLM正在生成集成测试用例" element-loading-background="rgba(255,255,255,1)"
        style="margin-top: 10px; width: 98%; z-index: 902" />
    <el-row v-if="show6">
        <span class="cn_name" style="color: #06B009;">LLM生成的测试用例如下</span>
    </el-row>
    <el-row v-if="show6" style="margin-top: 10px;">
        <el-input v-model="test_cases" style="width: 99%;" :autosize="{ minRows: 2, maxRows: 50 }" type="textarea"
            readonly />
    </el-row>
    <el-divider v-if="show6" border-style="dotted" />
    <el-row v-if="show6">
        <el-button style="width: 120px;" type="info" @click="reset">重置</el-button>
    </el-row>
</template>


<script lang="ts" setup>
import { ref, getCurrentInstance, reactive } from "vue";
import { Right } from '@element-plus/icons-vue'
import { ElMessage } from "element-plus";
import axios from "axios";

const test_cases = ref('')
const integration_type = ref('')
const integration_types = ref(['系统集成测试', '子系统间集成测试', '子系统内集成测试', '模块内集成测试', '类(class)内集成测试'])
const integration_unit = ref('')
const integration_units = ref()
const integration_info = ref('')
const strategy = ref(-1)
const strategies = ref(['大爆炸集成(Big Bang Integration)', '自顶向下集成(Top-Down Integration)', '自底向上集成(Bottom-up Intagration)',
    '三明治集成(Sandwich Integration)'])
const output_format = ref(0)
const output_formats = ref(['.txt(文字形式)', '.md(表格形式)', '.xml', '.csv'])

let integration_types_list: any = reactive([])
const menu_result = ref()
const integration_knowledge_result = ref()

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


const instance = getCurrentInstance()
if (instance == null) {
    ElMessage({ message: "平台出现了一些问题,无法获取关键信息", type: "error" });
}
const requestUrl = instance?.appContext.config.globalProperties.$requestUrl;
const project_id = instance?.appContext.config.globalProperties.$id;
const units_info = ref('')

const getUnitsInfo = async () => {
    await axios.get(requestUrl + "/project/info/" + project_id + "/2").then((resp) => {
        if (resp.data.data == false) {
            ElMessage({ message: resp.data.reason, type: "error" });
            return
        } else {
            units_info.value = resp.data.data
        }
    });
}

const generateUnitsInfo = async () => {
    await axios.get(requestUrl + "/project/llm/unit/menu/" + project_id).then((resp) => {
        if (resp.data.data == false) {
            ElMessage({ message: resp.data.reason, type: "error" });
            return
        } else {
            units_info.value = resp.data.data.text_info
        }
    });
}

const getIntegrationTestMenu = async () => {
    loading1.value = true
    await getUnitsInfo()
    if (units_info.value == '') {
        ElMessage({ message: "您还没有进行单元测试哦!", type: "warning" })
        await generateUnitsInfo()
    }
    await axios.post(requestUrl + "/project/llm/integration/menu", {
        summary: units_info.value
    }).then((resp) => {
        if (resp.data.data == false) {
            ElMessage({ message: resp.data.reason, type: "error" });
            return
        } else {
            menu_result.value = resp.data.data
            if (menu_result.value.subsystem_integration_test) {
                integration_types_list.push(integration_types.value[1])
            }
            else {
                // 子系统间进行集成测试就是整个系统的集成测试了
                integration_types_list.push(integration_types.value[0])
            }
            if (menu_result.value.subsystem_integration_menu.subsystem_test && menu_result.value.subsystem_integration_menu.subsystem_list.length) {
                integration_types_list.push(integration_types.value[2])
            }
            if (menu_result.value.module_integration_menu.module_test && menu_result.value.module_integration_menu.module_list.length) {
                integration_types_list.push(integration_types.value[3])
            }
            if (menu_result.value.class_integration_menu.class_test && menu_result.value.class_integration_menu.class_list.length) {
                integration_types_list.push(integration_types.value[4])
            }
            loading1.value = false
            show1.value = true
        }
    });
}

const generateIntegrations = () => {
    integration_unit.value = ''
    if (integration_type.value == integration_types.value[0]) {
        show2.value = false
    }
    else if (integration_type.value == integration_types.value[1]) {
        show2.value = false
    }
    else if (integration_type.value == integration_types.value[2]) {
        show2.value = true
        integration_units.value = menu_result.value.subsystem_integration_menu.subsystem_list
    }
    else if (integration_type.value == integration_types.value[3]) {
        show2.value = true
        integration_units.value = menu_result.value.module_integration_menu.module_list
    }
    else {
        show2.value = true
        integration_units.value = menu_result.value.class_integration_menu.class_list
    }
    show3.value = true
}

const furtherAnalyze = () => {
    show4.value = false
    if ((integration_type.value != integration_types.value[0]) && (integration_type.value != integration_types.value[1]) && integration_unit.value == '') {
        ElMessage({ message: "请先选择要集成测试的单元", type: "warning" });
        return
    }
    let name = ''
    let integ_type = -1
    if (integration_type.value == integration_types.value[0]) {
        integ_type = 0
    }
    else if (integration_type.value == integration_types.value[1]) {
        integ_type = 1
    }
    else if (integration_type.value == integration_types.value[2]) {
        integ_type = 2
    }
    else if (integration_type.value == integration_types.value[3]) {
        integ_type = 3
    }
    else {
        integ_type = 4
    }
    if ((integration_type.value == integration_types.value[0]) || (integration_type.value == integration_types.value[1])) {
        name = 'none'
    }
    else {
        name = integration_unit.value
    }
    loading2.value = true
    axios.get(requestUrl + "/project/llm/integration/info/" + project_id + "/" + integ_type + "/" + name).then((resp) => {
        if (resp.data.data == false) {
            ElMessage({ message: resp.data.reason, type: "error" });
            return
        } else {
            integration_info.value = resp.data.data
            loading2.value = false
            show4.value = true
        }
    });
}

const generateTestCases = async () => {
  loading4.value = true
  let integration_object = ''
  if(integration_type.value == integration_types.value[0]){
    integration_object = '业务中的整个系统'
  }
  else if(integration_type.value == integration_types.value[1]){
    integration_object = '业务中的由多个子系统构成的整体系统'
  }
  else{
    integration_object = integration_unit.value
  }
  await axios.post(requestUrl + "/project/llm/integration/case", {
    integration_test_knowledge: integration_knowledge_result.value.integration_test_knowledge,
    strategy: strategies.value[strategy.value],
    strategy_knowledge: integration_knowledge_result.value.integration_strategy_knowledge,
    blackbox_method_knowledge: integration_knowledge_result.value.static_blackbox_knowledge,
    integration_object: integration_object,
    integration_object_info: integration_info.value,
    output_type: output_format.value
  }).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      return
    }
    else {
      test_cases.value = resp.data.data
      show6.value = true
      loading4.value = false
    }
  });
}

const startIntegrationTest = async () => {
  if (strategy.value == -1) {
    ElMessage({ message: "请先选择集成测试策略", type: "warning" });
    loading3.value = false
    return
  }
  loading3.value = true
  await axios.get(requestUrl + "/project/llm/integration/knowledge/" + project_id + "/" + strategy.value).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      return
    }
    else {
      integration_knowledge_result.value = resp.data.data
      show5.value = true
      loading3.value = false
      generateTestCases()
    }
  });
}

const reset = () => {
  show3.value = false
  show4.value = false
  show5.value = false
  show6.value = false
  strategy.value = -1
  output_format.value = -1
  integration_info.value = ''
  loading1.value = false
  loading2.value = false
  loading3.value = false
  loading4.value = false
  test_cases.value = ''
}
</script>

<style scoped>
.el-row {
    min-width: 850px;
}

.cn_name {
    font-family: "Ali";
}

.en_name {
    font-family: "Quantify";
}
</style>