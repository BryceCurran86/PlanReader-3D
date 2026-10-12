# GPT3 Maryborough original-source first-stage checkpoint — 12 October 2026

**Read-only, unscored source-authority record.** This checkpoint is not a sealed
takeoff, a V2 matched object ledger, or proof of commercial quantities.

## Original evidence

- Exact source-attested workflow: [GitHub Actions run 38239001160](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38239001160)
- Run artifact: `11742271649`, `first_source_stage_ledger.json` and
  `opening_source_composition.json`, from production checkpoint PR #2532
  (merged `ea968d1c2676d119e912b29e7c646d7973549503`)
- Original architectural PDF SHA-256:
  `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`,
  matching the unchanged frozen Maryborough source manifest
- **Frozen manifest remains INCOMPLETE** (24 denominator items). Never
  infer 0% or 99% accuracy from this diagnostic.
- Source production result: `claim_status=abstained`, `combined_run_file=null`,
  no sealed `floor_area`, `floor_finish_area`, `ceiling_area`,
  `opening_area`, `opening_count` quantity file.

## Exact disjoint first-stage distribution

| First unproved original source stage | Unique physical opening IDs |
| --- | ---: |
| Host wall binding unproven | 176 |
| Host proven but complete physical wall frame unproven | 3 |
| Whole host/frame proved | 0 |
| **Total authenticated source physical-existence hypotheses** | **179** |

Within the 176 unhosted physical identities, the exact *first-stage reason
sets* are:

| Source reason set | Physical identities |
| --- | ---: |
| `no_authenticated_host_wall_band` | 88 |
| `ambiguous_physical_wall_equivalence_for_host` alone | 44 |
| equivalence ambiguous plus `opening_two_face_wall_lineage_ambiguous` | 23 |
| unresolved complete host-wall universe, no local candidates, viewport cropped | 14 |
| unresolved complete host-wall universe, no local candidates, not viewport cropped | 7 |

These five rows total exactly **176**. Other raw reason incidence counts
overlap and must not be added together as object counts.

## Three source-bound openings still missing whole-wall frame

All three are on original page 7, have authenticated local host bindings,
and **must remain ABSTAIN on complete physical frame**, until new original
source evidence closes the whole-wall role.

1. `physical_opening_existence_1c6ac920cdeec106726cd72730a4e9ee`
   - Bound group: `opening_host_binding_group_5294650b7c08de0ae33fd266dbf47b2b`
   - Original member wall candidates: `wall_12fa3ad36657c83534de`,
     `wall_63b19a98f5d3a656de9d`, `wall_76bf00fcfea603e8c303`,
     `wall_de2ea9106f42461b1e96`
2. `physical_opening_existence_7bab6cb7b27e8481a5485b92d0ae42a9`
   - Bound group: `opening_host_binding_group_2d1f8e5aed35dca5054a218dd7faac61`
   - Original member wall candidates: `wall_65056d7b91a350a71a58`,
     `wall_77f895d286df922670d8`, `wall_c28b38269ada1b28e494`,
     `wall_d69eb462b18f2d8db36d`
3. `physical_opening_existence_e6b66e87285e39a31fde2d3166c2bfae`
   - Bound group: `opening_host_binding_group_4d009eed1d0cd19ebf7e017a975cd665`
   - Original member wall candidates: `wall_340d73524055e836d1df`,
     `wall_7d89271d4c68bf010dcd`, `wall_9c784f21dd217f5a9137`,
     `wall_a4ea668bae262149152d`

Each original frame trace cites `opening_host_frame_whole_wall_unproven`,
`opening_host_frame_wall_unavailable`, and
`opening_host_frame_complete_wall_scope_unavailable`, with no
source-proven complete wall candidates. Do not choose a nearest wall,
extrapolate an aperture area, assume an opening count, or bind a material
using room names. The source-page and revision owner must be established
through existing physical-wall contracts.

## Comparing another original-source run

Once a new exact-source run yields a complete `first_source_stage_ledger.json`,
compare identity-by-identity using:

```bash
python tools/diag_gpt3_maryborough_source_stage_delta.py \
  --before original_20261012_first_source_stage_ledger.json \
  --after original_new_run_first_source_stage_ledger.json \
  --output source_stage_delta_UNPUBLISHED.json
```

The comparator requires the same original source SHA and valid physical
records. If candidate-universe IDs change, comparison is **non-comparable**
for progress claims. If original negative evidence changes without a stage
change, it reports that change without promoting a claim. It never computes
Full Plan V2 matched, coverage or precision-adjusted accuracy.

Frozen benchmark truth, eligibility, tolerances, source SHA controls,
evaluator, and 20,000 source primitive safety cap remain unchanged.
