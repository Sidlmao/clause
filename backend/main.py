"""Clause API — PRDs that test themselves.

Run:  uvicorn backend.main:app --reload --port 8734
UI:   http://localhost:8734
"""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import db
from .llm import get_provider
from .pipeline import compile_prd
from .runner import demo_target, run_suite

app = FastAPI(title="Clause", version="0.1.0")
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

SAMPLE_PRD = """# SupportBot — AI Customer Support Assistant (PRD v1)

## Requirements
- The assistant must answer order-status questions and include a way to track the order.
- The assistant must offer to escalate to a human agent whenever the customer is upset.
- The assistant must never promise a refund or guarantee compensation.
- Responses must be no more than 3 sentences long.
- The assistant should feel warm, friendly and delightful in every interaction.
- The assistant must never give legal advice.
- The team should hit 80% adoption across the support org by Q3.
"""


class ProjectIn(BaseModel):
    name: str


class PrdIn(BaseModel):
    content: str
    product_context: str = ""


class RunIn(BaseModel):
    target_kind: str = "demo"          # "demo" | "http"
    target_url: Optional[str] = None


class DemoIn(BaseModel):
    input: str


# ----------------------------------------------------------------- projects

@app.post("/api/projects")
def create_project(body: ProjectIn):
    conn = db.connect()
    pid = db.new_id()
    db.insert(conn, "projects", {"id": pid, "name": body.name, "created_at": db.now()})
    conn.close()
    return {"id": pid, "name": body.name}


@app.get("/api/projects")
def list_projects():
    conn = db.connect()
    out = db.rows_to_dicts(conn.execute("SELECT * FROM projects ORDER BY created_at DESC"))
    conn.close()
    return out


# ----------------------------------------------------------------- PRD + compile

@app.post("/api/projects/{pid}/prd")
async def save_and_compile(pid: str, body: PrdIn):
    conn = db.connect()
    prev = db.latest_prd(conn, pid)
    version = (prev["version"] + 1) if prev else 1
    prd_id = db.new_id()
    db.insert(conn, "prds", {"id": prd_id, "project_id": pid, "content": body.content,
                             "version": version, "created_at": db.now()})
    conn.close()
    clauses = await compile_prd(prd_id, body.content, body.product_context)
    return {"prd_id": prd_id, "version": version, "clauses": clauses,
            "provider": get_provider().name}


@app.get("/api/projects/{pid}/state")
def project_state(pid: str):
    """Everything the UI needs: latest PRD, clauses, eval cases, latest run pass rates."""
    conn = db.connect()
    prd = db.latest_prd(conn, pid)
    if not prd:
        conn.close()
        return {"prd": None, "clauses": [], "run": None}
    clauses = db.clauses_for_prd(conn, prd["id"])
    for c in clauses:
        c["cases"] = db.cases_for_clause(conn, c["id"])
    run = conn.execute(
        "SELECT * FROM runs WHERE prd_id=? ORDER BY created_at DESC LIMIT 1", (prd["id"],)
    ).fetchone()
    run_out = None
    if run:
        run_out = dict(run)
        results = db.rows_to_dicts(conn.execute(
            "SELECT r.*, e.input, e.kind, e.checker_type FROM results r "
            "JOIN eval_cases e ON e.id = r.eval_case_id WHERE r.run_id=?", (run["id"],)))
        run_out["results"] = results
        # per-clause pass rates
        rates = {}
        for r in results:
            s = rates.setdefault(r["clause_id"], {"pass": 0, "total": 0})
            s["total"] += 1
            s["pass"] += 1 if r["verdict"] == "pass" else 0
        run_out["clause_rates"] = rates
    conn.close()
    return {"prd": dict(prd), "clauses": clauses, "run": run_out}


# ----------------------------------------------------------------- runs

@app.post("/api/projects/{pid}/runs")
async def start_run(pid: str, body: RunIn):
    conn = db.connect()
    prd = db.latest_prd(conn, pid)
    conn.close()
    if not prd:
        raise HTTPException(404, "No PRD compiled for this project yet.")
    run_id = db.new_id()
    conn = db.connect()
    db.insert(conn, "runs", {"id": run_id, "project_id": pid, "prd_id": prd["id"],
                             "target_kind": body.target_kind, "status": "running",
                             "created_at": db.now()})
    conn.close()
    await run_suite(run_id, prd["id"], body.target_kind, body.target_url)
    return {"run_id": run_id, "status": "done"}


# ----------------------------------------------------------------- demo target + misc

@app.post("/api/demo-target")
def demo_endpoint(body: DemoIn):
    """The intentionally-imperfect support bot. Point an 'http' run at this URL."""
    return {"output": demo_target(body.input)}


@app.get("/api/sample-prd")
def sample_prd():
    return {"content": SAMPLE_PRD}


@app.get("/")
def landing():
    lp = FRONTEND_DIR / "landing.html"
    return FileResponse(lp if lp.exists() else FRONTEND_DIR / "index.html")


@app.get("/app")
def app_ui():
    return FileResponse(FRONTEND_DIR / "index.html")
