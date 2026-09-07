<template>
  <div class="agent-workbench">
    <header class="agent-hero">
      <div>
        <span class="eyebrow">Iteration 4 · 单 Agent 编排</span>
        <h2>测试编排 Agent 工作台</h2>
        <p>
          先生成结构化计划，再逐步审批受控工具。工作台不会展示或保存思维链，也不会在页面加载时调用模型。
        </p>
      </div>
      <div class="hero-status" aria-live="polite" aria-atomic="true">
        <span :data-state="currentRun?.status || 'idle'">
          {{ currentRun ? statusLabel(currentRun.status) : "尚未选择运行" }}
        </span>
      </div>
    </header>

    <FeedbackState
      v-if="loading"
      kind="loading"
      title="正在读取 Agent 能力与最近运行"
      description="仅执行只读请求，不会创建运行或产生模型调用。"
      skeleton="cards"
    />
    <FeedbackState
      v-else-if="pageError"
      kind="error"
      title="Agent 工作台暂不可用"
      :description="pageError"
    >
      <template #actions>
        <el-button type="primary" @click="initialize">重新读取</el-button>
      </template>
    </FeedbackState>

    <template v-else>
      <el-alert
        v-if="threadExpired"
        type="warning"
        :closable="false"
        title="Redis thread 已失效，无法恢复；MySQL 中的有效 artifact 不受影响。"
      />
      <section class="workbench-card create-card" aria-labelledby="agent-create-title">
        <div class="section-heading">
          <div>
            <span class="eyebrow">显式启动</span>
            <h3 id="agent-create-title">创建测试编排运行</h3>
          </div>
          <el-tag v-if="activeThreadId" type="warning">当前项目已有活跃运行</el-tag>
        </div>
        <form class="create-form" @submit.prevent="createRun">
          <label class="field field--goal">
            <span>测试目标</span>
            <el-input
              v-model="goal"
              type="textarea"
              :rows="3"
              maxlength="4000"
              show-word-limit
              placeholder="例如：为结算模块规划并生成关键 UI 测试用例"
              :disabled="creating || Boolean(activeThreadId)"
            />
          </label>
          <ModelSelector
            v-model="modelLabel"
            :options="modelOptions"
            label="规划与执行模型"
            description="同一模型用于单 Agent 的规划与工作流执行。"
            :disabled="creating || Boolean(activeThreadId)"
          />
          <fieldset class="field budget-choice" :disabled="creating || Boolean(activeThreadId)">
            <legend>受控预算预设</legend>
            <label>
              <input v-model="budgetPreset" type="radio" value="focused" />
              <span><strong>聚焦</strong> · 最多 3 步 / 20 分钟</span>
            </label>
            <label>
              <input v-model="budgetPreset" type="radio" value="standard" />
              <span><strong>标准</strong> · 最多 8 步 / 45 分钟</span>
            </label>
          </fieldset>
          <div class="create-actions">
            <el-button
              native-type="submit"
              type="primary"
              size="large"
              :loading="creating"
              :disabled="!goal.trim() || Boolean(activeThreadId)"
            >
              创建运行
            </el-button>
            <p>只有点击此按钮才会创建运行；页面加载始终为只读。</p>
          </div>
        </form>
      </section>

      <div class="workbench-grid">
        <div class="primary-column">
          <FeedbackState
            v-if="!currentRun"
            kind="empty"
            title="暂无运行快照"
            description="创建新运行，或从右侧最近运行中选择一项。"
          />

          <template v-else>
            <section class="workbench-card" aria-labelledby="agent-plan-title">
              <div class="section-heading">
                <div>
                  <span class="eyebrow">Plan v{{ currentRun.plan_version }}</span>
                  <h3 id="agent-plan-title">结构化执行计划</h3>
                </div>
                <el-tag :type="currentRun.active ? 'primary' : 'info'">
                  {{ currentRun.active ? "活跃" : "已释放运行槽" }}
                </el-tag>
              </div>
              <p class="goal-copy">{{ currentRun.goal }}</p>
              <ol v-if="currentRun.plan.length" class="plan-list">
                <li
                  v-for="step in currentRun.plan"
                  :key="step.step_id"
                  :class="{ 'is-current': step.current }"
                >
                  <div class="plan-title">
                    <strong>{{ step.operation }}</strong>
                    <span>{{
                      step.retention === "artifact" ? "项目 artifact" : "线程临时结果"
                    }}</span>
                  </div>
                  <div class="risk-row">
                    <el-tag v-for="risk in step.risks" :key="risk" size="small" type="warning">
                      {{ riskLabel(risk) }}
                    </el-tag>
                    <el-tag size="small" type="info">{{ step.model_label }}</el-tag>
                  </div>
                  <pre>{{ formatJson(step.arguments) }}</pre>
                  <div v-if="step.context_bindings.length" class="context-bindings">
                    <strong>可信上下文引用</strong>
                    <ul>
                      <li
                        v-for="binding in step.context_bindings"
                        :key="`${step.step_id}:${binding.payload_field}`"
                      >
                        <span>{{ binding.payload_field }} ← {{ binding.source_operation }}</span>
                        <code>{{ binding.artifact_key }} · {{ binding.content_sha256 }}</code>
                      </li>
                    </ul>
                  </div>
                </li>
              </ol>
              <FeedbackState
                v-else
                kind="empty"
                compact
                title="计划尚未生成"
                description="worker 接收排队命令后会生成受 catalog 约束的计划。"
              />
            </section>

            <section
              v-if="currentRun.approval"
              class="workbench-card approval-card"
              aria-labelledby="agent-approval-title"
            >
              <div class="section-heading">
                <div>
                  <span class="eyebrow">Human-in-the-loop</span>
                  <h3 id="agent-approval-title">风险审批</h3>
                </div>
                <el-tag :type="currentRun.approval.expired ? 'danger' : 'warning'">
                  {{ currentRun.approval.expired ? "审批已过期" : "等待人工决定" }}
                </el-tag>
              </div>
              <p>
                即将执行 <strong>{{ currentRun.approval.operation }}</strong
                >。paid 会产生模型用量，persistent 会写入有效 artifact，regenerate 会替换受 revision
                与 regeneration lock 保护的结果。
              </p>
              <dl class="approval-facts">
                <div>
                  <dt>Revision</dt>
                  <dd>{{ currentRun.source_revision }}</dd>
                </div>
                <div>
                  <dt>失效时间</dt>
                  <dd>{{ formatTime(currentRun.approval.expires_at) }}</dd>
                </div>
                <div>
                  <dt>预算</dt>
                  <dd>{{ currentRun.budget.preset }}</dd>
                </div>
              </dl>
              <div class="approval-actions">
                <button
                  ref="approvalTriggerRef"
                  class="primary-action"
                  type="button"
                  :disabled="currentRun.approval.expired"
                  @click="openApprovalDialog"
                >
                  审查并决定
                </button>
                <button type="button" class="secondary-action" @click="openEditDialog">
                  编辑目标并重新规划
                </button>
                <button type="button" class="danger-action" @click="cancelCurrentRun">
                  取消运行
                </button>
              </div>
            </section>

            <section class="workbench-card" aria-labelledby="agent-timeline-title">
              <div class="section-heading">
                <div>
                  <span class="eyebrow">可恢复事件流</span>
                  <h3 id="agent-timeline-title">运行时间线</h3>
                </div>
                <el-tag :type="eventsConnected ? 'success' : 'info'">
                  {{ eventsConnected ? "事件流已连接" : "事件流未连接" }}
                </el-tag>
              </div>
              <p class="sr-only" aria-live="polite" aria-atomic="true">
                {{ liveAnnouncement }}
              </p>
              <ol class="timeline-list">
                <li v-for="event in timeline" :key="event.sequence">
                  <span class="timeline-sequence">#{{ event.sequence }}</span>
                  <div>
                    <strong>{{ eventLabel(event.kind) }}</strong>
                    <p v-if="event.label || event.safe_message">
                      {{ event.safe_message || event.label }}
                    </p>
                    <el-progress
                      v-if="typeof event.percent === 'number'"
                      :percentage="Math.round(event.percent)"
                      :stroke-width="6"
                    />
                  </div>
                </li>
              </ol>
              <FeedbackState
                v-if="!timeline.length"
                kind="empty"
                compact
                title="暂无可显示事件"
                description="安全进度事件出现后会在这里按序展示。"
              />
            </section>

            <section class="workbench-card" aria-labelledby="agent-evidence-title">
              <div class="section-heading">
                <div>
                  <span class="eyebrow">验证证据</span>
                  <h3 id="agent-evidence-title">Step evidence</h3>
                </div>
              </div>
              <div v-if="currentRun.evidence.length" class="evidence-list">
                <ResultContainer
                  v-for="evidence in currentRun.evidence"
                  :key="evidence.step_id"
                  :title="evidence.operation"
                  :description="evidenceDescription(evidence)"
                  :retention="evidence.retention === 'session' ? 'session-only' : 'persistent'"
                  :retention-text="
                    evidence.retention === 'session' ? 'Agent thread · 7 天' : '已保存'
                  "
                >
                  <dl class="evidence-facts">
                    <div>
                      <dt>状态</dt>
                      <dd>{{ evidence.status }}</dd>
                    </div>
                    <div>
                      <dt>缓存</dt>
                      <dd>{{ evidence.from_cache ? "命中" : "未命中" }}</dd>
                    </div>
                    <div>
                      <dt>保存</dt>
                      <dd>{{ evidence.saved ? "已保存" : "未保存" }}</dd>
                    </div>
                    <div>
                      <dt>Revision</dt>
                      <dd>{{ evidence.source_revision || "—" }}</dd>
                    </div>
                  </dl>
                  <pre v-if="evidence.retention === 'session'">{{
                    formatJson(evidence.session_result)
                  }}</pre>
                  <section
                    v-if="evidence.retrieval_evidence"
                    class="retrieval-evidence"
                    :aria-label="`${evidence.operation} 检索引用`"
                  >
                    <h4>检索引用</h4>
                    <p>
                      {{ evidence.retrieval_evidence.strategy }} ·
                      {{ evidence.retrieval_evidence.context_tokens }} context tokens
                    </p>
                    <ol>
                      <template
                        v-for="query in evidence.retrieval_evidence.queries"
                        :key="query.query_hash"
                      >
                        <li
                          v-for="citation in query.citations"
                          :key="`${query.query_hash}:${citation.citation_id}`"
                        >
                          <strong>[{{ citation.citation_id }}] {{ citation.source_label }}</strong>
                          <span
                            >第 {{ citation.page }} 页 · rank {{ citation.rank }} ·
                            {{ citation.score_kind }}</span
                          >
                          <code>{{ citation.chunk_hash }}</code>
                        </li>
                      </template>
                    </ol>
                  </section>
                  <el-button
                    v-else-if="evidence.workspace_route"
                    type="primary"
                    plain
                    @click="goToEvidence(evidence.workspace_route)"
                  >
                    打开现有测试工作区
                  </el-button>
                </ResultContainer>
              </div>
              <FeedbackState
                v-else
                kind="empty"
                compact
                title="暂无步骤证据"
                description="工具完成并经过幂等记录后才会生成 evidence。"
              />
            </section>
          </template>
        </div>

        <aside class="secondary-column" aria-label="运行历史与诊断">
          <section class="workbench-card" aria-labelledby="agent-history-title">
            <div class="section-heading">
              <div>
                <span class="eyebrow">Redis · 7 天</span>
                <h3 id="agent-history-title">最近运行</h3>
              </div>
            </div>
            <ul v-if="runs.length" class="history-list">
              <li v-for="run in runs" :key="run.thread_id">
                <button
                  type="button"
                  :aria-current="run.thread_id === currentRun?.thread_id ? 'true' : undefined"
                  @click="selectRun(run.thread_id)"
                >
                  <strong>{{ run.goal }}</strong>
                  <span>{{ statusLabel(run.status) }} · {{ formatTime(run.created_at) }}</span>
                </button>
              </li>
            </ul>
            <p v-else class="muted">当前项目暂无保留中的 Agent 运行。</p>
          </section>

          <section v-if="currentRun" class="workbench-card" aria-labelledby="agent-budget-title">
            <div class="section-heading">
              <div>
                <span class="eyebrow">硬限制</span>
                <h3 id="agent-budget-title">预算与用量</h3>
              </div>
            </div>
            <dl class="budget-list">
              <div>
                <dt>步骤</dt>
                <dd>
                  {{ currentRun.budget.usage.steps }} / {{ currentRun.budget.limits.max_steps }}
                </dd>
              </div>
              <div>
                <dt>模型调用</dt>
                <dd>
                  {{ currentRun.budget.usage.model_calls }} /
                  {{ currentRun.budget.limits.max_model_calls }}
                </dd>
              </div>
              <div>
                <dt>Embedding</dt>
                <dd>
                  {{ currentRun.budget.usage.embedding_calls }} /
                  {{ currentRun.budget.limits.max_embedding_calls }}
                </dd>
              </div>
              <div>
                <dt>工具调用</dt>
                <dd>
                  {{ currentRun.budget.usage.tool_calls }} /
                  {{ currentRun.budget.limits.max_tool_calls }}
                </dd>
              </div>
              <div>
                <dt>输入 Token</dt>
                <dd>
                  {{ currentRun.budget.usage.input_tokens }} /
                  {{ currentRun.budget.limits.max_input_tokens }}
                </dd>
              </div>
              <div>
                <dt>输出 Token</dt>
                <dd>
                  {{ currentRun.budget.usage.output_tokens }} /
                  {{ currentRun.budget.limits.max_output_tokens }}
                </dd>
              </div>
              <div>
                <dt>合成成本单位</dt>
                <dd>{{ currentRun.budget.usage.estimated_cost_units }}</dd>
              </div>
              <div>
                <dt>Deadline</dt>
                <dd>{{ formatTime(currentRun.deadline_at) }}</dd>
              </div>
            </dl>
            <p class="muted">成本为测试估算单位，不代表人民币或供应商货币价格。</p>
          </section>

          <section
            v-if="currentRun"
            class="workbench-card"
            aria-labelledby="agent-diagnostics-title"
          >
            <div class="section-heading">
              <div>
                <span class="eyebrow">运行诊断</span>
                <h3 id="agent-diagnostics-title">恢复与观测状态</h3>
              </div>
            </div>
            <dl class="diagnostics-list">
              <div>
                <dt>Run ID</dt>
                <dd>{{ currentRun.run_id }}</dd>
              </div>
              <div>
                <dt>Thread ID</dt>
                <dd>{{ currentRun.thread_id }}</dd>
              </div>
              <div>
                <dt>Worker</dt>
                <dd>{{ currentRun.worker_available ? "可用" : "暂不可用 / 运行可能排队" }}</dd>
              </div>
              <div>
                <dt>Redis 到期</dt>
                <dd>{{ formatTime(currentRun.expires_at) }}</dd>
              </div>
              <div>
                <dt>Trace ID</dt>
                <dd v-if="currentRun.trace_id" class="trace-value">
                  <code>{{ currentRun.trace_id }}</code>
                  <button type="button" class="trace-action" @click="copyTraceId">复制</button>
                  <button type="button" class="trace-action" @click="openTrace">
                    在本地观测中查看
                  </button>
                </dd>
                <dd v-else>未启用</dd>
              </div>
            </dl>
            <el-alert
              v-if="threadExpired"
              type="warning"
              :closable="false"
              title="Redis thread 已失效，无法恢复；MySQL 中的有效 artifact 不受影响。"
            />
            <el-alert
              v-if="currentRun.last_error"
              type="error"
              :closable="false"
              :title="currentRun.last_error.safe_message"
            />
            <div class="control-actions">
              <el-button v-if="currentRun.can_cancel" type="danger" plain @click="cancelCurrentRun"
                >取消运行</el-button
              >
              <el-button v-if="currentRun.can_recover" type="primary" @click="recoverCurrentRun"
                >恢复运行</el-button
              >
            </div>
          </section>
        </aside>
      </div>
    </template>

    <el-dialog
      v-model="approvalDialogOpen"
      title="确认当前受控步骤"
      width="min(92vw, 560px)"
      @opened="focusDialogPrimary"
      @closed="restoreApprovalFocus"
    >
      <p>
        批准只绑定当前 plan hash、项目、revision、参数、模型与预算。任一变化都会使本次批准失效。
      </p>
      <div class="dialog-actions">
        <button
          ref="dialogPrimaryRef"
          class="primary-action"
          type="button"
          @click="submitApproval('approved')"
        >
          批准当前步骤
        </button>
        <button class="danger-action" type="button" @click="submitApproval('rejected')">
          拒绝并终止
        </button>
        <button class="secondary-action" type="button" @click="approvalDialogOpen = false">
          返回检查
        </button>
      </div>
    </el-dialog>

    <el-dialog v-model="editDialogOpen" title="编辑目标并重新规划" width="min(92vw, 560px)">
      <label class="field">
        <span>新目标</span>
        <el-input v-model="editedGoal" type="textarea" :rows="4" maxlength="4000" show-word-limit />
      </label>
      <div class="dialog-actions">
        <button
          class="primary-action"
          type="button"
          :disabled="!editedGoal.trim()"
          @click="submitEdit"
        >
          提交重新规划
        </button>
        <button class="secondary-action" type="button" @click="editDialogOpen = false">取消</button>
      </div>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { computed, getCurrentInstance, nextTick, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "@/shared/plugins/elementPlus";
import FeedbackState from "@/shared/components/FeedbackState.vue";
import ModelSelector from "@/shared/components/ModelSelector.vue";
import ResultContainer from "@/shared/components/ResultContainer.vue";
import { DEFAULT_MODEL, MODEL_OPTIONS, ModelLabel } from "@/shared/config/models";
import { useAgentEvents } from "@/features/agent/composables/useAgentEvents";
import {
  AgentBudgetPreset,
  AgentCapabilities,
  AgentEvidence,
  AgentRunStatus,
  AgentRunSummary,
  AgentRunView,
  AgentTimelineEvent,
  cancelAgentRun,
  createAgentRun,
  decideAgentApproval,
  editAgentGoal,
  getAgentRun,
  listAgentRuns,
  loadAgentCapabilities,
  recoverAgentRun,
} from "@/features/agent/state/agentWorkbench";

const instance = getCurrentInstance();
const router = useRouter();
const pid = String(instance?.appContext.config.globalProperties.$id || "");
const agentApiUrl = String(
  instance?.appContext.config.globalProperties.$agentApiUrl || "http://127.0.0.1:8231",
);
const storageKey = `ezllm-agent-selected-thread:${pid}`;

const loading = ref(true);
const creating = ref(false);
const pageError = ref("");
const threadExpired = ref(false);
const capabilities = ref<AgentCapabilities | null>(null);
const runs = ref<AgentRunSummary[]>([]);
const activeThreadId = ref<string | null>(null);
const currentRun = ref<AgentRunView | null>(null);
const timeline = ref<AgentTimelineEvent[]>([]);
const liveAnnouncement = ref("");
const goal = ref("");
const modelLabel = ref<ModelLabel>(DEFAULT_MODEL);
const budgetPreset = ref<AgentBudgetPreset>("focused");
const approvalDialogOpen = ref(false);
const editDialogOpen = ref(false);
const editedGoal = ref("");
const approvalTriggerRef = ref<HTMLButtonElement | null>(null);
const dialogPrimaryRef = ref<HTMLButtonElement | null>(null);
const eventStream = useAgentEvents();
const eventsConnected = eventStream.connected;

/**
 * 复制Trace ID，并保持现有状态与错误处理语义。
 */
const copyTraceId = async () => {
  const traceId = currentRun.value?.trace_id;
  if (!traceId) return;
  try {
    await navigator.clipboard.writeText(traceId);
    ElMessage({ message: "Trace ID 已复制", type: "success" });
  } catch {
    ElMessage({ message: "无法访问剪贴板，请手动复制 Trace ID", type: "warning" });
  }
};

/**
 * 打开Trace，并保持现有状态与错误处理语义。
 */
const openTrace = () => {
  const traceId = currentRun.value?.trace_id;
  if (!traceId) return;
  void router.push({
    path: "/observability",
    query: { window: "1h", trace: traceId },
  });
};

/**
 * 派生用于界面展示或请求判断的模型选项。
 */
const modelOptions = computed(() => {
  const allowed = new Set(capabilities.value?.models || []);
  const filtered = MODEL_OPTIONS.filter((option) => allowed.has(option.value));
  return filtered.length ? filtered : MODEL_OPTIONS;
});

/**
 * 处理状态标签，并保持现有输入输出约定。
 */
const statusLabel = (status: AgentRunStatus): string =>
  ({
    created: "已排队",
    planning: "规划中",
    awaiting_approval: "等待审批",
    executing: "执行中",
    validating: "验证中",
    completed: "已完成",
    cancelled: "已取消",
    failed: "失败",
    recovering: "恢复中",
  })[status];

/**
 * 处理事件标签，并保持现有输入输出约定。
 *
 * @param kind 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
const eventLabel = (kind: string): string =>
  ({
    queued: "已进入执行队列",
    planning: "正在生成结构化计划",
    approval_required: "需要人工审批",
    approval_submitted: "审批决定已提交",
    replanning: "目标已编辑，重新规划",
    cancel_requested: "取消请求已提交",
    executing: "正在执行受控工具",
    progress: "安全进度",
    tool_succeeded: "工具执行成功",
    tool_failed: "工具执行失败",
    stale: "Revision 已变化",
    recovering: "正在恢复并对账",
    completed: "运行完成",
    cancelled: "运行已取消",
    failed: "运行失败",
  })[kind] || kind;

/**
 * 处理风险标签，并保持现有输入输出约定。
 */
const riskLabel = (risk: string): string =>
  ({
    read_only: "只读",
    paid: "付费用量",
    persistent: "持久化",
    regenerate: "重新生成",
  })[risk] || risk;

/**
 * 格式化时间，并保持现有状态与错误处理语义。
 */
const formatTime = (value: string): string => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN");
};

