import { computed, ref } from "vue";
import { useLlmStream } from "@/composables/useLlmStream";
import type {
  RunStepOptions,
  TestWorkflowController,
} from "@/composables/useTestWorkflow";

interface RunWorkflowOptions {
  answerTitle: string;
  successTitle: string;
  regenerate?: boolean;
  keepPreviousOnFailure?: boolean;
}

export const useLlmWorkflow = (
  baseUrl: string,
  pid: string,
  testWorkflow?: TestWorkflowController
) => {
  const stream = useLlmStream(baseUrl);
  const activeOperation = ref("");
  const activeSelection = ref<Record<string, unknown>>({});
  const answerTitle = ref("模型流式输出");
  const successTitle = ref("大模型执行已完成");

  const runWorkflow = async (
    operation: string,
    llmName: string,
    payload: Record<string, unknown>,
    options: RunWorkflowOptions
  ) => {
    const stepOptions: RunStepOptions = {
      regenerate: options.regenerate === true,
      keepPreviousOnFailure: options.keepPreviousOnFailure === true,
    };
    if (testWorkflow && !testWorkflow.beginStep(operation, stepOptions)) {
      return false;
    }
    activeOperation.value = operation;
    activeSelection.value = payload;
    answerTitle.value = options.answerTitle;
    successTitle.value = options.successTitle;
    const succeeded = await stream.start("/project/llm/workflow/stream", {
      operation,
      pid,
      llm_name: llmName,
      regenerate: options.regenerate === true,
      payload,
    });
    if (testWorkflow) {
      if (succeeded) {
        testWorkflow.completeStep(
          operation,
          stream.result.value,
          payload,
          {
            artifactKey: stream.artifact.artifactKey || null,
            sourceRevision: stream.artifact.sourceRevision || null,
          },
          stepOptions
        );
      } else {
        testWorkflow.failStep(operation);
      }
    }
    return succeeded;
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
    activeSelection,
    executionProps,
    runWorkflow,
  };
};
