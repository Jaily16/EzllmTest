<template>
  <el-skeleton v-if="loading" :rows="6" animated />

  <el-empty
    v-else-if="!analysisReady || !analysisMenu"
    description="请先完成业务分析、测试计划和测试菜单生成"
  >
    <RouterLink to="/plan">
      <el-button type="success">前往测试计划</el-button>
    </RouterLink>
  </el-empty>

  <template v-else>
    <el-alert
      title="测试菜单已从数据库读取"
      description="以下测试类型由业务文档初步分析结果生成；如需更新，请回到测试计划页面重新分析。"
      type="success"
      :closable="false"
      show-icon
    />
    <template v-for="(type, index) in testList" :key="type.link">
      <el-row v-if="index % 2 === 0" style="min-width: 800px" :gutter="40">
        <el-col style="margin-top: 20px" :span="11">
          <TestTypeCard :type="type" />
        </el-col>
        <el-col
          v-if="testList[index + 1]"
          style="margin-top: 20px"
          :span="11"
        >
          <TestTypeCard :type="testList[index + 1]" />
        </el-col>
      </el-row>
    </template>
  </template>
</template>

<script lang="ts" setup>
import { computed, defineComponent, getCurrentInstance, h, onMounted, PropType, ref } from "vue";
import { DArrowRight } from "@element-plus/icons-vue";
import { ElButton, ElCard, ElImage, ElMessage, ElRow } from "element-plus";
import { RouterLink } from "vue-router";
import {
  analysisMenu,
  analysisReady,
  loadProjectAnalysisStatus,
  type TestMenuState,
} from "@/state/projectAnalysis";

interface TestTypeItem {
  key: keyof TestMenuState;
  cnName: string;
  enName: string;
  imgPath: string;
  link: string;
}

const testTypes: TestTypeItem[] = [
  {
    key: "test_plan",
    cnName: "测试计划",
    enName: "Testing Plan",
    imgPath: require("@/assets/static/image/testPlan.png"),
    link: "/plan",
  },
  {
    key: "unit_test",
    cnName: "单元测试",
    enName: "Unit Testing",
    imgPath: require("@/assets/static/image/unitTest.png"),
    link: "/unit",
  },
  {
    key: "integration_test",
    cnName: "集成测试",
    enName: "Integration Testing",
    imgPath: require("@/assets/static/image/integrationTest.png"),
    link: "/integration",
  },
  {
    key: "api_test",
    cnName: "api接口测试",
    enName: "API Testing",
    imgPath: require("@/assets/static/image/apiTest.png"),
    link: "/api",
  },
  {
    key: "ui_test",
    cnName: "前端UI测试",
    enName: "UI Testing",
    imgPath: require("@/assets/static/image/UITest.png"),
    link: "/ui",
  },
  {
    key: "db_test",
    cnName: "数据库测试",
    enName: "Database Testing",
    imgPath: require("@/assets/static/image/databaseTest.png"),
    link: "/database",
  },
  {
    key: "functional_test",
    cnName: "系统功能性测试",
    enName: "Functional Testing",
    imgPath: require("@/assets/static/image/functionalTest.png"),
    link: "/functional",
  },
  {
    key: "nonfunctional_test",
    cnName: "系统非功能性测试",
    enName: "Nonfunctional Testing",
    imgPath: require("@/assets/static/image/nonfunctionalTest.png"),
    link: "/nfunctional",
  },
  {
    key: "acceptance_test",
    cnName: "验收测试",
    enName: "Acceptance Testing",
    imgPath: require("@/assets/static/image/acceptanceTest.png"),
    link: "/acceptance",
  },
];

const TestTypeCard = defineComponent({
  name: "TestTypeCard",
  props: {
    type: { type: Object as PropType<TestTypeItem>, required: true },
  },
  setup(props) {
    return () =>
      h(
        ElCard,
        { style: "max-width: 95%; min-width: 300px" },
        {
          header: () =>
            h("div", { class: "card-header" }, [
              h("span", { class: "cn_name" }, props.type.cnName),
              h("span", { class: "en_name" }, `(${props.type.enName})`),
            ]),
          default: () => [
            h(
              "div",
              { class: "cn_name" },
              `根据业务文档分析，可以为该项目设计${props.type.cnName}的相关内容`
            ),
            h(ElImage, {
              style: "margin-top: 10px; border-radius: 20px; width: 100%",
              src: props.type.imgPath,
            }),
          ],
          footer: () =>
            h(ElRow, { style: "height: 38px" }, () =>
              h(RouterLink, { to: props.type.link }, () =>
                h(ElButton, {
                  style: "position: absolute; right: 0",
                  type: "success",
                  icon: DArrowRight,
                  circle: true,
                })
              )
            ),
        }
      );
  },
});

const instance = getCurrentInstance();
const loading = ref(true);
const requestUrl = String(instance?.appContext.config.globalProperties.$requestUrl || "");
const projectId = String(instance?.appContext.config.globalProperties.$id || "");
const testList = computed(() => {
  const menu = analysisMenu.value;
  return menu ? testTypes.filter((item) => menu[item.key]) : [];
});

onMounted(async () => {
  try {
    if (!analysisMenu.value) {
      await loadProjectAnalysisStatus(requestUrl, projectId);
    }
    if (instance) {
      instance.appContext.config.globalProperties.$test_menu = analysisMenu.value;
    }
  } catch (caught) {
    ElMessage({
      message: caught instanceof Error ? caught.message : "测试菜单读取失败",
      type: "error",
    });
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.cn_name {
  font-family: "Ali";
}
.en_name {
  font-family: "Quantify";
  margin-left: 8px;
}
.card-header {
  display: flex;
  align-items: baseline;
}
</style>
