<template>
  <el-row v-loading="loading" element-loading-text="LLM正在进行业务文档初步分析,请耐心等待"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 100%; z-index: 900">
  </el-row>
  <el-row v-if="analyzeFinished">
    <span class="cn_name">LLM对业务文档进行的初步分析和总结如下</span>
  </el-row>
  <el-row v-if="analyzeFinished">
    <el-input v-model="analyzeText" style="width: 100%; margin-top: 10px;" :autosize="{ minRows: 2, maxRows: 20 }"
      type="textarea" disabled />
  </el-row>
  <el-row v-if="restart">
    <span style="margin-top: 5px;" class="cn_name">
      请选择用于初步分析业务项目的大语言模型(首次初步分析默认使用GPT-3.5,您可以选择不同的大语言模型重新分析)
    </span>
  </el-row>
  <el-row v-if="restart">
    <el-segmented style="margin-top: 5px;" v-model="llm" :options="options" size="large" />
  </el-row>
  <el-row>
    <el-button v-if="restart" style="margin-top: 10px ;width: 180px;" type="info" :icon="Right" plain round
      @click="generateInfoAgain">重新进行项目整体分析</el-button>
  </el-row>
  <el-row v-if="menuFinished" style="margin-top: 10px;">
    <span class="cn_name">
      根据LLM对业务文档进行的测试分析您的业务推荐使用LLM进行以下测试的设计以及相关用例生成,您也可以手动选择进行何种测试。
    </span>
  </el-row>
  <el-row v-loading="menuLoading" element-loading-text="LLM正在分析适用于业务的测试类型"
    element-loading-background="rgba(255,255,255,1)" style="margin-top: 10px; width: 100%; z-index: 901">
  </el-row>
  <template v-for="(type, index) in test_list" :key="index">
    <el-row style="min-width: 800px" v-if="menuFinished && index % 2 === 0" :gutter="40">
      <el-col v-if="menuFinished" style="margin-top: 20px" :span="11">
        <el-card style="max-width: 95%; min-width: 300px">
          <template #header>
            <div class="card-header">
              <div>
                <span class="cn_name">{{ type.cnName }}</span>
              </div>
              <span class="en_name">({{ type.enName }})</span>
            </div>
          </template>
          <div class="cn_name">
            通过LLM分析,通过您提供的业务文档内容可以为您设计{{
              type.cnName
            }}的相关内容
          </div>
          <el-image style="margin-top: 10px; border-radius: 20px; width: 100%" :src="type.imgPath" />
          <template #footer>
            <el-row style="height: 38px">
              <RouterLink :to="type.link">
                <el-button style="position: absolute; right: 0" type="success" :icon="DArrowRight" circle />
              </RouterLink>
            </el-row>
          </template>
        </el-card>
      </el-col>
      <el-col style="margin-top: 20px" :span="11" v-if="menuFinished && (test_list[index + 1] != null)">
        <el-card style="max-width: 95%; min-width: 300px">
          <template #header>
            <div class="card-header">
              <div>
                <span class="cn_name">{{ test_list[index + 1].cnName }}</span>
              </div>
              <span class="en_name">({{ test_list[index + 1].enName }})</span>
            </div>
          </template>
          <div class="cn_name">
            通过LLM分析,通过您提供的业务文档内容可以为您设计{{
              test_list[index + 1].cnName
            }}的相关内容
          </div>
          <el-image style="margin-top: 10px; border-radius: 20px; width: 100%" :src="test_list[index + 1].imgPath" />
          <template #footer>
            <el-row style="height: 38px">
              <RouterLink :to="test_list[index + 1].link">
                <el-button style="position: absolute; right: 0" type="success" :icon="DArrowRight" circle />
              </RouterLink>
            </el-row>
          </template>
        </el-card>
      </el-col>
    </el-row>
  </template>
</template>

<script lang="ts" setup>
import { ref, getCurrentInstance, reactive } from "vue";
import { DArrowRight, Right } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import axios from "axios";

const loading = ref(true)
const menuLoading = ref(false)
const analyzeFinished = ref(false)
const analyzeText = ref('')
const menuFinished = ref(false)
const restart = ref(false)
let test_list: any = reactive([])
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

const instance = getCurrentInstance()
if (instance == null) {
  ElMessage({ message: "平台出现了一些问题,无法获取关键信息", type: "error" });
}
const requestUrl = instance?.appContext.config.globalProperties.$requestUrl;
const project_id = instance?.appContext.config.globalProperties.$id;
const test_menu = instance?.appContext.config.globalProperties.$test_menu;

