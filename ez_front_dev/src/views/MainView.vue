<template>
  <div class="common-layout">
    <el-container>
      <el-header style="position: sticky; top: 0; z-index: 999">
        <el-image style="width: 50px; height: 50px; margin-top: 5px" :src="require('@/assets/static/image/ezlogo.png')"
          fit="fill" />
        <div class="en_name">EzllmTest</div>
      </el-header>
      <el-container>
        <el-aside width="280px">
          <el-row v-model="name" style="text-align: center">
            <div class="info" style="margin-left: 5px;">项目名称: {{ name }}</div>
          </el-row>
          <el-row v-model="id" style="text-align: center">
            <div class="info" style="margin-left: 5px;">项目id: {{ id }}</div>
          </el-row>
          <el-menu default-active="1-1" class="el-menu-vertical-demo" @open="handleOpen" @close="handleClose">
            <el-sub-menu index="1">
              <template #title>
                <el-icon>
                  <DataAnalysis />
                </el-icon>
                <span>LLM智能测试分析</span>
              </template>
              <el-menu-item-group title="通过LLM分析可选测试类型">
                <router-link to="/menu">
                  <el-menu-item index="1-1">
                    <template #title>
                      <el-icon>
                        <Menu />
                      </el-icon>
                      <span>测试菜单</span>
                    </template>
                  </el-menu-item>
                </router-link>
              </el-menu-item-group>
              <el-menu-item-group title="如何正确使用本平台">
                <el-menu-item index="1-2">
                  <template #title>
                    <el-icon>
                      <Reading />
                    </el-icon>
                    <span>平台说明</span>
                  </template>
                </el-menu-item>
              </el-menu-item-group>
            </el-sub-menu>
            <el-sub-menu index="2">
              <template #title>
                <el-icon>
                  <HelpFilled />
                </el-icon>
                <span>手动选择LLM测试类型</span>
              </template>
              <el-menu-item-group title="所有目前支持的测试类型">
                <RouterLink to="/plan">
                  <el-menu-item index="2-1">
                    <template #title>
                      <el-icon>
                        <Notebook />
                      </el-icon>
                      <span>生成测试计划</span>
                    </template>
                  </el-menu-item>
                </RouterLink>
                <RouterLink to="/unit">
                  <el-menu-item index="2-2">
                    <template #title>
                      <el-icon>
                        <CollectionTag />
                      </el-icon>
                      <span>单元测试</span>
                    </template>
                  </el-menu-item>
                </RouterLink>
                <RouterLink to="/integration">
                  <el-menu-item index="2-3">
                    <template #title>
                      <el-icon>
                        <Files />
                      </el-icon>
                      <span>集成测试</span>
                    </template>
                  </el-menu-item>
                </RouterLink>
                <router-link to="/api">
                  <el-menu-item index="2-4">
                    <template #title>
                      <el-icon>
                        <Magnet />
                      </el-icon>
                      <span>api接口测试</span>
                    </template>
                  </el-menu-item>
                </router-link>
                <router-link to="/ui">
                  <el-menu-item index="2-5">
                    <template #title>
                      <el-icon>
                        <Monitor />
                      </el-icon>
                      <span>前端UI测试</span>
                    </template>
                  </el-menu-item>
                </router-link>
                <router-link to="/database">
                  <el-menu-item index="2-6">
                    <template #title>
                      <el-icon>
                        <MessageBox />
                      </el-icon>
                      <span>数据库测试</span>
                    </template>
                  </el-menu-item>
                </router-link>
                <router-link to="/functional">
                  <el-menu-item index="2-7">
                    <template #title>
                      <el-icon>
                        <Orange />
                      </el-icon>
                      <span>系统功能性测试</span>
                    </template>
                  </el-menu-item>
                </router-link>
                <router-link to="/nfunctional">
                  <el-menu-item index="2-8">
                    <template #title>
                      <el-icon>
                        <HelpFilled />
                      </el-icon>
                      <span>系统非功能性测试</span>
                    </template>
                  </el-menu-item>
                </router-link>
                <router-link to="/acceptance">
                  <el-menu-item index="2-9">
                    <template #title>
                      <el-icon>
                        <Box />
                      </el-icon>
                      <span>验收测试</span>
                    </template>
                  </el-menu-item>
                </router-link>
              </el-menu-item-group>
            </el-sub-menu>
            <RouterLink to="/create">
              <el-menu-item index="3">
                <el-icon>
                  <Platform />
                </el-icon>
                <span>创建新项目</span>
              </el-menu-item>
            </RouterLink>
            <RouterLink to="/">
              <el-menu-item index="4">
                <el-icon>
                  <HomeFilled />
                </el-icon>
                <span>返回开始界面</span>
              </el-menu-item>
            </RouterLink>
          </el-menu>
        </el-aside>
        <el-main><router-view /></el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script lang="ts" setup>
import { ref, getCurrentInstance } from "vue";
import { ElMessage } from "element-plus";
import axios from "axios";
const instance = getCurrentInstance()
const id = ref('')
const name = ref('')

if (instance == null) {
  ElMessage({ message: "平台出现了一些问题,无法获取关键信息", type: "error" });
}
const requestUrl = instance?.appContext.config.globalProperties.$requestUrl;

const getProjectName = () => {
  axios.get(requestUrl + "/project/login/" + id.value).then((resp) => {
    name.value = resp.data.data
  });
}

if (instance != null) {
  id.value = instance.appContext.config.globalProperties.$id
  if (id.value == null) {
    ElMessage({
      message: "请先通过项目id进行登录",
      type: "error",
    });
    setTimeout(function () {
      window.location.href = "http://localhost:8080"
    }, 400)
  }
  else {
    getProjectName()
  }
}
else {
  ElMessage({
    message: "发生了一些错误",
    type: "error",
  });
  window.location.href = "http://localhost:8080"
}


const handleOpen = (key: string, keyPath: string[]) => {
  console.log(key, keyPath);
};
const handleClose = (key: string, keyPath: string[]) => {
  console.log(key, keyPath);
};
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

* {
  text-decoration: none;
}

.router-link-active {
  text-decoration: none;
}
</style>
