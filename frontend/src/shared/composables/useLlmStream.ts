// 通用生成 SSE 生命周期与渲染状态，不导入计划页或测试页的业务状态。
import { parseSseBlock, type ParsedSseEvent } from "@/shared/transport/sse";
import { computed, onUnmounted, reactive, ref, shallowRef } from "vue";

export interface LlmProgress {
  stage: string;
  label: string;
  current: number | null;
  total: number | null;
  percent: number;
}

export interface LlmTokenUsage {
  input_tokens: number | null;
  reasoning_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
}

export interface LlmReasoningSection {
  stage: string;
  label: string;
  text: string;
}

export interface LlmStreamError {
  code: string;
  message: string;
  status: number;
  retryable: boolean;
}

export type LlmPersistence = "" | "artifact" | "session";

export interface LlmExecutionMeta {
  requestId: string;
  label: string;
  provider: string;
  model: string;
  operation: string;
  persistence: LlmPersistence;
}

export interface LlmArtifactMetadata {
  artifactKey: string;
  sourceRevision: string;
  promptVersion: string;
  modelLabel: string;
  status: string;
  stale: boolean;
}

interface StreamRequestBody {
  pid: string;
  llm_name: string;
  [key: string]: unknown;
}

/** 创建尚未收到 usage 的空计数，null 与真实的零消耗保持区别。 */
const emptyUsage = (): LlmTokenUsage => ({
  input_tokens: null,
  reasoning_tokens: null,
  output_tokens: null,
  total_tokens: null,
});

/** 仅接受数值型 usage 字段，缺失或其他类型统一表示未知。 */
const asNumberOrNull = (value: unknown): number | null =>
  typeof value === "number" ? value : null;

/**
 *
 * @param block 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */

/**
 * 管理一次生成流的网络连接、事件状态与渲染缓冲；业务状态通过返回值与调用方衔接，不导入页面状态。
 * @param baseUrl 沿用当前 TypeScript 类型约束的输入。
 */
