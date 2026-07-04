# Clause — Launch Checklist

## Week 1 — Get it running and make it yours
- [ ] Save the `clause/` folder somewhere permanent on your machine
- [ ] `pip install -r requirements.txt` → `uvicorn backend.main:app --reload --port 8734` → confirm the mock demo works (compile sample PRD, run, see 11/14 passing)
- [ ] Read every file until you can explain each one without notes — interviewers will probe this
- [ ] Create a GitHub repo, push, and commit in small pieces going forward (commit history is proof of work)
- [ ] Get an Anthropic API key ($5 goes far), set `.env`, switch `LLM_MODE=live`
- [ ] Run 3 real PRDs through live mode (write one, borrow templates for two) and note where extraction/linting is wrong

## Weeks 2–3 — Core product work
- [ ] Tune the 4 prompts in `backend/prompts.py` until live output beats mock quality — keep before/after examples
- [ ] Add UI toggle for `http` target so users can point Clause at their own endpoint
- [ ] Add judge override: PM can flip a verdict, store the disagreement (this is your calibration story)
- [ ] PRD versioning: show diff between v1/v2 clauses and what recompiled

## Weeks 4–5 — Ship it
- [ ] Deploy: frontend + API on Railway or Fly.io (single service is fine), custom domain (~$10)
- [ ] Add basic auth (Supabase auth is fastest) and per-user projects
- [ ] Seed 3 polished example PRDs visitors can try in one click
- [ ] Record a 2-minute demo video: vague clause flagged → rewrite → run → failure mapped to a PRD clause

## Week 6 — Launch
- [ ] Write launch post: "Show HN: Clause — PRDs that test themselves" (lead with the demo, not the tech)
- [ ] Post to r/ProductManagement, Lenny's Slack, Product School community, LinkedIn
- [ ] Add instrumentation first: signups, first PRD compiled (activation), first failed clause seen (aha), repeat runs (retention)
- [ ] Reply to every comment; log feature requests as GitHub issues

## Ongoing — Resume and interviews
- [ ] Resume bullet: built + shipped an eval tool for PMs; cite real numbers (users, PRDs compiled, pass-rate regressions caught)
- [ ] Prepare the 90-second interview story: the gap ("evals are the new PM skill, but no tool starts from the PRD"), the insight (testability linter), one metric, one thing you'd do differently
- [ ] Write one short blog/LinkedIn post on what you learned about LLM-as-judge reliability — it markets the project and you
