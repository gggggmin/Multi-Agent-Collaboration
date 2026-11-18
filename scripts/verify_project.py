"""Run a reproducible end-to-end verification for the thesis prototype."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_APP = ROOT / "target_app"


def run(cmd: list[str], *, cwd: Path = ROOT, timeout: int = 180) -> None:
    print(f"\n[verify] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, text=True, timeout=timeout)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def wait_for_health(url: str, timeout: int = 20) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    print(f"[verify] target app ready: {url}")
                    return
        except Exception as exc:  # pragma: no cover - diagnostic only
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"target app did not become healthy: {last_error}")


def start_target_app() -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("FLASK_ENV", "production")
    process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=TARGET_APP,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    wait_for_health("http://localhost:5000/health")
    return process


def compile_generated(output_dir: Path) -> None:
    files = [str(path) for path in output_dir.rglob("*.py")]
    if not files:
        raise RuntimeError(f"no generated Python files found in {output_dir}")
    run([sys.executable, "-m", "py_compile", *files], timeout=60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify RAG -> agents -> codegen -> pytest.")
    parser.add_argument("--output", default="artifacts/generated/output_verify_e2e", help="generated output directory")
    parser.add_argument("--use-rl", action="store_true", help="enable RL-AGS during generation")
    parser.add_argument("--skip-pytest", action="store_true", help="skip Playwright pytest execution")
    parser.add_argument("--pytest-timeout", type=int, default=180, help="pytest execution timeout in seconds")
    args = parser.parse_args()

    env = os.environ
    env.setdefault("EMBEDDING_BACKEND", "tfidf")

    output_dir = ROOT / args.output
    run([sys.executable, "-m", "compileall", "-q", "framework", "experiments", "target_app", "main.py", "config.py"])

    pipeline_cmd = [sys.executable, "main.py", "pipeline", "--output", args.output]
    if not args.use_rl:
        pipeline_cmd.append("--no-rl")
    run(pipeline_cmd, timeout=180)
    compile_generated(output_dir)

    if args.skip_pytest:
        print("[verify] skipped pytest execution")
        return

    process = start_target_app()
    try:
        run([sys.executable, "-m", "pytest", args.output, "-q", "--tb=short"], timeout=args.pytest_timeout)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    print("\n[verify] OK: full generated suite passed")


if __name__ == "__main__":
    main()