/**
 * 格式化JSON，并保持现有状态与错误处理语义。
 */
const formatJson = (value: unknown): string => JSON.stringify(value, null, 2);

/**
 * 处理证据描述，并保持现有输入输出约定。
 */
const evidenceDescription = (evidence: AgentEvidence): string =>
  evidence.retention === "session"
    ? "仅 Agent thread 保留 7 天，不写入项目 artifact。"
    : `仅保留 artifact 摘要；有效结果继续由项目存储管理。${
        evidence.artifact_key ? ` Artifact: ${evidence.artifact_key}` : ""
      }`;

/**
 * 刷新历史记录，并保持现有状态与错误处理语义。
 */
const refreshHistory = async () => {
  const history = await listAgentRuns(agentApiUrl, pid);
  runs.value = history.runs;
  activeThreadId.value = history.active_thread_id;
};

/**
 * 刷新当前运行，并保持现有状态与错误处理语义。
 */
const refreshCurrentRun = async (announce = false) => {
  if (!currentRun.value) return;
  try {
    currentRun.value = await getAgentRun(agentApiUrl, pid, currentRun.value.thread_id);
    threadExpired.value = false;
    if (announce) liveAnnouncement.value = statusLabel(currentRun.value.status);
    await refreshHistory();
  } catch (caught) {
    threadExpired.value = true;
    eventStream.stop();
    liveAnnouncement.value = caught instanceof Error ? caught.message : "Agent thread 已失效";
  }
};

