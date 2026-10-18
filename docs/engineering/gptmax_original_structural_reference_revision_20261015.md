# GPT MAX — original structural reference applicability, before any wall transfer

Tracking #2396, original source addition #2782, structural source blocker #2207. Architecture preflight: issue #2396 comment6188488810.

## Observed original source evidence

The original structural PDF (SHA256 `b40259589dd39a46e45d25e145cfa789d9a9415b50613ebc4fee01dceab6b3d6`), page 11, visually prints **Referenced Documents — Architectural drawings issued to STA on 22/01/26**. The separate original architectural PDF (SHA256 `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`), page 3, visibly prints **FLOOR PLAN — DATE 28/07/26 — REV E**.

The observed mismatch does not prove every January engineering detail invalid. It does mean that the structural source cannot currently authenticate July Rev E physical wall/opening correspondence. Separate SourceVisibilityProducer source roots, revision applicability, and structural W4/host/frame evidence cannot be aliased by common address, project, or title-block scale.

## Read-only diagnostic contract

`tools/diag_gptmax_structural_reference_revision.py` accepts explicit original PDF bytes and one-based page selectors. It inventories all matching engineer-certified architectural reference-date candidates and source-local title-block DATE-field candidates. A missing/invalid/competing date abstains; a print-date match is never treated as a source or physical identity proof. These are *native text candidates*, not independently authenticated `SourceVisibilityProducer.text_integrity_authority` receipts; the output always sets `source_text_integrity_verified=false`. No cross-file identity, revision applicability, dimension, scale, quantity, or customer-output grant is possible in this script.

## Verification and release boundary

10 local synthetic tests passed, covering different dates, same-date false equivalence, missing/invalid/competing references, original title-block label opposition, explicit pages, determinism. Actual owner-provided original PDFs, SHA-verified, yield referenced **2026-01-22** versus architectural **2026-07-28**. Exact-head GitHub workflow runs these tests under Python 3.13 and 3.14 and a separately SHA-pinned original source replay. Original architecture baseline 21 physical openings, 15 authenticated hosts, 9 frames, and 8 accepted customer quantities is unaffected because production producers are unchanged.

Untouched: all original sources, W2/W3/W4, physical opening/host/frame/canonical/measurement/quantity/customer, 20,000-primitive safety cap, frozen V2 references/manifests/evaluator/tolerances, signed V1 receipts.

Next authority stage: resolve a producer-issued text-integrity receipt for the actual certified reference and Rev E field, then obtain an explicit source-owner revision-compatibility record and physical wall-primitive equivalence. Do not pass either source's own evidence into the other snapshot until those independent gates close. This diagnostic is intentionally unpublished and requires independent source review before further promotion.
