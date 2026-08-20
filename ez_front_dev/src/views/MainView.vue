<template>
  <div class="common-layout">
    <el-container>
      <el-header style="position: sticky; top: 0; z-index: 999">
        <el-image
          style="width: 50px; height: 50px; margin-top: 5px"
          :src="require('@/assets/static/image/ezlogo.png')"
          fit="fill"
        />
        <div class="en_name">EzllmTest</div>
      </el-header>
      <el-container>
        <el-aside width="280px">
          <el-row style="text-align: center">
            <div class="info" style="margin-left: 5px">项目名称: {{ name }}</div>
          </el-row>
          <el-row style="text-align: center">
            <div class="info" style="margin-left: 5px">项目id: {{ id }}</div>
          </el-row>
          <el-menu :default-active="route.path" class="el-menu-vertical-demo" router>
            <el-sub-menu index="analysis">
              <template #title>
                <el-icon><DataAnalysis /></el-icon>
                <span>LLM智能测试分析</span>
              </template>
              <el-menu-item-group title="业务分析与测试规划">
                <el-menu-item index="/plan">
                  <el-icon><Notebook /></el-icon>
                  <span>测试计划</span>
                </el-menu-item>
                <el-menu-item index="/menu" :disabled="!analysisReady">
                  <el-icon><Menu /></el-icon>
                  <span>测试菜单</span>
                  <el-icon v-if="!analysisReady" class="lock-icon"><Lock /></el-icon>
                </el-menu-item>
              </el-menu-item-group>
              <el-menu-item-group title="如何正确使用本平台">
                <el-menu-item index="guide" disabled>
                  <el-icon><Reading /></el-icon>
                  <span>平台说明</span>
                </el-menu-item>
              </el-menu-item-group>
            </el-sub-menu>

            <el-sub-menu index="manual">
              <template #title>
                <el-icon><HelpFilled /></el-icon>
                <span>手动选择LLM测试类型</span>
                <el-icon v-if="!analysisReady" class="lock-icon"><Lock /></el-icon>
              </template>
              <el-menu-item-group
                :title="analysisReady ? '所有目前支持的测试类型' : '请先完成业务分析、测试计划和测试菜单'"
              >
                <el-menu-item index="/unit" :disabled="!analysisReady">
                  <el-icon><CollectionTag /></el-icon><span>单元测试</span>
                </el-menu-item>
                <el-menu-item index="/integration" :disabled="!analysisReady">
                  <el-icon><Files /></el-icon><span>集成测试</span>
                </el-menu-item>
                <el-menu-item index="/api" :disabled="!analysisReady">
                  <el-icon><Magnet /></el-icon><span>api接口测试</span>
                </el-menu-item>
                <el-menu-item index="/ui" :disabled="!analysisReady">
                  <el-icon><Monitor /></el-icon><span>前端UI测试</span>
                </el-menu-item>
                <el-menu-item index="/database" :disabled="!analysisReady">
                  <el-icon><MessageBox /></el-icon><span>数据库测试</span>
                </el-menu-item>
                <el-menu-item index="/functional" :disabled="!analysisReady">
                  <el-icon><Orange /></el-icon><span>系统功能性测试</span>
                </el-menu-item>
                <el-menu-item index="/nfunctional" :disabled="!analysisReady">
                  <el-icon><HelpFilled /></el-icon><span>系统非功能性测试</span>
                </el-menu-item>
                <el-menu-item index="/acceptance" :disabled="!analysisReady">
                  <el-icon><Box /></el-icon><span>验收测试</span>
                </el-menu-item>
              </el-menu-item-group>
            </el-sub-menu>

            <el-menu-item index="/create">
              <el-icon><Platform /></el-icon><span>创建新项目</span>
            </el-menu-item>
            <el-menu-item index="/">
              <el-icon><HomeFilled /></el-icon><span>返回开始界面</span>
            </el-menu-item>
          </el-menu>
        </el-aside>
        <el-main><router-view /></el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script lang="ts" setup>
import { getCurrentInstance, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import axios from "axios";
import { useRoute, useRouter } from "vue-router";
import {
  analysisMenu,
  analysisReady,
  loadProjectAnalysisStatus,
} from "@/state/projectAnalysis";

const instance = getCurrentInstance();
const route = useRoute();
const router = useRouter();
const id = ref("");
const name = ref("");

if (instance === null) {
  ElMessage({ message: "平台出现了一些问题,无法获取关键信息", type: "error" });
}
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");

const initializeProject = async () => {
  const projectId = instance?.appContext.config.globalProperties.$id;
  if (!projectId) {
    ElMessage({ message: "请先通过项目id进行登录", type: "error" });
    await router.replace("/");
    return;
  }

  id.value = String(projectId);
  try {
    const [projectResponse] = await Promise.all([
      axios.get(`${requestUrl}/project/login/${id.value}`),
      loadProjectAnalysisStatus(requestUrl, id.value),
    ]);
    name.value = String(projectResponse.data?.data || "");
    if (instance) {
      instance.appContext.config.globalProperties.$test_menu = analysisMenu.value;
    }
    if (!analysisReady.value && route.meta.requiresAnalysis) {
      await router.replace("/plan");
    }
  } catch (caught) {
    ElMessage({
      message: caught instanceof Error ? caught.message : "项目分析状态获取失败",
      type: "warning",
    });
    if (route.path !== "/plan") await router.replace("/plan");
  }
};

onMounted(initializeProject);
</script>

<style scoped>
.el-menu-vertical-demo {
  font-family: "Ali";
}
.info {
  font-family: "Ali";
  font-size: 15px;
  margin-top: 10px;
}
.el-header {
  background-color: #d1ffd3;
  display: flex;
}
.en_name {
  position: absolute;
  font-family: "Quantify";
  font-size: 40px;
  margin-top: 10px;
  margin-left: -60px;
  left: 50%;
}
.lock-icon {
  margin-left: auto;
}
</style>
