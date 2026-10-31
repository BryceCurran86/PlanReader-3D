# GPT2 — original RCP cross-sheet translation at native source precision

2026-10-29 AEST. A120 source-geometry candidate only; no ceiling m².

## First observed defect

Original floor/finish ink-ring source diagnostic compares native PDF points
after rounding x+dx and y+dy to three decimal places. That is the exact
already-used source comparison precision; it is not a floor area tolerance.

`pb_gpt2_w4_rcp_source_handoff.audit_gpt2_w4_original_rcp_ceiling_handoff`
checks a sealed W4 physical room and independently owned A120 material,
viewport, page, revision and snapshot. Its *last* source geometry check
instead float-converts any translation values (including Boolean and
string aliases) and compares an unrounded floating affine translation
via Shapely topological `equals()` against rounded native source points.
IEEE binary addition can make 20.12 + 0.1 appear as
20.220000000000002 rather than the producer's 20.22. Conversely,
`True` may be accepted as an invented 1-pt offset.

## Implementation

Reject nonnative translated coordinates: require exactly two `int` or
`float` values, excluding booleans, strings and nonfinite values.
Compare an explicitly translated copy of the actual source-floor
polygon at the same three-decimal coordinate precision already used
by the native source issuer. Do not change W4 room ownership,
original material-code identity, competing mark scope or any metric
ceiling computation. This is negative/compatibility geometry only.

Add adversarial source-free RCP regression tests for fractional native
coordinates, exact-equivalent decimal receipt, strings/booleans/nonfinite
vectors, and a truly different physical offset that still abstains.

## Authority limits

This bridge remains source-only and candidate-tier; the original
ceiling polygon is not a signed ceiling area. The page-9 RCP is not
interchangeable with page-7 floor area. No private customer PDFs,
source tokens, frozen120 truth, 20,000 primitive cap, 2.5pt snap,
customer output, GPT1 issuer or GPT3 signer is changed.
Owner-only original replay and exact-head Python3.13/3.14 CI are
release gates; synthetic-only passing tests do not prove physical
source authority or an accuracy-score increase.
