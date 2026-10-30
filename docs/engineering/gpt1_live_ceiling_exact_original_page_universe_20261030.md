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
