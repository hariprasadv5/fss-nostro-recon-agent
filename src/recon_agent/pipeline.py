"""Orchestrator: runs the agents end to end and writes the reconciliation pack."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from .agents import (IngestionAgent, InvestigationAgent, MatchingAgent, ResolutionAgent, build_breaks)
from .audit import AuditLog
from .config import SETTINGS
from .evaluation import evaluate
from .guardrails import Masker
from .llm import get_llm, traceable
from .rag import KnowledgeBase


@traceable(name="nostro_recon_run")
def run(evaluate_against_truth: bool = True) -> dict:
    out = SETTINGS.output_dir
    out.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S")
    audit = AuditLog(out / "audit_log.jsonl", run_id)
    llm = get_llm()
    audit.log("Orchestrator", "RUN_STARTED", llm=getattr(llm, "name", "?"), prompt_version=SETTINGS.prompt_version)

    # 1. ingest
    ledger, stmt, statements, accounts, checks, dq = IngestionAgent(audit).run()
    if not all(c["balance_proof_ok"] for c in checks):
        audit.log("Orchestrator", "RUN_STOPPED", reason="balance proof failed")
        raise SystemExit("Balance proof failed for at least one statement - request re-send (SOP-NR-01 step 1).")

    # 2. match
    res = MatchingAgent(audit).run(ledger, stmt)

    # 3. investigate
    kb = KnowledgeBase(SETTINGS.kb_dir, SETTINGS.retriever, out / "chroma")
    masker = Masker(ledger["counterparty"].dropna().tolist())
    investigator = InvestigationAgent(llm, kb, ledger, res.matched, masker, audit)
    breaks = build_breaks(res, {s.account_id: s.currency for s in statements})
    investigations = [investigator.investigate(b) for b in breaks]

    # 4. resolve under controls
    resolver = ResolutionAgent(audit)
    actions = [resolver.decide(inv, b) for inv, b in zip(investigations, breaks)]

    # 5. outputs
    pd.DataFrame(res.matched).to_csv(out / "matched_items.csv", index=False)
    inv_df = pd.DataFrame(investigations)
    inv_df.to_csv(out / "breaks_investigated.csv", index=False)
    act_df = pd.DataFrame(actions)
    act_df.to_csv(out / "actions_all.csv", index=False)
    act_df[act_df["status"] == "PENDING_CHECKER"].to_csv(out / "approval_queue.csv", index=False)
    qdir = out / "draft_mt199"
    qdir.mkdir(exist_ok=True)
    for f in qdir.glob("*.txt"):
        f.unlink()
    for a in actions:
        if a["draft_mt199"]:
            (qdir / f"{a['break_id']}.txt").write_text(a["draft_mt199"] + "\n", encoding="utf-8")

    total_items = len(ledger) + len(stmt)
    summary = dict(run_id=run_id, llm=getattr(llm, "name", "?"), retriever=kb.backend,
                   statements=checks, data_quality=dq, matching=res.summary(),
                   auto_match_rate=round(2 * len(res.matched) / total_items, 4),
                   breaks=len(breaks),
                   by_decision=act_df["decision"].value_counts().to_dict(),
                   by_category=act_df["category"].value_counts().to_dict())
    if evaluate_against_truth and SETTINGS.ground_truth_file.exists():
        summary["evaluation"] = evaluate(inv_df, SETTINGS.ground_truth_file, out)
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    write_report(summary, act_df, out / "recon_report.md")
    audit.log("Orchestrator", "RUN_COMPLETED", breaks=len(breaks), by_decision=summary["by_decision"])
    return summary


def write_report(s: dict, act: pd.DataFrame, path):
    lines = [f"# Nostro Reconciliation Report - FSS (DUMMY DATA)", "",
             f"Run: {s['run_id']}  |  LLM: {s['llm']}  |  Retriever: {s['retriever']}", "",
             "## Statement controls", "", "| Account | Stmt no | Lines | Opening | Closing | Balance proof |",
             "|---|---|---|---|---|---|"]
    for c in s["statements"]:
        lines.append(f"| {c['account_id']} | {c['statement_no']} | {c['lines']} | {c['opening']:,.2f} | "
                     f"{c['closing']:,.2f} | {'OK' if c['balance_proof_ok'] else 'FAILED'} |")
    m = s["matching"]
    lines += ["", "## Matching", "", f"- Auto-match rate: **{s['auto_match_rate']:.1%}**",
              f"- Matched pairs: {m['matched']} (tolerance {m['tolerance_matches']}, fuzzy reference {m['fuzzy_matches']})",
              f"- Breaks for investigation: {s['breaks']}", "", "## Breaks and actions", "",
              "| Break | Account | Amount | Category | Conf. | Decision | Proposed action |", "|---|---|---|---|---|---|---|"]
    for _, r in act.sort_values(["decision", "amount"], ascending=[True, False]).iterrows():
        lines.append(f"| {r['break_id']} | {r['account_id']} | {r['currency']} {r['amount']:,.2f} | {r['category']} | "
                     f"{r['confidence']:.2f} | {r['decision']} | {r['proposed_action']} |")
    if "evaluation" in s:
        e = s["evaluation"]
        lines += ["", "## Model evaluation (against injected ground truth)", "",
                  f"- Classification accuracy: **{e['accuracy']:.1%}** on {e['labelled_breaks']} labelled breaks",
                  f"- Break coverage (labelled breaks found): {e['coverage']:.1%}",
                  f"- Suspicious items escalated: {e['suspicious_escalation_rate']:.1%}"]
    lines += ["", "_All actions except AUTO_RESOLVE wait for a human checker (four-eyes). See approval_queue.csv._"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
