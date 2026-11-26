"""Call the Nostro agent API from Python with the `requests` library.

1. Start the API in one terminal:   uvicorn recon_agent.api:app --reload      (PYTHONPATH=src)
2. Run this in another terminal:    python examples/call_api.py
"""
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"


def show(title, resp):
    print(f"\n=== {title}  ->  HTTP {resp.status_code}")
    print(resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text)


# 1. GET: is the service up?
show("Health check", requests.get(f"{BASE}/health", timeout=10))

# 2. POST: run the reconciliation (the agents do their work)
r = requests.post(f"{BASE}/reconcile", timeout=300)
r.raise_for_status()                       # stop here if the server returned an error
summary = r.json()
print(f"\nAuto-match rate: {summary['auto_match_rate']:.1%}, breaks: {summary['breaks']}, "
      f"decisions: {summary['by_decision']}")

# 3. GET with query parameters: only the escalated breaks
esc = requests.get(f"{BASE}/breaks", params={"decision": "ESCALATE"}, timeout=10).json()
for b in esc:
    print(f"ESCALATED  {b['break_id']}  {b['currency']} {b['amount']:,.2f}  {b['category']}")

# 4. GET: the checker queue, then POST a decision on the first item (four-eyes)
queue = requests.get(f"{BASE}/approvals", timeout=10).json()
if queue:
    first = queue[0]["break_id"]
    show("Checker approves", requests.post(f"{BASE}/approvals/{first}",
         json={"checker": "HV01", "decision": "APPROVE", "comment": "Checked against fee schedule"}, timeout=10))
    # the AI trying to approve its own proposal is blocked with HTTP 422
    if len(queue) > 1:
        show("AI tries to approve itself", requests.post(f"{BASE}/approvals/{queue[1]['break_id']}",
             json={"checker": "recon-agent", "decision": "APPROVE"}, timeout=10))

# 5. POST to a webhook: push a statement, as a SWIFT gateway would
stmt = Path(__file__).resolve().parents[1] / "data" / "statements" / "NOS-GBP-003_MT950.txt"
show("Webhook: push MT950", requests.post(f"{BASE}/webhooks/statement",
     json={"filename": stmt.name, "content": stmt.read_text()},
     headers={"X-Webhook-Token": "change-me"}, timeout=10))

# 6. GET: ask the knowledge base
for hit in requests.get(f"{BASE}/kb/search", params={"q": "unidentified receipt suspense"}, timeout=30).json()[:2]:
    print(f"\nKB: {hit['source']} > {hit['section']} (score {hit['score']})")

# 7. GET: audit chain still intact?
show("Audit verify", requests.get(f"{BASE}/audit/verify", timeout=10))
