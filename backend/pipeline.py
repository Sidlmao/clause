"""Compile pipeline: PRD text → clauses → lint grades → eval cases."""
import asyncio
import json

from . import db
from .llm import get_provider


async def compile_prd(prd_id: str, prd_text: str, product_context: str = ""):
    """Extract clauses, lint each, generate evals for testable ones. Persists everything."""
    provider = get_provider()
    clauses = await provider.complete("extract", {"prd_text": prd_text})

    # Lint all clauses concurrently (bounded).
    sem = asyncio.Semaphore(5)

    async def lint(c):
        async with sem:
            return await provider.complete("lint", c)

    lints = await asyncio.gather(*[lint(c) for c in clauses])

    conn = db.connect()
    try:
        stored = []
        for i, (c, l) in enumerate(zip(clauses, lints)):
            cid = db.new_id()
            db.insert(conn, "clauses", {
                "id": cid, "prd_id": prd_id, "position": i,
                "text": c["text"], "category": c["category"],
                "testability": l["testability"], "lint_reason": l["reason"],
                "rewrite": l.get("rewrite"),
            })
            stored.append({**c, "id": cid, **l})

        # Generate eval cases for testable clauses.
        async def gen(c):
            async with sem:
                return c, await provider.complete("evalgen", {
                    "text": c["text"], "category": c["category"],
                    "product_context": product_context,
                })

        testable = [c for c in stored if c["testability"] == "testable"]
        for c, cases in await asyncio.gather(*[gen(c) for c in testable]):
            for case in cases:
                db.insert(conn, "eval_cases", {
                    "id": db.new_id(), "clause_id": c["id"], "input": case["input"],
                    "kind": case["kind"], "checker_type": case["checker_type"],
                    "checker_config": json.dumps(case["checker_config"]),
                })
        return stored
    finally:
        conn.close()
