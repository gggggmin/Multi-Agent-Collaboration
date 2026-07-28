"""沙箱执行器 — 在子进程中运行测试脚本并捕获输出"""
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


class SandboxExecutor:
    """沙箱执行器"""

    def __init__(self, work_dir: str = "."):
        self.work_dir = Path(work_dir)

    def run_script(self, script_path: str, timeout: int = 30) -> Dict:
        """运行单个测试脚本"""
        spath = Path(script_path)
        if not spath.exists():
            return {"success": False, "error": f"脚本不存在: {script_path}",
                    "stdout": "", "stderr": ""}

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(spath), "-v", "--tb=short"],
                capture_output=True, text=True, timeout=timeout,
                cwd=self.work_dir,
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
