import { onScopeDispose, ref } from "vue";
import type { AgentTimelineEvent } from "@/features/agent/state/agentWorkbench";

interface AgentEventOptions {
  baseUrl: string;
  pid: string;
  threadId: string;
  afterSequence: number;
  onEvent: (event: AgentTimelineEvent) => void;
  onReplayReset: () => void;
  onError: (message: string) => void;
}

const terminalKinds = new Set(["completed", "cancelled", "failed"]);

/**
 * 处理sleep，并保持现有输入输出约定。
 */
const sleep = (milliseconds: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

// SSE block 只解析 data 字段；sequence 去重和 replay reset 由工作台状态层处理。
/**
 * 解析block，并保持现有状态与错误处理语义。
 */
const parseBlock = (block: string): AgentTimelineEvent | null => {
  if (block.startsWith(":")) return null;
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  const value: unknown = JSON.parse(data);
  if (!value || typeof value !== "object") return null;
  return value as AgentTimelineEvent;
};

/**
 * 管理 Agent 事件流连接、游标回放与断线状态。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
 */
export const useAgentEvents = () => {
  const connected = ref(false);
  let controller: AbortController | null = null;
  let generation = 0;

  /**
   * 停止内部状态，并保持现有状态与错误处理语义。
   */
  const stop = () => {
    generation += 1;
    connected.value = false;
    controller?.abort();
    controller = null;
  };

  /**
   * 启动内部状态，并保持现有状态与错误处理语义。
   *
   * @param options 沿用当前 TypeScript 类型约束的输入。
   *
   * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
   */
  const start = (options: AgentEventOptions) => {
    stop();
    const currentGeneration = generation;
    let cursor = options.afterSequence;

    /**
     * 执行内部状态，并保持现有状态与错误处理语义。
     *
     * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
     */
    const run = async () => {
      for (let attempt = 0; attempt < 6; attempt += 1) {
        if (currentGeneration !== generation) return;
        controller = new AbortController();
        try {
          const base = options.baseUrl.replace(/\/$/, "");
          const response = await fetch(
            `${base}/agent/v1/projects/${encodeURIComponent(options.pid)}/runs/${encodeURIComponent(
              options.threadId,
            )}/events?after_sequence=${cursor}`,
            {
              headers: { Accept: "text/event-stream" },
              signal: controller.signal,
            },
          );
          if (!response.ok || !response.body) {
            throw new Error("Agent 事件流暂不可用");
          }
          connected.value = true;
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          while (currentGeneration === generation) {
            const { value, done } = await reader.read();
            buffer += decoder.decode(value, { stream: !done });
            let boundary = buffer.indexOf("\n\n");
            while (boundary >= 0) {
              const block = buffer.slice(0, boundary).replace(/\r/g, "");
              buffer = buffer.slice(boundary + 2);
              const event = parseBlock(block);
              if (event) {
                if (event.kind === "replay_reset") {
                  options.onReplayReset();
                } else {
                  cursor = Math.max(cursor, event.sequence || 0);
                  options.onEvent(event);
                }
                if (terminalKinds.has(event.kind)) {
                  connected.value = false;
                  return;
                }
              }
              boundary = buffer.indexOf("\n\n");
            }
            if (done) break;
          }
          connected.value = false;
          if (currentGeneration !== generation) return;
        } catch (caught) {
          connected.value = false;
          if (controller.signal.aborted || currentGeneration !== generation) return;
          if (attempt === 5) {
            options.onError(caught instanceof Error ? caught.message : "Agent 事件流连接失败");
            return;
          }
        }
        await sleep(Math.min(8_000, 500 * 2 ** attempt));
      }
    };

    void run();
  };

  onScopeDispose(stop);
  return { connected, start, stop };
};