/**
 * 订阅内部状态，并保持现有状态与错误处理语义。
 */
const subscribe = () => {
  if (!currentRun.value) return;
  const afterSequence = timeline.value.reduce(
    (highest, event) => Math.max(highest, event.sequence || 0),
    0,
  );
  eventStream.start({
    baseUrl: agentApiUrl,
    pid,
    threadId: currentRun.value.thread_id,
    afterSequence,
    /**
     * 响应事件，并保持现有状态与错误处理语义。
     */
    onEvent: (event) => {
      if (!timeline.value.some((item) => item.sequence === event.sequence)) {
        timeline.value.push(event);
        timeline.value.sort((left, right) => left.sequence - right.sequence);
      }
      liveAnnouncement.value = eventLabel(event.kind);
      void refreshCurrentRun();
    },
    /**
     * 响应replay reset，并保持现有状态与错误处理语义。
     */
    onReplayReset: () => {
      timeline.value = [];
      liveAnnouncement.value = "事件保留窗口已变化，已重新读取运行快照";
      void refreshCurrentRun(true);
    },
    /**
     * 响应错误，并保持现有状态与错误处理语义。
     */
    onError: (message) => {
      liveAnnouncement.value = message;
    },
  });
};

/**
 * 选择指定 Agent 运行并恢复其当前状态与事件游标。
 *
 * @param threadId Agent 运行线程 ID。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
 */
