"""HTTP-level tests with FastAPI's TestClient. Skipped automatically if fastapi/httpx are not installed."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from recon_agent.api import app  # noqa: E402

client = TestClient(app)


def test_end_to_end_over_http():
    assert client.get("/health").json()["status"] == "ok"
    r = client.post("/reconcile")
    assert r.status_code == 200 and r.json()["breaks"] > 0
    esc = client.get("/breaks", params={"decision": "ESCALATE"}).json()
    assert all(b["category"] == "SUSPICIOUS" for b in esc)
    assert client.get("/breaks/NOPE").status_code == 404
    q = client.get("/approvals").json()
    bad = client.post(f"/approvals/{q[0]['break_id']}", json={"checker": "recon-agent", "decision": "APPROVE"})
    assert bad.status_code == 422                              # four-eyes enforced over HTTP
    assert client.post(f"/approvals/{q[0]['break_id']}", json={"checker": "x", "decision": "MAYBE"}).status_code == 422
    ok = client.post(f"/approvals/{q[0]['break_id']}", json={"checker": "HV01", "decision": "APPROVE"})
    assert ok.status_code == 200 and ok.json()["status"] == "APPROVED"
    assert client.get("/kb/search", params={"q": "bank charges"}).status_code == 200
    assert client.get("/audit/verify").json()["intact"]
