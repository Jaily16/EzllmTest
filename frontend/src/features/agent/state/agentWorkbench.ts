import axios, { AxiosRequestConfig } from "axios";
import type { ModelLabel } from "@/shared/config/models";

export type AgentBudgetPreset = "focused" | "standard";
export type AgentRunStatus =
  | "created"
  | "planning"
  | "awaiting_approval"
  | "executing"
  | "validating"
  | "completed"
  | "cancelled"
  | "failed"
  | "recovering";

export interface AgentCapabilities {
  schema_version: number;
  graph_version: string;
  models: ModelLabel[];
  budget_presets: Array<{
    name: AgentBudgetPreset;
    budget: Record<string, number>;
    cost_unit: "synthetic_test_unit";
  }>;
  risks: string[];
  trace_status: "not_instrumented" | "instrumented";
  telemetry?: {
    mode: "disabled" | "recording";
    schema_version: "iteration4-aspect7-v1";
  };
  retrieval: {
    strategy: "dense_v1" | "hybrid_rrf_v1" | "hybrid_rerank_v1";
    policy_version: "iteration4-aspect5-v1";
    citation_mode: "metadata_only";
    rerank_enabled: boolean;
    agent_only: true;
  };
}

export interface AgentContextBinding {
  payload_field: string;
  source_operation: string;
  artifact_key: string;
  source_revision: string;
  result_path: string[];
  content_sha256: string;
}

export interface AgentRunSummary {
  run_id: string;
  thread_id: string;
  goal: string;
  status: AgentRunStatus;
  model_label: ModelLabel;
  budget_preset: AgentBudgetPreset;
  created_at: string;
  active: boolean;
}

export interface AgentPlanStep {
  step_id: string;
  operation: string;
  arguments: Record<string, unknown>;
  risks: string[];
  model_label: ModelLabel;
  retention: "artifact" | "session";
  current: boolean;
  context_bindings: AgentContextBinding[];
}

export interface AgentRetrievalCitation {
  citation_id: string;
  corpus: "design" | "requirements" | "knowledge";
  source_label: string;
  page: number;
  rank: number;
  score: number;
  score_kind: "dense" | "rrf" | "term_coverage";
  chunk_hash: string;
}

export interface AgentRetrievalEvidence {
  policy_version: "iteration4-aspect5-v1";
  strategy: "dense_v1" | "hybrid_rrf_v1" | "hybrid_rerank_v1";
  context_tokens: number;
  index_builds: number;
  index_reuses: number;
  queries: Array<{
    strategy: "dense_v1" | "hybrid_rrf_v1" | "hybrid_rerank_v1";
    policy_version: "iteration4-aspect5-v1";
    corpus: "design" | "requirements" | "knowledge";
    source_revision: string;
    query_hash: string;
    index_status: "build" | "reuse";
    context_tokens: number;
    citations: AgentRetrievalCitation[];
  }>;
}

export interface AgentApproval {
  plan_hash: string;
  plan_version: number;
  step_id: string;
  operation: string;
  risks: string[];
  expires_at: string;
  expired: boolean;
}

export interface AgentEvidence {
  step_id: string;
  operation: string;
  retention: "artifact" | "session";
  status: "success" | "cancelled" | "stale" | "error";
  saved: boolean;
  from_cache: boolean;
  source_revision: string | null;
  artifact_key: string | null;
  workspace_route: string | null;
  session_result: unknown;
  usage: AgentUsage;
  error_code: string | null;
  safe_message: string | null;
  retrieval_evidence: AgentRetrievalEvidence | null;
}

export interface AgentUsage {
  steps: number;
  elapsed_ms: number;
  input_tokens: number;
  output_tokens: number;
  model_calls: number;
  embedding_calls: number;
  tool_calls: number;
  estimated_cost_units: number;
}

