# Lot16 exact original-source development reconciliation — 2026-10-12

The unchanged Full Plan V2 exact-project reconciler returns **7/27 matched
within tolerance (25.9259259%)**, 20 missed, 0 outside tolerance, 0 partial,
0 unresolved, 0 unsupported extras and 0 lineage conflicts. Coverage and
precision-adjusted accuracy are both 25.9259259%.

This is the Lot16 **development project** result for the existing 27 verified
eligible objects. The source manifest remains INCOMPLETE. It is not an official
full-suite publication or an overall PlanReader accuracy claim. Maryborough,
3Laurel and Q5446 still require their own authentic seals and identity maps;
the 120-object suite remains unpublished. No absent family is assigned zero
quantity or removed from the denominator.

## Independently established source identity

Original architectural SHA:
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`.
The exact Actions sealed artifact is 11749443101 from run 38253415979, producer
head `7fc6462d45a8c8c7a51c952ffb658f4746d44ef6`, merged through #2549.
The two source/customer JSON files here are its unchanged original bytes.
The existing customer verifier confirms seven source-firm, lineage-valid rows
in exact quantity-ID bijection with the original signed run.

Fresh source-only page-3 replay, using the read-only opt-in export in #2551,
recovered each original figured-label proof, native observation and exact box.
Reissuing quantities through the existing producer and source-trace seam
reproduced the **entire original signed payload**, not just its totals:
`1aa3020eccf785894b3e7aa2f44258e277d0dd5eb4f4c27f140278d8855b81a9`.
All original host/frame, physical, label, source-root and quantity fingerprints
therefore remain exact. All-source-page diagnostics have a different snapshot
and must not substitute their different host/frame receipt IDs for this seal.

Every native text-integrity receipt was independently reauthenticated from the
SHA-verified PDF through SourceVisibilityProducer and PdfTextIntegrityAuthority;
its complete receipt JSON matches exactly. The existing page-title authority
binds native FLOOR PLAN to the DRAWING TITLE field and native sheet number 3.
This identifies the source sheet; it does not promote raster viewport or wall
scope authority.

After sealing, each label box is compared with the independently frozen source
location box at its **existing one-decimal recorded precision**. Exact rounded
four-coordinate equality admits one and only one frozen original-source location
for each signed opening. Neither quantity, dimension magnitude, text similarity,
name, nearest coordinate, bbox overlap nor item order selects a pair. The two
2.16 m² windows are distinguished by their original text observation IDs and
different exact boxes, not their values. Frozen coordinate precision and
measurement tolerances remain unchanged.

| Physical identity suffix | Frozen original object reference |
|---|---|
| c4d87543028146e1cff0b5e2ca480c55 | lot16:opening:p3:1218_sgw:01 |
| 91ae06327d4fcc8004a557b116a77820 | lot16:opening:p3:1218_sgw:02 |
| 661fc5e6f0c5975d5e9bdd5d759bd180 | lot16:opening:p3:0615_sgw:01 |
| 2c31ccb074d8eae86cac281c0fde1176 | lot16:opening:p3:2148_panel_lift:01 |
| dbcec9c3cfa8e22b332479d09a601985 | lot16:opening:p3:0621_sgw:01 |
| bd108c2c1bfd88752311aab5901737bb | lot16:opening:p3:0906_sgw_obs:01 |
| f5adf8438fb6f48cc03b03d8ca2125f5 | lot16:opening:p3:0630_fg:01 |

`source_identity_proof.json` retains full per-pair source, canonical, original
label receipts and fingerprints. `identity_map.json` is benchmark-side only;
production never consumes it. `exact_project_report.json` includes all produced
items and the unchanged evaluator's exact outcome fields.

## Reproduce the source and evaluator checks

Run source-only diagnostics first, without benchmark inputs:

```bash
PYTHONPATH=. python tools/diag_gptmax_source_authority_stages.py \
  --pdf 'documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf' \
  --page-id 3 --include-identity-text-receipts --output /tmp/lot16-original-identity.json
```

Verify original source/customer bytes with existing
`sealed_source_closed_run_from_dict` and `verify_sealed_customer_output`.
The source proof documents the independent exact native receipt and source
location checks. Then run the unchanged reconciler:

```bash
PYTHONPATH=. python benchmarks/frozen_holdout/full_plan_v2/run_exact_project_reconciliation.py \
  --manifest benchmarks/frozen_holdout/full_plan_v2/projects/au_qld_lot16_power/source_manifest.json \
  --sealed-run docs/engineering/lot16_original_identity_reconciliation_20261012/source_sealed_run.json \
  --identity-map docs/engineering/lot16_original_identity_reconciliation_20261012/identity_map.json \
  --output /tmp/lot16-exact-project-report.json
```

No frozen truth, denominator, tolerance, scorer, measurement authority or
20,000-source-primitive cap changed. Seven residual raster hosts, incomplete
opening counts, missing metric floors/ceilings/walls and PR #2511's source-parity
failure remain engineering blockers. This report resolves the seven sealed
rows' previously missing benchmark identity mapping; it adds no geometry or
new produced quantity.
