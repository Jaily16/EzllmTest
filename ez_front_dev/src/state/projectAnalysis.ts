import axios from "axios";
import { computed, ref } from "vue";

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

export interface ProjectAnalysisBundle {
  summary: string;
  plan: string;
  menu: TestMenuState;
}

export type ProjectStage =
  | "setup_required"
  | "analysis_required"
  | "analysis_ready"
  | "testing_in_progress"
  | "testing_ready";

export interface ProjectWorkflowStatus {
  pid: string;
  stage: ProjectStage;
  allowed_routes: string[];
  completed_operations: string[];
  stale_operations: string[];
  menu: TestMenuState | null;
  source_revision: string | null;
  message: string;
}

interface ProjectAnalysisStatus {
  summary_ready: boolean;
  plan_ready: boolean;
  menu_ready: boolean;
  ready: boolean;
  menu: TestMenuState | null;
}

const TEST_MENU_KEYS: Array<keyof TestMenuState> = [
  "test_plan",
  "unit_test",
  "integration_test",
  "api_test",
  "ui_test",
  "db_test",
  "functional_test",
  "nonfunctional_test",
  "acceptance_test",
];

const parseProjectAnalysisMenu = (value: unknown): TestMenuState => {
  let candidate = value;
  if (typeof candidate === "string") {
    try {
      candidate = JSON.parse(candidate);
    } catch {
      throw new Error("已保存的测试菜单格式无效，请重新生成测试计划");
    }
  }
  if (!candidate || typeof candidate !== "object") {
    throw new Error("未读取到有效的测试菜单，请重新生成测试计划");
  }
  const record = candidate as Record<string, unknown>;
  if (TEST_MENU_KEYS.some((key) => typeof record[key] !== "boolean")) {
    throw new Error("已保存的测试菜单字段不完整，请重新生成测试计划");
  }
  return Object.fromEntries(
    TEST_MENU_KEYS.map((key) => [key, record[key]])
  ) as unknown as TestMenuState;
};

const projectInfoValue = (
  response: { data?: { data?: unknown; reason?: unknown } },
  label: string
): unknown => {
  const value = response.data?.data;
  if (value === false || value === null || value === undefined) {
    throw new Error(String(response.data?.reason || `${label}读取失败`));
  }
  return value;
};

const WORKFLOW_STATUS_PATH = "/project/workflow/status/";
const READY_STAGES: ProjectStage[] = [
  "analysis_ready",
  "testing_in_progress",
  "testing_ready",
];
const MENU_ROUTES: Array<[keyof TestMenuState, string]> = [
  ["unit_test", "/unit"],
  ["integration_test", "/integration"],
  ["api_test", "/api"],
  ["ui_test", "/ui"],
  ["db_test", "/database"],
  ["functional_test", "/functional"],
  ["nonfunctional_test", "/nfunctional"],
  ["acceptance_test", "/acceptance"],
];
let pendingWorkflowStatus:
  | { key: string; promise: Promise<ProjectWorkflowStatus> }
  | null = null;

export const analysisReady = ref(false);
export const analysisStatusLoaded = ref(false);
export const analysisMenu = ref<TestMenuState | null>(null);
export const projectWorkflowStatus = ref<ProjectWorkflowStatus | null>(null);
export const workflowStatusLoaded = ref(false);
export const workflowRedirectMessage = ref("");
export const projectAnalysisRegenerating = ref(false);
export const completedOperations = computed(
  () => projectWorkflowStatus.value?.completed_operations ?? []
);
export const staleOperations = computed(
  () => projectWorkflowStatus.value?.stale_operations ?? []
);

const resetLegacyAnalysisState = () => {
  analysisReady.value = false;
  analysisStatusLoaded.value = false;
  analysisMenu.value = null;
};

export const resetProjectAnalysisState = () => {
  resetLegacyAnalysisState();
  projectWorkflowStatus.value = null;
  workflowStatusLoaded.value = false;
  workflowRedirectMessage.value = "";
  projectAnalysisRegenerating.value = false;
};

export const beginProjectAnalysisRegeneration = () => {
  projectAnalysisRegenerating.value = true;
};

export const finishProjectAnalysisRegeneration = () => {
  projectAnalysisRegenerating.value = false;
};

const routesForMenu = (menu: TestMenuState): string[] => [
  "/plan",
  "/menu",
  ...MENU_ROUTES.filter(([key]) => menu[key]).map(([, route]) => route),
];

const applyWorkflowStatus = (status: ProjectWorkflowStatus) => {
  projectWorkflowStatus.value = status;
  workflowStatusLoaded.value = true;
  analysisStatusLoaded.value = true;
  analysisReady.value = READY_STAGES.includes(status.stage);
  analysisMenu.value = analysisReady.value ? status.menu : null;
};

export const setProjectAnalysisReady = (menu: TestMenuState | null) => {
  analysisMenu.value = menu;
  analysisReady.value = menu !== null;
  analysisStatusLoaded.value = true;
  if (!menu) return;

  const previous = projectWorkflowStatus.value;
  const stage =
    previous?.stage === "testing_in_progress" ||
    previous?.stage === "testing_ready"
      ? previous.stage
      : "analysis_ready";
  applyWorkflowStatus({
    pid: previous?.pid ?? "",
    stage,
    allowed_routes: routesForMenu(menu),
    completed_operations: Array.from(
      new Set([...(previous?.completed_operations ?? []), "project_analysis"])
    ),
    stale_operations: (previous?.stale_operations ?? []).filter(
      (operation) => operation !== "project_analysis"
    ),
    menu,
    source_revision: previous?.source_revision ?? null,
    message: "项目分析已就绪，可以开始测试",
  });
};

export const loadProjectAnalysisStatus = async (
  baseUrl: string,
  pid: string
): Promise<ProjectAnalysisStatus> => {
  const status = await loadProjectWorkflowStatus(baseUrl, pid);
  const ready = READY_STAGES.includes(status.stage);
  const bundleReady = status.completed_operations.includes("project_analysis");
  return {
    summary_ready: bundleReady,
    plan_ready: bundleReady,
    menu_ready: status.menu !== null,
    ready,
    menu: status.menu,
  };
};

export const fetchProjectAnalysisBundle = async (
  baseUrl: string,
  pid: string,
  signal?: AbortSignal
): Promise<ProjectAnalysisBundle> => {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, "");
  if (!normalizedBaseUrl || !pid) {
    throw new Error("无法获取后端地址或项目编号");
  }
  const [summaryResponse, planResponse, menuResponse] = await Promise.all([
    axios.get(`${normalizedBaseUrl}/project/info/${pid}/1`, { signal }),
    axios.get(`${normalizedBaseUrl}/project/info/${pid}/22`, { signal }),
    axios.get(`${normalizedBaseUrl}/project/info/${pid}/23`, { signal }),
  ]);
  const summaryValue = projectInfoValue(summaryResponse, "业务摘要");
  const planValue = projectInfoValue(planResponse, "测试计划");
  const menuValue = projectInfoValue(menuResponse, "测试菜单");
  const summary = typeof summaryValue === "string" ? summaryValue.trim() : "";
  const plan = typeof planValue === "string" ? planValue.trim() : "";
  if (!summary || !plan) {
    throw new Error("已保存的业务摘要或测试计划为空，请重新生成");
  }
  return {
    summary,
    plan,
    menu: parseProjectAnalysisMenu(menuValue),
  };
};

export const loadProjectWorkflowStatus = async (
  baseUrl: string,
  pid: string
): Promise<ProjectWorkflowStatus> => {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, "");
  const key = `${normalizedBaseUrl}:${pid}`;
  if (pendingWorkflowStatus?.key === key) {
    return pendingWorkflowStatus.promise;
  }
  const promise = (async () => {
    const response = await axios.get(
      `${normalizedBaseUrl}${WORKFLOW_STATUS_PATH}${pid}`
    );
    const data = response.data?.data as ProjectWorkflowStatus | false;
    if (
      !data ||
      typeof data !== "object" ||
      !Array.isArray(data.allowed_routes) ||
      !Array.isArray(data.completed_operations) ||
      !Array.isArray(data.stale_operations)
    ) {
      workflowStatusLoaded.value = true;
      throw new Error(String(response.data?.reason || "项目工作流状态获取失败"));
    }
    applyWorkflowStatus(data);
    return data;
  })();
  pendingWorkflowStatus = { key, promise };
  try {
    return await promise;
  } finally {
    if (pendingWorkflowStatus?.promise === promise) {
      pendingWorkflowStatus = null;
    }
  }
};

export const isWorkflowRouteAllowed = (path: string): boolean => {
  if (projectAnalysisRegenerating.value) return path === "/plan";
  return projectWorkflowStatus.value?.allowed_routes.includes(path) === true;
};

export const getWorkflowRedirectPath = (): string =>
  projectWorkflowStatus.value?.stage === "setup_required" ? "/create" : "/plan";

export const setWorkflowRedirectMessage = (path: string) => {
  const fallback = `当前项目状态不允许访问 ${path}`;
  workflowRedirectMessage.value = projectWorkflowStatus.value?.message || fallback;
};
