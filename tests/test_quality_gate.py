from framework.multi_agent.coordinator import Coordinator
from framework.multi_agent.pipeline import AgentPipeline


class _StaticCreator:
    def generate(self, requirement_chunks, module):
        return [
            {
                "test_id": "TC-DEMO-001",
                "module": module,
                "title": "demo",
                "steps": ["open page"],
                "expected": "page opens",
                "type": "positive",
            }
        ]


class _ErrorAuditor:
    def audit(self, cases, requirement_chunks):
        return {
            "passed": False,
            "issues": [
                {
                    "severity": "error",
                    "type": "hallucination",
                    "description": "missing evidence",
                }
            ],
            "summary": "failed",
        }


class _PassingAuditor:
    def audit(self, cases, requirement_chunks):
        return {"passed": True, "issues": [], "summary": "passed"}


def _coordinator(auditor):
    coordinator = Coordinator(use_rl=False)
    coordinator.creator = _StaticCreator()
    coordinator.auditor = auditor
    coordinator._regenerate = lambda cases, chunks, issues: cases
    return coordinator


def test_error_result_cannot_leave_generation_after_max_iterations():
    result = _coordinator(_ErrorAuditor()).run([{"content": "demo"}], "demo")

    assert result["accepted"] is False
    assert result["eligible_for_codegen"] is False
    assert result["termination_status"] == "failed_max_iterations"
    assert result["passed"] is False
    assert all(item["decision"] == "continue" for item in result["history"])


def test_auditor_pass_is_eligible_for_code_generation():
    result = _coordinator(_PassingAuditor()).run([{"content": "demo"}], "demo")

    assert result["accepted"] is True
    assert result["eligible_for_codegen"] is True
    assert result["termination_status"] == "accepted_audit"
    assert result["total_iterations"] == 1


def test_pipeline_excludes_failed_review_cases_from_code_generation(tmp_path):
    pipeline = AgentPipeline(modules=["demo"], output_dir=str(tmp_path / "generated"))
    pipeline._build_rag = lambda: ([], object())
    pipeline._run_generation = lambda retriever: {
        "demo": {
            "eligible_for_codegen": False,
            "cases": [{"test_id": "TC-BLOCKED"}],
        }
    }
    pipeline._evaluate = lambda cases, chunks, healing: {"case_count": len(cases)}
    pipeline._save_result = lambda run_id, result: "result.json"

    def _must_not_generate(cases):
        raise AssertionError("failed review cases reached code generation")

    pipeline._run_code_generation = _must_not_generate

    result = pipeline.run()

    assert result["num_cases"] == 0
    assert result["artifacts"]["page_files"] == []
