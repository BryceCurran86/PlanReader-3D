# GPT1 — exact original ceiling page universe before live source ingestion (2026-10-30)

## OBSERVED — repository and function trace

Base main: `65dc4684fbcf1ce36c704457d896fc7c12a651de`. Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, W1–W10 architecture/spec, retired public-tender firewall, accuracy levers, CI, hub #3462 and GPT1 tracker #2017. Exclusive claim: hub #6510695819 / tracker #6510696485.

`pb_live_ceiling_lining_integration._selected_page_indices` currently uses `int(index)` in a filtering comprehension. This converts `"0"` and `0.0` into original page 0, drops a negative or out-of-range sibling, silently removes bool values, and may throw on malformed input. `collect_live_ceiling_lining_claims` uses this for both `pages` and `topology_pages` **before** `SourceVisibilityProducer.ingest_native_pdf_bytes`; the latter receives only the selected page IDs. A requested original source page can therefore disappear before a ceiling claim is assembled. An invalid topology page can disappear before the subset check.

The real downstream chain is `collect_live_ceiling_lining_claims` → `run_source_owned_ceiling_lining_shadow` → `canonical_ceiling_from_shadow_quantity` / `LiveCeilingLiningResult` → `publish_live_ceiling_area_quantities` or cross-view ceiling issuer → `build_live_ceiling_lining_source_traces` → `project_live_ceiling_customer_rows` / `seal_source_closed_run` → unchanged frozen V2 evaluator. This source selection does **not** grant FIRM measurement or commercial authority; missing source/geometry/finish/scale/axes must continue to abstain.

## INFERRED risk

Partial source-page universes can hide rival finish, physical room, scale, or RCP evidence while retaining a plausible provisional ceiling claim. Coercing imported page selectors makes source identity ambiguous even if a downstream quantity is otherwise well-formed.

## PROPOSED narrow change

Require each explicitly selected page index to be an exact `int` within `[0, page_count)`, validate the entire sequence before deduplication or ingestion, reject malformed containers and mixed valid/invalid inputs with a typed `ValueError`. Preserve `None` = all pages, explicit empty selection, sorted unique valid indices, and the existing topology-pages-subset-of-pages rule. No new page inference, scale, geometry, authority, or customer row. This is a negative-only original-source completeness guard.

## Tests and expected abstentions

Use generated public-safe multi-page PDFs and an ingestion spy: valid page/topology split ingests exactly the requested source pages; bool/float/string/out-of-range/negative/huge/non-iterable and mixed selections fail before source ingestion; deterministic sorted deduplication and no-mutation; topology subset still fails. Tests are source-neutral, not original PDF proof. Full exact-head Python 3.13/3.14 CI, trusted original SHA-verified source replay, signed Lot16 nine and Maryborough three customer/quantity body preservation, and unchanged frozen120 evaluator remain release gates.

## Isolation and benchmark firewall

Only `pb_live_ceiling_lining_integration.py`, one new focused test file and this architecture report are changed. GPT1 #4130 edits `pb_live_physical_net_wall_integration.py` and is separate. GPT2 owns Maryborough physical room/FT2/FT3/RCP; GPT MAX/Claude own hosts/glazing; GPT3 owns signed/customer/frozen scoring. Do not modify private PDFs/tokens, benchmark truth, source snapshots, 20k primitive cap or 2.5 pt snap. No expected BOQ or project name enters prediction. This is an unmerged integrity implementation, not a source-signed FIRM or accuracy gain.

## Follow-up original ceiling quantity page-identity gate (2026-10-30)

**OBSERVED:** After source-owned provisional ceiling quantity shape checks, `_claim_from_quantity` calls `int(meta.get("page_no", -1))`. This can coerce a foreign bool/float/text page token to the source page, or throw for malformed/overflowing tokens. A valid-looking source page alias can therefore pass the quantity-to-canonical-ceiling boundary. This is independent of the entrypoint page-universe repair above.

**INFERRED:** Original PDF page ownership is not safely proven by a coerced metadata token. The correct failure is a missing/invalid ceiling claim (ABSTAIN), not a crash or a guessed page. No new measurement or FIRM authority is implied.

**PROPOSED:** Require `type(meta.get("page_no")) is int` and exact equality to the selected source page before looking up source room/finish/scale evidence. Add source-quantity boundary regressions for valid integer, bool, float, numeric text, NaN/Infinity, object, None and huge values; retain input immutability and deterministic replay. The prior `#4134` source-page entrypoint behavior, legitimate ceiling source claims and commercial isolation remain unchanged.

