from framework.rl.safe_generation_env import GenerationAction, SafeGenerationEnv


def test_unsafe_accept_is_projected_to_targeted_revision():
    env = SafeGenerationEnv()
    env.reset(
        seed=1,
        options={
            "state": {
                "num_errors": 2,
                "num_hallucinations": 1,
                "num_warnings": 0,
                "coverage": 0.9,
                "evidence_consistency": 0.9,
            }
        },
    )

    action = env.project_safe_action(GenerationAction.ACCEPT)

    assert action == GenerationAction.REVISE_CONSISTENCY


def test_irrelevant_revision_is_projected_when_evidence_is_missing():
    env = SafeGenerationEnv()
    env.reset(
        seed=4,
        options={
            "state": {
                "num_errors": 1,
                "num_hallucinations": 1,
                "num_warnings": 1,
                "coverage": 0.9,
                "evidence_consistency": 0.2,
            }
        },
    )

    action = env.project_safe_action(GenerationAction.REVISE_BOUNDARY)

    assert action == GenerationAction.REFRESH_EVIDENCE


def test_direct_unsafe_accept_is_reported():
    env = SafeGenerationEnv()
    env.reset(
        seed=2,
        options={
            "state": {
                "num_errors": 1,
                "num_hallucinations": 0,
                "num_warnings": 0,
                "coverage": 0.9,
                "evidence_consistency": 0.9,
            }
        },
    )

    _, reward, terminated, truncated, info = env.step(GenerationAction.ACCEPT)

    assert terminated is True
    assert truncated is False
    assert info["unsafe_accept"] is True
    assert reward < 0


def test_clean_state_can_be_accepted():
    env = SafeGenerationEnv()
    env.reset(
        seed=3,
        options={
            "state": {
                "num_errors": 0,
                "num_hallucinations": 0,
                "num_warnings": 2,
                "coverage": 0.9,
                "evidence_consistency": 0.8,
            }
        },
    )

    _, reward, terminated, _, info = env.step(GenerationAction.ACCEPT)

    assert terminated is True
    assert info["accepted"] is True
    assert reward > 0
