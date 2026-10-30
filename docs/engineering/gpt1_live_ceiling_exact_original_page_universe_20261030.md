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