const selectRun = async (threadId: string) => {
  eventStream.stop();
  timeline.value = [];
  pageError.value = "";
  try {
    currentRun.value = await getAgentRun(agentApiUrl, pid, threadId);
    window.localStorage.setItem(storageKey, threadId);
    threadExpired.value = false;
    subscribe();
  } catch (caught) {
    threadExpired.value = true;
    currentRun.value = null;
    liveAnnouncement.value = caught instanceof Error ? caught.message : "运行读取失败";
  }
};

// 首屏只读取能力与已有运行，不创建运行或触发付费模型调用。
/**
 * 加载当前页面所需的能力与已有状态，不创建运行或触发模型调用。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
 */
const initialize = async () => {
  loading.value = true;
  pageError.value = "";
  if (!pid) {
    pageError.value = "请先通过项目 ID 登录后再进入 Agent 工作台";
    loading.value = false;
    return;
  }
  try {
    const [nextCapabilities] = await Promise.all([
      loadAgentCapabilities(agentApiUrl),
      refreshHistory(),
    ]);
    capabilities.value = nextCapabilities;
    const remembered = window.localStorage.getItem(storageKey);
    const selected =
      activeThreadId.value ||
      (remembered && runs.value.some((run) => run.thread_id === remembered)
        ? remembered
        : runs.value[0]?.thread_id);
    if (selected) await selectRun(selected);
  } catch (caught) {
    pageError.value = caught instanceof Error ? caught.message : "Agent 工作台加载失败";
  } finally {
    loading.value = false;
  }
};

