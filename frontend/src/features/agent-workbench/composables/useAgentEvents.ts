// 带游标的 Agent 事件订阅与有界重连；页面回调负责去重、快照重载和错误展示。
import { onScopeDispose, ref } from "vue";
import type { AgentTimelineEvent } from "@/entities/agent-run/types";

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

/** 使用浏览器定时器为重连退避，不阻塞主线程。 */
const sleep = (milliseconds: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

// SSE block 只解析 data 字段；sequence 去重和 replay reset 由工作台状态层处理。
/** 合并 SSE data 行并解析人工或服务端事件；注释心跳及无数据块不进入时间线。 */
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

/** 管理运行事件连接与重放游标；切换订阅通过 generation 使旧连接退出。 */
export const useAgentEvents = () => {
  const connected = ref(false);
  let controller: AbortController | null = null;
  let generation = 0;

  /** 增加订阅代次并中断当前 fetch，使旧循环不能继续更新新运行的连接状态。 */
  const stop = () => {
    generation += 1;
    connected.value = false;
    controller?.abort();
    controller = null;
  };

  /**
   * 先关闭旧订阅，再从调用方提供的 sequence 恢复事件；组件作用域销毁时统一停止。
   * @param options 沿用当前 TypeScript 类型约束的输入。
   */
  const start = (options: AgentEventOptions) => {
    stop();
    const currentGeneration = generation;
    let cursor = options.afterSequence;

    /** 最多尝试六次连接，按有界指数退避恢复；收到终态停止，replay_reset 交给状态层重新同步。 */
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
