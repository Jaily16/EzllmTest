"""生成流的稳定错误类型，不包含传输或 provider 实现。"""
from __future__ import annotations
class WorkflowStreamError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 500,
        retryable: bool = True,
    ) -> None:
        """保存流式错误的稳定代码、HTTP 状态和可重试标记，供生成接口编码错误事件。"""
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable

class TestPlanStreamError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, status: int = 500, retryable: bool = True
    ) -> None:
        """保存测试计划流的错误类别及重试语义；构造异常本身不保存或替换生成结果。"""
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable
