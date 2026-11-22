# SOP-NR-02: Break Categories and Standard Actions (DUMMY)

## TIMING_DIFFERENCE
Entry booked in our ledger but not yet on the correspondent statement, typically a late cut-off or T+1 settlement at the agent.
Action: keep open, expect on next statement; no adjustment. If not cleared in 2 business days, raise a MT199 query to the correspondent.

## BANK_CHARGES
Debit on the statement with transaction code NCHG (or narrative mentioning fee/charge/maintenance) and no ledger entry.
Action: validate against the correspondent fee schedule, then post a charges entry to GL 640110 (Correspondent Bank Charges). Posting requires checker approval.

## INTEREST
Credit or debit with code NINT and no matching ledger reference, narrative mentions interest.
Action: validate against the agreed Nostro interest rate; post to GL 410220 (Nostro Interest Income) with checker approval.

## DUPLICATE_POSTING
Two ledger entries with the same reference, amount and value date, only one on the statement.
Action: reverse the duplicate ledger entry. Reversal requires checker approval and the original booking user must be notified.

## ROUNDING_FX_DIFFERENCE
Same reference, difference within the tolerance (default 1.00 in account currency), typically FX rate rounding.
Action: may be auto-cleared to GL 699900 (Rounding Differences) when below the auto-action limit and confidence is high.

## AMOUNT_MISMATCH
Same reference, amount differs beyond tolerance. Common cause: the correspondent or an intermediary deducted a fee from a client receipt (SHA/BEN charges) when the instruction said OUR.
Action: check charge instructions on the payment; claim the fee back from the correspondent via MT199, or advise the client. Never write off without approval.

## UNIDENTIFIED_RECEIPT
Credit on the statement with no known reference (NONREF or unknown remitter).
Action: park in the suspense account GL 290500 with approval, query the correspondent for remitter details via MT199. Must not be applied to any client account until identified.

## SUSPICIOUS
Debit we did not instruct, unusually large amount, reference not in our systems, or narrative with unusual instructions.
Action: escalate immediately to Team Lead and Financial Crime Compliance; request recall/cover from the correspondent. No automated action allowed.
