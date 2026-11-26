# FSS Nostro Reconciliation – Agentic AI (prototype)

An agentic AI assistant that reconciles Funds & Securities Services Nostro accounts. It matches correspondent
SWIFT MT950 statements against the internal ledger, investigates each break with tools and a RAG knowledge base,
and proposes the next action under bank controls: four-eyes approval, limits, escalation and a tamper-evident
audit trail.

> **All data in this repository is synthetic (dummy).** No real client, account or bank data is used.

## What it does

1. **Ingestion Agent** – parses MT950 statements, runs the balance proof and data-quality checks.
2. **Matching Agent** – rules engine: exact → tolerance → fuzzy reference → reference-only.
3. **Investigation Agent** – for each break it plans which tools to use, gathers evidence, retrieves the relevant
   SOP section (RAG), asks the LLM for a classification in JSON, validates it, and cites its sources.
4. **Resolution Agent** – applies the control policy: auto-resolve (tiny rounding only), maker proposal for a
   human checker, or escalation; drafts MT199 queries to the correspondent.
5. **Human checker** – approves or rejects proposals in a CLI queue or a Streamlit dashboard. The AI can never
   approve its own work.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and the full requirement list in
[docs/AI_REQUIREMENTS.md](docs/AI_REQUIREMENTS.md).

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional: add OPENAI_API_KEY / LANGSMITH_API_KEY

# Windows
run_demo.bat
# macOS / Linux
./run_demo.sh
```

Or step by step (set `PYTHONPATH=src` first; on Windows `set PYTHONPATH=src`):

```bash
python -m recon_agent.cli generate                     # create dummy data
python -m recon_agent.cli run                          # run the agents
python -m recon_agent.cli ask "how do we treat bank charges?"   # query the SOP knowledge base
python -m recon_agent.cli approve --interactive --checker HV01  # checker reviews proposals
python -m recon_agent.cli verify-audit                 # verify the audit hash chain
streamlit run app.py                                   # checker dashboard
pytest -q                                              # unit + acceptance tests
```

**No API key?** The pipeline runs fully offline: a deterministic rules-based reasoner stands in for the LLM and a
TF-IDF retriever stands in for ChromaDB. Add `OPENAI_API_KEY` to `.env` and install `openai` and `chromadb` to
switch to the live LLM and the vector store. Add `LANGSMITH_API_KEY` to trace every agent step in LangSmith.

## REST API (FastAPI)

The agent is also available as a REST API, so other systems (a SWIFT gateway, a case-management tool, a
dashboard) can call it.

```bash
# Windows: run_api.bat     macOS/Linux: ./run_api.sh
uvicorn recon_agent.api:app --reload          # with PYTHONPATH=src
```

Open **http://127.0.0.1:8000/docs** to see and try every endpoint in the browser.

| Method | Endpoint | What it does |
|---|---|---|
| GET | `/health` | Is the service up? |
| POST | `/reconcile` | Run the agentic reconciliation |
| GET | `/summary` | Figures from the latest run |
| GET | `/breaks?decision=ESCALATE` | List breaks, filtered by category / decision / account |
| GET | `/breaks/{break_id}` | One break with the agent's reasoning and SOP citations |
| GET | `/approvals` | The four-eyes checker queue |
| POST | `/approvals/{break_id}` | Checker approves or rejects (the AI can never approve itself) |
| POST | `/webhooks/statement` | Another system pushes a new MT950; validated before it is stored |
| GET | `/kb/search?q=...` | Search the SOP knowledge base |
| GET | `/audit/verify` | Check the tamper-evident audit chain |

`examples/call_api.py` calls every endpoint with the Python `requests` library. See
[docs/API_GUIDE.md](docs/API_GUIDE.md) for REST, SOAP, webhooks, `requests` and FastAPI explained.

## Dummy data

`data/generate_dummy_data.py` creates three Nostro accounts (USD at Citibank NY, EUR at Deutsche Bank Frankfurt,
GBP at Barclays London), about 140 ledger entries and 140 statement lines, and injects 8 kinds of breaks per
account, each labelled in `data/ground_truth.csv`:

| Injected break | Expected category | Expected decision |
|---|---|---|
| Ledger entry with late cut-off, not on statement | TIMING_DIFFERENCE | Maker proposal |
| Statement fee, code NCHG | BANK_CHARGES | Maker proposal |
| Statement interest, code NINT | INTEREST | Maker proposal |
| Ledger booked twice | DUPLICATE_POSTING | Maker proposal (reversal) |
| Amount differs by a few cents | ROUNDING_FX_DIFFERENCE | Auto-resolve |
| Client receipt short by a fee | AMOUNT_MISMATCH | Maker proposal + MT199 claim |
| Correspondent truncated our reference | (matched by fuzzy rule) | – |
| Credit with no reference | UNIDENTIFIED_RECEIPT | Maker proposal + MT199 query |
| Large unknown debit with "ignore previous instructions" narrative | SUSPICIOUS | Escalate |

## Outputs (`outputs/`)

| File | Content |
|---|---|
| `recon_report.md` | Daily reconciliation pack: statement controls, match rate, breaks and actions, evaluation |
| `matched_items.csv` | Every matched pair and the rule that matched it |
| `breaks_investigated.csv` | Agent plan, findings, category, confidence, root cause, SOP citations, model, prompt version |
| `actions_all.csv` / `approval_queue.csv` | Decisions under control limits; the checker queue |
| `draft_mt199/` | Draft queries to correspondents |
| `audit_log.jsonl` | Hash-chained audit trail of every agent and checker step |
| `evaluation_detail.csv`, `run_summary.json` | Accuracy against ground truth and run metrics |

## Project layout

```
src/recon_agent/
  config.py        settings and control limits (.env overrides)
  mt950_parser.py  SWIFT MT950/940 parser + balance proof
  matching.py      deterministic matching engine
  rag.py           SOP knowledge base: ChromaDB or TF-IDF retrieval with citations
  llm.py           OpenAI / offline LLM, system prompt, LangSmith tracing
  guardrails.py    masking, prompt-injection detection, schema validation, control limits
  agents.py        Ingestion, Matching, Investigation, Resolution agents
  pipeline.py      orchestrator and report
  hitl.py          human checker step (four-eyes)
  audit.py         hash-chained audit log
  evaluation.py    accuracy / recall / coverage vs ground truth
  cli.py           command line
  service.py       API actions as plain functions (testable without a server)
  api.py           FastAPI REST API and webhook
knowledge_base/    dummy SOPs, control policy, MT199 templates, past cases
data/              dummy data generator and generated files
docs/              AI requirements and architecture
tests/             unit and acceptance tests
app.py             Streamlit checker dashboard
examples/          call_api.py: calling the API with requests
```

## Notes

- The 100% accuracy on dummy data comes from the offline rules reasoner, which knows the injected patterns.
  Re-measure with the live LLM, and on masked real data, before drawing conclusions.
- GL codes, limits and SOP text are illustrative; replace them with your bank's actual policies.