/**
 * 创建运行，并保持现有状态与错误处理语义。
 */
const createRun = async () => {
  if (!goal.value.trim() || creating.value || activeThreadId.value) return;
  creating.value = true;
  try {
    const handle = await createAgentRun(agentApiUrl, pid, {
      goal: goal.value.trim(),
      model_label: modelLabel.value,
      budget_preset: budgetPreset.value,
    });
    goal.value = "";
    await refreshHistory();
    await selectRun(handle.thread_id);
    ElMessage({ message: "Agent 运行已排队", type: "success" });
  } catch (caught) {
    ElMessage({
      message: caught instanceof Error ? caught.message : "创建运行失败",
      type: "error",
    });
  } finally {
    creating.value = false;
  }
};

/**
 * 打开审批对话框，并保持现有状态与错误处理语义。
 */
const openApprovalDialog = () => {
  approvalDialogOpen.value = true;
};

/**
 * 聚焦对话框主操作，并保持现有状态与错误处理语义。
 */
const focusDialogPrimary = async () => {
  await nextTick();
  dialogPrimaryRef.value?.focus();
};

/**
 * 恢复审批焦点，并保持现有状态与错误处理语义。
 */
const restoreApprovalFocus = () => {
  approvalTriggerRef.value?.focus();
};

// 审批请求携带当前 plan hash，后端据此拒绝过期或跨 revision 的决策。
/**
 * 提交与当前 plan hash 绑定的审批决定。
 *
 * @param decision 沿用当前 TypeScript 类型约束的输入。
 */
