# API Guide: REST, SOAP, webhooks, `requests` and FastAPI

A plain-English guide, using this project's own API as the example.

## 1. What is an API?

An **API** (Application Programming Interface) is a door that lets one program ask another program to do something
or give it data, without a person clicking screens.

Banking example: instead of an analyst downloading the reconciliation report, the bank's case-management tool calls
`GET /breaks?decision=ESCALATE` and receives the escalated breaks as data, ready to open cases automatically.

Every API call has the same parts:

| Part | Meaning | Example |
|---|---|---|
| **URL / endpoint** | Where to send the request | `http://127.0.0.1:8000/breaks` |
| **Method** | What kind of action | `GET` (read), `POST` (create / do something) |
| **Parameters** | Filters in the URL | `?decision=ESCALATE` |
| **Body** | Data sent with the request, usually JSON | `{"checker": "HV01", "decision": "APPROVE"}` |
| **Headers** | Extra information, often security | `X-Webhook-Token: change-me` |
| **Status code** | Did it work? | `200` OK, `201` created, `401` not authorised, `404` not found, `422` rule broken, `500` server error |

## 2. REST, SOAP and webhooks

### REST (most common today)

- Data is exchanged as **JSON**, simple and readable: `{"break_id": "L-FSS26112000044", "amount": 15.0}`.
- Uses the standard web methods: **GET** read, **POST** create or run, **PUT/PATCH** update, **DELETE** remove.
- Each URL is a "resource": `/breaks`, `/breaks/{id}`, `/approvals`.
- **When used:** almost all modern systems, cloud services and AI services. The OpenAI API itself is a REST API.
- **In this project:** every endpoint in `api.py` is REST.

### SOAP (older, still common in banks)

- Data is exchanged as **XML**, wrapped in a fixed "envelope", with a formal contract file called a **WSDL** that
  describes every operation and field exactly.
- Stricter and heavier, but with built-in standards for security and reliable messaging.
- **When used:** older enterprise and banking systems: core banking, treasury and payment platforms, and many
  integrations built before about 2015. You will meet it when connecting AI to legacy systems.
- Example of a SOAP request body:

```xml
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetBreaks><Decision>ESCALATE</Decision></GetBreaks>
  </soap:Body>
</soap:Envelope>
```

- In Python, SOAP services are usually called with the `zeep` library, which reads the WSDL for you.

### Webhooks ("don't call us, we'll call you")

- With REST you **pull**: you call the other system when you want something.
- With a webhook the other system **pushes**: it calls *your* URL the moment something happens.
- **When used:** events. "Payment received", "statement arrived", "ticket closed". It avoids asking "anything new?"
  every minute (polling).
- **Security:** because anyone could call your URL, webhooks normally carry a secret token or signature in a header,
  and the receiver checks it.
- **In this project:** `POST /webhooks/statement`. A SWIFT gateway could push each new MT950 as it arrives. The API
  checks the `X-Webhook-Token` header, validates the MT950 (format, balance proof, known account), refuses
  suspicious file names, logs it in the audit trail, then stores it for the next run.

### Quick comparison

| | REST | SOAP | Webhook |
|---|---|---|---|
| Direction | You call them (pull) | You call them (pull) | They call you (push) |
| Format | JSON | XML + WSDL contract | Usually JSON |
| Weight | Light | Heavy, strict | Light |
| Typical use | Modern apps, AI, cloud | Legacy enterprise / banking | Event notifications |

Integration platforms such as **MuleSoft**, which you have used, sit in the middle: they can receive SOAP from an
old system and expose it as REST to a new one.

## 3. Calling an API from Python with `requests`

`requests` is the standard Python library for calling REST APIs. See `examples/call_api.py` for a full run.

```python
import requests

BASE = "http://127.0.0.1:8000"

# GET: read data, with query parameters
r = requests.get(f"{BASE}/breaks", params={"decision": "ESCALATE"}, timeout=10)
print(r.status_code)         # 200 means OK
breaks = r.json()            # JSON text -> Python list of dicts

# POST with a JSON body: run an action
r = requests.post(f"{BASE}/approvals/L-FSS26112000044",
                  json={"checker": "HV01", "decision": "APPROVE", "comment": "Fee refunded"},
                  timeout=10)

# Headers: e.g. security tokens
r = requests.post(f"{BASE}/webhooks/statement", json={...}, headers={"X-Webhook-Token": "change-me"})

# Stop if the server returned an error (4xx / 5xx)
r.raise_for_status()
```

Good habits:
- Always set a **timeout**, or a slow server can hang your program.
- Check `status_code` or call `raise_for_status()` before using the data.
- Keep tokens and keys in `.env`, never in code.

## 4. Exposing the agent as an API with FastAPI

**FastAPI** turns Python functions into web endpoints. **Uvicorn** is the web server that runs it.

The pattern used in `src/recon_agent/api.py`:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="FSS Nostro Reconciliation Agent API")

class CheckerDecision(BaseModel):          # the shape the request body must have
    checker: str
    decision: Literal["APPROVE", "REJECT"]
    comment: str = ""

@app.get("/health")                        # GET /health
def health():
    return {"status": "ok"}                # returned dict becomes JSON automatically

@app.post("/approvals/{break_id}")         # {break_id} comes from the URL
def approve(break_id: str, body: CheckerDecision):
    return service.decide(break_id, body.checker, body.decision, body.comment)
```

What FastAPI gives you for free:
- **Validation:** a body with `"decision": "MAYBE"` is rejected with HTTP 422 before your code runs.
- **Automatic documentation:** open `http://127.0.0.1:8000/docs` to see every endpoint and try it in the browser.
  This is ideal for demos.
- **JSON in and out**, with no manual conversion.

### Design choice: a thin API over a service layer

`api.py` contains almost no logic. It calls functions in `service.py`, which do the real work (four-eyes check,
MT950 validation, filtering). Benefits:
- The logic is tested without starting a server (`tests/test_service.py`).
- The same functions can serve the CLI, the Streamlit dashboard or a different API framework.
- Business errors map cleanly to HTTP codes: `NotFound` → 404, `Rejected` (rule broken) → 422.

### Run it

```bash
pip install -r requirements.txt
# Windows: run_api.bat     macOS/Linux: ./run_api.sh
# or: set PYTHONPATH=src  then  uvicorn recon_agent.api:app --reload
```

Then, in a second terminal: `python examples/call_api.py`.

## 5. How to demo it (pre-sales style, about 5 minutes)

1. Open `/docs` and show the list of endpoints: "the agent is now a service any system can call".
2. `POST /reconcile` → show the auto-match rate and the breaks by decision.
3. `GET /breaks?decision=ESCALATE` → the planted suspicious debit with "ignore previous instructions" was caught.
4. `GET /breaks/{id}` → show the root cause and the SOP citation: explainable AI.
5. `POST /approvals/{id}` as `recon-agent` → HTTP 422, four-eyes enforced. Then as `HV01` → approved.
6. `POST /webhooks/statement` with a tampered closing balance → rejected by the balance proof.
7. `GET /audit/verify` → every step is in a tamper-evident log.
