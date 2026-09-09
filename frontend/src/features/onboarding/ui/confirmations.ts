// 所属功能的业务确认边界，用户取消后不触发后续上传、恢复或结果替换动作。
import { ElMessageBox } from "@/shared/ui/messages";
import type { SetupGroup } from "@/entities/project/model/setup";

/**
 * 展示项目名称和各组文件数，确认后才允许创建及上传。
 * @param name 沿用当前 TypeScript 类型约束的输入。
 * @param counts 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
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

/**
 * 切换准备中的项目之前说明当前恢复记录的处理影响。
 * @param previousPid 沿用当前 TypeScript 类型约束的输入。
 * @param nextPid 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
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

/**
 * 丢弃本地恢复记录前确认；不会据此删除服务器项目。
 * @param pid 项目 ID。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
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

/**
 * 资料准备未结束时确认离开，避免误认为所有上传已完成。
 * @param pid 项目 ID。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
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

/**
 * 从待上传列表移出文件前确认，不删除已存储的服务器文件。
 * @param filename 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
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
