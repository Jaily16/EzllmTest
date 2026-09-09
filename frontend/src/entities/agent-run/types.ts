// Agent 运行、审批和证据的共享 DTO；项目授权与执行权限仍由后端判断。
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
