"""Service-layer tests: the logic behind every API endpoint, without starting a web server."""
import runpy
import sys
from pathlib import Path

import pytest

from recon_agent import service
from recon_agent.config import SETTINGS


@pytest.fixture(scope="module", autouse=True)
def fresh_run():
    sys.argv = ["gen"]
    runpy.run_path(str(SETTINGS.data_dir / "generate_dummy_data.py"), run_name="__main__")
    service.run_reconciliation()


def test_filters_and_detail():
    esc = service.list_breaks(decision="ESCALATE")
    assert esc and all(b["decision"] == "ESCALATE" for b in esc)
    d = service.get_break(esc[0]["break_id"])
    assert d["category"] == "SUSPICIOUS" and d["action"]["status"] == "ESCALATED"
    with pytest.raises(service.NotFound):
        service.get_break("NO-SUCH-BREAK")


def test_four_eyes_via_service():
    q = service.approval_queue()
    with pytest.raises(service.Rejected):
        service.decide(q[0]["break_id"], "recon-agent", "APPROVE")
    done = service.decide(q[0]["break_id"], "HV01", "APPROVE", "ok")
    assert done["status"] == "APPROVED"
    with pytest.raises(service.Rejected):          # cannot decide twice
        service.decide(q[0]["break_id"], "HV02", "REJECT")


def test_webhook_validation():
    good = (SETTINGS.statements_dir / "NOS-USD-001_MT950.txt").read_text()
    info = service.receive_statement("NOS-USD-001_MT950.txt", good)
    assert info["account_id"] == "NOS-USD-001" and info["lines"] > 0
    with pytest.raises(service.Rejected):          # tampered closing balance -> balance proof fails
        service.receive_statement("NOS-USD-001_MT950.txt", good.replace(":62F:C", ":62F:D"))
    with pytest.raises(service.Rejected):          # path tricks in filename are refused
        service.receive_statement("../../evil_MT950.txt", good)


def test_kb_and_audit():
    assert service.search_kb("bank charges fee")[0]["section"] == "BANK_CHARGES"
    assert service.audit_status()["intact"]