export interface AgentBudgetView {
  preset: AgentBudgetPreset;
  limits: Record<string, number>;
  usage: AgentUsage;
  remaining: Record<string, number>;
  cost_unit: "synthetic_test_unit";
}

export interface AgentRunView {
  run_id: string;
  thread_id: string;
  goal: string;
  status: AgentRunStatus;
  source_revision: string;
  created_at: string;
  deadline_at: string;
  expires_at: string;
  model_label: ModelLabel;
  budget: AgentBudgetView;
  plan_version: number;
  current_step_index: number;
  plan: AgentPlanStep[];
  approval: AgentApproval | null;
  evidence: AgentEvidence[];
  last_error: { code: string; safe_message: string; retryable: boolean } | null;
  last_event_sequence: number;
  worker_available: boolean;
  active: boolean;
  can_approve: boolean;
  can_edit: boolean;
  can_cancel: boolean;
  can_recover: boolean;
  trace_id: string | null;
  trace_status: "not_instrumented" | "instrumented";
}

export interface AgentTimelineEvent {
  schema_version: number;
  sequence: number;
  kind: string;
  occurred_at?: string;
  status?: AgentRunStatus;
  step_id?: string | null;
  operation?: string | null;
  stage?: string | null;
  label?: string | null;
  percent?: number | null;
  saved?: boolean | null;
  from_cache?: boolean | null;
  artifact_key?: string | null;
  error_code?: string | null;
  safe_message?: string | null;
  reason?: string;
}

interface AgentEnvelope<T> {
  status: string;
  reason: string;
  data: T;
}

/**
 * 处理normalized，并保持现有输入输出约定。
 */
const normalized = (baseUrl: string): string => baseUrl.replace(/\/$/, "");

// 所有 Agent 请求都验证统一响应信封，避免把错误响应当作可持久化运行数据。
/**
 * 处理请求，并保持现有输入输出约定。
 *
 * @param baseUrl 沿用当前 TypeScript 类型约束的输入。
 * @param path 沿用当前 TypeScript 类型约束的输入。
 * @param config 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
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

/**
 * 执行路径，并保持现有状态与错误处理语义。
 */
const runPath = (pid: string, threadId = ""): string =>
  `/agent/v1/projects/${encodeURIComponent(pid)}/runs${
    threadId ? `/${encodeURIComponent(threadId)}` : ""
  }`;

/**
 * 加载Agent能力清单，并保持现有状态与错误处理语义。
 */
export const loadAgentCapabilities = (baseUrl: string) =>
  request<AgentCapabilities>(baseUrl, "/agent/v1/capabilities");

/**
 * 处理list Agent运行，并保持现有输入输出约定。
 */
export const listAgentRuns = (baseUrl: string, pid: string) =>
  request<{
    runs: AgentRunSummary[];
    active_thread_id: string | null;
    next_cursor: number | null;
  }>(baseUrl, runPath(pid));

/**
 * 获取Agent运行，并保持现有状态与错误处理语义。
 */
export const getAgentRun = (baseUrl: string, pid: string, threadId: string) =>
  request<AgentRunView>(baseUrl, runPath(pid, threadId));

/**
 * 创建Agent运行，并保持现有状态与错误处理语义。
 */
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

/**
 * 处理decide Agent审批，并保持现有输入输出约定。
 */
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

/**
 * 处理编辑内容 Agent goal，并保持现有输入输出约定。
 */
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

/**
 * 取消Agent运行，并保持现有状态与错误处理语义。
 */
export const cancelAgentRun = (baseUrl: string, pid: string, threadId: string) =>
  request<AgentRunView>(baseUrl, `${runPath(pid, threadId)}/cancel`, {
    method: "POST",
  });

/**
 * 恢复Agent运行，并保持现有状态与错误处理语义。
 */
export const recoverAgentRun = (baseUrl: string, pid: string, threadId: string) =>
  request<{ command_id: string }>(baseUrl, `${runPath(pid, threadId)}/recover`, {
    method: "POST",
  });
