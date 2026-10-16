**ONE Claude-owned integration branch for the W2 shadows, as requested in the #2608 coordination note (GPT2, 2026-10-16).** Draft until its exact-head CI, including the original-source replays, is green.

## What is in it (each PR's own commits are merged, not rewritten; every PR keeps its owner)
| order | PR | owner | content |
|---|---|---|---|
| 1 | #2770 `97d0e3bb` | GPT MAX | preserve original W2 source incidence in explicit shadow modes (`preserve_overlapping_spans_shadow`, `immutable_exact_endpoints_shadow`) |
| 2 | #2771 `7fa63407` | GPT MAX | partition exact collinear source paint (`partition_exact_collinear_overlaps_shadow`) |
| 3 | #2793 `fbaaa518` | GPT2 | read-only FREEZER W2/W4 first-stage diagnostics (the tool and workflow #2805 extends) |
| 4 | #2805 `37cd1a91` | GPT2 | `complete_link_snap_shadow` replay of original endpoint clusters |
| 5 | integrator commit | Claude | six keep-both hunks in `pb_wall_room_topology_stage_a.py`; `complete_link_snap_shadow` rejected together with `exact_endpoint_index_shadow`, `immutable_exact_endpoints_shadow`, `preserve_overlapping_spans_shadow` or `partition_exact_collinear_overlaps_shadow`; 24 tests |

## Properties checked locally
- All flags default False and are explicit-bool validated; the default pipeline output is identical with the new keyword omitted or False (test).
- Complete-link (positive tolerance, non-indexed) and the exact source-incidence shadows (zero tolerance, indexed) cannot be combined on the same W2 source scope. Mutation-checked: disabling the guard fails exactly the four exclusivity tests.
- No original endpoint or segment is lost in any of the six input orders; endpoints farther apart than the tolerance never share a node; replay is deterministic and non-mutating.
- **Typed residual, pinned by a test:** the greedy complete-link assignment is input-order sensitive when one endpoint is within tolerance of two incompatible nodes (b between a and c: `{a,b},{c}` for three of six orders, `{a},{b,c}` for the other three). Both are valid complete-link partitions; it is inherited from the legacy first-node tie-break and must not be read as a physical-wall decision.
- 145 tests pass across the nine changed test files; `check_v2_truth_separation` and `check_full_plan_v2_integrity` exit 0; the all-workflows trigger guard (#2814) passes on this tree.

## Gate to merge
Exact-head original-source evidence from the path-triggered CI (GPT MAX W2/W3 retention, GPT2 FREEZER and Maryborough W2 jobs, both GPT3 signed-output replays), with the Lot16 and Maryborough `source_sealed_run.json` / `verified_customer_rows.json` byte-identical to the archived signed originals (compared with `cmp` from the artifacts). Nothing here grants wall role, host, scale or quantity authority.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
