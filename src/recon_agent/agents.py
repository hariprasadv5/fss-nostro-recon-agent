"""The four agents of the Nostro reconciliation workflow.

  IngestionAgent     - loads ledger + MT950 statements, runs data-quality and balance-proof controls
  MatchingAgent      - deterministic rules engine (exact / tolerance / fuzzy / reference-only)
  InvestigationAgent - for each break: chooses tools, gathers evidence, retrieves SOPs (RAG), asks the LLM,
                       validates the answer against a schema, falls back to rules if the answer is invalid
  ResolutionAgent    - applies control limits: auto-resolve, maker proposal for human checker, or escalate;
                       drafts MT199 queries to the correspondent
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

import pandas as pd

from .audit import AuditLog
from .config import SETTINGS
from .guardrails import Masker, control_decision, detect_injection, validate_llm_output
from .llm import SYSTEM_PROMPT, MockLLM, traceable
from .matching import MatchResult, match
from .mt950_parser import load_statements
from .rag import KnowledgeBase, clean_query

AGENT_ID = "recon-agent"   # the AI is always the MAKER


# ---------------------------------------------------------------------------
class IngestionAgent:
    name = "IngestionAgent"

    def __init__(self, audit: AuditLog):
        self.audit = audit

    @traceable(name="ingestion")
    def run(self):
        ledger = pd.read_csv(SETTINGS.ledger_file, dtype={"reference": str})
        accounts = pd.read_csv(SETTINGS.accounts_file, dtype=str)
        statements = load_statements(SETTINGS.statements_dir)
        checks = []
        for s in statements:
            checks.append(dict(account_id=s.account_id, statement_no=s.statement_no, lines=len(s.lines),
                               opening=s.opening_balance, closing=s.closing_balance, balance_proof_ok=s.balance_proof_ok))
            if not s.balance_proof_ok:
                self.audit.log(self.name, "BALANCE_PROOF_FAILED", account_id=s.account_id)
        dq = {
            "ledger_rows": len(ledger),
            "ledger_null_refs": int(ledger["reference"].isna().sum()),
            "ledger_non_positive_amounts": int((ledger["amount"] <= 0).sum()),
            "unknown_accounts": sorted(set(ledger["account_id"]) - set(accounts["account_id"])),
        }
        stmt_df = pd.DataFrame([l.to_dict() for s in statements for l in s.lines])
        self.audit.log(self.name, "DATA_LOADED", statements=checks, data_quality=dq)
        return ledger, stmt_df, statements, accounts, checks, dq


# ---------------------------------------------------------------------------
class MatchingAgent:
    name = "MatchingAgent"

    def __init__(self, audit: AuditLog):
        self.audit = audit

    @traceable(name="matching")
    def run(self, ledger: pd.DataFrame, stmt: pd.DataFrame) -> MatchResult:
        res = match(ledger, stmt, SETTINGS.amount_tolerance, SETTINGS.fuzzy_ref_threshold, SETTINGS.date_window_days)
        self.audit.log(self.name, "MATCHING_DONE", **res.summary(),
                       rules=dict(tolerance=SETTINGS.amount_tolerance, fuzzy=SETTINGS.fuzzy_ref_threshold))
        return res


# ---------------------------------------------------------------------------
@dataclass
class Break:
    break_id: str
    break_type: str            # LEDGER_ONLY | STATEMENT_ONLY | PAIRED
    account_id: str
    currency: str
    amount: float              # exposure: item amount, or |difference| for paired items
    item: dict
    counter_item: dict | None = None
    findings: dict = field(default_factory=dict)


def build_breaks(res: MatchResult, stmt_currency: dict) -> list[Break]:
    out = []
    for l in res.ledger_only:
        out.append(Break(l["ledger_id"], "LEDGER_ONLY", l["account_id"], l["currency"], l["amount"], l))
    for s in res.statement_only:
        out.append(Break(s["stmt_id"], "STATEMENT_ONLY", s["account_id"], s["currency"], s["amount"], s))
    for p in res.paired_breaks:
        l = p["ledger"]
        out.append(Break(l["ledger_id"], "PAIRED", l["account_id"], l["currency"], abs(p["diff"]), l, p["statement"],
                         {"diff": p["diff"]}))
    # tolerance matches are matched, but the small difference still needs clearing -> route through agents
    for m in res.matched:
        if m["rule"] == "TOLERANCE" and m["diff"] != 0:
            out.append(Break(m["ledger_id"], "PAIRED", m["account_id"], stmt_currency.get(m["account_id"], ""),
                             abs(m["diff"]), {"ledger_id": m["ledger_id"], "reference": m["reference"],
                                              "amount": m["ledger_amount"]}, {"stmt_id": m["stmt_id"],
                                                                              "amount": m["stmt_amount"]},
                             {"diff": m["diff"]}))
    return out


class InvestigationAgent:
    name = "InvestigationAgent"

    def __init__(self, llm, kb: KnowledgeBase, ledger: pd.DataFrame, matched: list, masker: Masker, audit: AuditLog):
        self.llm, self.kb, self.ledger, self.masker, self.audit = llm, kb, ledger, masker, audit
        self.matched_ids = {m["ledger_id"] for m in matched}
        self.fallback = MockLLM()

    # ---- tools the agent can call -------------------------------------------------
    def tool_find_duplicate(self, item: dict) -> str | None:
        same = self.ledger[(self.ledger["reference"] == item.get("reference")) &
                           (self.ledger["amount"] == item.get("amount")) &
                           (self.ledger["ledger_id"] != item.get("ledger_id"))]
        hit = same[same["ledger_id"].isin(self.matched_ids)]
        return None if hit.empty else hit.iloc[0]["ledger_id"]

    def tool_reference_known(self, ref: str) -> bool:
        return bool(ref) and ref != "NONREF" and (self.ledger["reference"] == ref).any()

    def tool_search_kb(self, query: str):
        return self.kb.search(query, k=SETTINGS.top_k)

    # ---- plan -> act -> reason ------------------------------------------------------
    def plan(self, b: Break) -> list[str]:
        steps = ["check_injection", "search_kb"]
        if b.break_type == "LEDGER_ONLY":
            steps.insert(1, "find_duplicate")
        if b.break_type == "STATEMENT_ONLY":
            steps.insert(1, "reference_known")
            steps.insert(1, "check_escalation_limit")
        if b.break_type == "PAIRED":
            steps.insert(1, "compare_amounts")
        return steps

    @traceable(name="investigate_break")
    def investigate(self, b: Break) -> dict:
        steps = self.plan(b)
        f = b.findings
        f["tolerance"] = SETTINGS.amount_tolerance
        text = " ".join(str(b.item.get(k, "")) for k in ("narrative", "reference"))
        for step in steps:
            if step == "check_injection":
                f["injection_detected"] = detect_injection(text)
            elif step == "find_duplicate":
                f["duplicate_of"] = self.tool_find_duplicate(b.item)
            elif step == "reference_known":
                f["reference_known"] = self.tool_reference_known(b.item.get("reference", ""))
            elif step == "check_escalation_limit":
                f["over_escalation_limit"] = b.amount >= SETTINGS.escalation_amount
            elif step == "compare_amounts":
                f["diff"] = round(f["diff"], 2)
        query = clean_query(b.break_type.replace("_", " "), b.item.get("txn_code", ""), b.item.get("narrative", ""),
                            "duplicate" if f.get("duplicate_of") else "",
                            "amount difference fee" if b.break_type == "PAIRED" else "")
        hits = self.tool_search_kb(query)

        evidence = {"break_type": b.break_type, "account_id": b.account_id, "currency": b.currency,
                    "item": {k: (self.masker.mask(v) if isinstance(v, str) else v) for k, v in b.item.items()},
                    "findings": f}
        sop = "\n".join(f"- [{h['source']} > {h['section']}] (score {h['score']}) {h['text'][:500]}" for h in hits)
        user = f"EVIDENCE:\n{json.dumps(evidence, default=str)}\nSOP EXTRACTS:\n{sop}\n"
        system = SYSTEM_PROMPT.format(categories=", ".join(SETTINGS.allowed_categories))

        source, error = getattr(self.llm, "name", "llm"), None
        try:
            raw = self.llm.complete_json(system, user)
            inv, error = validate_llm_output(raw)
        except Exception as e:  # network / API / JSON failures
            inv, error = None, f"{type(e).__name__}: {e}"
        if inv is None:   # guardrail: invalid or failed answer -> deterministic fallback
            inv, _ = validate_llm_output(self.fallback.complete_json(system, user))
            source = f"fallback:{self.fallback.name}"
        result = dict(break_id=b.break_id, break_type=b.break_type, account_id=b.account_id, currency=b.currency,
                      amount=b.amount, plan=steps, findings=f, retrieved=[f"{h['source']} > {h['section']}" for h in hits],
                      model=source, prompt_version=SETTINGS.prompt_version, llm_error=error, **inv.model_dump())
        self.audit.log(self.name, "BREAK_INVESTIGATED", **{k: result[k] for k in (
            "break_id", "break_type", "amount", "category", "confidence", "model", "prompt_version",
            "plan", "retrieved", "citations", "llm_error")})
        return result


# ---------------------------------------------------------------------------
QUERY_TEMPLATES = {
    "UNIDENTIFIED_RECEIPT": "Please provide full remitter name, ordering institution and payment details for your "
                            "credit of {ccy} {amount:,.2f} value {vdate}, your reference {bank_ref}.",
    "FEE_DEDUCTED": "Your credit of {ccy} {stmt_amount:,.2f} value {vdate} ref {ref} was received short by "
                    "{diff:,.2f}. The payment was instructed with charges OUR. Please refund the deducted charges.",
    "UNAUTHORISED_DEBIT": "We have no record of instructing your debit of {ccy} {amount:,.2f} value {vdate}, your "
                          "reference {bank_ref}. Please provide the underlying instruction and arrange immediate "
                          "recall/reversal pending investigation.",
}


class ResolutionAgent:
    name = "ResolutionAgent"

    def __init__(self, audit: AuditLog):
        self.audit = audit

    def draft_query(self, inv: dict, b: Break) -> str | None:
        key = inv.get("query_to_correspondent")
        if key not in QUERY_TEMPLATES:
            return None
        s = b.counter_item if b.break_type == "PAIRED" else b.item
        body = QUERY_TEMPLATES[key].format(ccy=b.currency, amount=b.item.get("amount", 0), vdate=b.item.get("value_date", ""),
                                           bank_ref=b.item.get("bank_reference", ""), ref=b.item.get("reference", ""),
                                           stmt_amount=(s or {}).get("amount", 0), diff=abs(b.findings.get("diff", 0)))
        return f":20:Q-{b.break_id[-16:]}\n:21:{b.item.get('reference', 'NONREF')[:16]}\n:79:{body}"

    def decide(self, inv: dict, b: Break) -> dict:
        decision, reason = control_decision(inv["category"], inv["amount"], inv["confidence"],
                                            inv["findings"].get("injection_detected", False))
        status = {"AUTO_RESOLVE": "RESOLVED_AUTO", "MAKER_PROPOSAL": "PENDING_CHECKER",
                  "ESCALATE": "ESCALATED"}[decision]
        action = dict(break_id=inv["break_id"], account_id=inv["account_id"], currency=inv["currency"],
                      amount=inv["amount"], category=inv["category"], confidence=inv["confidence"],
                      decision=decision, status=status, control_reason=reason,
                      proposed_action=inv["recommended_action"], maker=AGENT_ID,
                      draft_mt199=self.draft_query(inv, b), checker="", checker_decision="", checker_comment="")
        self.audit.log(self.name, "ACTION_DECIDED", **{k: action[k] for k in (
            "break_id", "category", "decision", "status", "control_reason", "maker")})
        return action
