import { computed, reactive, ref } from "vue";
import {
  loadProjectWorkflowStatus,
  type ProjectWorkflowStatus,
} from "@/features/planning/state/projectAnalysis";
import { confirmResultReplacement } from "@/shared/ui/confirmations";

export type WorkflowStepState = "locked" | "ready" | "running" | "completed" | "stale" | "failed";

export interface TestWorkflowStep<Result = unknown> {
  operation: string;
  label: string;
  state: WorkflowStepState;
  result: Result | null;
  artifactKey: string | null;
  dependsOn: string[];
  selectionFields: string[];
  persistResult: boolean;
}

export interface TestWorkflowStepDefinition {
  operation: string;
  label: string;
  artifactKey?: string;
  dependsOn?: string[];
  selectionFields?: string[];
  persistResult?: boolean;
}

export interface WorkflowArtifactMetadata {
  artifactKey: string | null;
  sourceRevision: string | null;
}

export interface RunStepOptions {
  regenerate?: boolean;
  keepPreviousOnFailure?: boolean;
}

export interface TestWorkflowController {
  canRunStep: (operation: string) => boolean;
  beginStep: (operation: string, options?: RunStepOptions) => boolean;
  completeStep: (
    operation: string,
    result: unknown,
    selection: Record<string, unknown>,
    metadata: WorkflowArtifactMetadata,
    options?: RunStepOptions,
  ) => void;
  failStep: (operation: string) => void;
}

interface StoredStep {
  state: WorkflowStepState;
  result: unknown;
  selection: Record<string, unknown>;
  artifactKey: string | null;
}

interface StoredWorkflow {
  version: 1;
  sourceRevision: string | null;
  steps: Record<string, StoredStep>;
}

interface UseTestWorkflowOptions {
  baseUrl: string;
  pid: string;
  steps: TestWorkflowStepDefinition[];
}

/**
 * 处理usable状态，并保持现有输入输出约定。
 */
const usableState = (step: TestWorkflowStep): boolean =>
  step.state === "completed" || (step.state === "failed" && step.result !== null);

/**
 * 规范化值，并保持现有状态与错误处理语义。
 */
const normalizeValue = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(normalizeValue);
  if (value !== null && typeof value === "object") {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((normalized, key) => {
        normalized[key] = normalizeValue((value as Record<string, unknown>)[key]);
        return normalized;
      }, {});
  }
  return value;
};

/**
 * 规范化selections，并保持现有状态与错误处理语义。
 */
export const normalizeSelections = (selection: Record<string, unknown>): Record<string, unknown> =>
  normalizeValue(selection) as Record<string, unknown>;

/**
 * 管理测试生成工作区的恢复、执行、失效与重新生成流程。
 *
 * @param { baseUrl, pid, steps: definitions } 沿用当前 TypeScript 类型约束的输入。
 *
 * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
 */
