"""Human-in-the-loop checker step (four-eyes).

The AI is the maker. A human checker reviews outputs/approval_queue.csv, fills in
`checker`, `checker_decision` (APPROVE / REJECT) and `checker_comment`, then runs:
    python -m recon_agent.cli approve
or reviews items one by one on screen with:
    python -m recon_agent.cli approve --interactive --checker <your-id>
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .agents import AGENT_ID
from .audit import AuditLog
from .config import SETTINGS


def apply_decisions(interactive: bool = False, checker_id: str | None = None) -> dict:
    out = SETTINGS.output_dir
    q = pd.read_csv(out / "approval_queue.csv", dtype=str).fillna("")
    audit = AuditLog(out / "audit_log.jsonl", datetime.now(timezone.utc).strftime("CHK-%Y%m%dT%H%M%S"))
    done = {"APPROVED": 0, "REJECTED": 0, "SKIPPED": 0, "BLOCKED": 0}

    for i, r in q.iterrows():
        if r["status"] != "PENDING_CHECKER":
            continue
        checker, decision, comment = r["checker"], r["checker_decision"].upper(), r["checker_comment"]
        if interactive:
            print(f"\n[{r['break_id']}] {r['currency']} {float(r['amount']):,.2f}  {r['category']} "
                  f"(conf {r['confidence']})\n  Proposed: {r['proposed_action']}")
            decision = input("  APPROVE / REJECT / SKIP? ").strip().upper()
            comment = input("  Comment: ").strip() if decision in ("APPROVE", "REJECT") else ""
            checker = checker_id or input("  Checker id: ").strip()
        if decision not in ("APPROVE", "REJECT"):
            done["SKIPPED"] += 1
            continue
        if not checker or checker == AGENT_ID or checker == r["maker"]:   # maker cannot be checker
            done["BLOCKED"] += 1
            audit.log("HITL", "FOUR_EYES_VIOLATION_BLOCKED", break_id=r["break_id"], checker=checker)
            continue
        q.loc[i, ["checker", "checker_decision", "checker_comment"]] = [checker, decision, comment]
        q.loc[i, "status"] = "APPROVED" if decision == "APPROVE" else "REJECTED"
        done["APPROVED" if decision == "APPROVE" else "REJECTED"] += 1
        audit.log("HITL", f"CHECKER_{decision}", break_id=r["break_id"], checker=checker, comment=comment,
                  category=r["category"])

    q.to_csv(out / "approval_queue.csv", index=False)
    return done
