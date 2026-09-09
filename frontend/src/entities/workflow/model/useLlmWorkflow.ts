// 连接生成流与工作流步骤控制器，完整成功才晋升结果，失败由控制器恢复旧版本。
import { computed, ref } from "vue";
import { useLlmStream } from "@/shared/composables/useLlmStream";
import type {
  RunStepOptions,
  TestWorkflowController,
} from "@/entities/workflow/model/useTestWorkflow";

interface RunWorkflowOptions {
  answerTitle: string;
  successTitle: string;
  regenerate?: boolean;
  keepPreviousOnFailure?: boolean;
}

/**
 * 把通用流状态接入工作流控制器，统一完整成功后的接纳与失败后的旧结果恢复。
 * @param baseUrl 沿用当前 TypeScript 类型约束的输入。
 * @param pid 项目 ID。
 * @param testWorkflow 沿用当前 TypeScript 类型约束的输入。
 */
export const useLlmWorkflow = (
  baseUrl: string,
  pid: string,
  testWorkflow?: TestWorkflowController,
) => {
  const stream = useLlmStream(baseUrl);
  const activeOperation = ref("");
  const activeSelection = ref<Record<string, unknown>>({});
  const answerTitle = ref("模型流式输出");
  const successTitle = ref("大模型执行已完成");

  /**
   * 通过 beginStep 后才启动流；成功传递产物键与 revision，失败调用 failStep 恢复运行前状态。
   * @param operation 工作流操作名。
   * @param llmName 沿用当前 TypeScript 类型约束的输入。
   * @param payload 沿用当前 TypeScript 类型约束的输入。
   * @param options 沿用当前 TypeScript 类型约束的输入。
   */
  const runWorkflow = async (
    operation: string,
    llmName: string,
    payload: Record<string, unknown>,
    options: RunWorkflowOptions,
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
          stepOptions,
        );
      } else {
        testWorkflow.failStep(operation);
      }
    }
    return succeeded;
  };

  /**
   * 派生用于界面展示或请求判断的execution props。
   */
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
