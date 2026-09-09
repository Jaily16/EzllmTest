// 项目资料准备状态及浏览器恢复记录；恢复不等于重新上传，服务端确认决定资料是否齐全。
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

/** 创建三个资料组的独立计数初值。 */
const emptyCounts = (): Record<SetupGroup, number> => ({
  knowledge: 0,
  requirements: 0,
  design: 0,
});

/** 创建三个资料组各自的文件名数组，避免共享可变引用。 */
const emptyFiles = (): Record<SetupGroup, string[]> => ({
  knowledge: [],
  requirements: [],
  design: [],
});

/** 建立尚未绑定项目的准备状态，各组从 pending 开始。 */
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

/** 只检查浏览器对象存在性；实际存储权限仍可能在调用时失败。 */
const storageAvailable = (): boolean => typeof window !== "undefined";

/**
 * 有项目 ID 时把准备进度写入 localStorage，供刷新后的恢复提示使用。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const persistProjectSetupState = (): void => {
  if (!storageAvailable() || !projectSetupState.pid) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(projectSetupState));
};

/** 去除路径前缀，只使用文件名参与前端去重。 */
const basename = (filename: string): string => filename.trim().split(/[\\/]/).pop() || "";

/** 按上传命名规则转换文件主名，保留扩展名供重复文件检测。 */
export const normalizeUploadedDocumentName = (filename: string): string => {
  const safeName = basename(filename);
  const extensionIndex = safeName.lastIndexOf(".");
  const stem = extensionIndex >= 0 ? safeName.slice(0, extensionIndex) : safeName;
  const extension = extensionIndex >= 0 ? safeName.slice(extensionIndex) : "";
  return `${stem.replace(/ /g, "-").replace(/\./g, "_")}${extension}`;
};

/** 规范化后不区分大小写比较文件名，防止同一资料重复上传。 */
const sameUploadedDocument = (left: string, right: string): boolean =>
  normalizeUploadedDocumentName(left).toLocaleLowerCase() ===
  normalizeUploadedDocumentName(right).toLocaleLowerCase();

/**
 * 清空本地准备状态及恢复记录，不删除后端项目或已上传文件。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
export const resetProjectSetupState = (): void => {
  Object.assign(projectSetupState, emptyState());
  setupRequestActive.value = false;
  if (storageAvailable()) window.localStorage.removeItem(STORAGE_KEY);
};

/** 绑定新项目 ID 后记录 project_created 阶段，允许上传中断后继续恢复。 */
export const beginProjectSetup = (pid: string): void => {
  Object.assign(projectSetupState, emptyState(), {
    pid,
    stage: "project_created",
    message: "项目 ID 已生成，请继续上传资料",
  });
  persistProjectSetupState();
};

/** 更新单个资料组的阶段并保存本地恢复状态。 */
export const markSetupGroup = (group: SetupGroup, state: SetupStepState): void => {
  projectSetupState.groups[group] = state;
  persistProjectSetupState();
};

/** 仅在指定资料组内检查规范化文件名是否已登记。 */
export const isUploadedDocument = (group: SetupGroup, filename: string): boolean =>
  projectSetupState.documentFiles[group].some((stored) => sameUploadedDocument(stored, filename));

/** 登记成功上传的文件名并更新计数，忽略空名称和重复文件。 */
export const recordUploadedDocument = (group: SetupGroup, filename: string): void => {
  const normalized = normalizeUploadedDocumentName(filename);
  if (!normalized || isUploadedDocument(group, normalized)) return;
  projectSetupState.documentFiles[group].push(normalized);
  projectSetupState.documentCounts[group] = Math.max(
    projectSetupState.documentCounts[group] + 1,
    projectSetupState.documentFiles[group].length,
  );
  persistProjectSetupState();
};

/** 从未知载荷中筛选并规范化文件名，去除大小写等价的重复项。 */
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

/** 把计数限制为非负整数且不少于已知文件数，防止恢复状态倒退。 */
const safeCount = (value: unknown, minimum: number): number => {
  const numeric = typeof value === "number" && Number.isFinite(value) ? value : 0;
  return Math.max(Math.floor(numeric), minimum, 0);
};

/**
 * 以服务端资料状态校正三个组的文件清单、计数和允许动作，再保存恢复记录。
 * @param status 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
export const applyProjectSetupStatus = (
  status: ProjectSetupStatusResponse,
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

/**
 * 校验本地恢复载荷并补全资料组状态，损坏或无项目 ID 的记录不恢复。
 * @param value 待处理的值。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
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
    next.groups[group] = SETUP_STATES.includes(state)
      ? state === "running"
        ? "pending"
        : state
      : "pending";
    const files = safeFiles(restored.documentFiles?.[group]);
    next.documentFiles[group] = files;
    next.documentCounts[group] = safeCount(restored.documentCounts?.[group], files.length);
  }
  return next;
};

/**
 * 读取本地准备记录并按结构校验恢复；仅恢复页面状态，不自动重新上传文件。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
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

/** 校验并规范化显式后端地址，避免用缺失端点发送资料请求。 */
const normalizedBaseUrl = (baseUrl: string): string => baseUrl.replace(/\/$/, "");

/** 从准备接口响应提取已校验的项目状态，错误原因由统一信封提供。 */
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

/**
 * 请求指定项目准备状态，读取接口不负责生成或消费任务。
 * @param baseUrl 沿用当前 TypeScript 类型约束的输入。
 * @param pid 项目 ID。
 * @param signal 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
export const fetchProjectSetupStatus = async (
  baseUrl: string,
  pid: string,
  signal?: AbortSignal,
): Promise<ProjectSetupStatusResponse> => {
  const response = await axios.get(
    `${normalizedBaseUrl(baseUrl)}${SETUP_STATUS_PATH}${encodeURIComponent(pid)}`,
    { signal },
  );
  return statusFromResponse(response);
};

/** 读取准备状态后同步前端恢复记录，使重试跳过已登记的文件。 */
export const loadProjectSetupStatus = async (
  baseUrl: string,
  pid: string,
): Promise<ProjectSetupStatusResponse> =>
  applyProjectSetupStatus(await fetchProjectSetupStatus(baseUrl, pid));

/**
 * 显式提交资料确认请求并同步返回状态；模型分析由后续用户动作启动。
 * @param baseUrl 沿用当前 TypeScript 类型约束的输入。
 * @param pid 项目 ID。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
export const finalizeProjectSetup = async (
  baseUrl: string,
  pid: string,
): Promise<ProjectSetupStatusResponse> => {
  const response = await axios.post(
    `${normalizedBaseUrl(baseUrl)}${SETUP_FINALIZE_PATH}${encodeURIComponent(pid)}`,
  );
  return applyProjectSetupStatus(statusFromResponse(response));
};
