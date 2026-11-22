"""Deterministic matching engine (rules first, AI only for what rules cannot explain).

Passes, in order of confidence:
  1. EXACT      - same account, reference, amount, direction, value date
  2. TOLERANCE  - same reference & direction, |amount diff| <= tolerance   -> matched, flagged ROUNDING_FX_DIFFERENCE
  3. FUZZY_REF  - same amount, direction, value date (+/- window), reference similarity >= threshold
  4. REF_ONLY   - same reference & direction but amount differs beyond tolerance -> PAIRED BREAK (amount mismatch)
Everything left over is an unmatched break (ledger-only or statement-only).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher

import pandas as pd


@dataclass
class MatchResult:
    matched: list = field(default_factory=list)       # dicts: ledger_id, stmt_id, rule, diff
    paired_breaks: list = field(default_factory=list)  # matched by ref but amount differs: need investigation
    ledger_only: list = field(default_factory=list)    # ledger rows (dict)
    statement_only: list = field(default_factory=list) # statement rows (dict)

    def summary(self) -> dict:
        return {
            "matched": len(self.matched),
            "tolerance_matches": sum(1 for m in self.matched if m["rule"] == "TOLERANCE"),
            "fuzzy_matches": sum(1 for m in self.matched if m["rule"] == "FUZZY_REF"),
            "paired_breaks": len(self.paired_breaks),
            "ledger_only": len(self.ledger_only),
            "statement_only": len(self.statement_only),
        }


def ref_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").upper(), (b or "").upper()).ratio()


def _days(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def match(ledger: pd.DataFrame, stmt: pd.DataFrame, tolerance: float = 1.0,
          fuzzy_threshold: float = 0.6, date_window: int = 2) -> MatchResult:
    res = MatchResult()
    L = ledger.to_dict("records")
    S = stmt.to_dict("records")
    used_l, used_s = set(), set()

    def take(l, s, rule):
        used_l.add(l["ledger_id"]); used_s.add(s["stmt_id"])
        res.matched.append(dict(ledger_id=l["ledger_id"], stmt_id=s["stmt_id"], account_id=l["account_id"],
                                rule=rule, ledger_amount=l["amount"], stmt_amount=s["amount"],
                                diff=round(s["amount"] - l["amount"], 2), reference=l["reference"]))

    def candidates(l):
        return [s for s in S if s["stmt_id"] not in used_s and s["account_id"] == l["account_id"]
                and s["dr_cr"] == l["dr_cr"]]

    # pass 1 exact
    for l in L:
        for s in candidates(l):
            if s["reference"] == l["reference"] and abs(s["amount"] - l["amount"]) < 0.005 \
                    and s["value_date"] == l["value_date"]:
                take(l, s, "EXACT"); break

    # pass 2 tolerance
    for l in L:
        if l["ledger_id"] in used_l:
            continue
        for s in candidates(l):
            if s["reference"] == l["reference"] and abs(s["amount"] - l["amount"]) <= tolerance:
                take(l, s, "TOLERANCE"); break

    # pass 3 fuzzy reference
    for l in L:
        if l["ledger_id"] in used_l:
            continue
        best, score = None, 0.0
        for s in candidates(l):
            if abs(s["amount"] - l["amount"]) < 0.005 and _days(s["value_date"], l["value_date"]) <= date_window:
                sc = ref_similarity(s["reference"], l["reference"])
                if sc > score:
                    best, score = s, sc
        if best is not None and score >= fuzzy_threshold:
            take(l, best, "FUZZY_REF")

    # pass 4 same reference, amount outside tolerance -> paired break
    for l in L:
        if l["ledger_id"] in used_l:
            continue
        for s in candidates(l):
            if s["reference"] == l["reference"] and s["reference"] not in ("NONREF", ""):
                used_l.add(l["ledger_id"]); used_s.add(s["stmt_id"])
                res.paired_breaks.append(dict(ledger=l, statement=s, diff=round(s["amount"] - l["amount"], 2)))
                break

    res.ledger_only = [l for l in L if l["ledger_id"] not in used_l]
    res.statement_only = [s for s in S if s["stmt_id"] not in used_s]
    return res
