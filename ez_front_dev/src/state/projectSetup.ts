import axios from "axios";
import { reactive, ref } from "vue";


export type SetupStepState = "pending" | "running" | "completed" | "failed";
export type SetupGroup = "knowledge" | "requirements" | "design";

export interface ProjectSetupState {
  pid: string;
  stage: string;
  groups: Record<SetupGroup, SetupStepState>;
  sourceRevision: string | null;
  message: string;
}

export interface ProjectSetupStatusResponse {
  pid: string;
  project_exists: boolean;
  stage: string;
  document_counts: Record<SetupGroup, number>;
  document_files: Record<SetupGroup, string[]>;
  allowed_actions: string[];
  source_revision: string | null;
  message: string;
}

const STORAGE_KEY = "ezllmtest.projectSetup";
const SETUP_STATUS_PATH = "/project/setup/status/";
const SETUP_FINALIZE_PATH = "/project/setup/finalize/";
const SETUP_GROUPS: SetupGroup[] = ["knowledge", "requirements", "design"];

const emptyState = (): ProjectSetupState => ({
  pid: "",
  stage: "",
  groups: {
    knowledge: "pending",
    requirements: "pending",
    design: "pending",
  },
  sourceRevision: null,
  message: "",
});

export const projectSetupState = reactive<ProjectSetupState>(emptyState());
export const setupRequestActive = ref<boolean>(false);

const storageAvailable = (): boolean => typeof window !== "undefined";

const persistProjectSetupState = (): void => {
  if (!storageAvailable() || !projectSetupState.pid) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(projectSetupState));
};

export const resetProjectSetupState = (): void => {
  Object.assign(projectSetupState, emptyState());
  setupRequestActive.value = false;
  if (storageAvailable()) window.localStorage.removeItem(STORAGE_KEY);
};

export const beginProjectSetup = (pid: string): void => {
  Object.assign(projectSetupState, emptyState(), {
    pid,
    stage: "project_created",
    message: "项目id已生成，请继续上传资料",
  });
  persistProjectSetupState();
};

export const markSetupGroup = (
  group: SetupGroup,
  state: SetupStepState
): void => {
  projectSetupState.groups[group] = state;
  persistProjectSetupState();
};

export const applyProjectSetupStatus = (
  status: ProjectSetupStatusResponse
): ProjectSetupStatusResponse => {
  projectSetupState.pid = status.pid;
  projectSetupState.stage = status.stage;
  projectSetupState.sourceRevision = status.source_revision;
  projectSetupState.message = status.message;
  for (const group of SETUP_GROUPS) {
    projectSetupState.groups[group] =
      status.document_counts[group] > 0 ? "completed" : "pending";
  }
  persistProjectSetupState();
  return status;
};

export const restoreProjectSetupState = (): boolean => {
  if (!storageAvailable()) return false;
  const serialized = window.localStorage.getItem(STORAGE_KEY);
  if (!serialized) return false;
  try {
    const restored = JSON.parse(serialized) as Partial<ProjectSetupState>;
    if (
      typeof restored.pid !== "string" ||
      !restored.pid ||
      typeof restored.stage !== "string" ||
      !restored.groups
    ) {
      window.localStorage.removeItem(STORAGE_KEY);
      return false;
    }
    Object.assign(projectSetupState, emptyState(), restored);
    return true;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return false;
  }
};

const normalizedBaseUrl = (baseUrl: string): string => baseUrl.replace(/\/$/, "");

const statusFromResponse = (response: {
  status: number;
  data?: { data?: ProjectSetupStatusResponse | false; reason?: string };
}): ProjectSetupStatusResponse => {
  const status = response.data?.data;
  if (
    response.status >= 400 ||
    !status ||
    typeof status !== "object" ||
    status.project_exists !== true
  ) {
    throw new Error(String(response.data?.reason || "项目资料状态获取失败"));
  }
  return applyProjectSetupStatus(status);
};

export const loadProjectSetupStatus = async (
  baseUrl: string,
  pid: string
): Promise<ProjectSetupStatusResponse> => {
  const response = await axios.get(
    `${normalizedBaseUrl(baseUrl)}${SETUP_STATUS_PATH}${encodeURIComponent(pid)}`
  );
  return statusFromResponse(response);
};

export const finalizeProjectSetup = async (
  baseUrl: string,
  pid: string
): Promise<ProjectSetupStatusResponse> => {
  const response = await axios.post(
    `${normalizedBaseUrl(baseUrl)}${SETUP_FINALIZE_PATH}${encodeURIComponent(pid)}`
  );
  return statusFromResponse(response);
};
