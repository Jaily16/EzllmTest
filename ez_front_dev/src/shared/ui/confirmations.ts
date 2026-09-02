import { ElMessageBox } from "@/shared/plugins/elementPlus";
import type { SetupGroup } from "@/features/onboarding/state/projectSetup";

export const confirmResultReplacement = async (label: string): Promise<boolean> => {
  try {
    await ElMessageBox.confirm(
      `重新生成“${label}”将替换已保存的有效结果，是否继续？`,
      "确认重新生成",
      {
        confirmButtonText: "重新生成",
        cancelButtonText: "保留原结果",
        type: "warning",
      },
    );
    return true;
  } catch {
    return false;
  }
};

export const confirmSessionOnlyResultReset = async (label: string): Promise<boolean> => {
  try {
    await ElMessageBox.confirm(
      `“${label}”仅保留在当前页面。清空后无法从项目中恢复，是否继续？`,
      "确认清空当前结果",
      {
        confirmButtonText: "清空结果",
        cancelButtonText: "保留结果",
        type: "warning",
      },
    );
    return true;
  } catch {
    return false;
  }
};

export const confirmProjectCreation = async (
  name: string,
  counts: Record<SetupGroup, number>,
): Promise<boolean> => {
  try {
    await ElMessageBox.confirm(
      `将创建项目“${name}”并上传：测试知识库 ${counts.knowledge} 个、业务需求 ${counts.requirements} 个、开发设计 ${counts.design} 个文件。上传完成后不会自动启动模型分析。`,
      "确认创建并上传",
      {
        confirmButtonText: "创建并上传",
        cancelButtonText: "继续检查",
        type: "info",
      },
    );
    return true;
  } catch {
    return false;
  }
};

export const confirmRecoverySwitch = async (
  previousPid: string,
  nextPid: string,
): Promise<boolean> => {
  try {
    await ElMessageBox.confirm(
      `本机正在恢复 ${previousPid}。切换到 ${nextPid} 会替换浏览器中的快速恢复指针，但不会删除服务器上的项目或文档。请先保存原项目 ID。`,
      "切换恢复项目",
      {
        confirmButtonText: "切换项目",
        cancelButtonText: "保留原项目",
        type: "warning",
      },
    );
    return true;
  } catch {
    return false;
  }
};

export const confirmRecoveryDiscard = async (pid: string): Promise<boolean> => {
  try {
    await ElMessageBox.confirm(
      `将清除浏览器中 ${pid} 的快速恢复状态，但不会删除服务器上的项目或文档。请确认已妥善保存项目 ID。`,
      "创建其他项目",
      {
        confirmButtonText: "清除并继续",
        cancelButtonText: "保留恢复状态",
        type: "warning",
      },
    );
    return true;
  } catch {
    return false;
  }
};

export const confirmProjectSetupExit = async (pid: string): Promise<boolean> => {
  try {
    await ElMessageBox.confirm(
      `项目 ${pid} 尚未完成。离开后进度仍会保留，可凭项目 ID 返回继续；不会删除服务器上的项目或文档。`,
      "离开资料上传",
      {
        confirmButtonText: "保留并离开",
        cancelButtonText: "保留恢复状态",
        type: "warning",
      },
    );
    return true;
  } catch {
    return false;
  }
};

export const confirmPendingFileRemoval = async (filename: string): Promise<boolean> => {
  try {
    await ElMessageBox.confirm(
      `仅从当前待上传清单移除“${filename}”，不会删除已上传的服务器文档。`,
      "移除待上传文档",
      {
        confirmButtonText: "移除",
        cancelButtonText: "保留文件",
        type: "warning",
      },
    );
    return true;
  } catch {
    return false;
  }
};

export const confirmProjectAnalysisRegeneration = async (): Promise<boolean> => {
  try {
    await ElMessageBox.confirm(
      "重新生成期间，测试菜单和八类测试工作区会临时锁定。成功后新摘要、计划和菜单将替换当前版本；失败或取消会继续保留当前有效版本。新菜单可能改变可进入的测试类型，下游结果是否过期以服务器状态为准。",
      "确认重新生成测试计划",
      {
        confirmButtonText: "开始重新生成",
        cancelButtonText: "保留当前计划",
        type: "warning",
      },
    );
    return true;
  } catch {
    return false;
  }
};