const submitApproval = async (decision: "approved" | "rejected") => {
  if (!currentRun.value?.approval) return;
  try {
    await decideAgentApproval(
      agentApiUrl,
      pid,
      currentRun.value.thread_id,
      decision,
      currentRun.value.approval.plan_hash,
    );
    approvalDialogOpen.value = false;
    await refreshCurrentRun(true);
    subscribe();
  } catch (caught) {
    ElMessage({
      message: caught instanceof Error ? caught.message : "审批提交失败",
      type: "error",
    });
  }
};

/**
 * 打开编辑内容对话框，并保持现有状态与错误处理语义。
 */
const openEditDialog = () => {
  editedGoal.value = currentRun.value?.goal || "";
  editDialogOpen.value = true;
};

/**
 * 提交编辑内容，并保持现有状态与错误处理语义。
 */
const submitEdit = async () => {
  if (!currentRun.value?.approval || !editedGoal.value.trim()) return;
  try {
    await editAgentGoal(
      agentApiUrl,
      pid,
      currentRun.value.thread_id,
      editedGoal.value.trim(),
      currentRun.value.approval.plan_hash,
    );
    editDialogOpen.value = false;
    await refreshCurrentRun(true);
    subscribe();
  } catch (caught) {
    ElMessage({
      message: caught instanceof Error ? caught.message : "重新规划提交失败",
      type: "error",
    });
  }
};

// 取消后仍刷新历史和事件游标，避免延迟保存结果覆盖用户看到的终态。
/**
 * 取消当前运行，并保持现有状态与错误处理语义。
 */
const cancelCurrentRun = async () => {
  if (!currentRun.value) return;
  try {
    currentRun.value = await cancelAgentRun(agentApiUrl, pid, currentRun.value.thread_id);
    await refreshHistory();
    subscribe();
  } catch (caught) {
    ElMessage({ message: caught instanceof Error ? caught.message : "取消失败", type: "error" });
  }
};

