"""Create and verify a reproducible self-healing demo case.

The demo intentionally breaks the generated combination-search test by using a
too-broad submit-button locator. Playwright strict mode fails, the diagnoser
classifies the failure as a locator issue, and the healing agent rewrites the
locator to a semantic role-based selector.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_APP = ROOT / "target_app"
RESULTS_DIR = ROOT / "experiments" / "results"
sys.path.insert(0, str(ROOT))


def run(cmd: list[str], *, cwd: Path = ROOT, timeout: int = 180, check: bool = False) -> dict:
    print(f"\n[healing-demo] {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    print(result.stdout[-2000:])
    if result.stderr:
        print(result.stderr[-1000:])
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def wait_for_health(url: str, timeout: int = 20) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    print(f"[healing-demo] target app ready: {url}")
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"target app did not become healthy: {last_error}")


def start_target_app() -> subprocess.Popen:
    process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=TARGET_APP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    wait_for_health("http://localhost:5000/health")
    return process


def prepare_broken_case(source_dir: Path, demo_dir: Path) -> Path:
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    shutil.copytree(source_dir, demo_dir)

    test_file = demo_dir / "test_search.py"
    content = test_file.read_text(encoding="utf-8")
    good = 'page.get_by_role("button", name="搜索").click()'
    bad = 'page.locator("button[type=\'submit\']").click()'
    if good not in content:
        raise RuntimeError("expected semantic search-button locator was not found")
    test_file.write_text(content.replace(good, bad), encoding="utf-8")
    return test_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strict-mode locator self-healing demo.")
    parser.add_argument("--source", default="artifacts/generated/output_verify_e2e", help="verified generated suite")
    parser.add_argument("--demo-dir", default="artifacts/generated/output_healing_demo", help="temporary broken suite")
    args = parser.parse_args()

    source_dir = ROOT / args.source
    demo_dir = ROOT / args.demo_dir
    if not source_dir.exists():
        run([sys.executable, "scripts/verify_project.py", "--output", args.source, "--skip-pytest"], check=True)

    broken_script = prepare_broken_case(source_dir, demo_dir)

    from framework.self_healing import ErrorDiagnoser, HealingAgent, SandboxExecutor

    process = start_target_app()
    try:
        executor = SandboxExecutor(str(demo_dir))
        # 只执行被注入故障的单个用例。若把整个 search 模块都跑一遍，
        # 运行时长会污染“修复成本”，还可能被沙箱超时误判为定位器故障。
        before_target = f"{broken_script}::test_search_005"
        before = executor.run_script(before_target, timeout=60)
        diagnosis = ErrorDiagnoser().diagnose(before)
        script_content = broken_script.read_text(encoding="utf-8")

        healer = HealingAgent()
        heal_result = healer.heal(script_content, diagnosis)
        fixed_script = broken_script.with_name("test_search_healed.py")
        fixed_script.write_text(heal_result.get("fixed_code", script_content), encoding="utf-8")
        after_target = f"{fixed_script}::test_search_005"
        after = executor.run_script(after_target, timeout=60)
        heal_result["success"] = after.get("success", False)
        healer.record_strategy_result(
            heal_result.get("strategy", "unknown"),
            heal_result.get("error_category", "unknown"),
            heal_result["success"],
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    report = {
        "case": "playwright_strict_mode_locator",
        "broken_script": str(broken_script),
        "fixed_script": str(fixed_script),
        "pytest_node": "test_search_005",
        "before": {
            "success": before.get("success", False),
            "returncode": before.get("returncode"),
            "executor_error": before.get("error", ""),
            "error_excerpt": (before.get("stdout", "") + before.get("stderr", ""))[-1200:],
        },
        "diagnosis": diagnosis,
        "healing": {
            "success": heal_result.get("success", False),
            "strategy": heal_result.get("strategy"),
            "attempts": heal_result.get("attempts"),
            "error_category": heal_result.get("error_category"),
        },
        "after": {
            "success": after.get("success", False),
            "returncode": after.get("returncode"),
            "executor_error": after.get("error", ""),
            "stdout_excerpt": after.get("stdout", "")[-1200:],
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / "healing_demo.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[healing-demo] report: {report_path}")
    print(f"[healing-demo] before_success={report['before']['success']}")
    print(f"[healing-demo] after_success={report['after']['success']}")
    if not report["after"]["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
