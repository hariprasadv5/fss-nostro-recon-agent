"""REST API for the Nostro reconciliation agent (FastAPI).

Start it (from the project folder, with PYTHONPATH=src):
    uvicorn recon_agent.api:app --reload
Then open http://127.0.0.1:8000/docs for interactive documentation where you can try every endpoint.

Endpoints
    GET  /health                    is the service up?
    POST /reconcile                 run the agentic reconciliation now
    GET  /summary                   figures from the latest run
    GET  /breaks                    list breaks (filter by category, decision, account)
    GET  /breaks/{break_id}         one break with the agent's reasoning and citations
    GET  /approvals                 the four-eyes checker queue
    POST /approvals/{break_id}      a human checker approves or rejects a proposal
    POST /webhooks/statement        another system pushes a new MT950 statement to us
    GET  /kb/search?q=...           search the SOP knowledge base (RAG retrieval)
    GET  /audit/verify              check the tamper-evident audit chain
"""
from __future__ import annotations

import os
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from . import __version__, service

app = FastAPI(
    title="FSS Nostro Reconciliation Agent API",
    version=__version__,
    description="Agentic AI for Nostro reconciliation (dummy data). The AI is the maker; humans approve.",
)


# ---------------------------------------------------------------- request bodies (validated by pydantic)
class CheckerDecision(BaseModel):
    checker: str = Field(..., min_length=2, description="Checker's user id. Must not be the maker (recon-agent).")
    decision: Literal["APPROVE", "REJECT"]
    comment: str = ""


class StatementPush(BaseModel):
    filename: str = Field(..., examples=["NOS-USD-001_MT950.txt"])
    content: str = Field(..., description="Full MT950 text")


# ---------------------------------------------------------------- helpers
def _call(fn, *args, **kwargs):
    """Translate service errors into proper HTTP status codes."""
    try:
        return fn(*args, **kwargs)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except service.Rejected as e:
        raise HTTPException(status_code=422, detail=str(e))


# ---------------------------------------------------------------- endpoints
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "version": __version__}


@app.post("/reconcile", tags=["reconciliation"])
def reconcile():
    """Runs ingestion -> matching -> investigation -> resolution and returns the run summary."""
    return _call(service.run_reconciliation)


@app.get("/summary", tags=["reconciliation"])
def summary():
    return _call(service.latest_summary)


@app.get("/breaks", tags=["breaks"])
def breaks(category: Optional[str] = Query(None, examples=["BANK_CHARGES"]),
           decision: Optional[str] = Query(None, examples=["ESCALATE"]),
           account_id: Optional[str] = Query(None, examples=["NOS-USD-001"])):
    return _call(service.list_breaks, category, decision, account_id)


@app.get("/breaks/{break_id}", tags=["breaks"])
def break_detail(break_id: str):
    return _call(service.get_break, break_id)


@app.get("/approvals", tags=["four-eyes"])
def approvals(status: str = "PENDING_CHECKER"):
    return _call(service.approval_queue, status)


@app.post("/approvals/{break_id}", tags=["four-eyes"])
def approve_or_reject(break_id: str, body: CheckerDecision):
    return _call(service.decide, break_id, body.checker, body.decision, body.comment)


@app.post("/webhooks/statement", status_code=201, tags=["webhooks"])
def statement_webhook(body: StatementPush, x_webhook_token: Optional[str] = Header(None)):
    """Called by another system (e.g. the SWIFT gateway) when a new statement arrives.
    If WEBHOOK_TOKEN is set in .env, the caller must send the same value in the X-Webhook-Token header."""
    expected = os.getenv("WEBHOOK_TOKEN")
    if expected and x_webhook_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Webhook-Token")
    return _call(service.receive_statement, body.filename, body.content)


@app.get("/kb/search", tags=["knowledge base"])
def kb_search(q: str = Query(..., min_length=3, examples=["how do we treat bank charges"]), k: int = 3):
    return _call(service.search_kb, q, k)


@app.get("/audit/verify", tags=["system"])
def audit_verify():
    return service.audit_status()
