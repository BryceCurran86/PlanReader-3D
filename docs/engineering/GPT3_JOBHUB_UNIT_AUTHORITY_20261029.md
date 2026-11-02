# GPT3 JobHub source-unit authority and final customer-line gate — 2026-10-29

## Observed repository behaviour

- `pb_jobhub_publishing_pipeline.build_publishing_package_from_workspace` reads the real SQLite takeoff source and had `str(r["unit"] or "m²")`, silently creating an area unit for NULL/empty source unit.
- `pb_jobhub_publishing_contract.validate_publishing_gate` verifies value/rate/price/identity/commercial authority but had no explicit nonempty measurement-unit guard despite its documented valid-unit contract. Caller-constructed, self-hashed packages could bypass source ingestion and enter `execute_jobhub_publishing`.
- The actual consumer writes `painting_takeoff_package_lines.unit` to JobHub; there is no later unit-provenance resolver.

## Inference and first failing authority boundary

An absent unit cannot be inferred from element, trade, section, or an assumed `m²`. A scalar quantity with no dimension is unfit even for a *persisted* draft JobHub line. An explicitly excluded scope item is not a measured line and need not have a unit.

## Implemented production changes

1. Preserve an explicitly provided nonblank textual unit from the original source row, stripping peripheral whitespace; missing, nontext or blank source unit stays `""` rather than fabricating area.
2. Reject any package line with blank or nontext unit in `validate_publishing_gate` for both commercial and draft mode, before opening the JobHub destination.
3. Do **not** impose a false all-trades allowed-unit vocabulary: `m`, `m²`, `m2`, `kg`, `each` all remain usable when explicitly sourced.
4. Add SQLite source-to-sealed-SHA-to-persisted-line positives, null/blank/blob source negatives, caller-forged hash negatives and excluded-scope no-line retention.

## Scope, benchmark observations, required verification

Only production `pb_jobhub_publishing_pipeline.py`, `pb_jobhub_publishing_contract.py`, the new dedicated test and this report change. Frozen evaluator/denominators, original PDFs/tokens, signed archive, existing customer receipts, 20,000 primitive cap and 2.5pt snap remain untouched. Source-neutral synthetic tests cannot establish a new original drawing quantity, FIRM, an 8→9 signed Lot16 promotion, or any 120-item accuracy gain.

Required before merge: immutable exact-head full Python 3.13 and 3.14 checks; applicable signed/customer/raster/performance companions; final PR diff review against current main. Original-source replay is not claimed or required to demonstrate the negative-only downstream gate, but any subsequent commercial FIRM promotion must have its own original-positive proof.