// 恢复沿用服务端 checkpoint/租约边界，页面只重新读取状态，不自行重放工具。
/**
 * 恢复当前运行，并保持现有状态与错误处理语义。
 */
const recoverCurrentRun = async () => {
  if (!currentRun.value) return;
  try {
    await recoverAgentRun(agentApiUrl, pid, currentRun.value.thread_id);
    await refreshCurrentRun(true);
    subscribe();
  } catch (caught) {
    ElMessage({ message: caught instanceof Error ? caught.message : "恢复失败", type: "error" });
  }
};

/**
 * 跳转到证据，并保持现有状态与错误处理语义。
 */
const goToEvidence = (path: string) => {
  void router.push(path);
};

/**
 * 组件挂载后执行既有初始化或恢复流程。
 */
onMounted(() => {
  void initialize();
});
</script>

<style scoped>
.agent-workbench {
  display: grid;
  gap: var(--ez-space-6);
  min-width: 0;
}

.agent-hero,
.section-heading,
.plan-title,
.approval-actions,
.dialog-actions,
.control-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ez-space-3);
}

.agent-hero {
  padding: var(--ez-space-6);
  background: linear-gradient(135deg, var(--ez-color-brand-50), var(--ez-color-surface));
  border: 1px solid var(--ez-color-brand-100);
  border-radius: var(--ez-radius-large);
}

.agent-hero h2,
.section-heading h3 {
  margin: var(--ez-space-1) 0 0;
  overflow-wrap: anywhere;
}

.agent-hero h2 {
  font-size: var(--ez-font-size-24);
}
.section-heading h3 {
  font-size: var(--ez-font-size-16);
}
.agent-hero p,
.approval-card > p,
.goal-copy,
.muted {
  color: var(--ez-color-text-secondary);
  line-height: var(--ez-line-height-body);
  overflow-wrap: anywhere;
}
.agent-hero p {
  max-width: var(--ez-reading-measure);
  margin: var(--ez-space-2) 0 0;
}

.eyebrow {
  color: var(--ez-color-brand-700);
  font-size: var(--ez-font-size-12);
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.hero-status span {
  display: block;
  padding: var(--ez-space-2) var(--ez-space-3);
  white-space: nowrap;
  background: var(--ez-color-surface);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-pill);
}

.workbench-card {
  min-width: 0;
  padding: var(--ez-space-6);
  background: var(--ez-color-surface);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-large);
  box-shadow: var(--ez-shadow-small);
}
.create-form {
  display: grid;
  gap: var(--ez-space-4);
  margin-top: var(--ez-space-4);
}
.field {
  display: grid;
  gap: var(--ez-space-2);
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}
.field > span,
.field legend {
  padding: 0;
  color: var(--ez-color-text-primary);
  font-size: var(--ez-font-size-14);
  font-weight: 700;
}
.budget-choice {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ez-space-3);
}
.budget-choice legend {
  width: 100%;
}
.budget-choice label {
  display: flex;
  align-items: center;
  min-height: var(--ez-touch-target);
  gap: var(--ez-space-2);
  padding: var(--ez-space-2) var(--ez-space-3);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
  cursor: pointer;
}
.budget-choice input {
  width: 18px;
  height: 18px;
}
.create-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ez-space-3);
}
.create-actions .el-button {
  min-height: var(--ez-touch-target);
}
.create-actions p {
  margin: 0;
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-13);
}

.workbench-grid {
  display: grid;
  gap: var(--ez-space-6);
  min-width: 0;
}
.primary-column,
.secondary-column {
  display: grid;
  align-content: start;
  gap: var(--ez-space-6);
  min-width: 0;
}
.plan-list,
.timeline-list,
.history-list {
  display: grid;
  gap: var(--ez-space-3);
  margin: var(--ez-space-4) 0 0;
  padding: 0;
  list-style: none;
}
.plan-list li {
  min-width: 0;
  padding: var(--ez-space-4);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
}
.plan-list li.is-current {
  border-color: var(--ez-color-brand-500);
  box-shadow: inset 3px 0 0 var(--ez-color-brand-500);
}
.plan-title span {
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
}
.risk-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ez-space-2);
  margin-top: var(--ez-space-3);
}
pre {
  max-width: 100%;
  margin: var(--ez-space-3) 0 0;
  padding: var(--ez-space-3);
  overflow: auto;
  color: var(--ez-color-text-primary);
  font: var(--ez-font-size-12)/1.6 var(--ez-font-code);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: var(--ez-color-surface-subtle);
  border-radius: var(--ez-radius-small);
}

