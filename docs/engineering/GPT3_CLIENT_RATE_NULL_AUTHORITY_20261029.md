# GPT3 commercial client-rate source authority — 2026-10-29

## Observed
The SQLite source to source-sealed JobHub customer pipeline used rate = float(r["rate"] or 0.0) for all modes. SQL NULL therefore became an apparently approved $0 client rate. An explicitly zero total also yields a passing commercial quote cost calculation even though there is no entered rate. Missing commercial total is already rejected separately.

## Production fix
Reject missing SQL unit rate in COMMERCIAL before sealing a customer payload, with its physical source row ID in the error. Preserve actual explicit zero unit price plus zero total; preserve all other verified customer rates and decimal cent totals. Draft remains noncommercial and can display provisional zero estimate without making it a sale.

## Focused verification
Source-neutral real SQLite null rate and absent/zero/positive totals blocked; valid explicitly entered $0, $20, high-precision rate passes actual payload SHA, commercial gate and JobHub persisted lines; draft remains Draft. Existing no-inferred-total and price mismatch checks remain.

## Frozen and private-source firewall
Three files only. No original PDFs, source-signed issuer, archived customer receipts, frozen evaluator/denominators, 20,000 primitive cap or 2.5pt snap edits. This is a negative-only commercial pricing safeguard; no FIRM or frozen120 score gain. Exact-head full dual Python3.13/3.14 and all relevant companion checks required before merge.
