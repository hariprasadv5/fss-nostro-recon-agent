"""Parser for SWIFT MT950 / MT940 customer statements (the correspondent's side of the Nostro).

Field :61: layout (simplified, per SWIFT UHB):
  6!n  value date YYMMDD
  [4!n] entry date MMDD
  2a   D | C | RD | RC
  15d  amount (comma decimal)
  1!a3!c  transaction type (e.g. NTRF, NCHG, NINT)
  16x  reference for the account owner
  [//16x] account servicing institution reference
Next line (optional) = supplementary details / narrative.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path

LINE_61 = re.compile(
    r"^:61:(?P<vdate>\d{6})(?P<edate>\d{4})?(?P<dc>R?[DC])(?P<amount>[\d,]+)"
    r"(?P<code>[NSF][A-Z0-9]{3})(?P<ref>[^/\n]{1,16})(//(?P<bank_ref>.{1,16}))?$"
)
BAL = re.compile(r"^:(?P<tag>60F|60M|62F|62M):(?P<dc>[DC])(?P<date>\d{6})(?P<ccy>[A-Z]{3})(?P<amount>[\d,]+)$")


class StatementError(ValueError):
    pass


@dataclass
class StatementLine:
    stmt_id: str
    account_id: str
    currency: str
    value_date: str
    dr_cr: str
    amount: float
    txn_code: str
    reference: str
    bank_reference: str
    narrative: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Statement:
    account_id: str
    their_account_no: str
    statement_no: str
    currency: str
    opening_balance: float
    closing_balance: float
    lines: list

    @property
    def balance_proof_ok(self) -> bool:
        """Opening + credits - debits must equal closing balance (completeness control)."""
        net = sum(l.amount if l.dr_cr == "C" else -l.amount for l in self.lines)
        return round(self.opening_balance + net, 2) == round(self.closing_balance, 2)


def _amt(s: str) -> float:
    return float(s.replace(",", "."))


def _d(yymmdd: str) -> str:
    return datetime.strptime(yymmdd, "%y%m%d").date().isoformat()


def parse_mt950(text: str) -> Statement:
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    acct = their = stmt_no = ccy = None
    opening = closing = None
    items: list[StatementLine] = []
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.startswith(":20:"):
            acct = l[4:].rsplit("-", 1)[0]
        elif l.startswith(":25:"):
            their = l[4:]
        elif l.startswith(":28C:"):
            stmt_no = l[5:]
        elif (m := BAL.match(l)):
            val = _amt(m["amount"]) * (1 if m["dc"] == "C" else -1)
            ccy = m["ccy"]
            if m["tag"].startswith("60"):
                opening = val
            else:
                closing = val
        elif l.startswith(":61:"):
            m = LINE_61.match(l)
            if not m:
                raise StatementError(f"Malformed :61: line: {l}")
            narrative = ""
            if i + 1 < len(lines) and not lines[i + 1].startswith(":") and not lines[i + 1].startswith("-}"):
                narrative = lines[i + 1]
                i += 1
            bank_ref = (m["bank_ref"] or "").strip()
            items.append(StatementLine(
                stmt_id=f"S-{acct}-{bank_ref}", account_id=acct, currency=ccy or "",
                value_date=_d(m["vdate"]), dr_cr=m["dc"][-1], amount=_amt(m["amount"]),
                txn_code=m["code"], reference=m["ref"].strip(), bank_reference=bank_ref, narrative=narrative,
            ))
        i += 1
    if None in (acct, opening, closing):
        raise StatementError("Statement missing :20:, :60F: or :62F:")
    for it in items:
        it.currency = ccy
    return Statement(acct, their, stmt_no, ccy, opening, closing, items)


def load_statements(folder: Path) -> list[Statement]:
    return [parse_mt950(p.read_text(encoding="utf-8")) for p in sorted(Path(folder).glob("*.txt"))]
