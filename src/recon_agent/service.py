"""Service layer: the actions the API offers, as plain Python functions.

Keeping the logic here (not inside api.py) means it can be tested without a web server,
and the same functions can be reused by the CLI, the dashboard or a different API framework.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pandas as pd

from .agents import AGENT_ID
from .audit import AuditLog, verify_chain
from .config import SETTINGS
from .mt950_parser import StatementError, parse_mt950

OUT = SETTINGS.output_dir


class NotFound(Exception):
    pass


class Rejected(Exception):
    """The request is understood but breaks a rule (e.g. four-eyes, bad statement)."""


def _audit(prefix: str) -> AuditLog:
    return AuditLog(OUT / "audit_log.jsonl", datetime.now(timezone.utc).strftime(f"{prefix}-%Y%m%dT%H%M%S"))


def _records(df: pd.DataFrame) -> list[dict]:
    # pandas NaN is not valid JSON -> replace with None
    return json.loads(df.to_json(orient="records"))


# ---------------------------------------------------------------- reconciliation
def run_reconciliation() -> dict:
    from .pipeline import run      # imported here: heavy, only needed when a run is requested
    s = run()
    return {k: s[k] for k in ("run_id", "llm", "retriever", "matching", "auto_match_rate",
                              "breaks", "by_decision", "by_category")} | (
        {"evaluation": {k: s["evaluation"][k] for k in ("accuracy", "coverage", "suspicious_escalation_rate")}}
        if "evaluation" in s else {})


def latest_summary() -> dict:
    p = OUT / "run_summary.json"
    if not p.exists():
        raise NotFound("No reconciliation has been run yet. Call POST /reconcile first.")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- breaks
def _actions() -> pd.DataFrame:
    p = OUT / "actions_all.csv"
    if not p.exists():
        raise NotFound("No reconciliation has been run yet. Call POST /reconcile first.")
    return pd.read_csv(p)


def list_breaks(category: str | None = None, decision: str | None = None, account_id: str | None = None) -> list[dict]:
    df = _actions()
    if category:
        df = df[df["category"] == category.upper()]
    if decision:
        df = df[df["decision"] == decision.upper()]
    if account_id:
        df = df[df["account_id"] == account_id]
    return _records(df)


def get_break(break_id: str) -> dict:
    inv = pd.read_csv(OUT / "breaks_investigated.csv")
    act = _actions()
    i, a = inv[inv["break_id"] == break_id], act[act["break_id"] == break_id]
    if i.empty:
        raise NotFound(f"Break {break_id} not found.")
    out = _records(i)[0]
    out["action"] = _records(a)[0] if not a.empty else None
    return out


# ---------------------------------------------------------------- four-eyes approvals
def approval_queue(status: str = "PENDING_CHECKER") -> list[dict]:
    q = pd.read_csv(OUT / "approval_queue.csv", dtype=str).fillna("")
    return _records(q[q["status"] == status] if status else q)


def decide(break_id: str, checker: str, decision: str, comment: str = "") -> dict:
    """A human checker approves or rejects one maker proposal. The AI can never be the checker."""
    decision = decision.upper()
    if decision not in ("APPROVE", "REJECT"):
        raise Rejected("decision must be APPROVE or REJECT")
    p = OUT / "approval_queue.csv"
    q = pd.read_csv(p, dtype=str).fillna("")
    rows = q.index[q["break_id"] == break_id]
    if len(rows) == 0:
        raise NotFound(f"Break {break_id} is not in the approval queue.")
    i = rows[0]
    if q.loc[i, "status"] != "PENDING_CHECKER":
        raise Rejected(f"Break {break_id} is already {q.loc[i, 'status']}.")
    audit = _audit("API")
    if not checker or checker in (AGENT_ID, q.loc[i, "maker"]):
        audit.log("API", "FOUR_EYES_VIOLATION_BLOCKED", break_id=break_id, checker=checker)
        raise Rejected("Four-eyes rule: the checker must be a named person different from the maker.")
    q.loc[i, ["checker", "checker_decision", "checker_comment"]] = [checker, decision, comment]
    q.loc[i, "status"] = "APPROVED" if decision == "APPROVE" else "REJECTED"
    q.to_csv(p, index=False)
    audit.log("API", f"CHECKER_{decision}", break_id=break_id, checker=checker, comment=comment)
    return _records(q.loc[[i]])[0]


# ---------------------------------------------------------------- inbound statements (webhook)
SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-]+_MT950\.txt$")


def receive_statement(filename: str, content: str) -> dict:
    """Validate an MT950 pushed by another system and store it for the next reconciliation run."""
    if not SAFE_NAME.match(filename or ""):
        raise Rejected("filename must look like <ACCOUNT>_MT950.txt (letters, digits, - and _ only)")
    try:
        stmt = parse_mt950(content)
    except StatementError as e:
        raise Rejected(f"Not a valid MT950: {e}")
    if not stmt.balance_proof_ok:
        raise Rejected("Balance proof failed (opening + credits - debits != closing). Statement not stored.")
    known = set(pd.read_csv(SETTINGS.accounts_file, dtype=str)["account_id"])
    if stmt.account_id not in known:
        raise Rejected(f"Unknown Nostro account {stmt.account_id}.")
    (SETTINGS.statements_dir / filename).write_text(content, encoding="utf-8")
    info = dict(account_id=stmt.account_id, statement_no=stmt.statement_no, currency=stmt.currency,
                lines=len(stmt.lines), opening=stmt.opening_balance, closing=stmt.closing_balance,
                stored_as=filename)
    _audit("WEBHOOK").log("Webhook", "STATEMENT_RECEIVED", **info)
    return info


# ---------------------------------------------------------------- knowledge base & audit
def search_kb(question: str, k: int | None = None) -> list[dict]:
    from .rag import KnowledgeBase
    kb = KnowledgeBase(SETTINGS.kb_dir, SETTINGS.retriever, OUT / "chroma")
    return kb.search(question, k or SETTINGS.top_k)


def audit_status() -> dict:
    p = OUT / "audit_log.jsonl"
    if not p.exists():
        return {"intact": True, "records": 0}
    ok, n = verify_chain(p)
    return {"intact": ok, "records": n}