**RELEASE GATES:** Full exact-head Python 3.13/3.14 CI, trusted SHA-verified original-source producer-to-issuer-to-customer replay, immutable signed Lot16 nine/Maryborough three, and unchanged frozen120 evaluation remain mandatory. The isolated Maryborough original PDF has been SHA-checked, but that alone is not source-positive customer proof. No benchmark or source bytes are committed.

## Follow-up original ceiling quantity-ID collision gate (2026-10-30)

**OBSERVED:** In `pb_live_ceiling_lining_integration.collect_live_ceiling_lining_claims`, the real source-owned ceiling provider returns `result.ceiling_quantities` for a resolved original viewport. The collector appends every validated record to `by_descriptor` while overwriting `validated_quantities[quantity.quantity_id]` on repeated IDs. The aggregate `quantity_m2` sums every appended record, but `room_quantity_ids` is deduplicated and the final `quantity_evidence` retains only the last record. A byte-identical replay of the same original ceiling quantity ID can double provisional m²; a changed record under the same ID can make the claim, canonical ceiling and quantity evidence disagree. This is the FIRST failing source quantity-identity gate, upstream of `publish_live_ceiling_area_quantities`, source-closed seal/customer and unchanged frozen V2 evaluator.

**INFERRED:** A quantity ID denotes one source-owned physical ceiling quantity in one exact original page/viewport. A duplicate with the same typed record and exact scope is an idempotent replay, not a second ceiling. A changed record or cross-scope reuse of the same ID is unresolved source identity, not permission to select first/last or sum both.

**PROPOSED:** Census every source-owned ceiling quantity ID before accepting its live claim. Keep exactly one same-scope equal replay; retain conflict evidence and revoke *all* matching claim, canonical and QuantityEvidence entries on changed/cross-scope reuse. Emit a typed quantity-ID conflict reason. Do not grant source, geometry, material, scale, metric, FIRM or commercial authority. Preserve other independent source IDs. This is not an estimator accuracy gain.

**EXPECTED ABSTENTIONS / TESTS:** A generated original-neutral framed PDF with real source-owned ceiling producer output remains positive; identical quantity-ID replay is byte/quantity-idempotent, not double counted. Changed evidence/confidence under the same ID in either input order abstains for that ID, and the source input is not mutated. Verify real producer→live claim/canonical/evidence coherence. Full exact-head Python3.13/3.14 CI and owner-trusted SHA-verified original-source production replay with signed Lot16 nine/Maryborough three customer body preservation remain release gates. No benchmark gold, private PDF/token, 20k primitive cap or 2.5pt snap changes. Claim: tracker #2017 comment 6512455209, coordination #3462 review 5706966607.


## Follow-up physical canonical ceiling conflict revocation (2026-10-30)

**OBSERVED:** At exact head `5f128c4268aa81f37c2a5c9c48786c706ff6cc5d`, `collect_live_ceiling_lining_claims` detects two distinct source ceiling quantities mapping to one original physical `canonical_ceiling_id`, then removes the disputed canonical object, but retains both `by_descriptor` area rows. A positive provisional claim can therefore double the original ceiling area while its canonical identity is revoked and its issuer evidence is absent. This is the FIRST failing source-owned canonical identity gate before `publish_live_ceiling_area_quantities`, source-closed seal/customer and the unchanged frozen V2 evaluator.

**INFERRED:** Different source quantity IDs cannot independently claim the same physical room/viewport ceiling when the canonical identities conflict. No first/last selection or summation is authoritative. Unrelated source-owned canonical ceilings must remain eligible.

**PROPOSED / IMPLEMENTED:** Census canonical-ID-to-source-quantity-ID ownership; when the existing canonical conflict is detected, revoke all attached descriptor rows and validated issuer evidence together with the disputed canonical object. Preserve `LIVE_CEILING_CANONICAL_IDENTITY_CONFLICT`, independent quantity-ID conflict behavior, valid unrelated positives, existing source/metric/finish/scale gates, and no mutation.

