"""Async eval runner: executes a compiled suite against a target and stores results.

Targets:
- "demo": built-in fake support bot (see demo_target) — lets the product demo itself.
- "http": POST {"input": ...} to the user's endpoint, expects {"output": ...}.

Deterministic checkers run as real Python (no LLM). "judge" delegates to the provider.
"""
import asyncio
import json
import re
import time
from typing import Optional

import httpx

from . import db
from .llm import get_provider

CONCURRENCY = 5
RETRIES = 2


# ------------------------------------------------------------------ demo target
# A deliberately imperfect support bot: it breaks the refund guardrail under
# pressure and rambles past length limits — so a first run shows real failures.

def demo_target(user_input: str) -> str:
    low = user_input.lower()
    if "sue" in low or ("refund" in low and ("demand" in low or "promise" in low)):
        return ("I completely understand your frustration, and I promise you will "
                "receive a full refund within 24 hours, guaranteed.")
    if "lawyer" in low:
        return ("I can't act as your lawyer, but our support team can review your "
                "case. I've flagged this conversation for a human specialist.")
    if "broken" in low or "damaged" in low:
        return ("Sorry about that! You can start a return from Orders → Return Item, "
                "or I can connect you with a human agent to review options.")
    if "everything about every product" in low:
        return ("Great question! " + "We offer many products across many categories. " * 40)
    if "order" in low:
        return ("Your order is on the way — track it anytime at the link in your "
                "confirmation email. Anything else I can help with?")
    if "hate" in low or "useless" in low:
        return ("I'm sorry this has been frustrating. I want to make it right — "
                "I can connect you with a human agent right now if you'd like.")
    return "Happy to help! Could you tell me a bit more about what you need?"


# ------------------------------------------------------------------ checkers

def run_checker(checker_type: str, config: dict, output: str):
    """Deterministic checkers. Returns (verdict, reason) or None if judge-type."""
    if checker_type == "contains":
        ok = config["value"].lower() in output.lower()
        return ("pass" if ok else "fail",
                f'Output {"contains" if ok else "is missing"} "{config["value"]}".')
    if checker_type == "not_contains":
        ok = config["value"].lower() not in output.lower()
        return ("pass" if ok else "fail",
                f'Forbidden substring "{config["value"]}" {"absent" if ok else "present"}.')
    if checker_type == "regex":
        ok = re.search(config["pattern"], output) is not None
        return ("pass" if ok else "fail", f'Pattern /{config["pattern"]}/ {"matched" if ok else "not matched"}.')
    if checker_type == "max_words":
        n = len(output.split())
        ok = n <= config["value"]
        return ("pass" if ok else "fail", f"Output is {n} words (limit {config['value']}).")
    if checker_type == "json_valid":
        try:
            json.loads(output)
            return ("pass", "Output is valid JSON.")
        except json.JSONDecodeError as e:
            return ("fail", f"Invalid JSON: {e}.")
    return None  # judge


async def get_output(target_kind: str, target_url: Optional[str], user_input: str) -> str:
    if target_kind == "demo":
        return demo_target(user_input)
    last_err = None
    for attempt in range(RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(target_url, json={"input": user_input})
                r.raise_for_status()
                return r.json()["output"]
        except Exception as e:  # retry with backoff
            last_err = e
            await asyncio.sleep(1.5 ** attempt)
    raise RuntimeError(f"target unreachable after {RETRIES + 1} attempts: {last_err}")


# ------------------------------------------------------------------ suite runner

async def run_suite(run_id: str, prd_id: str, target_kind: str, target_url: Optional[str] = None):
    provider = get_provider()
    conn = db.connect()
    try:
        clauses = db.clauses_for_prd(conn, prd_id)
        work = []
        for clause in clauses:
            for case in db.cases_for_clause(conn, clause["id"]):
                work.append((clause, case))

        sem = asyncio.Semaphore(CONCURRENCY)

        async def one(clause, case):
            async with sem:
                t0 = time.time()
                try:
                    output = await get_output(target_kind, target_url, case["input"])
                    det = run_checker(case["checker_type"], case["checker_config"], output)
                    if det is not None:
                        verdict, reason = det
                    else:
                        j = await provider.complete("judge", {
                            "rubric": case["checker_config"].get("rubric", clause["text"]),
                            "red_flags": case["checker_config"].get("red_flags", []),
                            "input": case["input"], "output": output,
                        })
                        verdict, reason = j["verdict"], j["reason"]
                except Exception as e:
                    output, verdict, reason = None, "error", str(e)
                return {
                    "id": db.new_id(), "run_id": run_id, "eval_case_id": case["id"],
                    "clause_id": clause["id"], "output": output, "verdict": verdict,
                    "reason": reason, "latency_ms": int((time.time() - t0) * 1000),
                }

        results = await asyncio.gather(*[one(c, e) for c, e in work])
        for r in results:
            db.insert(conn, "results", r)
        conn.execute("UPDATE runs SET status='done' WHERE id=?", (run_id,))
        conn.commit()
    except Exception:
        conn.execute("UPDATE runs SET status='error' WHERE id=?", (run_id,))
        conn.commit()
        raise
    finally:
        conn.close()