.approval-card {
  border-color: var(--ez-color-warning);
  background: var(--ez-color-warning-bg);
}
.approval-facts,
.evidence-facts,
.budget-list,
.diagnostics-list {
  display: grid;
  gap: var(--ez-space-2);
  margin: var(--ez-space-4) 0;
}
.approval-facts div,
.evidence-facts div,
.budget-list div,
.diagnostics-list div {
  display: grid;
  grid-template-columns: minmax(90px, 0.7fr) minmax(0, 1.3fr);
  gap: var(--ez-space-3);
  padding-block: var(--ez-space-2);
  border-bottom: 1px solid var(--ez-color-border);
}
dt {
  color: var(--ez-color-text-muted);
}
dd {
  min-width: 0;
  margin: 0;
  text-align: right;
  overflow-wrap: anywhere;
}
.trace-value {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--ez-space-2);
  align-items: center;
}
.trace-value code {
  overflow-wrap: anywhere;
}
.trace-action {
  min-height: var(--ez-touch-target);
  padding: var(--ez-space-2);
  color: var(--ez-color-brand-700);
  font: inherit;
  background: transparent;
  border: 1px solid var(--ez-color-border-strong);
  border-radius: var(--ez-radius-small);
  cursor: pointer;
}
.primary-action,
.secondary-action,
.danger-action {
  min-height: var(--ez-touch-target);
  padding: var(--ez-space-2) var(--ez-space-4);
  font: inherit;
  font-weight: 700;
  border-radius: var(--ez-radius-medium);
  cursor: pointer;
}
.primary-action {
  color: white;
  background: var(--ez-color-brand-600);
  border: 1px solid var(--ez-color-brand-600);
}
.secondary-action {
  color: var(--ez-color-text-primary);
  background: var(--ez-color-surface);
  border: 1px solid var(--ez-color-border-strong);
}
.danger-action {
  color: var(--ez-color-danger);
  background: var(--ez-color-surface);
  border: 1px solid var(--ez-color-danger);
}
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.timeline-list li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--ez-space-3);
  padding-bottom: var(--ez-space-3);
  border-bottom: 1px solid var(--ez-color-border);
}
.timeline-sequence {
  color: var(--ez-color-text-muted);
  font: var(--ez-font-size-12) var(--ez-font-code);
}
.timeline-list p {
  margin: var(--ez-space-1) 0 0;
  color: var(--ez-color-text-secondary);
  overflow-wrap: anywhere;
}
.evidence-list {
  display: grid;
  gap: var(--ez-space-4);
  margin-top: var(--ez-space-4);
}
.context-bindings,
.retrieval-evidence {
  min-width: 0;
  margin-top: var(--ez-space-3);
  padding: var(--ez-space-3);
  background: var(--ez-color-surface-subtle);
  border-radius: var(--ez-radius-small);
}
.context-bindings ul,
.retrieval-evidence ol {
  display: grid;
  gap: var(--ez-space-2);
  margin: var(--ez-space-2) 0 0;
  padding-inline-start: var(--ez-space-5);
}
.context-bindings li,
.retrieval-evidence li {
  min-width: 0;
}
.context-bindings span,
.context-bindings code,
.retrieval-evidence span,
.retrieval-evidence code {
  display: block;
  overflow-wrap: anywhere;
}
.retrieval-evidence h4,
.retrieval-evidence p {
  margin: 0;
}
.retrieval-evidence p,
.retrieval-evidence span {
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
}
.history-list button {
  display: grid;
  width: 100%;
  min-height: var(--ez-touch-target);
  padding: var(--ez-space-3);
  text-align: left;
  color: inherit;
  background: var(--ez-color-surface-subtle);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-medium);
  cursor: pointer;
}
.history-list button[aria-current="true"] {
  border-color: var(--ez-color-brand-500);
  box-shadow: inset 3px 0 0 var(--ez-color-brand-500);
}
.history-list strong,
.history-list span {
  overflow-wrap: anywhere;
}
.history-list span {
  margin-top: var(--ez-space-1);
  color: var(--ez-color-text-muted);
  font-size: var(--ez-font-size-12);
}
.dialog-actions {
  flex-wrap: wrap;
  margin-top: var(--ez-space-4);
}
.control-actions {
  justify-content: flex-start;
  flex-wrap: wrap;
  margin-top: var(--ez-space-4);
}

@media (min-width: 720px) {
  .create-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .field--goal,
  .create-actions {
    grid-column: 1 / -1;
  }
}

@media (min-width: 1024px) {
  .workbench-grid {
    grid-template-columns: minmax(0, 1.65fr) minmax(280px, 0.75fr);
  }
  .secondary-column {
    position: sticky;
    top: calc(var(--ez-shell-header-height) + var(--ez-space-6));
  }
}

@media (max-width: 600px) {
  .agent-hero,
  .section-heading,
  .plan-title,
  .approval-actions {
    flex-direction: column;
  }
  .approval-actions > button,
  .dialog-actions > button {
    width: 100%;
  }
  .approval-facts div,
  .evidence-facts div,
  .budget-list div,
  .diagnostics-list div {
    grid-template-columns: minmax(0, 1fr);
  }
  dd {
    text-align: left;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    scroll-behavior: auto !important;
  }
}

@media (forced-colors: active) {
  .workbench-card,
  .plan-list li,
  .history-list button {
    border: 1px solid CanvasText;
  }
  .primary-action {
    border: 2px solid ButtonText;
  }
}
</style>
