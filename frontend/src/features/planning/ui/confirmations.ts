// 所属功能的业务确认边界，用户取消后不触发后续上传、恢复或结果替换动作。
import { ElMessageBox } from "@/shared/ui/messages";

/**
 * 说明计划重新生成会影响下游有效性，用户确认后才启动替换流程。
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
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