**TEST / RELEASE:** Generated public-safe PDF exercises the real source-owned ceiling producer; inject two otherwise eligible quantity IDs for the same original canonical room, both input orders, deterministic replay, no-mutation and full claim/canonical/issuer abstention. Existing authentic single-ceiling and quantity-ID collision positives remain. Exact-head Python 3.13/3.14 CI and owner-trusted SHA-verified original-source producer→issuer→sealed/customer replay preserving Lot16 signed nine and Maryborough three are mandatory before merge. No original PDF/token, benchmark gold/evaluator, 20k cap, 2.5pt snap, FIRM grant or customer projection change. Exclusive claim: tracker #2017 comment 6514726488; coordination #3462 review 5707966950. This is an unmerged integrity candidate, not an official accuracy gain.


## Follow-up source metric validation before provisional ceiling publication (2026-10-30)

**OBSERVED:** In the real source-owned `collect_live_ceiling_lining_claims` path, `_claim_from_quantity` compares `float(area.value)` with `float(quantity.value)` without requiring exact native numeric types, finite positive m², or catching integer-to-float overflow. Thus a copied boolean/numeric-text source area can pass this early equality check, infinite area can compare equal, and an oversized integer can raise before canonicalization. The downstream real canonical issuer `pb_live_ceiling_area_quantity_publication._publish_one` independently checks native finite area, but it cannot make the earlier provisional source producer's claim or exception safe. The customer bridge `project_live_ceiling_area_customer_rows` consumes only issuer-authorized source-closed quantities; unchanged frozen V2 scoring remains after trusted production replay.

**INFERRED:** Source area is not authenticated by permissive Python float coercion. An invalid or nonpositive room/ceiling area must abstain before the provisional claim and canonical ceiling are built. A legitimate native finite positive int/float must keep its exact numeric value; no minimum area, geometry or finish inference is authorized.

**PROPOSED:** At `_claim_from_quantity`, validate both original room-area and provisional ceiling area as exact built-in int/float, finite positive m², with conversion errors handled; compare the validated metric values. Add positive and adversarial tests for both input positions, bool, numeric text, NaN, infinity, zero/negative, huge integer and arbitrary object, plus deterministic replay and no input mutation. Keep source/room/viewport/finish/figured-axis/scale gates unchanged. This is one source-metric integrity gate, not a new source-signed FIRM quantity.

**BENCHMARK EXCLUSION / RELEASE:** No original PDF, private token, signed fixture, frozen120 truth/evaluator, 20k primitive cap or 2.5pt snap is changed. Exact-head full Python 3.13/3.14 CI, technical self-review, SHA-verified owner-trusted original source producer→real issuer→sealed/customer replay, and byte-identical Lot16 nine plus Maryborough three preservation remain mandatory before merge. Exclusive claim tracker #2017 comment 6516064988 and coordination #3462 review 5708591744.


## Follow-up: exact original ceiling material receipt types (2026-10-30)

**OBSERVED** (main `65dc4684fbcf1ce36c704457d896fc7c12a651de`, draft `#4134` at `5069b19e437f2f006f56047d2ff1b7ad15601b2e`): `pb_ceiling_lining_quantity.build_ceiling_lining_quantity` emits `finish_descriptor` as producer-owned text and `finish_source_methods` / `finish_evidence_ids` as typed source tuples. `pb_live_ceiling_lining_integration._claim_from_quantity` currently stringifies, strips and iterates imported metadata before verifying producer-owned finish methods and receipt inclusion. An imported bare string, numeric token, padded receipt or malformed container can be coerced to match original material provenance or raise unexpectedly. This is the FIRST failing material-receipt shape gate on source-owned ceiling shadow -> live claim -> canonical ceiling -> real FIRM issuer -> source-closed customer -> unchanged frozen V2 evaluator.

**INFERRED:** A matching normalized string is not proof of an original text-integrity observation or its physical material ownership. Rejecting malformed metadata prevents false source-material promotion; it does not establish new finish semantics or a new FIRM ceiling.

**PROPOSED:** Require an exact native, nonblank, unpadded descriptor; typed tuple/list method and receipt sequences with exact nonblank unpadded string members; the existing `SOURCE_CEILING_FINISH_METHOD` and exact finish receipt subset of typed source quantity evidence. Reject duplicate receipt IDs, malformed iterables and coercible aliases without sorting/deduplicating them into apparent source evidence. Retain valid source tuples and the existing no-claim/ABSTAIN behavior. Add focused adversarial, positive, deterministic replay and input-preservation tests using the existing source-shaped fixture. No second material authority or guessed RCP room ownership.

