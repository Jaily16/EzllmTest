import axios from "axios";
import { reactive, ref } from "vue";

export type SetupStepState = "pending" | "running" | "completed" | "failed";
export type SetupGroup = "knowledge" | "requirements" | "design";

export interface ProjectSetupState {
  pid: string;
  stage: string;
  groups: Record<SetupGroup, SetupStepState>;
  documentCounts: Record<SetupGroup, number>;
  documentFiles: Record<SetupGroup, string[]>;
  allowedActions: string[];
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
const SETUP_STATES: SetupStepState[] = ["pending", "running", "completed", "failed"];

const emptyCounts = (): Record<SetupGroup, number> => ({
  knowledge: 0,
  requirements: 0,
  design: 0,
});

const emptyFiles = (): Record<SetupGroup, string[]> => ({
  knowledge: [],
  requirements: [],
  design: [],
});

const emptyState = (): ProjectSetupState => ({
  pid: "",
  stage: "",
  groups: { knowledge: "pending", requirements: "pending", design: "pending" },
  documentCounts: emptyCounts(),
  documentFiles: emptyFiles(),
  allowedActions: [],
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

const basename = (filename: string): string =>
  filename.trim().split(/[\\/]/).pop() || "";

export const normalizeUploadedDocumentName = (filename: string): string => {
  const safeName = basename(filename);
  const extensionIndex = safeName.lastIndexOf(".");
  const stem = extensionIndex >= 0 ? safeName.slice(0, extensionIndex) : safeName;
  const extension = extensionIndex >= 0 ? safeName.slice(extensionIndex) : "";
  return `${stem.replace(/ /g, "-").replace(/\./g, "_")}${extension}`;
};

const sameUploadedDocument = (left: string, right: string): boolean =>
  normalizeUploadedDocumentName(left).toLocaleLowerCase() ===
  normalizeUploadedDocumentName(right).toLocaleLowerCase();

export const resetProjectSetupState = (): void => {
  Object.assign(projectSetupState, emptyState());
  setupRequestActive.value = false;
  if (storageAvailable()) window.localStorage.removeItem(STORAGE_KEY);
};

export const beginProjectSetup = (pid: string): void => {
  Object.assign(projectSetupState, emptyState(), {
    pid,
    stage: "project_created",
    message: "项目 ID 已生成，请继续上传资料",
  });
  persistProjectSetupState();
};

export const markSetupGroup = (group: SetupGroup, state: SetupStepState): void => {
  projectSetupState.groups[group] = state;
  persistProjectSetupState();
};

export const isUploadedDocument = (group: SetupGroup, filename: string): boolean =>
  projectSetupState.documentFiles[group].some((stored) =>
    sameUploadedDocument(stored, filename)
  );

export const recordUploadedDocument = (group: SetupGroup, filename: string): void => {
  const normalized = normalizeUploadedDocumentName(filename);
  if (!normalized || isUploadedDocument(group, normalized)) return;
  projectSetupState.documentFiles[group].push(normalized);
  projectSetupState.documentCounts[group] = Math.max(
    projectSetupState.documentCounts[group] + 1,
    projectSetupState.documentFiles[group].length
  );
  persistProjectSetupState();
};

const safeFiles = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  const unique: string[] = [];
  for (const item of value) {
    if (typeof item !== "string") continue;
    const normalized = normalizeUploadedDocumentName(item);
    if (normalized && !unique.some((stored) => sameUploadedDocument(stored, normalized))) {
      unique.push(normalized);
    }
  }
  return unique;
};

const safeCount = (value: unknown, minimum: number): number => {
  const numeric = typeof value === "number" && Number.isFinite(value) ? value : 0;
  return Math.max(Math.floor(numeric), minimum, 0);
};

export const applyProjectSetupStatus = (
  status: ProjectSetupStatusResponse
): ProjectSetupStatusResponse => {
  projectSetupState.pid = status.pid;
  projectSetupState.stage = status.stage;
  projectSetupState.sourceRevision = status.source_revision;
  projectSetupState.message = status.message;
  projectSetupState.allowedActions = Array.isArray(status.allowed_actions)
    ? status.allowed_actions.filter((action) => typeof action === "string")
    : [];
  for (const group of SETUP_GROUPS) {
    const files = safeFiles(status.document_files?.[group]);
    const count = safeCount(status.document_counts?.[group], files.length);
    projectSetupState.documentFiles[group] = files;
    projectSetupState.documentCounts[group] = count;
    projectSetupState.groups[group] = count > 0 ? "completed" : "pending";
  }
  persistProjectSetupState();
  return status;
};

const restoredState = (value: unknown): ProjectSetupState | null => {
  if (!value || typeof value !== "object") return null;
  const restored = value as Partial<ProjectSetupState>;
  if (
    typeof restored.pid !== "string" ||
    !restored.pid ||
    typeof restored.stage !== "string" ||
    !restored.groups
  ) {
    return null;
  }

  const next = emptyState();
  next.pid = restored.pid;
  next.stage = restored.stage;
  next.sourceRevision =
    typeof restored.sourceRevision === "string" ? restored.sourceRevision : null;
  next.message = typeof restored.message === "string" ? restored.message : "";
  next.allowedActions = Array.isArray(restored.allowedActions)
    ? restored.allowedActions.filter((action): action is string => typeof action === "string")
    : [];

  for (const group of SETUP_GROUPS) {
    const state = restored.groups[group];
    next.groups[group] =
      SETUP_STATES.includes(state) ? (state === "running" ? "pending" : state) : "pending";
    const files = safeFiles(restored.documentFiles?.[group]);
    next.documentFiles[group] = files;
    next.documentCounts[group] = safeCount(restored.documentCounts?.[group], files.length);
  }
  return next;
};

export const restoreProjectSetupState = (): boolean => {
  if (!storageAvailable()) return false;
  const serialized = window.localStorage.getItem(STORAGE_KEY);
  if (!serialized) return false;
  try {
    const restored = restoredState(JSON.parse(serialized));
    if (!restored) {
      window.localStorage.removeItem(STORAGE_KEY);
      return false;
    }
    Object.assign(projectSetupState, restored);
    persistProjectSetupState();
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
  return status;
};

export const fetchProjectSetupStatus = async (
  baseUrl: string,
  pid: string,
  signal?: AbortSignal
): Promise<ProjectSetupStatusResponse> => {
  const response = await axios.get(
    `${normalizedBaseUrl(baseUrl)}${SETUP_STATUS_PATH}${encodeURIComponent(pid)}`,
    { signal }
  );
  return statusFromResponse(response);
};

export const loadProjectSetupStatus = async (
  baseUrl: string,
  pid: string
): Promise<ProjectSetupStatusResponse> =>
  applyProjectSetupStatus(await fetchProjectSetupStatus(baseUrl, pid));

export const finalizeProjectSetup = async (
  baseUrl: string,
  pid: string
): Promise<ProjectSetupStatusResponse> => {
  const response = await axios.post(
    `${normalizedBaseUrl(baseUrl)}${SETUP_FINALIZE_PATH}${encodeURIComponent(pid)}`
  );
  return applyProjectSetupStatus(statusFromResponse(response));
};
