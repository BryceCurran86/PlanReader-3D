# GPT3 — Exact physical takeoff row identity at JobHub publish gate (2026-10-29)

## Repository behavior (observed)

Read AGENTS.md, engineering playbook, frozen/source firewall, CI, the main `pb_jobhub_publishing_contract.py` gate, real PlanReader→JobHub `pb_jobhub_publishing_pipeline.py` writer, SQLite fixture, and prior #4061 upstream identity checks. On main `f64d1617cad9ff45de4a39b9c386aa4513e361d2`, `QuantityLineItemPayload.row_id: int` is only a type annotation. `validate_publishing_gate` checks `len(row_ids) != len(set(row_ids))` but does not validate the physical source ID type. The full SHA hash sorts by `row_id`. Two string aliases `"1"` and `"01"` are different to the Python set, therefore both pass that duplicate check, both become signed consumer rows, and JobHub final SQL inserts both amounts without any `row_id` field in its line table. A lone Boolean, float or nonpositive ID is likewise not authenticated as a physical row. Real SQLite workspace primary keys are exact positive integers.

## Inference and first failing production boundary

A noncanonical caller ID is not source ownership proof. Normalizing `int("01")` would launder an alias into a physical source receipt, so reject rather than cast. This is downstream JobHub contract identity safety, not a measurement source producer or benchmark score change. The existing upstream preflight #4061 solves different quantity-ID duplication and remains intact.

## Change

Gate commercial *and* draft publishing on `type(row_id) is int and row_id > 0` before set uniqueness and SHA validation. Preserve existing exact duplicate detection, full evidence fingerprint, signed quantity/rates, source SHA, pricing, warnings/exclusions, TOCTOU, JobHub DB lock, duplicate transaction and destination integrity. Real SQLite tests reject aliases, missing IDs, Boolean, float, negative, zero, containers, and `"1"/"01"` pairs with **zero destination writes**, while validating genuinely distinct exact positive integers persist and replay duplicates still veto.

## Authority boundary

Original-plan PDFs and hashes, signed fixtures/customer rows, all frozen V2 project objects/evaluator, 20,000 primitive cap, 2.5pt snap, other agents' GPT1/2/MAX/AntiGravity/Claude paths, GPT3 #3796 release and independent JobHub writer #4080 remain untouched. Synthetic FIRM test fixtures are merely gate mechanics, NOT original source authority or a new official frozen score.

## Required validation

Review the exact three-path patch; run full Python3.13/3.14 CI plus signed/customer/raster/performance companions on the immutable PR head. Do not merge or count until actual results succeed.