export const useLlmStream = <TMenu = Record<string, boolean>>(baseUrl: string) => {
  const isRunning = ref(false);
  const completed = ref(false);
  const cancelled = ref(false);
  const saved = ref(false);
  const fromCache = ref(false);
  const ready = ref(false);
  const summary = ref("");
  const menu = shallowRef<TMenu | null>(null);
  const result = ref<unknown>(null);
  const answer = ref("");
  const reasoningSections = ref<LlmReasoningSection[]>([]);
  const usage = ref<LlmTokenUsage>(emptyUsage());
  const usageReceived = ref(false);
  const error = ref<LlmStreamError | null>(null);
  const artifact = reactive<LlmArtifactMetadata>({
    artifactKey: "",
    sourceRevision: "",
    promptVersion: "",
    modelLabel: "",
    status: "",
    stale: false,
  });
  const progress = reactive<LlmProgress>({
    stage: "",
    label: "等待开始",
    current: null,
    total: null,
    percent: 0,
  });
  const meta = reactive<LlmExecutionMeta>({
    requestId: "",
    label: "",
    provider: "",
    model: "",
    operation: "",
    persistence: "",
  });

  let controller: AbortController | null = null;
  let frameId: number | null = null;
  let pendingSummary = "";
  let pendingAnswer = "";
  const pendingReasoning = new Map<string, { label: string; text: string }>();

  /** 把暂存的正文、摘要和分阶段推理合入响应式状态，并清理已安排的动画帧。 */
  const flushPending = () => {
    if (frameId !== null) {
      cancelAnimationFrame(frameId);
      frameId = null;
    }
    if (pendingAnswer) {
      answer.value += pendingAnswer;
      pendingAnswer = "";
    }
    if (pendingSummary) {
      summary.value += pendingSummary;
      pendingSummary = "";
    }
    if (pendingReasoning.size > 0) {
      const sections = [...reasoningSections.value];
      pendingReasoning.forEach((pending, stage) => {
        const existing = sections.find((section) => section.stage === stage);
        if (existing) existing.text += pending.text;
        else sections.push({ stage, label: pending.label, text: pending.text });
      });
      reasoningSections.value = sections;
      pendingReasoning.clear();
    }
  };

  /** 同一帧内只安排一次刷新，避免每个 token 都触发整块界面更新。 */
  const scheduleFlush = () => {
    if (frameId === null) frameId = requestAnimationFrame(flushPending);
  };

  /** 中断当前请求并清空本次流状态；持久化产物的保留由外层工作流控制器处理。 */
  const reset = () => {
    if (controller) controller.abort();
    flushPending();
    isRunning.value = false;
    completed.value = false;
    cancelled.value = false;
    saved.value = false;
    fromCache.value = false;
    ready.value = false;
    summary.value = "";
    menu.value = null;
    result.value = null;
    answer.value = "";
    reasoningSections.value = [];
    usage.value = emptyUsage();
    usageReceived.value = false;
    error.value = null;
    progress.stage = "";
    progress.label = "正在连接后端";
    progress.current = null;
    progress.total = null;
    progress.percent = 0;
    meta.requestId = "";
    meta.label = "";
    meta.provider = "";
    meta.model = "";
    meta.operation = "";
    meta.persistence = "";
    artifact.artifactKey = "";
    artifact.sourceRevision = "";
    artifact.promptVersion = "";
    artifact.modelLabel = "";
    artifact.status = "";
    artifact.stale = false;
  };

  /**
   * 按 SSE 事件类型更新元数据、进度、增量和终态；saved 与 completed 分开表示保存和生成完成。
   * @param event 当前事件对象。
   */
  const applyEvent = (event: ParsedSseEvent) => {
    const data = event.data;
    switch (event.event) {
      case "meta":
        meta.requestId = String(data.request_id || "");
        meta.label = String(data.label || "");
        meta.provider = String(data.provider || "");
        meta.model = String(data.model || "");
        meta.operation = String(data.operation || "");
        meta.persistence =
          data.persistence === "artifact"
            ? "artifact"
            : data.persistence === "session"
              ? "session"
              : "";
        artifact.artifactKey = String(data.artifact_key || "");
        artifact.sourceRevision = String(data.source_revision || "");
        artifact.promptVersion = String(data.prompt_version || "");
        break;
      case "stale":
        artifact.stale = true;
        artifact.artifactKey = String(data.artifact_key || artifact.artifactKey);
        artifact.sourceRevision = String(data.source_revision || artifact.sourceRevision);
        break;
      case "artifact":
        artifact.artifactKey = String(data.artifact_key || artifact.artifactKey);
        artifact.sourceRevision = String(data.source_revision || artifact.sourceRevision);
        artifact.promptVersion = String(data.prompt_version || artifact.promptVersion);
        artifact.modelLabel = String(data.model_label || artifact.modelLabel);
        artifact.status = String(data.status || "");
        artifact.stale = false;
        break;
      case "progress":
        progress.stage = String(data.stage || "");
        progress.label = String(data.label || "正在处理");
        progress.current = asNumberOrNull(data.current);
        progress.total = asNumberOrNull(data.total);
        progress.percent = Math.max(
          progress.percent,
          Math.min(100, asNumberOrNull(data.percent) ?? progress.percent),
        );
        break;
      case "reasoning_delta": {
        const stage = String(data.stage || "thinking");
        const pending = pendingReasoning.get(stage) || {
          label: String(data.label || "模型思考"),
          text: "",
        };
        pending.text += String(data.text || "");
        pendingReasoning.set(stage, pending);
        scheduleFlush();
        break;
      }
      case "answer_delta":
        pendingAnswer += String(data.text || "");
        scheduleFlush();
        break;
      case "summary_delta":
        pendingSummary += String(data.text || "");
        scheduleFlush();
        break;
      case "menu":
        menu.value = (data.menu || null) as TMenu | null;
        break;
      case "result":
        result.value = data.result ?? null;
        break;
      case "usage":
        usage.value = {
          input_tokens: asNumberOrNull(data.input_tokens),
          reasoning_tokens: asNumberOrNull(data.reasoning_tokens),
          output_tokens: asNumberOrNull(data.output_tokens),
          total_tokens: asNumberOrNull(data.total_tokens),
        };
        usageReceived.value = true;
        break;
      case "completed":
        flushPending();
        saved.value = data.saved === true;
        fromCache.value = data.from_cache === true;
        ready.value = data.ready === true;
        completed.value = true;
        break;
      case "error":
        flushPending();
        error.value = {
          code: String(data.code || "stream_error"),
          message: String(data.message || "大模型流式执行失败"),
          status: asNumberOrNull(data.status) ?? 500,
          retryable: data.retryable !== false,
        };
        break;
    }
  };

  /**
   * 显式提交生成请求并持续解码 SSE；HTTP 错误、取消及提前断流分别记录，不把不完整输出判为成功。
   * @param path 沿用当前 TypeScript 类型约束的输入。
   * @param body 沿用当前 TypeScript 类型约束的输入。
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   */
  const start = async (path: string, body: StreamRequestBody): Promise<boolean> => {
    reset();
    if (!baseUrl || !body.pid) {
      error.value = {
        code: "missing_context",
        message: "无法获取后端地址或项目编号",
        status: 0,
        retryable: false,
      };
      return false;
    }

    const activeController = new AbortController();
    controller = activeController;
    isRunning.value = true;
    try {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
        method: "POST",
        headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: activeController.signal,
      });
      if (!response.ok) {
        let message = `后端返回 HTTP ${response.status}`;
        try {
          const payload = (await response.json()) as { reason?: string };
          message = payload.reason || message;
        } catch {
          // Keep the sanitized HTTP message when the body is not JSON.
        }
        throw new Error(message);
      }
      if (!response.body) throw new Error("浏览器无法读取流式响应");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let streamDone = false;
      while (!streamDone) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        let boundary = /\r?\n\r?\n/.exec(buffer);
        while (boundary && boundary.index !== undefined) {
          const block = buffer.slice(0, boundary.index);
          buffer = buffer.slice(boundary.index + boundary[0].length);
          const parsed = parseSseBlock(block);
          if (parsed) applyEvent(parsed);
          boundary = /\r?\n\r?\n/.exec(buffer);
        }
        streamDone = done;
      }
      if (buffer.trim()) {
        const parsed = parseSseBlock(buffer);
        if (parsed) applyEvent(parsed);
      }
      flushPending();
      if (!completed.value && !error.value && !cancelled.value) {
        error.value = {
          code: "stream_closed",
          message: "流式连接提前结束，本次结果未保存",
          status: 0,
          retryable: true,
        };
      }
      return completed.value;
    } catch (caught) {
      flushPending();
      if (caught instanceof DOMException && caught.name === "AbortError") return false;
      error.value = {
        code: "network_error",
        message: caught instanceof Error ? caught.message : "无法连接后端",
        status: 0,
        retryable: true,
      };
      return false;
    } finally {
      if (controller === activeController) controller = null;
      isRunning.value = false;
    }
  };

  /** 中止当前浏览器请求并标为取消；不会把当前未完成文本标记成已保存产物。 */
  const cancel = () => {
    if (!controller) return;
    cancelled.value = true;
    controller.abort();
    controller = null;
    isRunning.value = false;
    progress.label = "已取消，本次生成结果未保存";
  };

  /**
   * 派生用于界面展示或请求判断的has activity。
   */
  const hasActivity = computed(
    () =>
      isRunning.value ||
      completed.value ||
      cancelled.value ||
      error.value !== null ||
      summary.value.length > 0 ||
      answer.value.length > 0 ||
      reasoningSections.value.length > 0,
  );

  /**
   * 组件卸载时释放事件监听、定时器或流式连接。
   */
  onUnmounted(() => {
    if (controller) controller.abort();
    if (frameId !== null) cancelAnimationFrame(frameId);
  });

  return {
    isRunning,
    completed,
    cancelled,
    saved,
    fromCache,
    ready,
    summary,
    menu,
    result,
    answer,
    reasoningSections,
    usage,
    usageReceived,
    error,
    progress,
    meta,
    artifact,
    hasActivity,
    start,
    cancel,
    resetStream: reset,
  };
};
