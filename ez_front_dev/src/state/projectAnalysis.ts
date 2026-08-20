import axios from "axios";
import { ref } from "vue";

export interface TestMenuState {
  test_plan: boolean;
  unit_test: boolean;
  integration_test: boolean;
  api_test: boolean;
  ui_test: boolean;
  db_test: boolean;
  functional_test: boolean;
  nonfunctional_test: boolean;
  acceptance_test: boolean;
}

interface ProjectAnalysisStatus {
  summary_ready: boolean;
  plan_ready: boolean;
  menu_ready: boolean;
  ready: boolean;
  menu: TestMenuState | null;
}

export const analysisReady = ref(false);
export const analysisStatusLoaded = ref(false);
export const analysisMenu = ref<TestMenuState | null>(null);

export const resetProjectAnalysisState = () => {
  analysisReady.value = false;
  analysisStatusLoaded.value = false;
  analysisMenu.value = null;
};

export const setProjectAnalysisReady = (menu: TestMenuState | null) => {
  analysisMenu.value = menu;
  analysisReady.value = menu !== null;
  analysisStatusLoaded.value = true;
};

export const loadProjectAnalysisStatus = async (
  baseUrl: string,
  pid: string
): Promise<ProjectAnalysisStatus> => {
  const response = await axios.get(
    `${baseUrl.replace(/\/$/, "")}/project/analysis/status/${pid}`
  );
  const data = response.data?.data as ProjectAnalysisStatus | false;
  if (!data || typeof data !== "object") {
    resetProjectAnalysisState();
    analysisStatusLoaded.value = true;
    throw new Error(String(response.data?.reason || "项目分析状态获取失败"));
  }
  analysisReady.value = data.ready === true;
  analysisMenu.value = data.menu ?? null;
  analysisStatusLoaded.value = true;
  return data;
};
