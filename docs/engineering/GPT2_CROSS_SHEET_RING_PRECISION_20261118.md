# GPT2 — original source-only cross-sheet ring precision and edge correspondence

**Architecture report, 18 November 2026 AEST.** One original PlanReader production measuring engine; this patch affects **only** a quantity-free GPT2 source-ink diagnostic and its regression tests. #4135 records this function-specific claim. #4516 independently owns the FT2/FT3 correspondence classifier, and GPT MAX owns live Maryborough physical/finish/issuer/customer calculations.

## Observed exact repo call path

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `tools/diag_gpt2_source_finish_floor_handoff_shadow.py`, `tests/test_gpt2_source_geometry_bridges_synthetic.py`, and the existing Office/D15/FT3 original-source first-gate review. In `audit_gpt2_original_cross_sheet_ring_correspondence`, an existing source registrar's p7/p11 fixed transform and source edge identity witnesses must match before `_single_ring` accepts exactly one source-native simple ring on each sheet. The function then compares transformed floor vertices against finish vertices. It cannot authenticate W4 walls or finish area.

## Source-neutral defect

The floor point set is rounded to 0.001 PDF points, while the finish point set is built from *unrounded* floats. A genuinely equivalent native source ring differing only by sub-0.0005pt floating representation therefore abstains. Also, unordered vertex-set equality can approve source polygons whose vertex sequence creates different perimeter edge connections (e.g., a crossed instead of an ordered rectangle) when counts happen to match.

## Proposed bounded correction

Validate every vertex as a complete finite native point; reject non-finite/ill-typed, 2^53-overflowing and quantization-collapsing distinct corners rather than selecting an arbitrary one. Canonicalize both ring sides at the **existing** 0.001pt granularity after source-provided translation, preserving optional closing-vertex repetition. Compare full cyclic *undirected edge identities* instead of just unordered corner sets. A cyclic rotation or reversed traversal is the same physical perimeter; scrambling diagonal connections is not. Preserve original source edge-ID count equality and witness membership. No metric normalization, nearest/tie assignment or new tolerance.

## Release firewall and tests

All positives remain `original_source_ink_ring_translation_candidate`, `physical_room_identity_proven=False`, `source_finished_face_verified=False` and `new_firm_quantities=0`. No original PDF bytes, benchmark gold, frozen120, signed/customer outputs, W4 wall source producer or physical line/door geometry altered. Synthetic tests: equivalent subquantum endpoints positive; reversed/cyclic ring positive; crossed vertex cycle, beyond-quantum mismatch, invalid/NaN coordinates and corner collision negative. Require clean exact-main branch, new exact-head dual Python3.13/3.14 CI and protected regression checks. Private Maryborough Office D15 physical W4 ring and doorway threshold remain unproved; the verified 31-page source PDF SHA is `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`, but that is identity, not producer acceptance.
