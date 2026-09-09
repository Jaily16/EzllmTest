// 工作流状态区分运行草稿、旧有效结果和过期结果；会话快照只是恢复便利，服务端 revision 为准。
import { computed, reactive, ref } from "vue";
import {
  loadProjectWorkflowStatus,
  type ProjectWorkflowStatus,
} from "@/entities/project/model/analysis";
import { confirmResultReplacement } from "@/entities/workflow/ui/confirmations";

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

/** 已完成的步骤可作为依赖；重试失败但仍保留旧结果时，也允许下游继续引用该结果。 */
const usableState = (step: TestWorkflowStep): boolean =>
  step.state === "completed" || (step.state === "failed" && step.result !== null);

/** 递归排序对象键、保留数组顺序，使选择条件可以用稳定 JSON 比较。 */
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

/** 把选择条件转换为稳定键序；不改变字段值或丢弃业务字段。 */
export const normalizeSelections = (selection: Record<string, unknown>): Record<string, unknown> =>
  normalizeValue(selection) as Record<string, unknown>;

/**
 * 为项目的一组工作流管理依赖、会话恢复和失效状态；服务端 revision 决定结果是否过期，重试失败恢复原有效结果。
 * @param { baseUrl, pid, steps: definitions } 沿用当前 TypeScript 类型约束的输入。
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

  /** 按 operation 查找当前步骤；未知操作返回 undefined，由调用方决定是否拒绝动作。 */
  const stepFor = (operation: string): TestWorkflowStep | undefined =>
    steps.value.find((step) => step.operation === operation);

  /** 只有每个上游都存在且有可用状态时才开放当前步骤。 */
  const dependenciesReady = (step: TestWorkflowStep): boolean =>
    step.dependsOn.every((operation) => {
      const dependency = stepFor(operation);
      return dependency !== undefined && usableState(dependency);
    });

  /** 重算尚未完成步骤的依赖锁；运行中、过期结果及带旧结果的失败状态不被覆盖。 */
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
   * 仅序列化允许恢复的步骤与选择条件，session-only 结果不会写入浏览器会话快照。
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
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

  /** 把恢复快照写入项目专属 sessionStorage；存储失败不影响页面执行，服务端产物仍是持久真源。 */
  const persist = () => {
    if (typeof window === "undefined" || !pid) return;
    try {
      window.sessionStorage.setItem(storageKey, JSON.stringify(storedWorkflow()));
    } catch {
      // Browser storage is a refresh convenience; persisted server artifacts remain authoritative.
    }
  };

  /**
   * 只接受版本匹配的会话快照，恢复可持久步骤及选择条件；损坏快照按无缓存处理。
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
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
   * 用服务端完成清单及来源 revision 校正会话状态；资料变化或服务端标记失效时保留内容并标为 stale。
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

  /** 先恢复会话内容，再请求服务端工作流状态；失败显示恢复错误并保留已恢复结果。 */
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

  /** 阻止未知、锁定或运行中的步骤，并再次核对全部上游依赖可用。 */
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
   * 保存运行前快照后标为 running；后续失败可恢复旧结果，未满足执行条件时不开始。
   * @param operation 工作流操作名。
   * @param options 沿用当前 TypeScript 类型约束的输入。
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
   * 沿 dependsOn 关系求传递下游集合，用于上游变化后的连带失效。
   * @param operation 工作流操作名。
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

  /** 只把已有结果或已完成的下游标为 stale，不凭空制造下游产物。 */
  const markDependentsStale = (operation: string) => {
    dependentOperations(operation).forEach((dependent) => {
      const step = stepFor(dependent);
      if (step && (step.result !== null || step.state === "completed")) step.state = "stale";
    });
  };

  /** 标记当前步骤及可选下游失效，保留旧内容供参考，再更新依赖锁与会话快照。 */
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
   * 选择条件偏离已生成结果时暂存原状态并标失效；用户改回原选择后恢复这份状态基线。
   * @param operation 工作流操作名。
   * @param selection 沿用当前 TypeScript 类型约束的输入。
   * @param includeDependents 沿用当前 TypeScript 类型约束的输入。
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
   * 完整成功后接纳结果、选择条件和产物 revision；重生成或输入变化会让下游旧结果失效。
   * @param operation 工作流操作名。
   * @param result 沿用当前 TypeScript 类型约束的输入。
   * @param selection 沿用当前 TypeScript 类型约束的输入。
   * @param metadata 沿用当前 TypeScript 类型约束的输入。
   * @param options 沿用当前 TypeScript 类型约束的输入。
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
   * 有运行前有效结果时恢复其状态、内容和产物键；首次执行失败才保留 failed 状态。
   * @param operation 工作流操作名。
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

  /** 已有结果或完成记录时要求用户确认替换；没有旧产物时直接允许。 */
  const confirmReplacement = async (operation: string): Promise<boolean> => {
    const step = stepFor(operation);
    if (!step || (step.result === null && step.state !== "completed" && step.state !== "stale")) {
      return true;
    }
    return confirmResultReplacement(step.label);
  };

  /** 用户确认替换后才调用页面提供的生成动作，取消确认不会启动请求。 */
  const regenerateStep = async (
    operation: string,
    runner: () => Promise<boolean>,
  ): Promise<boolean> => {
    if (!(await confirmReplacement(operation))) return false;
    return runner();
  };

  /**
   * 仅清除本地步骤结果与选择基线，不向服务端发送删除产物请求。
   * @param operation 工作流操作名。
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

  /** 读取步骤的当前可见结果，缺失时统一返回 null。 */
  const resultFor = <Result = unknown>(operation: string): Result | null =>
    (stepFor(operation)?.result as Result | null | undefined) ?? null;

  /**
   * 读取生成该结果时的选择条件；没有记录时返回空对象。
   * @param operation 工作流操作名。
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   */
  const selectionFor = (operation: string): Record<string, unknown> =>
    selections.get(operation) ?? {};

  /** 只选取该步骤声明的 selectionFields，再进行稳定键序规范化。 */
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

  /** 按步骤的选择字段比较两份输入；未知步骤不视为匹配。 */
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
   * 将当前输入与已生成结果的选择条件比较；无选择字段的步骤无需额外匹配。
   * @param operation 工作流操作名。
   * @param selection 沿用当前 TypeScript 类型约束的输入。
   * @returns 保持当前 TypeScript 返回类型与调用方约定。
   */
  const selectionMatches = (operation: string, selection: Record<string, unknown>): boolean => {
    const step = stepFor(operation);
    if (!step) return false;
    if (step.selectionFields.length === 0) return true;
    const savedSelection = selections.get(operation);
    if (!savedSelection) return false;
    return selectionsMatch(operation, savedSelection, selection);
  };

  /** 结果内容或 completed/stale 状态均表示已有产物记录，可能仍需要从服务端恢复正文。 */
  const hasSavedResult = (operation: string): boolean => {
    const step = stepFor(operation);
    return Boolean(
      step && (step.result !== null || step.state === "completed" || step.state === "stale"),
    );
  };

  /** 按结果是否为 null 判断可见性；调用方应传入已定义的 operation。 */
  const hasVisibleResult = (operation: string): boolean => stepFor(operation)?.result !== null;

  /** 可见结果还必须匹配当前选择条件，避免展示其他目标的产物。 */
  const hasVisibleResultFor = (operation: string, selection: Record<string, unknown>): boolean =>
    hasVisibleResult(operation) && selectionMatches(operation, selection);

  /** 有服务端完成记录但本地缺少正文的持久步骤，需要另行恢复结果。 */
  const needsResultRecovery = (operation: string): boolean => {
    const step = stepFor(operation);
    return Boolean(
      step && step.persistResult && step.state === "completed" && step.result === null,
    );
  };

  /** 为 stale 步骤提供仅供参考的提示，未过期步骤不显示此警告。 */
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
