// 项目作用域内的 Agent HTTP 客户端，命令提交与状态查询分开，不包含工具执行实现。
import type {
  AgentBudgetPreset,
  AgentCapabilities,
  AgentRunSummary,
  AgentRunView,
} from "@/entities/agent-run/types";
import axios, { AxiosRequestConfig } from "axios";
import type { ModelLabel } from "@/shared/config/models";

interface AgentEnvelope<T> {
  status: string;
  reason: string;
  data: T;
}

/** 移除端点末尾的一个斜杠，便于拼接固定接口路径。 */
const normalized = (baseUrl: string): string => baseUrl.replace(/\/$/, "");

// 所有 Agent 请求都验证统一响应信封，避免把错误响应当作可持久化运行数据。
/**
 * 统一读取 Agent 响应信封；非成功状态抛出服务端允许展示的原因。
 * @param baseUrl 沿用当前 TypeScript 类型约束的输入。
 * @param path 沿用当前 TypeScript 类型约束的输入。
 * @param config 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const request = async <T>(
  baseUrl: string,
  path: string,
  config: AxiosRequestConfig = {},
): Promise<T> => {
  const response = await axios.request<AgentEnvelope<T>>({
    url: `${normalized(baseUrl)}${path}`,
    ...config,
  });
  const envelope = response.data;
  if (response.status >= 400 || envelope?.status !== "success") {
    throw new Error(envelope?.reason || "Agent 服务请求失败");
  }
  return envelope.data;
};

/** 分别编码项目和 thread 标识，构造项目作用域内的运行路径。 */
const runPath = (pid: string, threadId = ""): string =>
  `/agent/v1/projects/${encodeURIComponent(pid)}/runs${
    threadId ? `/${encodeURIComponent(threadId)}` : ""
  }`;

/** 读取 Agent 能力清单，供界面判断支持的操作与限制。 */
export const loadAgentCapabilities = (baseUrl: string) =>
  request<AgentCapabilities>(baseUrl, "/agent/v1/capabilities");

/** 读取项目运行摘要及活动运行标识，不创建新任务。 */
export const listAgentRuns = (baseUrl: string, pid: string) =>
  request<{
    runs: AgentRunSummary[];
    active_thread_id: string | null;
    next_cursor: number | null;
  }>(baseUrl, runPath(pid));

/** 读取指定运行快照，供订阅前初始化与重放重置后恢复。 */
export const getAgentRun = (baseUrl: string, pid: string, threadId: string) =>
  request<AgentRunView>(baseUrl, runPath(pid, threadId));

/** 提交目标、模型与预算档位创建运行，返回排队命令及运行标识。 */
export const createAgentRun = (
  baseUrl: string,
  pid: string,
  payload: {
    goal: string;
    model_label: ModelLabel;
    budget_preset: AgentBudgetPreset;
  },
) =>
  request<{ run_id: string; thread_id: string; command_id: string }>(baseUrl, runPath(pid), {
    method: "POST",
    data: payload,
  });

/** 提交批准或拒绝时绑定 expected_plan_hash，防止旧弹窗批准已变化的计划。 */
export const decideAgentApproval = (
  baseUrl: string,
  pid: string,
  threadId: string,
  decision: "approved" | "rejected",
  expectedPlanHash: string,
) =>
  request<{ command_id: string }>(baseUrl, `${runPath(pid, threadId)}/approval`, {
    method: "POST",
    data: { decision, expected_plan_hash: expectedPlanHash },
  });

/** 编辑目标携带当前计划哈希，让后端拒绝过时界面的修改。 */
export const editAgentGoal = (
  baseUrl: string,
  pid: string,
  threadId: string,
  goal: string,
  expectedPlanHash: string,
) =>
  request<{ command_id: string }>(baseUrl, `${runPath(pid, threadId)}/edit`, {
    method: "POST",
    data: { goal, expected_plan_hash: expectedPlanHash },
  });

/** 向指定运行提交取消请求；实际终止和保存边界由后端协调器管理。 */
export const cancelAgentRun = (baseUrl: string, pid: string, threadId: string) =>
  request<AgentRunView>(baseUrl, `${runPath(pid, threadId)}/cancel`, {
    method: "POST",
  });

/** 显式请求恢复既有运行，返回命令标识而不在浏览器重放工具调用。 */
export const recoverAgentRun = (baseUrl: string, pid: string, threadId: string) =>
  request<{ command_id: string }>(baseUrl, `${runPath(pid, threadId)}/recover`, {
    method: "POST",
  });