**BENCHMARK FIREWALL / RELEASE:** Do not use expected V2 quantities to set these rules. No benchmark truth, original PDFs, credentials, source snapshot, signed customer body, 20k raster cap, 2.5pt snap or other agents' lanes changed. Require fresh exact-head Python 3.13/3.14, trusted original SHA-verified production replay and immutable nine Lot16 + three Maryborough signed/customer body comparison before merging. Integrity-only, no claimed FIRM/accuracy gain.


## GPT1 follow-up — finite aggregate original ceiling m² (2026-10-30 17:12 AEST)

**OBSERVED** (head `737757144be26d7144abaddfed5ca20d044edafd`, main `65dc4684fbcf1ce36c704457d896fc7c12a651de`): `_claim_from_quantity` verifies each producer-owned metric area as native finite positive. However `collect_live_ceiling_lining_claims` groups independently validated rows by source finish descriptor, then performs `quantity_m2 = sum(row[3] for row in rows)` without a finite aggregate check. Two distinct individually finite positive original m² values (e.g. 1e308 each in an adversarial test) produce `inf`; `stable_contract_id` then receives a nonphysical quantity, before any downstream quantity issuer/customer seal. The same collector supplies `LiveCeilingLiningResult.claims` and `quantity_evidence` to `publish_live_ceiling_area_quantities` and customer projection. The unchanged frozen V2 evaluator is post-seal only.

**INFERENCE:** The live original Maryborough source is not proven to contain such large areas. This is an independently demonstrated source-metric overflow hazard, not a new original-source quantity or frozen score gain. SHA-256 of owner-controlled private Maryborough PDF was independently verified in an isolated runtime as `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007` (31 pages); source identity is not full production replay or signed-output preservation.

**PROPOSED:** Retain the existing `sum` exactly (to preserve byte-identical finite totals and stable IDs), but reject a nonfinite or nonpositive descriptor aggregate before building any claim. Record a typed aggregate-nonfinite reason. Keep unrelated descriptors, all plausible candidates and existing canonical/issuer evidence gates unchanged. Tests: valid finite sums and stable real generated-PDF producer→issuer/customer parity, adversarial finite-input aggregate overflow in the actual collector, deterministic replay, no input mutation, and no FIRM/customer output. No PDF/tokens, frozen truth/evaluator, source geometry, guessed dimensions, 20k raster cap or 2.5pt snap changes. This correction remains DRAFT until exact-head Python 3.13/3.14 and original-source signed/customer preservation gates pass.

## 2026-10-30 — incomplete original source-viewport producer universe

**Observed repository behavior:** `collect_live_ceiling_lining_claims` ingests the selected original PDF page universe and iterates independently authoritative F.07 floor-plan viewports. The per-viewport `run_source_owned_ceiling_lining_shadow` call was wrapped in `except Exception: continue`, silently dropping a failed viewport while previously collected source claims remained eligible for `canonical_ceiling_from_shadow_quantity` and the real `publish_live_ceiling_area_quantities` / `project_live_ceiling_area_customer_rows` consumers.

**Inference:** A partial successful source-viewport run does not prove that a descriptor is complete across the selected original drawing. A later/earlier failed sibling may contain conflicting or duplicate physical ceilings; the system cannot publish the successful sibling as a complete measured source universe.

**Narrow change:** Fail closed for the entire selected live ceiling collection on a per-viewport source producer exception. Return typed `ABSTAINED`, `live_ceiling_lining_unavailable` and `live_ceiling_lining_source_viewport_failure`, with zero claims, canonical objects and issuer evidence. No guessed replacement viewport, source dimensions, defaults or changed source authority. The existing fully successful path is untouched.

**Proof and limits:** The generated native-PDF regression first establishes a real source-positive ceiling via the unmodified producer, then injects a second independently identified viewport that fails before or after the valid viewport. Both orders and deterministic replays must abstain at the collector, real FIRM issuer and customer projection. These tests do not authenticate any private original PDF, signed customer preservation or frozen V2 score; those release gates remain mandatory before merge. GPT2 physical FT/RCP, GPT MAX/Claude host/glazing, GPT3 signing/scoring, source PDFs/tokens, frozen evaluator, 20k cap and 2.5pt snap remain untouched.


## 2026-10-30 19:23 AEST — canonical room presence before live claim

**OBSERVED:** In `collect_live_ceiling_lining_claims`, `_claim_from_quantity`
authenticates provisional source-owned metric/material receipts, but the collector
previously appended the descriptor claim row and source quantity **before**
`canonical_ceiling_from_shadow_quantity` checked the producer-owned room index
and polygon. If the room index/room polygon was absent, the live provisional
claim survived with no corresponding canonical physical ceiling. The later
`publish_live_ceiling_area_quantities` requires a canonical/source pair, but
the earlier claim boundary remained inconsistent.

