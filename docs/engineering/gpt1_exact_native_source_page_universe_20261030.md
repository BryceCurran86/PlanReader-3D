# GPT1 — Exact native PDF page-universe admission (2026-10-30)

## Observed repository behavior

`pb_live_physical_net_wall_integration._selected_page_indices` currently filters a caller's source page sequence with `isinstance(page, int)` and an in-range predicate, then coerces with `int(page)`. Thus `True` is admitted as native PDF page index 1 and malformed/out-of-range competing page entries are silently discarded if any other entry is valid. `_collect_live_physical_net_wall_claim` invokes this selector for the decoded geometry universe, physical topology, original room-area support and finish/RCP semantic pages before the `SourceVisibilityProducer.ingest_native_pdf_bytes` call. The actual path continues through `compose_live_wall_opening_authority`, source-owned physical/canonical room/finish/ceiling quantity issuers, source-closed traces, customer verification and the unchanged frozen V2 evaluator. Opening-area recovery already has stricter separate page checks; ordinary production does not.

## First failing gate and inference

An invalid or partially elided caller page universe can hide a source sheet or conflicting source evidence while retaining apparently valid selected pages. This is a source-scope completeness and identity defect, **not** a reason to infer a missing dimension, physical room, finish mark, scale, host, count, or FIRM area.

## Narrow correction

Reject the entire explicit page selection unless it is a replayable list/tuple of **exact** native integers, every member is in range, and the selection is nonempty. Do not silently repair, drop, coerce or truncate any invalid member. Preserve the existing deterministic sorted unique valid page selection and `pages=None` all-page behavior; repeated *valid* page indices are idempotent and do not create additional physical evidence. The existing subset requirement for topology and original-source authority downstream remains unchanged.

## Tests and release firewall

Exercise direct selector and actual generated-PDF public entrypoint with mixed valid+invalid members (boolean, float, string, negative, out of range, one-shot iterable), all-invalid, legitimate Maryborough-shaped valid selectors, sorted-order/duplicate invariance and no-mutation. An invalid source scope must fail **before** the native producer is instantiated. Do not use benchmark truth, synthetic positives as FIRM proof, or alter signed/customer outputs. Exact-head Python 3.13/3.14 CI, technical diff review, SHA-verified original-source production replay and byte-exact preservation of nine Lot16 signed customer bodies and three verified Maryborough floor inputs are required before merge.

## Isolation

Only `pb_live_physical_net_wall_integration.py`, a GPT1-specific regression file and this report. No GPT2 original FT2/FT3/RCP geometry or material authority, GPT MAX/Claude opening hosts, GPT3 signing/scoring, other GPT1 draft, original PDFs/tokens, frozen120 truth/evaluator, 20,000 primitive cap or 2.5pt snap changes. This is source-scope integrity, not an accuracy milestone.
