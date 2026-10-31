# GPT3 — legacy typed JobHub quantity source metadata receipt

2026-10-31 AEST; source-neutral architecture review against main `953d4951f23cf2323721abfc7b0dab076bb58eb8`.

## OBSERVED live repository behavior

`pb_takeoff_output_authority.TakeoffOutputRow.from_dict` (already corrected on main by #4107) refuses publishable input whose explicit serialized source/authority fields are absent, blank or non-native strings; unpublished legacy rows receive BLOCKED/BLOCKED. `pb_planreader_jobhub_publish_contract.PlanReaderJobHubQuantityRow.from_dict` still substitutes `documented_dimension` and `firm` when `source_type` and `authority_status` are absent or falsy. Raw dictionary `run_jobhub_publish_preflight` rejects those omissions, but a typed deserialized row takes the direct typed branch, which cannot recover the missing original receipt. With source page, dimension_text_id, a matching revision and an explicit true publishability flag, the final legacy commercial gate may accept a row whose source identity was never actually asserted.

## INFERRED first failing source-to-customer boundary

Serialized untrusted legacy quantity → `PlanReaderJobHubQuantityRow.from_dict` creates documented/firm metadata → `run_jobhub_publish_preflight` receives typed row and cannot distinguish defaulted from source-issued authority → `build_jobhub_payload` can make a customer-ready payload. This is an authorization/lineage integrity defect, not a new metric detector or a source-backed accuracy gain. Fingerprint computation cannot authenticate evidence that was synthesized before hashing.

## PROPOSED negative-only correction

Treat a serialized `is_publishable=True` claim as invalid unless both source fields are exact nonblank native strings, with no coercion. Unpublishable legacy snapshots missing either receipt remain hydratable but both source and authority are explicitly `blocked`. Already complete source-approved serialized records and real direct issuer rows behave identically. Do not change defaults of directly constructed dataclasses or any unrelated source/quantity family.

Focused synthetic test matrix: missing each/both receipts, empty, whitespace-only, None, bool/numeric/list object, complete valid positive, unpublished backward-compatible negative, raw and typed preflight equivalence, end-to-end builder result, determinism and caller immutability.

## BENCHMARK observation (not implementation input)

Frozen Full Plan V2 has 120 immutable denominator objects. No expected BOQ quantity, filename, drawing label, gold mapping or score is used as an implementation input. This guard supplies zero original-backed signed quantities; #3796's owner-trusted original 8-default/9-explicit both-Python sealed/customer acceptance and four authenticated projects remain independent release gates.

## SCOPE / SAFETY

ONLY the legacy JobHub deserializer, dedicated test and this report. No original PDFs, credentials, source producer, receipt ledger, signed Lot16 nine/Maryborough three, customer archives, frozen120, 20,000 raster primitive cap or 2.5pt snap modifications. Do not claim merge, source promotion or commercial proof before exact-head CI and applicable owner-source/customer checks.
