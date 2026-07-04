# Clause — PRDs that test themselves

Write a PRD → Clause segments it into atomic requirement clauses, grades each for
**testability** (with suggested rewrites for vague ones), compiles testable clauses into a
runnable **eval suite**, executes it against your AI feature, and renders the PRD as a
living dashboard of which product promises are currently passing.

## Quick start (no API key needed)

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8734
# open http://localhost:8734
```

Click **Load sample → Compile to eval suite → Run against demo target.**
The built-in demo target is a deliberately imperfect support bot: it breaks the
"never promise refunds" guardrail under pressure and rambles past the length limit,
so your first run shows real failures mapped back to specific PRD clauses.

## Modes

- **mock** (default): deterministic heuristics stand in for the LLM at every stage.
  Fully offline. Exercises the real pipeline, runner, checkers, and UI.
- **live**: `cp .env.example .env`, add `ANTHROPIC_API_KEY`, set `LLM_MODE=live`,
  restart with `uvicorn backend.main:app --env-file .env`. The four prompts in
  `backend/prompts.py` take over extraction, linting, eval generation, and judging.

## Test your own AI feature

Expose it as `POST /your-endpoint` accepting `{"input": "..."}` and returning
`{"output": "..."}`, then run with `{"target_kind": "http", "target_url": "..."}`
(UI toggle coming; API supports it now).

## Architecture

```
frontend/index.html      single-file React UI (no build step)
backend/main.py          FastAPI routes + sample PRD + demo target endpoint
backend/pipeline.py      compile: extract clauses → lint testability → generate evals
backend/runner.py        async suite runner (httpx, semaphore, retries) + checkers
backend/llm.py           provider interface: LiveProvider (Anthropic) / MockProvider
backend/prompts.py       the four core prompts — the product's real IP
backend/db.py            SQLite (stdlib), swap for Supabase/Postgres in v0.2
```

Checkers: `contains`, `not_contains`, `regex`, `max_words`, `json_valid` run as plain
Python; `judge` uses LLM-as-judge with a PM-readable rubric. Deterministic-first keeps
runs cheap and reproducible.

## Roadmap to launch (weeks 5–8)

- Nightly scheduled runs + regression alerts ("model update broke clause 4.2")
- PRD version diffing → suite recompilation with change report
- `clause check` CLI + GitHub Action (PRD as merge gate)
- Notion/docx import, auth, hosted deployment (Vercel + Railway/Fly)
- Judge calibration: PM overrides judge verdicts, disagreement rate tracked
