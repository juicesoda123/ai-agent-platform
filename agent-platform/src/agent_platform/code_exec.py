"""代码执行沙箱 —— Agent 能写 Python → 运行 → 拿结果。"""

import subprocess
import tempfile
import os


def execute_python(code: str, timeout: int = 10) -> str:
    """执行 Python 代码，返回 stdout+stderr。"""
    # 写临时文件
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
    tmp.write(code)
    tmp.close()

    try:
        proc = subprocess.run(
            ["python", tmp.name],
            capture_output=True, text=True, timeout=timeout,
            cwd=os.path.dirname(tmp.name),
        )
        out = proc.stdout
        if proc.stderr:
            out += "\n[stderr]\n" + proc.stderr
        if proc.returncode != 0:
            out += f"\n[exit code: {proc.returncode}]"
        return out[:3000] if out.strip() else "(无输出)"
    except subprocess.TimeoutExpired:
        return f"执行超时 ({timeout}s)，请简化代码或拆分步骤。"
    except Exception as e:
        return f"执行失败: {e}"
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def execute_shell(command: str, timeout: int = 15) -> str:
    """执行 shell 命令（受限：只能读文件，不能写/删）。"""
    # 安全检查
    dangerous = ["rm -rf", "del /f", "format", "shutdown", "reboot", "> /dev/", "mkfs"]
    for d in dangerous:
        if d in command.lower():
            return f"危险命令被拦截: {d}"

    try:
        proc = subprocess.run(
            command, shell=True,
            capture_output=True, text=True, timeout=timeout,
        )
        out = proc.stdout
        if proc.stderr:
            out += "\n[stderr]\n" + proc.stderr
        return out[:3000] if out.strip() else "(无输出)"
    except subprocess.TimeoutExpired:
        return f"执行超时 ({timeout}s)"
    except Exception as e:
        return f"执行失败: {e}"
