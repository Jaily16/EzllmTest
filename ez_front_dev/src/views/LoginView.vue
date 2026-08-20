<template>
  <div class="background">
    <div class="main_container">
      <el-image style="width: 200px; height: 200px" :src="require('@/assets/static/image/ezlogo.png')" fit="fill" />
      <div class="en_name">EzllmTest</div>
      <div class="cn_name">LLM驱动的软件测试平台</div>
      <div class="id_area">
        <el-input v-model="input_pid" style="width: 230px; margin-left: -30px" placeholder="请输入项目id(若已创建项目)"
          :suffix-icon="User" maxlength="21" clearable />
        <el-button type="success" style="margin-left: 15px" @click="login" plain>开始分析业务和生成测试计划</el-button>
      </div>
      <RouterLink to="/create"><el-button type="success" style="margin-top: 20px; margin-left: 50px">创建新项目</el-button>
      </RouterLink>
    </div>
    <div class="platform_info">2.0测试版(可自由选择LLM进行测试分析,开发中)</div>
  </div>
</template>

<script lang="ts" setup>
import { ref, getCurrentInstance } from "vue";
import { User } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import axios from "axios";
import { useRouter } from "vue-router";
import { resetProjectAnalysisState } from "@/state/projectAnalysis";

const input_pid = ref('');
const instance = getCurrentInstance();
const router = useRouter()

//恢复整个项目的初始化
if(instance != null){
  instance.appContext.config.globalProperties.$test_menu = null
  instance.appContext.config.globalProperties.$unit_menu_result = null
  instance.appContext.config.globalProperties.$integration_menu_result = null
  instance.appContext.config.globalProperties.$id = null
  resetProjectAnalysisState()
}

if (instance == null) {
  ElMessage({ message: "平台出现了一些问题,无法获取关键信息", type: "error" });
}
const requestUrl = instance?.appContext.config.globalProperties.$requestUrl;


const login = async() => {
  if (input_pid.value == '') {
    ElMessage({ message: "请先输入项目id", type: "warning" });
    return
  }
  if (input_pid.value.length != 21){
    ElMessage({ message: "输入的项目id有误,请重新输入", type: "warning" });
    return
  }
  axios.get(requestUrl + "/project/login/" + input_pid.value).then((resp) => {
    if (resp.data.data == false) {
      ElMessage({ message: resp.data.reason, type: "error" });
      return
    }else{
      ElMessage({ message: resp.data.reason, type: "success" });
      if(instance != null){
        instance.appContext.config.globalProperties.$id = input_pid.value
      }
      // 用一点延时增强交互性
      setTimeout(function(){
        router.push({name: "testMain"})
      }, 400)
    }
  });
}

</script>

<style scoped>
.background {
  position: fixed;
  height: 100%;
  width: 100%;
  background-size: 100% 100%;
  background-image: linear-gradient(to bottom right,
      rgba(106, 255, 71, 0.5),
      white);
}

.main_container {
  position: absolute;
  left: 50%;
  top: 30%;
  margin: -100px 0 0 -100px;
  /* background-color: rosybrown; */
}

.en_name {
  width: 200px;
  font-family: "Quantify";
  font-size: 45px;
  text-align: center;
}

.cn_name {
  width: 200px;
  font-family: "Gjhn";
  font-size: 17px;
  text-align: center;
}

.id_area {
  display: flex;
  margin-top: 150px;
}

.platform_info {
  position: absolute;
  bottom: 0;
  right: 0;
  font-size: small;
}
</style>
