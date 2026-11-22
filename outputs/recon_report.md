# Nostro Reconciliation Report - FSS (DUMMY DATA)

Run: RUN-20261121T184229  |  LLM: mock-rules-v1  |  Retriever: tfidf

## Statement controls

| Account | Stmt no | Lines | Opening | Closing | Balance proof |
|---|---|---|---|---|---|
| NOS-EUR-002 | 302/1 | 48 | 12,300,000.00 | 16,299,517.07 | OK |
| NOS-GBP-003 | 303/1 | 48 | 6,780,000.00 | 18,227,411.68 | OK |
| NOS-USD-001 | 301/1 | 48 | 25,450,000.00 | 31,788,606.16 | OK |

## Matching

- Auto-match rate: **91.5%**
- Matched pairs: 129 (tolerance 3, fuzzy reference 3)
- Breaks for investigation: 24

## Breaks and actions

| Break | Account | Amount | Category | Conf. | Decision | Proposed action |
|---|---|---|---|---|---|---|
| L-FSS26112000088 | NOS-EUR-002 | EUR 0.37 | ROUNDING_FX_DIFFERENCE | 0.96 | AUTO_RESOLVE | Clear difference to GL 699900 (Rounding Differences). |
| L-FSS26112000043 | NOS-USD-001 | USD 0.05 | ROUNDING_FX_DIFFERENCE | 0.96 | AUTO_RESOLVE | Clear difference to GL 699900 (Rounding Differences). |
| L-FSS26112000133 | NOS-GBP-003 | GBP 0.01 | ROUNDING_FX_DIFFERENCE | 0.96 | AUTO_RESOLVE | Clear difference to GL 699900 (Rounding Differences). |
| S-NOS-EUR-002-DEUT52101056 | NOS-EUR-002 | EUR 2,364,217.78 | SUSPICIOUS | 0.97 | ESCALATE | Escalate to Team Lead and Financial Crime Compliance; request recall from correspondent. No automated action. |
| S-NOS-GBP-003-BARC96911784 | NOS-GBP-003 | GBP 1,672,391.84 | SUSPICIOUS | 0.97 | ESCALATE | Escalate to Team Lead and Financial Crime Compliance; request recall from correspondent. No automated action. |
| S-NOS-USD-001-CITI94705205 | NOS-USD-001 | USD 1,517,977.10 | SUSPICIOUS | 0.97 | ESCALATE | Escalate to Team Lead and Financial Crime Compliance; request recall from correspondent. No automated action. |
| L-FSS26112000087-DUP | NOS-EUR-002 | EUR 388,411.19 | DUPLICATE_POSTING | 0.95 | MAKER_PROPOSAL | Propose reversal of the duplicate ledger entry for checker approval; notify booking user. |
| L-FSS26112000042-DUP | NOS-USD-001 | USD 314,342.82 | DUPLICATE_POSTING | 0.95 | MAKER_PROPOSAL | Propose reversal of the duplicate ledger entry for checker approval; notify booking user. |
| L-FSS26112000041 | NOS-USD-001 | USD 232,101.57 | TIMING_DIFFERENCE | 0.85 | MAKER_PROPOSAL | Keep open and expect on next statement; raise MT199 if not cleared in 2 business days. |
| L-FSS26112000132-DUP | NOS-GBP-003 | GBP 188,829.05 | DUPLICATE_POSTING | 0.95 | MAKER_PROPOSAL | Propose reversal of the duplicate ledger entry for checker approval; notify booking user. |
| L-FSS26112000131 | NOS-GBP-003 | GBP 186,479.00 | TIMING_DIFFERENCE | 0.85 | MAKER_PROPOSAL | Keep open and expect on next statement; raise MT199 if not cleared in 2 business days. |
| L-FSS26112000086 | NOS-EUR-002 | EUR 118,931.55 | TIMING_DIFFERENCE | 0.85 | MAKER_PROPOSAL | Keep open and expect on next statement; raise MT199 if not cleared in 2 business days. |
| S-NOS-GBP-003-BARC59737181 | NOS-GBP-003 | GBP 44,270.24 | UNIDENTIFIED_RECEIPT | 0.86 | MAKER_PROPOSAL | Park in suspense GL 290500 with approval and query correspondent for remitter details. |
| S-NOS-USD-001-CITI39557077 | NOS-USD-001 | USD 28,409.18 | UNIDENTIFIED_RECEIPT | 0.86 | MAKER_PROPOSAL | Park in suspense GL 290500 with approval and query correspondent for remitter details. |
| S-NOS-EUR-002-DEUT68326160 | NOS-EUR-002 | EUR 18,672.20 | UNIDENTIFIED_RECEIPT | 0.86 | MAKER_PROPOSAL | Park in suspense GL 290500 with approval and query correspondent for remitter details. |
| S-NOS-USD-001-CITIINT665492 | NOS-USD-001 | USD 2,416.25 | INTEREST | 0.93 | MAKER_PROPOSAL | Validate rate and post to GL 410220 with checker approval. |
| S-NOS-GBP-003-BARCINT493537 | NOS-GBP-003 | GBP 1,741.77 | INTEREST | 0.93 | MAKER_PROPOSAL | Validate rate and post to GL 410220 with checker approval. |
| S-NOS-EUR-002-DEUTINT172792 | NOS-EUR-002 | EUR 804.72 | INTEREST | 0.93 | MAKER_PROPOSAL | Validate rate and post to GL 410220 with checker approval. |
| S-NOS-USD-001-CITICHG543692 | NOS-USD-001 | USD 75.00 | BANK_CHARGES | 0.94 | MAKER_PROPOSAL | Validate against fee schedule and post to GL 640110 with checker approval. |
| S-NOS-EUR-002-DEUTCHG444207 | NOS-EUR-002 | EUR 60.00 | BANK_CHARGES | 0.94 | MAKER_PROPOSAL | Validate against fee schedule and post to GL 640110 with checker approval. |
| S-NOS-GBP-003-BARCCHG703766 | NOS-GBP-003 | GBP 45.00 | BANK_CHARGES | 0.94 | MAKER_PROPOSAL | Validate against fee schedule and post to GL 640110 with checker approval. |
| L-FSS26112000044 | NOS-USD-001 | USD 15.00 | AMOUNT_MISMATCH | 0.88 | MAKER_PROPOSAL | Check charge instruction (OUR/SHA); claim deducted fee via MT199 or advise client. No write-off without approval. |
| L-FSS26112000089 | NOS-EUR-002 | EUR 15.00 | AMOUNT_MISMATCH | 0.88 | MAKER_PROPOSAL | Check charge instruction (OUR/SHA); claim deducted fee via MT199 or advise client. No write-off without approval. |
| L-FSS26112000134 | NOS-GBP-003 | GBP 15.00 | AMOUNT_MISMATCH | 0.88 | MAKER_PROPOSAL | Check charge instruction (OUR/SHA); claim deducted fee via MT199 or advise client. No write-off without approval. |

## Model evaluation (against injected ground truth)

- Classification accuracy: **100.0%** on 24 labelled breaks
- Break coverage (labelled breaks found): 100.0%
- Suspicious items escalated: 100.0%

_All actions except AUTO_RESOLVE wait for a human checker (four-eyes). See approval_queue.csv._
