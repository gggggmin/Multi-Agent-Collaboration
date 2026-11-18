from types import SimpleNamespace
from pathlib import Path

from framework.self_healing.executor import SandboxExecutor


def test_run_script_supports_pytest_node_id(monkeypatch):
    test_file = Path(__file__).resolve()
    work_dir = test_file.parent
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="passed", stderr="")

    monkeypatch.setattr("framework.self_healing.executor.subprocess.run", fake_run)

    result = SandboxExecutor(str(work_dir)).run_script(
        f"{test_file}::test_run_script_supports_pytest_node_id"
    )

    assert result["success"] is True
    assert captured["command"][3] == (
        f"{test_file}::test_run_script_supports_pytest_node_id"
    )
    assert captured["kwargs"]["cwd"] == work_dir
