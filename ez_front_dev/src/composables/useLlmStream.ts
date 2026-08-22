import { computed, onUnmounted, reactive, ref } from "vue";
import type { TestMenuState } from "@/state/projectAnalysis";

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

interface ParsedSseEvent {
  event: string;
  data: Record<string, unknown>;
}

const emptyUsage = (): LlmTokenUsage => ({
  input_tokens: null,
  reasoning_tokens: null,
  output_tokens: null,
  total_tokens: null,
});

const asNumberOrNull = (value: unknown): number | null =>
  typeof value === "number" ? value : null;

const parseSseBlock = (block: string): ParsedSseEvent | null => {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) return null;
  const parsed = JSON.parse(dataLines.join("\n"));
  if (typeof parsed !== "object" || parsed === null) return null;
  return { event, data: parsed as Record<string, unknown> };
};

export const useLlmStream = (baseUrl: string) => {
  const isRunning = ref(false);
  const completed = ref(false);
  const cancelled = ref(false);
  const saved = ref(false);
  const fromCache = ref(false);
  const ready = ref(false);
  const summary = ref("");
  const menu = ref<TestMenuState | null>(null);
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
  const meta = reactive({ requestId: "", label: "", provider: "", model: "", operation: "" });

  let controller: AbortController | null = null;
  let frameId: number | null = null;
  let pendingSummary = "";
  let pendingAnswer = "";
  const pendingReasoning = new Map<string, { label: string; text: string }>();

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

  const scheduleFlush = () => {
    if (frameId === null) frameId = requestAnimationFrame(flushPending);
  };

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
    artifact.artifactKey = "";
    artifact.sourceRevision = "";
    artifact.promptVersion = "";
    artifact.modelLabel = "";
    artifact.status = "";
    artifact.stale = false;
  };

  const applyEvent = (event: ParsedSseEvent) => {
    const data = event.data;
    switch (event.event) {
      case "meta":
        meta.requestId = String(data.request_id || "");
        meta.label = String(data.label || "");
        meta.provider = String(data.provider || "");
        meta.model = String(data.model || "");
        meta.operation = String(data.operation || "");
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
          Math.min(100, asNumberOrNull(data.percent) ?? progress.percent)
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
        menu.value = (data.menu || null) as TestMenuState | null;
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

  const cancel = () => {
    if (!controller) return;
    cancelled.value = true;
    controller.abort();
    controller = null;
    isRunning.value = false;
    progress.label = "已取消，本次生成结果未保存";
  };

  const hasActivity = computed(
    () =>
      isRunning.value || completed.value || cancelled.value || error.value !== null ||
      summary.value.length > 0 || answer.value.length > 0 ||
      reasoningSections.value.length > 0
  );

  onUnmounted(() => {
    if (controller) controller.abort();
    if (frameId !== null) cancelAnimationFrame(frameId);
  });

  return {
    isRunning, completed, cancelled, saved, fromCache, ready, summary, menu, result,
    answer, reasoningSections,
    usage, usageReceived, error, progress, meta, artifact, hasActivity, start, cancel,
    resetStream: reset,
  };
};
