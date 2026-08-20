import { computed, ref } from "vue";
import { useLlmStream } from "@/composables/useLlmStream";

interface RunWorkflowOptions {
  answerTitle: string;
  successTitle: string;
  regenerate?: boolean;
}

export const useLlmWorkflow = (baseUrl: string, pid: string) => {
  const stream = useLlmStream(baseUrl);
  const activeOperation = ref("");
  const answerTitle = ref("模型流式输出");
  const successTitle = ref("大模型执行已完成");

  const runWorkflow = async (
    operation: string,
    llmName: string,
    payload: Record<string, unknown>,
    options: RunWorkflowOptions
  ) => {
    activeOperation.value = operation;
    answerTitle.value = options.answerTitle;
    successTitle.value = options.successTitle;
    return stream.start("/project/llm/workflow/stream", {
      operation,
      pid,
      llm_name: llmName,
      regenerate: options.regenerate === true,
      payload,
    });
  };

  const executionProps = computed(() => ({
    visible: stream.hasActivity.value,
    running: stream.isRunning.value,
    completed: stream.completed.value,
    cancelled: stream.cancelled.value,
    saved: stream.saved.value,
    fromCache: stream.fromCache.value,
    progress: stream.progress,
    meta: stream.meta,
    reasoningSections: stream.reasoningSections.value,
    usage: stream.usage.value,
    usageReceived: stream.usageReceived.value,
    error: stream.error.value,
    answer: stream.answer.value,
    answerTitle: answerTitle.value,
    successTitle: successTitle.value,
  }));

  return {
    ...stream,
    activeOperation,
    executionProps,
    runWorkflow,
  };
};
