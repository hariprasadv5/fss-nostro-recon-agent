from recon_agent.mt950_parser import parse_mt950

SAMPLE = """{4:
:20:NOS-USD-001-261120
:25:36001234
:28C:301/1
:60F:C261119USD1000,00
:61:2611201120D250,50NCHGNONREF//CITICHG123
ACCOUNT MAINTENANCE FEE
:61:2611201120C100,00NTRFFSS26112000001//CITI00000001
ALPHA FUND
:62F:C261120USD849,50
-}"""


def test_parse_lines_and_balance_proof():
    s = parse_mt950(SAMPLE)
    assert s.account_id == "NOS-USD-001" and s.currency == "USD"
    assert len(s.lines) == 2
    assert s.lines[0].dr_cr == "D" and s.lines[0].amount == 250.50 and s.lines[0].txn_code == "NCHG"
    assert s.lines[0].narrative == "ACCOUNT MAINTENANCE FEE"
    assert s.balance_proof_ok


def test_balance_proof_detects_missing_line():
    s = parse_mt950(SAMPLE.replace(":62F:C261120USD849,50", ":62F:C261120USD900,00"))
    assert not s.balance_proof_ok
