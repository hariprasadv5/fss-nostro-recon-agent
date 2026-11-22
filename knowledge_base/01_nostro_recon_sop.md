# SOP-NR-01: Daily Nostro Reconciliation – Funds & Securities Services (DUMMY)

## Purpose
Reconcile every FSS Nostro account daily: internal ledger (our books) against the correspondent's SWIFT MT950 statement (their books).

## Daily steps
1. Load MT950 statements received by 08:00 local time. Run the balance proof: opening balance + credits - debits must equal the closing balance. If the proof fails, stop and request a re-send of the statement from the correspondent.
2. Run auto-matching: exact, tolerance, fuzzy reference.
3. Investigate every open break the same day. Each break must have a category, an owner and a next action.
4. Breaks older than 3 business days are escalated to the Team Lead; older than 10 business days to the Head of FSS Operations and Finance.
5. Sign-off: the maker prepares the reconciliation, a different checker approves it (four-eyes principle).

## Ageing buckets
- 0-3 days: operations analyst
- 4-10 days: team lead, chase correspondent with MT199/MT999 query
- over 10 days: provision review by Finance; report in monthly control MI
