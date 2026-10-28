# GPT2 — source page-plan correspondence diagnostic record identity

Date: 2026-10-29 (AEST). Shadow-only change, scoped to the independent
`pb_source_page11_page7_plan_correspondence_shadow` module.

## Observed code path

`SourcePagePlanCorrespondenceProducer.evaluate_and_publish` accepts a
`SourcePagePlanCorrespondenceSelector`, candidate source-native segment
collections, a figured room box and candidate plan marks. It runs
`build_lines` → `rank_registrations` → `box_correspondence` → material
mark containment, then issues a `SourcePagePlanCorrespondenceRecord`
indexed by the entire `selector.key`. The record is immutable,
CANDIDATE-only, `commercial_projection_allowed=False` and
`takeoff_eligible=False`. Its authority lookup is
`SourcePagePlanCorrespondenceAuthority.resolve`; there is no signed
quantity, issuer, JobHub or frozen evaluator call in this module.

On the checked main version, the producer's `stable_contract_id`
payload omits `decision_scope_id`, geometry, registration, side evidence,
and contained mark locations. Two different candidate claims can
therefore carry the same `record_id`, despite different source/physical
ownership. That is a *diagnostic source-identity collision*, not proof
that either candidate is a physical room.

## Proposed and implemented boundary

Keep the existing source selector, candidate tier, geometric thresholds and
read-only authority unchanged. Calculate the record ID over the same
document/revision/hash/snapshot/page/room lineage **plus** the decision
scope and the actual candidate's room boxes, orientation, scale,
translation, the four paired sides' merged face intervals and second
faces, and the inside-room candidate finish mark code/center observations.
Canonical sorting of candidate mark observations makes input iteration
order immaterial. Source interval union is retained, so splitting a stroke
does not change the record identity. This does not turn caller-supplied
PDF segments into authenticated physical-wall authority.

## Expected abstentions and unchanged boundaries

Original Maryborough p11 FT2/FT3 ↔ p7 OFFICE W4 uniqueness, viewport
crop and competing registrations are still unresolved unless independently
source-authenticated. A CANDIDATE record is not a FIRM floor/finish area.
Do not edit original PDFs, the frozen 120-item benchmark, live quantity
issuers, signed customer rows, the 20,000 primitive cap, or 2.5pt snap.

## Regression evidence to collect

Exercise real candidate record production with changed decision scope,
changed original-face geometry, changed second-wall face and changed
finish-mark center (all must produce distinct IDs). Repeat under input
permutation, line splitting and equivalent source observations (must
reproduce one ID). Confirm each record retains CANDIDATE, no publication,
and no takeoff eligibility. Run exact-head dual Python 3.13/3.14 CI
and other applicable guards before a merge. These source-free regressions
are not an owner-original proof or an accuracy-score claim.
