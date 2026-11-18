"""沙箱执行器 — 在子进程中运行测试脚本并捕获输出"""
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


class SandboxExecutor:
    """沙箱执行器"""

    def __init__(self, work_dir: str = "."):
        self.work_dir = Path(work_dir).resolve()

    def run_script(self, script_path: str, timeout: int = 30) -> Dict:
        """运行单个测试脚本"""
        # pytest node id（如 test_x.py::test_case）也应被支持；文件存在性
        # 只检查 ``::`` 之前的路径，执行时再把选择器拼回去。
        raw_path, separator, node_selector = script_path.partition("::")
        spath = Path(raw_path)
        if not spath.is_absolute():
            direct = spath.resolve()
            work_relative = (self.work_dir / spath).resolve()
            spath = direct if direct.exists() else work_relative
        if not spath.exists():
            return {"success": False, "error": f"脚本不存在: {script_path}",
                    "stdout": "", "stderr": ""}

        try:
            project_root = Path(__file__).resolve().parents[2]
            process_env = os.environ.copy()
            existing_pythonpath = process_env.get("PYTHONPATH", "")
            process_env["PYTHONPATH"] = os.pathsep.join(
                part for part in (str(project_root), existing_pythonpath) if part
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    f"{spath}::{node_selector}" if separator else str(spath),
                    "-v",
                    "--tb=short",
                    "-p",
                    "no:cacheprovider",
                ],
                capture_output=True, text=True, timeout=timeout,
                cwd=self.work_dir,
                env=process_env,
            )
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:],  # 截取后2000字符
                "stderr": result.stderr[-2000:],
                "error": result.stderr[:500] if result.returncode != 0 else "",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "执行超时",
                    "stdout": "", "stderr": ""}
        except Exception as e:
            return {"success": False, "error": str(e),
                    "stdout": "", "stderr": ""}

    def run_pylint(self, script_path: str) -> Dict:
        """静态检查脚本"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pylint", str(script_path),
                 "--score=n", "--output-format=text"],
                capture_output=True, text=True, timeout=15,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout[-1000:],
            }
        except Exception as e:
            return {"success": False, "output": str(e)}