const test_type = [
  // '生成测试计划', '单元测试', '集成测试', 'api接口测试','前端UI测试','数据库测试','系统功能性测试', '系统非功能性测试', '验收测试'
  {
    cnName: "生成测试计划",
    enName: "Generate Testing Plan",
    imgPath: require("@/assets/static/image/testPlan.png"),
    link: "/plan",
  },
  {
    cnName: "单元测试",
    enName: "Unit Testing",
    imgPath: require("@/assets/static/image/unitTest.png"),
    link: "/unit",
  },
  {
    cnName: "集成测试",
    enName: "Integration Testing",
    imgPath: require("@/assets/static/image/integrationTest.png"),
    link: "/integration",
  },
  {
    cnName: "api接口测试",
    enName: "Api Testing",
    imgPath: require("@/assets/static/image/apiTest.png"),
    link: "/api",
  },
  {
    cnName: "前端UI测试",
    enName: "UI Testing",
    imgPath: require("@/assets/static/image/UITest.png"),
    link: "/ui",
  },
  {
    cnName: "数据库测试",
    enName: "Database Testing",
    imgPath: require("@/assets/static/image/databaseTest.png"),
    link: "/database",
  },
  {
    cnName: "系统功能性测试",
    enName: "Functional Testing",
    imgPath: require("@/assets/static/image/functionalTest.png"),
    link: "/functional",
  },
  {
    cnName: "系统非功能性测试",
    enName: "Nonfunctional Testing",
    imgPath: require("@/assets/static/image/nonfunctionalTest.png"),
    link: "/nfunctional",
  },
  {
    cnName: "验收测试",
    enName: "Acceptance Testing",
    imgPath: require("@/assets/static/image/acceptanceTest.png"),
    link: "/acceptance",
  },
]

const generateMenu = async (summary: string) => {
  await axios.post(requestUrl + "/project/llm/menu/acquire", {
    summary: summary
  }).then((resp) => {
    let menu = resp.data.data
    if (menu.test_plan){
      test_list.push(test_type[0])
    }
    if (menu.unit_test) {
      test_list.push(test_type[1])
    }
    if (menu.integration_test) {
      test_list.push(test_type[2])
    }
    if (menu.api_test) {
      test_list.push(test_type[3])
    }
    if (menu.ui_test) {
      test_list.push(test_type[4])
    }
    if (menu.db_test) {
      test_list.push(test_type[5])
    }
    if (menu.functional_test) {
      test_list.push(test_type[6])
    }
    if (menu.nonfunctional_test) {
      test_list.push(test_type[7])
    }
    if (menu.acceptance_test) {
      test_list.push(test_type[8])
    }
    if (instance != null) {
      instance.appContext.config.globalProperties.$test_menu = test_list
    }
    menuLoading.value = false
    menuFinished.value = true
  });
}

const getinfo = async () => {
  await axios.get(requestUrl + "/project/llm/menu/analyze/" + project_id).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      return
    } else {
      analyzeFinished.value = true
      analyzeText.value = resp.data.data
      restart.value = true
      loading.value = false
      menuLoading.value = true
      generateMenu(analyzeText.value)
    }
  });
}

const generateInfoAgain = async () => {
  menuFinished.value = false
  analyzeFinished.value = false
  restart.value = false
  test_list = reactive([])
  loading.value = true
  await axios.get(requestUrl + "/project/llm/menu/analyze/update/" + project_id + "/" + llm.value).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      loading.value = false
      restart.value = true
      return
    } else {
      analyzeFinished.value = true
      analyzeText.value = resp.data.data
      loading.value = false
      restart.value = true
      menuLoading.value = true
      generateMenu(analyzeText.value)
    }
  });
}

if (project_id != null) {
  // 之前分析过不再继续分析S
  if (test_menu != null) {
    loading.value = false
    menuFinished.value = true
    restart.value = true
    test_list = test_menu
  }
  else {
    getinfo()
  }
}

// const openFullScreen = () => {
//   const loading = ElLoading.service({
//     lock: true,
//     text: "LLM正在为您进行测试分析",
//     background: "rgba(0,0,0,0.7)",
//   });
// };
// openFullScreen()
// 无论如何生成测试计划总是有的
</script>

<style scoped>
.cn_name {
  font-family: "Ali";
}

.en_name {
  font-family: "Quantify";
}
</style>
