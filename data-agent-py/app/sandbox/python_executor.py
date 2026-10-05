"""Python 代码沙箱执行器。

对应 Java 的 SimplePythonExecutor。

【为什么必须用 Docker】
  要执行的代码是**大模型现写的**，不能直接在本机跑。
  一个跑野了的分支就可能删你文件、偷你环境变量、往外发数据。
  所以要扔进容器里，并把资源锁死。

【那串参数是安全边界，一条都不能省】
    --network none                    断网：代码不能往外发数据
    --cpus 1                          限 1 核：不能把机器跑满
    --memory 512m                     限内存：不能吃光内存
    --pids-limit 128                  限进程数：防 fork 炸弹
    --security-opt no-new-privileges  禁止提权
    -v <临时目录>:/work:ro             只读挂载：容器内改不了宿主机文件

【执行模型】
  把代码写进 script.py、输入数据写进 input.json，
  容器里跑 python script.py，input.json 通过 stdin 喂进去。
"""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from app import settings
from app.domain.python_result import PythonExecutionResult

logger = logging.getLogger(__name__)

def execute(
    python_code: str,
    input_json: str,
    timeout_sec: int | None = None,
) -> PythonExecutionResult:
    """在 Docker 沙箱里执行 Python 代码。

    注意：这个函数**不抛异常**，失败会包装在返回值的 success=False 里。
    调用方（PythonExecuteNode）负责把它转成错误标记。
    """
    timeout_sec = timeout_sec or settings.PYTHON_SANDBOX_TIMEOUT
    work_dir = Path(tempfile.mkdtemp(prefix="ai_python_exec_"))
    try:
        script_file = work_dir / "script.py"
        data_file = work_dir / "input.json"
        script_file.write_text(python_code, encoding="utf-8")
        data_file.write_text(input_json, encoding="utf-8")

        if not _docker_available():
            return PythonExecutionResult(
                success=False,
                output="",
                error=(
                    "需要 Docker 才能安全执行 Python 代码，但没有检测到。"
                    "请先启动 Docker Desktop。"
                ),
            )

        image = settings.PYTHON_SANDBOX_IMAGE
        memory = settings.PYTHON_SANDBOX_MEMORY

        command = [
            "docker", "run", "--rm", "-i",
            "--network", "none",
            "--cpus", "1",
            "--memory", memory,
            "--pids-limit", "128",
            "--security-opt", "no-new-privileges",
            "-v", f"{work_dir}:/work:ro",
            "-w", "/work",
            image,
            "python", "/work/script.py",
        ]

        try:
            with open(data_file, "rb") as stdin:
                proc = subprocess.run(  # noqa: S603 - 参数是固定列表，没有 shell 注入面
                    command,
                    stdin=stdin,
                    capture_output=True,
                    timeout=timeout_sec,
                    encoding="utf-8",
                    errors="replace",
                )
        except subprocess.TimeoutExpired:
            return PythonExecutionResult(
                success=False,
                output="",
                error=f"执行超时（超过 {timeout_sec} 秒）",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("启动沙箱失败")
            return PythonExecutionResult(success=False, output="", error=str(exc))

        output = (proc.stdout or "").strip()
        error = (proc.stderr or "").strip()
        success = proc.returncode == 0
        if not success:
            error = f"{error}\n\nSandbox image: {image}".strip()
        return PythonExecutionResult(success=success, output=output, error=error)

    finally:
        # 不管成功失败都清掉临时目录（里面是模型生成的代码和业务数据）
        shutil.rmtree(work_dir, ignore_errors=True)


def _docker_available() -> bool:
    """检查 docker 命令可用且守护进程在跑。"""
    try:
        proc = subprocess.run(  # noqa: S603
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode == 0
    except Exception:  # noqa: BLE001
        return False