**INFERENCE:** An incomplete physical room-index replay can produce misleading
live provisional ceiling totals even while the FIRM issuer correctly abstains.
This is an integrity gate, not evidence that the original Maryborough RCP
contains an authenticated area or material.

**PROPOSED AND IMPLEMENTED:** Require a non-None source-owned canonical ceiling
object before retaining a descriptor row or source quantity. Existing
canonical-identity and quantity-ID conflict revocations still apply. Keep
independent supported objects and all abstentions; do not create polygons,
metrics, materials, FIRM status or customer rows.

**TEST PLAN:** Generated native-PDF positive producer baseline and deterministic
adversarial replay with a missing source-owned room index; verify no provisional
claim, canonical object, issuer quantity or customer row, with original producer
inputs unchanged. Exact-head Python 3.13/3.14 and trusted SHA-verified original
source→issuer→sealed/customer replay (Lot16 nine, Maryborough three preserved)
remain release gates. No frozen V2 score or FIRM improvement is asserted.

**FILES UNTOUCHED:** GPT2 FT/RCP physical source interpretation, GPT MAX/Claude
opening hosts, GPT3 signing/scoring, original PDFs/tokens, signed fixtures,
frozen evaluator, 20,000 primitive cap and 2.5pt snap.


## 2026-10-30 20:52 AEST — complete original published revision-snapshot universe

**OBSERVED:** After SourceVisibilityProducer.ingest_native_pdf_bytes selects
the original PDF pages, collect_live_ceiling_lining_claims obtains the
published revision snapshot separately for every authoritative F.07 viewport.
Before this change, published_snapshot_for_revision returning None silently
continued, omitting the missing viewport and leaving any previously accepted
sibling's ceiling claims, canonical objects and source quantity evidence
eligible. The earlier source-viewport exception fix did not cover this
non-exceptional missing-snapshot outcome. This is the FIRST failing source
snapshot completeness gate before run_source_owned_ceiling_lining_shadow,
canonical_ceiling_from_shadow_quantity,
publish_live_ceiling_area_quantities, source-closed customer sealing and
the unchanged frozen V2 evaluator.

**INFERRED:** A partial published source snapshot is not evidence that the
unexamined viewport lacks another ceiling or conflicting finish. Continuing
could expose a plausible but incomplete live ceiling area. No original
Maryborough source has yet been demonstrated to hit this path.

**IMPLEMENTATION:** Return a complete LiveCeilingLiningResult with
ABSTAINED, live_ceiling_lining_unavailable and the distinct
live_ceiling_lining_source_snapshot_unavailable reason immediately on a
missing published snapshot. Do not keep earlier sibling claims, canonical
ceilings or issuer quantity evidence. Do not infer source snapshots or change
any upstream source, physical, metric or finish authority.

**TESTS:** Generate a native PDF with a real source-positive ceiling producer
baseline, then inject a second selected F.07 viewport whose published revision
snapshot is unavailable before or after the real one. Assert deterministic
complete abstention in both orders, original PDF bytes and source viewport
unchanged, and zero outputs from the real FIRM quantity issuer and source-closed
customer projection. These are generated-PDF/adversarial safety tests only.

**RELEASE:** New exact-head Python 3.13 and 3.14 CI must pass. Owner-trusted
SHA-verified original-source producer→issuer→sealed/customer replay and
immutable nine Lot16 plus three Maryborough signed/customer bodies remain
mandatory before merge. This is an unmerged integrity candidate, not a new
FIRM ceiling, commercial customer quantity or official frozen120 score rise.
No changes to GPT2 FT2/FT3/RCP physical ownership, GPT MAX/Claude host/glazing,
GPT3 signing/scoring, other GPT1 PRs, private PDFs/tokens, frozen truth,
20,000 raster cap or 2.5pt snap.


## GPT1 — post-producer source-root and viewport continuity (2026-10-30)

**OBSERVED on main and draft #4134:** `collect_live_ceiling_lining_claims`
reads the exact original PDF bytes, publishes a source revision through
`SourceVisibilityProducer.ingest_native_pdf_bytes`, and creates one
`ProviderContext` per authenticated F.07 viewport. It calls
`run_source_owned_ceiling_lining_shadow`, which legitimately replaces ONLY
`evidence_snapshot_id` when the trusted wall producer advances the source
snapshot. The collector then used the returned `effective_context` to create
`LiveCanonicalCeilingSurfaceObject` without checking that its document,
SHA-256, revision, selected page, viewport, and project/workspace owner still
matched the collector's original context. Provisional claims used the PDF
SHA and initial published revision, creating an inconsistent source-root
handoff if the returned context was substituted.

