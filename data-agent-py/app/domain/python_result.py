"""Python 代码执行结果。对应 Java 的 PythonExecutionResult。"""

from pydantic import BaseModel, Field


class PythonExecutionResult(BaseModel):
    """沙箱执行 Python 代码的产出。"""

    success: bool = Field(default=False, description="是否执行成功")
    output: str = Field(default="", description="标准输出")
    error: str = Field(default="", description="标准错误 / 失败原因")
