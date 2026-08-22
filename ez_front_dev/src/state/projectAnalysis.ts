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