**INFERRED failure:** a returned provider result with a foreign source root
could survive the provisional collector and create a canonical ceiling under
a different source identity. The downstream issuer/customer may independently
reject it, but that is too late for a source-closed provisional collector.
The first failing boundary is the post-producer result-context check, not
floor/ceiling geometry or finish semantics.

**IMPLEMENTED:** `_source_result_context_matches` requires the exact
`ProviderContext` type and equality with the collector's context except
for the nonempty, producer-advanced source snapshot ID. A mismatch makes
the **entire selected source run** ABSTAINED with
`live_ceiling_lining_source_context_mismatch` and no claims, canonical
ceilings or quantity evidence. The genuine wall-producer snapshot advance
remains accepted. No source-derived dimension, room, finish, material, FIRM
authority, scoring or customer publication is invented.

**TEST DESIGN:** generated native PDF real-source positive; post-producer
injected foreign document, SHA, revision, page, viewport, owner and blank
snapshot negatives; before/after ordering of a valid viewport with a
foreign-source sibling; deterministic replay and original-PDF preservation.
Check `publish_live_ceiling_area_quantities` and
`project_live_ceiling_area_customer_rows` return no issued/customer quantities
for every invalid source context. This is source-neutral regression, **not**
an original Maryborough/Lot16 source-positive replay.

**RELEASE GATES:** exact-head Python 3.13/3.14 CI, full source-closed
SHA-verified original producer→real issuer→sealed/customer replay and
byte-identical preservation of the existing nine Lot16 signed/customer
quantity bodies and three Maryborough floor inputs are still required.
Do not merge or count toward accuracy before those checks. The unchanged
frozen 120-item evaluator, PDFs, credentials, 20k primitive cap and
2.5pt snap remain untouched. GPT2 owns original FT/RCP physical source
correspondence, GPT MAX/Claude host/glazing, GPT3 signing/scoring.


## Follow-up source room-polygon geometry completeness gate (2026-10-30)

**OBSERVED:** Exact head `a82788ae2ab2e879abc46411ea303a7755a900a9`; live producer `collect_live_ceiling_lining_claims` validates a provisional ceiling metric via `_claim_from_quantity`, then `canonical_ceiling_from_shadow_quantity` reads `source_result.pipeline.room_area_bridge.room_index.room(room_id).polygon_pdf_pts`. Only `len >= 3` is checked before unguarded `float(point[0/1])` conversion and `geometry_complete=True`. Invalid native coordinates (bool/text aliases, NaN/Infinity, huge-int overflow) or zero-area collinear polygons can therefore either crash or be labelled physically complete. `publish_live_ceiling_area_quantities` trusts the canonical geometry-complete flag and does not independently reconstruct the source polygon; source-closed export/customer follow the published QuantityEvidence. This is the FIRST failing source geometry gate, independent of GPT2's original physical-room/W4 ownership.

**INFERRED:** A canonical ceiling must not assert source-room geometry completeness from a malformed/nonphysical polygon. Source-native 2D points must be finite real numbers (not bool or numeric text); the polygon must have a finite, nonzero signed area. Rejecting this input cannot create new area, room ownership or material authority.

**PROPOSED:** In the existing GPT1 integration only, validate each point's native type and finite conversion, compute finite nonzero twice-signed area using origin-relative triangle fan and `math.fsum`, return `None` before canonical creation on invalid source geometry. Preserve the exact ordered point tuple for legitimate original source polygons. The test will use the existing generated native PDF and real source producer, replace only its room-index geometry receipt with adversarial rings, and assert deterministic ABSTAIN through live claims, canonical objects, real QuantityEvidence issuer and customer projection. Include positive finite source polygon and no-input-mutation checks. No new source measurements or benchmark values, no PDF/tokens, no 20k/2.5pt change.

**RELEASE:** This is a source-integrity candidate, not a FIRM/score improvement. Exact-head Python3.13/3.14 tests and owner-only SHA-verified original-source replay with immutable Lot16 nine and Maryborough three signed/customer bodies remain required before merge. Exclusive coordination claim #4135 comment 6524458042 and tracker #2017 comment 6524459362.
