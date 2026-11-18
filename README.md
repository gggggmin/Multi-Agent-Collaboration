# Multi-Agent Requirement-Driven Test Generation

This project is a thesis prototype for generating automated tests from requirement documents:

1. RAG parses requirement Markdown into semantic chunks.
2. Creator/Auditor agents generate and review structured test cases.
3. Page/Test agents generate Playwright + Pytest code with Page Object Model.
4. The generated tests run against the local Flask ecommerce target app.
5. The self-healing module diagnoses execution failures and applies repair strategies.

## Quick Verification

```bash
python scripts/verify_project.py
```

Expected result:

```text
26 passed
[verify] OK: full generated suite passed
```

On Windows, Playwright may need permission to start browser subprocesses. If a
sandboxed run fails with `PermissionError: [WinError 5]`, rerun the verification
outside the restricted sandbox before treating it as a framework failure.

## Self-Healing Demo

```bash
python scripts/run_healing_demo.py
```

The demo injects an over-broad Playwright locator, verifies the failure,
classifies it as a locator issue, repairs it, and reruns the healed script.
The report is written to `experiments/results/healing_demo.json`.

The verification script compiles the framework, runs the full pipeline, starts the target Flask app, executes the generated Playwright tests, and stops the app.

## Common Commands

```bash
python main.py rag --query "登录失败"
python main.py generate --module login --no-rl
python main.py pipeline --no-rl
python main.py heal artifacts/generated/output/test_search.py --dir artifacts/generated/output --fix
python main.py experiment --type healing
python scripts/run_healing_demo.py
```

## Configuration

Use `.env.example` as the template. The default embedding backend is `tfidf` because it is deterministic and avoids HuggingFace cache/symlink issues on Windows.

To use sentence-transformers explicitly:

```bash
set EMBEDDING_BACKEND=sentence-transformers
```

## Current Demo Scope

The verified target app is `target_app/`, a Flask ecommerce demo covering login, search, cart, and checkout. The generated suite currently covers 26 end-to-end cases.

## Repository Layout

- `framework/`: generation, audit, reinforcement-learning, and self-healing code.
- `experiments/`: reproducible benchmarks and research evaluation scripts.
- `target_app/`: compact Flask application used by the verified test suite.
- `my-store/`: larger Spree/Next.js system used for realistic experiments.
- `tests/`: framework unit and integration tests.
- `scripts/`: verification, demos, and document-generation utilities.
- `docs/`: project notes, thesis material, proposals, and presentations.
- `artifacts/`: local generated tests, logs, renders, and build caches; heavy artifacts are ignored by Git.

## Thesis Evidence Artifacts

- `experiments/results/healing_demo.json`: strict-mode locator failure before/after self-healing.
- `experiments/results/agent_traces/*.jsonl`: prompt/response traces for Creator, Auditor, and Healing agents when tracing is enabled.
- `experiments/results/agent_pipeline_*.json`: generated cases, artifacts, and evaluation metrics for each pipeline run.
