import pandas as pd
from recon_agent.matching import match

def L(i, ref, amt, dc="D"):
    return dict(ledger_id=i, account_id="A", currency="USD", value_date="2026-11-20", dr_cr=dc, amount=amt, reference=ref)

def S(i, ref, amt, dc="D"):
    return dict(stmt_id=i, account_id="A", currency="USD", value_date="2026-11-20", dr_cr=dc, amount=amt, reference=ref)


def test_rule_passes():
    led = pd.DataFrame([L("l1", "REF001", 100.0), L("l2", "REF002", 200.0), L("l3", "FSS26112000123", 300.0),
                        L("l4", "REF004", 400.0), L("l5", "REF005", 500.0)])
    st = pd.DataFrame([S("s1", "REF001", 100.0), S("s2", "REF002", 200.4), S("s3", "FSS26112000X", 300.0),
                       S("s4", "REF004", 380.0), S("s6", "NONREF", 50.0)])
    r = match(led, st, tolerance=1.0, fuzzy_threshold=0.6)
    rules = {m["ledger_id"]: m["rule"] for m in r.matched}
    assert rules == {"l1": "EXACT", "l2": "TOLERANCE", "l3": "FUZZY_REF"}
    assert [p["ledger"]["ledger_id"] for p in r.paired_breaks] == ["l4"]
    assert [l["ledger_id"] for l in r.ledger_only] == ["l5"]
    assert [s["stmt_id"] for s in r.statement_only] == ["s6"]


def test_direction_must_match():
    r = match(pd.DataFrame([L("l1", "R1", 10.0, "D")]), pd.DataFrame([S("s1", "R1", 10.0, "C")]))
    assert not r.matched
