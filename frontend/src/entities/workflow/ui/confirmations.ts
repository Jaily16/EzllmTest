// 工作流通用展示与确认交互，明确区分缓存恢复、已保存结果及会话草稿。
import { ElMessageBox } from "@/shared/ui/messages";

/**
 * 告知旧结果替换影响并等待用户确认，取消时不启动生成。
 * @param label 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
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

/**
 * 清空会话结果前确认其保留边界，不把操作描述为删除长期项目产物。
 * @param label 沿用当前 TypeScript 类型约束的输入。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
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
