# GPT1 — positive source wall-finish area cannot become zero customer m² (2026-10-30)

## Compliance: actual files and functions read

- `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/wall_topology_observability_architecture.md`, `docs/planreader_wall_room_topology_spec.md`, `docs/planreader_public_tender_benchmarks.md`, `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`, and `.github/workflows/ci.yml`.
- `pb_bound_wall_finish_quantity_authority.py`: `SourceBoundWallFinishQuantityProducer.publish`, `SourceBoundWallFinishQuantityRecord`.
- `pb_live_wall_finish_quantity_publication.py`: `publish_bound_wall_finish_quantity` and `_positive_source_finish_area`.
- `pb_bound_wall_finish_customer_bridge.py`: `bound_wall_finish_record_to_takeoff_row`, `build_bound_wall_finish_rows`; customer runtime entrypoint in `pb_auto_geometry_v1219.py`.
- `tests/test_bound_wall_finish_quantity_authority_v1.py` source-owned test fixtures and `tests/test_gpt1_wall_finish_customer_batch_atomicity.py` existing valid-row, mixed ABSTAIN and batch atomicity contracts.

## OBSERVED first failing production customer gate

The source producer may issue a valid positive finite net finish area such as 0.004 m², and the independent real `publish_bound_wall_finish_quantity` issuer retains 0.004 m². The customer bridge computes `round(max(0.0, float(record.quantity_m2)), 2)` before checking the issuer. That silently emits a zero quantity in the canonical 21-field measured takeoff row. The customer row therefore disagrees in sign with the authenticated source quantity, without an ABSTAIN or error. This is a real commercial output defect, not a new geometric or material source authority.

## INFERRED impact and authority boundary

Original PDF → physical wall/opening/net-wall geometry → complete source-owned finish-face scope → `SourceBoundWallFinishQuantityProducer.publish` → `publish_bound_wall_finish_quantity` → `bound_wall_finish_record_to_takeoff_row` / `build_bound_wall_finish_rows` → live customer takeoff. A positive source metric that rounds to zero cannot be represented faithfully in this existing two-decimal customer format. Neither a zero row nor inventing 0.01 m² is source-safe. The existing bridge already discards the complete staged batch on any customer projection exception.

## PROPOSED narrow implementation

Reprove the source record with the real issuer before customer rounding. Preserve the current two-decimal presentation for all representable positive quantities, but fail closed with `ValueError` if that rounded quantity is zero. The batch bridge catches this and emits no partial customer rows. Do not modify source producer, net-wall geometry, authority, source IDs, frozen evaluator, customer row schema or precision. Do not alter the established mixed independent ABSTAIN behavior.

## Tests and evidence limitations

Use the existing source-owned producer fixtures, then actual `publish_bound_wall_finish_quantity` and the direct/indirect customer bridge. Adversarial 0.004 and 0.0001 m²; valid 0.006 and 12.5 m²; deterministic replay, original-record immutability, canonical 21-field positive row, and fail-closed batch. Python 3.13/3.14 exact-head CI is required. These are synthetic source-neutral tests, **not** SHA-verified original-source proof. Trusted original-source producer→real issuer→sealed/customer replay and byte-exact retention of the nine Lot16 and three Maryborough signed/customer bodies remain required before any merge.

## BENCHMARK / lane separation

No expected BOQ, project names, frozen truth, scorer tolerance, or holdout metric informed the change. Leave GPT2 physical FT2/FT3/RCP, MAX/Claude host/glazing, GPT3 signing/scoring, other GPT1 draft PRs, original PDFs/tokens, 20,000 primitive cap and 2.5 pt snap untouched. This is an unmerged integrity candidate, not an original FIRM or official score gain.