export const useTestWorkflow = ({ baseUrl, pid, steps: definitions }: UseTestWorkflowOptions) => {
  const steps = ref<TestWorkflowStep[]>(
    definitions.map((definition, index) => ({
      operation: definition.operation,
      label: definition.label,
      state: index === 0 ? "ready" : "locked",
      result: null,
      artifactKey: definition.artifactKey ?? null,
      dependsOn: definition.dependsOn ?? (index === 0 ? [] : [definitions[index - 1].operation]),
      selectionFields: definition.selectionFields ?? [],
      persistResult: definition.persistResult !== false,
    })),
  );
  const sourceRevision = ref<string | null>(null);
  const hydrating = ref(true);
  const hydrationError = ref("");
  const selections = reactive(new Map<string, Record<string, unknown>>());
  const previousSteps = new Map<string, TestWorkflowStep>();
  const selectionBaselines = new Map<string, Map<string, WorkflowStepState>>();
  const storageKey = `ezllmtest:test-workflow:v1:${pid}:${definitions
    .map((definition) => definition.operation)
    .join(",")}`;

  /**
   * 处理步骤 for，并保持现有输入输出约定。
   */
  const stepFor = (operation: string): TestWorkflowStep | undefined =>
    steps.value.find((step) => step.operation === operation);

  /**
   * 处理依赖就绪状态，并保持现有输入输出约定。
   */
  const dependenciesReady = (step: TestWorkflowStep): boolean =>
    step.dependsOn.every((operation) => {
      const dependency = stepFor(operation);
      return dependency !== undefined && usableState(dependency);
    });

  /**
   * 刷新locked states，并保持现有状态与错误处理语义。
   */
  const refreshLockedStates = () => {
    steps.value.forEach((step) => {
      if (step.state === "running" || step.state === "completed" || step.state === "stale") {
        return;
      }
      if (step.state === "failed" && step.result !== null) return;
      step.state = dependenciesReady(step)
        ? step.state === "failed"
          ? "failed"
          : "ready"
        : "locked";
    });
  };

  /**
   * 处理stored工作流，并保持现有输入输出约定。
   *
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   *
   * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
   */
  const storedWorkflow = (): StoredWorkflow => ({
    version: 1,
    sourceRevision: sourceRevision.value,
    steps: Object.fromEntries(
      steps.value
        .filter((step) => step.persistResult)
        .map((step) => [
          step.operation,
          {
            state: step.state,
            result: step.result,
            selection: selections.get(step.operation) ?? {},
            artifactKey: step.artifactKey,
          },
        ]),
    ),
  });

  /**
   * 持久化内部状态，并保持现有状态与错误处理语义。
   *
   * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
   */
  const persist = () => {
    if (typeof window === "undefined" || !pid) return;
    try {
      window.sessionStorage.setItem(storageKey, JSON.stringify(storedWorkflow()));
    } catch {
      // Browser storage is a refresh convenience; persisted server artifacts remain authoritative.
    }
  };

  /**
   * 恢复会话，并保持现有状态与错误处理语义。
   *
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   *
   * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
   */
  const restoreSession = (): string | null => {
    if (typeof window === "undefined" || !pid) return null;
    try {
      const raw = window.sessionStorage.getItem(storageKey);
      if (!raw) return null;
      const stored = JSON.parse(raw) as Partial<StoredWorkflow>;
      if (stored.version !== 1 || !stored.steps || typeof stored.steps !== "object") {
        return null;
      }
      steps.value.forEach((step) => {
        if (!step.persistResult) return;
        const saved = stored.steps?.[step.operation];
        if (!saved || typeof saved !== "object") return;
        step.result = saved.result ?? null;
        step.artifactKey = saved.artifactKey ?? step.artifactKey;
        step.state = saved.state ?? step.state;
        selections.set(step.operation, normalizeSelections(saved.selection ?? {}));
      });
      return stored.sourceRevision ?? null;
    } catch {
      return null;
    }
  };

  /**
   * 应用状态，并保持现有状态与错误处理语义。
   *
   * @param status 沿用当前 TypeScript 类型约束的输入。
   * @param storedRevision 沿用当前 TypeScript 类型约束的输入。
   */
  const applyStatus = (status: ProjectWorkflowStatus, storedRevision: string | null) => {
    sourceRevision.value = status.source_revision;
    const sourceChanged = Boolean(
      storedRevision && status.source_revision && storedRevision !== status.source_revision,
    );
    steps.value.forEach((step) => {
      if (
        status.stale_operations.includes(step.operation) ||
        (sourceChanged && step.result !== null)
      ) {
        step.state = "stale";
      } else if (step.persistResult && status.completed_operations.includes(step.operation)) {
        step.state = step.state === "stale" ? "stale" : "completed";
      } else if (step.result !== null) {
        step.state = "stale";
      } else {
        step.state = "locked";
      }
    });
    refreshLockedStates();
  };

  /**
   * 加载并校验当前项目的已保存工作流快照。
   */
  const hydrateWorkflow = async (): Promise<void> => {
    hydrating.value = true;
    hydrationError.value = "";
    const storedRevision = restoreSession();
    try {
      const status = await loadProjectWorkflowStatus(baseUrl, pid);
      applyStatus(status, storedRevision);
    } catch (caught) {
      hydrationError.value = caught instanceof Error ? caught.message : "工作流状态恢复失败";
      refreshLockedStates();
    } finally {
      hydrating.value = false;
    }
    persist();
  };

  /**
   * 判断能否运行步骤，并保持现有状态与错误处理语义。
   */
  const canRunStep = (operation: string): boolean => {
    const step = stepFor(operation);
    return Boolean(
      step && step.state !== "locked" && step.state !== "running" && dependenciesReady(step),
    );
  };

  /**
   * 派生用于界面展示或请求判断的allowed next actions。
   */
  const allowedNextActions = computed(() =>
    steps.value.filter((step) => canRunStep(step.operation)).map((step) => step.operation),
  );

  /**
   * 处理begin步骤，并保持现有输入输出约定。
   *
   * @param operation 工作流操作名。
   * @param options 沿用当前 TypeScript 类型约束的输入。
   *
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   */
  const beginStep = (operation: string, options: RunStepOptions = {}): boolean => {
    const step = stepFor(operation);
    if (!step || !canRunStep(operation)) return false;
    previousSteps.set(operation, {
      ...step,
      dependsOn: [...step.dependsOn],
      selectionFields: [...step.selectionFields],
      persistResult: step.persistResult,
    });
    if (!options.keepPreviousOnFailure && step.state !== "completed" && step.state !== "stale") {
      step.result = null;
    }
    step.state = "running";
    persist();
    return true;
  };

  /**
   * 处理dependent operations，并保持现有输入输出约定。
   *
   * @param operation 工作流操作名。
   *
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   */
  const dependentOperations = (operation: string): Set<string> => {
    const dependents = new Set<string>();
    let changed = true;
    while (changed) {
      changed = false;
      steps.value.forEach((step) => {
        if (
          !dependents.has(step.operation) &&
          step.dependsOn.some(
            (dependency) => dependency === operation || dependents.has(dependency),
          )
        ) {
          dependents.add(step.operation);
          changed = true;
        }
      });
    }
    return dependents;
  };

  /**
   * 标记dependents过期，并保持现有状态与错误处理语义。
   */
  const markDependentsStale = (operation: string) => {
    dependentOperations(operation).forEach((dependent) => {
      const step = stepFor(dependent);
      if (step && (step.result !== null || step.state === "completed")) step.state = "stale";
    });
  };

  /**
   * 标记步骤过期，并保持现有状态与错误处理语义。
   */
  const markStepStale = (operation: string, includeDependents = true) => {
    const step = stepFor(operation);
    if (step && (step.result !== null || step.state === "completed" || step.state === "stale")) {
      step.state = "stale";
    }
    if (includeDependents) markDependentsStale(operation);
    refreshLockedStates();
    persist();
  };

  /**
   * 处理reconcile步骤选择条件，并保持现有输入输出约定。
   *
   * @param operation 工作流操作名。
   * @param selection 沿用当前 TypeScript 类型约束的输入。
   * @param includeDependents 沿用当前 TypeScript 类型约束的输入。
   *
   * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
   */
  const reconcileStepSelection = (
    operation: string,
    selection: Record<string, unknown>,
    includeDependents = true,
  ) => {
    const baseline = selectionBaselines.get(operation);
    if (selectionMatches(operation, selection)) {
      baseline?.forEach((state, affectedOperation) => {
        const affectedStep = stepFor(affectedOperation);
        if (affectedStep) affectedStep.state = state;
      });
      selectionBaselines.delete(operation);
      refreshLockedStates();
      persist();
      return;
    }

    if (!baseline) {
      const affectedOperations = new Set([operation]);
      if (includeDependents) {
        dependentOperations(operation).forEach((dependent) => affectedOperations.add(dependent));
      }
      const states = new Map<string, WorkflowStepState>();
      affectedOperations.forEach((affectedOperation) => {
        const affectedStep = stepFor(affectedOperation);
        if (
          affectedStep &&
          (affectedStep.result !== null ||
            affectedStep.state === "completed" ||
            affectedStep.state === "stale")
        ) {
          states.set(affectedOperation, affectedStep.state);
        }
      });
      if (states.size > 0) selectionBaselines.set(operation, states);
    }
    markStepStale(operation, includeDependents);
  };

  /**
   * 处理complete步骤，并保持现有输入输出约定。
   *
   * @param operation 工作流操作名。
   * @param result 沿用当前 TypeScript 类型约束的输入。
   * @param selection 沿用当前 TypeScript 类型约束的输入。
   * @param metadata 沿用当前 TypeScript 类型约束的输入。
   * @param options 沿用当前 TypeScript 类型约束的输入。
   *
   * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
   */
  const completeStep = (
    operation: string,
    result: unknown,
    selection: Record<string, unknown>,
    metadata: WorkflowArtifactMetadata,
    options: RunStepOptions = {},
  ) => {
    const step = stepFor(operation);
    if (!step) return;
    const normalized = normalizeSelections(
      Object.fromEntries(
        step.selectionFields
          .filter((field) => Object.prototype.hasOwnProperty.call(selection, field))
          .map((field) => [field, selection[field]]),
      ),
    );
    const previousSelection = selections.get(operation);
    const selectionChanged =
      previousSelection !== undefined &&
      JSON.stringify(previousSelection) !== JSON.stringify(normalized);
    const previous = previousSteps.get(operation);
    step.result = result;
    step.artifactKey = metadata.artifactKey ?? step.artifactKey;
    step.state = "completed";
    sourceRevision.value = metadata.sourceRevision ?? sourceRevision.value;
    selections.set(operation, normalized);
    selectionBaselines.delete(operation);
    if (
      options.regenerate ||
      selectionChanged ||
      (previous?.state === "stale" && result !== null)
    ) {
      markDependentsStale(operation);
    }
    previousSteps.delete(operation);
    refreshLockedStates();
    persist();
  };

  /**
   * 处理fail步骤，并保持现有输入输出约定。
   *
   * @param operation 工作流操作名。
   *
   * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
   */
  const failStep = (operation: string) => {
    const step = stepFor(operation);
    if (!step) return;
    const previous = previousSteps.get(operation);
    if (
      previous &&
      (previous.result !== null || previous.state === "completed" || previous.state === "stale")
    ) {
      step.state = previous.state;
      step.result = previous.result;
      step.artifactKey = previous.artifactKey;
    } else {
      step.state = "failed";
    }
    previousSteps.delete(operation);
    refreshLockedStates();
    persist();
  };

  /**
   * 处理confirm replacement，并保持现有输入输出约定。
   */
  const confirmReplacement = async (operation: string): Promise<boolean> => {
    const step = stepFor(operation);
    if (!step || (step.result === null && step.state !== "completed" && step.state !== "stale")) {
      return true;
    }
    return confirmResultReplacement(step.label);
  };

  /**
   * 在用户确认后按既有失效规则重新执行指定步骤。
   */
  const regenerateStep = async (
    operation: string,
    runner: () => Promise<boolean>,
  ): Promise<boolean> => {
    if (!(await confirmReplacement(operation))) return false;
    return runner();
  };

  /**
   * 重置步骤，并保持现有状态与错误处理语义。
   *
   * @param operation 工作流操作名。
   *
   * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
   */
  const resetStep = (operation: string) => {
    const step = stepFor(operation);
    if (!step) return;
    step.result = null;
    selections.delete(operation);
    selectionBaselines.delete(operation);
    step.state = dependenciesReady(step) ? "ready" : "locked";
    persist();
  };

  /**
   * 处理结果 for，并保持现有输入输出约定。
   */
  const resultFor = <Result = unknown>(operation: string): Result | null =>
    (stepFor(operation)?.result as Result | null | undefined) ?? null;

  /**
   * 处理选择条件 for，并保持现有输入输出约定。
   *
   * @param operation 工作流操作名。
   *
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   *
   * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
   */
  const selectionFor = (operation: string): Record<string, unknown> =>
    selections.get(operation) ?? {};

  /**
   * 规范化选择条件 for步骤，并保持现有状态与错误处理语义。
   */
  const normalizeSelectionForStep = (
    operation: string,
    selection: Record<string, unknown>,
  ): Record<string, unknown> | null => {
    const step = stepFor(operation);
    if (!step) return null;
    return normalizeSelections(
      Object.fromEntries(
        step.selectionFields
          .filter((field) => Object.prototype.hasOwnProperty.call(selection, field))
          .map((field) => [field, selection[field]]),
      ),
    );
  };

  /**
   * 处理selections match，并保持现有输入输出约定。
   */
  const selectionsMatch = (
    operation: string,
    first: Record<string, unknown>,
    second: Record<string, unknown>,
  ): boolean => {
    const normalizedFirst = normalizeSelectionForStep(operation, first);
    const normalizedSecond = normalizeSelectionForStep(operation, second);
    return (
      normalizedFirst !== null &&
      normalizedSecond !== null &&
      JSON.stringify(normalizedFirst) === JSON.stringify(normalizedSecond)
    );
  };

  /**
   * 处理选择条件 matches，并保持现有输入输出约定。
   *
   * @param operation 工作流操作名。
   * @param selection 沿用当前 TypeScript 类型约束的输入。
   *
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   *
   * 副作用：可能调用本地 API、浏览器存储或流式连接，并更新当前页面状态。
   */
  const selectionMatches = (operation: string, selection: Record<string, unknown>): boolean => {
    const step = stepFor(operation);
    if (!step) return false;
    if (step.selectionFields.length === 0) return true;
    const savedSelection = selections.get(operation);
    if (!savedSelection) return false;
    return selectionsMatch(operation, savedSelection, selection);
  };

  /**
   * 判断是否存在已保存结果，并保持现有状态与错误处理语义。
   */
  const hasSavedResult = (operation: string): boolean => {
    const step = stepFor(operation);
    return Boolean(
      step && (step.result !== null || step.state === "completed" || step.state === "stale"),
    );
  };

  /**
   * 判断是否存在可见状态结果，并保持现有状态与错误处理语义。
   */
  const hasVisibleResult = (operation: string): boolean => stepFor(operation)?.result !== null;

  /**
   * 判断是否存在可见状态结果 for，并保持现有状态与错误处理语义。
   */
  const hasVisibleResultFor = (operation: string, selection: Record<string, unknown>): boolean =>
    hasVisibleResult(operation) && selectionMatches(operation, selection);

  /**
   * 处理needs结果恢复，并保持现有输入输出约定。
   */
  const needsResultRecovery = (operation: string): boolean => {
    const step = stepFor(operation);
    return Boolean(
      step && step.persistResult && step.state === "completed" && step.result === null,
    );
  };

  /**
   * 处理过期警告，并保持现有输入输出约定。
   */
  const staleWarning = (operation: string): string => {
    const step = stepFor(operation);
    return step?.state === "stale"
      ? `“${step.label}”基于旧的项目资料或上游结果，重新生成前仅供参考。`
      : "";
  };

  return {
    steps,
    sourceRevision,
    hydrating,
    hydrationError,
    allowedNextActions,
    hydrateWorkflow,
    canRunStep,
    beginStep,
    completeStep,
    failStep,
    regenerateStep,
    confirmReplacement,
    markDependentsStale,
    markStepStale,
    reconcileStepSelection,
    resetStep,
    resultFor,
    selectionFor,
    selectionsMatch,
    selectionMatches,
    hasSavedResult,
    hasVisibleResult,
    hasVisibleResultFor,
    needsResultRecovery,
    staleWarning,
  };
};
