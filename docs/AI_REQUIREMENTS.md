# AI Requirements – Agentic AI for FSS Nostro Reconciliation

Version 0.1 · Prototype on dummy data · Owner: Hariprasad Venugopal

Each requirement shows where the prototype implements it. "Planned" items are for the production build.

## 1. Business requirements

| ID | Requirement | Prototype |
|---|---|---|
| BR-01 | Reconcile every FSS Nostro account daily: internal ledger vs correspondent MT950 statement. | `pipeline.run()` |
| BR-02 | Raise the auto-match rate above the manual baseline; target ≥ 90% of items matched without human effort. | `MatchingAgent`, report shows auto-match rate |
| BR-03 | Every break gets a category, root cause, owner and next action on the same day. | `InvestigationAgent`, `ResolutionAgent` |
| BR-04 | Reduce analyst effort on investigation by drafting correspondent queries (MT199) and adjustment proposals. | `outputs/draft_mt199/` |
| BR-05 | No loss of control: four-eyes, limits, escalation and full audit trail remain in force. | §5, §6 |

## 2. Functional requirements

| ID | Requirement | Prototype |
|---|---|---|
| FR-01 | Ingest SWIFT MT950/MT940 statements and ledger extracts (CSV / API). | `mt950_parser.py` |
| FR-02 | Run the balance proof (opening + credits − debits = closing) and stop if it fails. | `Statement.balance_proof_ok`, run stops |
| FR-03 | Data-quality checks: missing references, non-positive amounts, unknown accounts. | `IngestionAgent` |
| FR-04 | Rules-based matching first: exact, tolerance, fuzzy reference, reference-only. | `matching.py` |
| FR-05 | Classify breaks into a controlled list: timing, bank charges, interest, duplicate, rounding/FX, amount mismatch, missing in ledger/statement, unidentified receipt, suspicious. | `config.allowed_categories` |
| FR-06 | The agent plans which tools to use per break type (duplicate search, reference lookup, limit check, amount comparison, knowledge-base search). | `InvestigationAgent.plan()` |
| FR-07 | Retrieve the relevant SOP / policy / past case (RAG) and cite it in every recommendation. | `rag.py`, `citations` column |
| FR-08 | Draft MT199 free-format queries to the correspondent from approved templates. | `ResolutionAgent.draft_query()` |
| FR-09 | Produce the daily reconciliation pack: report, matched items, breaks, actions, approval queue. | `outputs/` |
| FR-10 | Analysts can ask the SOP knowledge base questions in plain English. | `cli ask "…"` |
| FR-11 | Checker reviews and approves/rejects proposals in a queue or dashboard. | `hitl.py`, `app.py` |

## 3. Data requirements

| ID | Requirement | Prototype |
|---|---|---|
| DR-01 | Sources: correspondent MT950 (or ISO 20022 camt.053 – planned), internal FSS ledger, account static data. | `data/` |
| DR-02 | Development and testing use synthetic data only; no client data leaves the bank. | `generate_dummy_data.py` |
| DR-03 | Labelled ground truth for every injected break to measure accuracy. | `data/ground_truth.csv` |
| DR-04 | Data lineage: every output row traces back to a ledger id or statement bank reference. | `break_id` = `ledger_id` / `S-<acct>-<bank_ref>` |
| DR-05 | Production: lakehouse layering (Bronze raw → Silver parsed → Gold reconciled) on Databricks with Unity Catalog permissions. | Planned |

## 4. Model and RAG requirements

| ID | Requirement | Prototype |
|---|---|---|
| MR-01 | LLM is configurable (OpenAI model via env) and runs at temperature 0 for repeatable answers. | `llm.py`, `.env` |
| MR-02 | Structured output: JSON validated against a schema with an allowed category list; invalid answers are rejected. | `guardrails.Investigation` |
| MR-03 | Deterministic fallback when the LLM fails, times out or returns invalid output; the run never stops on AI errors. | `MockLLM` fallback, `llm_error` column |
| MR-04 | Prompt is versioned and the version is logged with every decision. | `prompt_version` |
| MR-05 | Knowledge base chunked by SOP section; top-k retrieval with scores; vector store (ChromaDB) with offline TF-IDF fallback. | `rag.py` |
| MR-06 | Confidence score per classification; low confidence never auto-actions. | `control_decision()` |

## 5. Guardrails and controls

| ID | Requirement | Prototype |
|---|---|---|
| GR-01 | The AI is a maker only. It can never approve its own proposal; maker ≠ checker is enforced. | `hitl.py` blocks checker = maker |
| GR-02 | Auto-action limited to ROUNDING_FX_DIFFERENCE, ≤ 250 in account currency, confidence ≥ 0.90. | `control_decision()` |
| GR-03 | Items ≥ 1,000,000 are escalated regardless of category. | `ESCALATION_AMOUNT` |
| GR-04 | Statement narratives are untrusted: prompt-injection patterns are detected and the item is escalated as suspicious. | `detect_injection()` |
| GR-05 | Client and counterparty names and account numbers are masked before any external LLM call. | `Masker` |
| GR-06 | Suspicious items go to Team Lead and Financial Crime Compliance; no automated action. | ESCALATE path |
| GR-07 | All limits are configuration, not code, and changes are logged. | `.env`, `config.py` |

## 6. Audit, explainability and governance

| ID | Requirement | Prototype |
|---|---|---|
| AG-01 | Immutable audit trail of every agent step: inputs summary, plan, retrieved sources, model, prompt version, output, decision, checker. | `audit_log.jsonl` |
| AG-02 | Tamper evidence: hash-chained log with a verification command. | `cli verify-audit` |
| AG-03 | Explainability: each break shows root cause, evidence findings and SOP citations in plain English. | `breaks_investigated.csv` |
| AG-04 | Model risk management: model inventory entry, validation report, periodic re-validation, change control for prompts and models. | Planned |
| AG-05 | Align with the bank's AI / model risk policy and regulator expectations on outsourcing and data residency. | Planned |

## 7. Evaluation and acceptance criteria

| Metric | Target | Prototype result (dummy data) |
|---|---|---|
| Break coverage (injected breaks found) | 100% | 100% |
| Classification accuracy | ≥ 90% | 100% with the offline rules engine; re-measure with the live LLM |
| Suspicious items escalated | 100% | 100% |
| Auto-actions outside policy | 0 | 0 (enforced in tests) |
| Audit chain intact | Yes | Yes |
| Auto-match rate | ≥ 90% | ≈ 91% |

Acceptance tests: `pytest` (`tests/test_end_to_end.py`). Before go-live, run parallel with the manual process for at least one month-end and compare break lists line by line.

## 8. Non-functional requirements

| ID | Requirement |
|---|---|
| NF-01 | Daily run for all FSS Nostros completes before 10:00 local time. |
| NF-02 | Runs are idempotent and re-runnable for a business date. |
| NF-03 | Secrets in a vault / environment, never in code. |
| NF-04 | Observability: traces per break (LangSmith), run metrics, error alerts. |
| NF-05 | Role-based access: analyst (maker view), checker (approve), auditor (read-only audit log). |
| NF-06 | LLM cost and latency tracked per run; budget alert. |

## 9. Roadmap

1. Prototype on dummy data (this repo).
2. Connect to masked UAT extracts of ledger and MT950; measure accuracy with the live LLM.
3. Databricks pipeline (Bronze/Silver/Gold), ISO 20022 camt.053 support, many-to-one matching.
4. Checker dashboard with SSO; integration to the case management / break tool.
5. Model risk validation, parallel run, controlled go-live.
