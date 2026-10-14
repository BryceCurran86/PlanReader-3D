# GPT MAX — Original G17 nomination source-retention audit (read-only)

## Observed repository behavior

Source of truth is the immutable Lot16 original PDF, SHA `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, GitHub Actions [run 38492065194](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38492065194) artifact `11863555873`, **before.json** and **after.json** (recovered directly from Actions). The comparison is of current-main production vs draft [#2660](https://github.com/BryceCurran86/PlanReader-3D/pull/2660), not benchmark truth. No existing source PDFs or frozen evaluator are changed by this audit.

The real authority chain traced is `SourceVisibilityProducer.ingest_native_pdf_bytes` → `augment_with_raster_opening_primitives` → `PhysicalOpeningAuthority.prove_existence` → `SourceVisibilityProducer.augment_with_raster_visible_segments` → `_proven_raster_opening_flank_boxes` + `detect_unchanged_terminal_band_segments` → W2/W3/W4 physical wall authority → `_resolve_opening_local_mixed_scope_source_band` → host/frame authority → canonical opening → quantity → sealed customer output. These are **separate authority boundaries**. Source paint, candidate nomination, W4 geometry and source-closed metric area are not interchangeable.

The current production source stage requires `OpeningLabelDimensionProducer.publish_scope(...).evidence.area_m2` before nominating G17 supplemental flank source evidence. Original Bathroom 870 is a real source-authenticated G17 opening with only one figured numeric label and no per-instance height; area remains ABSTAIN. The 300-DPI closed left painted face spans 17 pixel cells (4.08 PDF pt) but its endpoint centres are 3.84pt apart. The G17 supplemental perception minimum counts centre gaps against the ordinary 4pt policy; these are **two** upstream nomination gates, neither being a positive physical wall proof.

## Original-source result — candidate #2660 is NOT retention safe

These are observations from before/after original-source JSON, never prediction constants:

| Evidence family | Before | After |
|---|---:|---:|
| Source-authenticated G17 openings | 21 | 21 |
| Authenticated opening hosts | 15 | 17 |
| Complete source frames | 9 | 9 |
| W4 candidate records | 2,094 | 2,094 |
| Canonical opening-area records | 8 | 8 |
| W4 record content | unchanged | unchanged |
| Existing host receipt address changed | — | **15 of 15** |
| Existing frame receipt address changed | — | **9 of 9** |
| Prior firm canonical area evidence lineage changed | — | **8 of 8** |
| Room face records | 61 | 61, **content changed** |
| Ownership witness census | 107 | 107 |
| Room abstentions | 41 | 41 |

Two extra proposed physical host IDs are `physical_opening_existence_a68d0b7d738b5de9a1588b4e680e1a8f` and `physical_opening_existence_ba7f75a2e5f68bcce87cd00ac1acf90b`; **neither has a newly source-supported second dimension, framed opening, FIRM quantity or signed customer row**. Replacing the 1215 host member set and rekeying its accepted binding is a regression risk, even though its observed area value remained 1.80m². All eight area values remained numerically equal; this does not preserve their source receipt IDs. Physical graph and room-face content changes additionally require a separate authority review. No changed existing host may be silently interpreted as the same owner by equal shape, nearest location, title, or nominal area.

The source-retention workflows correctly **failed** on this draft (including original Lot16 opening binding, strict original source host/frame, and fresh signed customer proof). The failure is *not* an outdated benchmark count assertion. Do not merge #2660 or merely waive historical receipts.

## Diagnostic change and safety boundary

`tools/diag_gptmax_g17_nomination_retention.py` accepts two full original stage JSON reports and produces a machine-readable **read-only** risk ledger. It authenticates identical 64-character source SHA and unchanged primitive safety cap, complete uniquely keyed physical/canonical opening universes, unique W4 candidates and nonempty room scopes. It independently lists gained vs lost hosts, changes to **all old** host and frame receipts, changes to existing canonical quantity evidence or values, W4 source changes, and room scope changes. Any corrupted/foreign/duplicate inventory fails closed. It intentionally always returns `ready_for_production_promotion=false`, `physical_host_granted=false`, `customer_quantity_granted=false`, `benchmark_score_granted=false`. This is an observability ledger, **not** a new host resolver or a waiver of existing source gates.

The attached focused tests exercise a genuine candidate gain masking an old receipt rekey, untouched W4 with changed room and quantity lineage, missing and duplicate observations, foreign source/cap, quantity tamper, original input nonmutation and no publication. Original source before/after artifact identifies the first unsafe authority seam; any later G17 geometry hypothesis must run source-only shadow first, independently establish structural wall role, W2 retained local fragment and W4 physical equivalence, then preserve sealed customer lineage.

## Benchmark firewall and expected abstentions

The frozen 27-object Lot16 denominator, 24-object Maryborough denominator, all frozen truth files, evaluator, tolerances, mapping and source documents remain immutable and are never read by the comparison algorithm. Project names, opening IDs, quantities and observed score are **report context only**, not runtime geometry decisions. Current accepted Lot16 score stays **8/27**, Maryborough **0/24**, combined **8/51**, pending separately authenticated customer output and independent GPT3 reconciliation.

No second metric axis, source-signed opening count, scale, wall-height, physical wall role, W10 takeoff eligibility, canonical quantity or customer row is promoted. Unknown, competing, incomplete and rekeyed physical source propositions remain ABSTAIN/CONFLICT until an original-source equivalence authority proves them. This work does not change production detector thresholds, host/frame identities, source-geometry authority, the 20,000 input safety cap or any commercial output.

### Files consulted

`AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md`; `docs/wall_topology_observability_architecture.md`; `docs/planreader_wall_room_topology_spec.md`; `docs/planreader_public_tender_benchmarks.md`; `.github/workflows/ci.yml`; `pb_source_visibility_authority.py`; `pb_raster_unchanged_band_segments.py`; `pb_opening_host_binding_authority.py`; `tools/diag_gptmax_raster_unhosted_flank_source.py`; and the original-source Actions run above.
