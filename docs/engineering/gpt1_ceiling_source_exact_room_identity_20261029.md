# GPT1 — exact original room receipts at ceiling source-closed issuer (2026-10-29)

## Files read and observed production path

Read live `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, accuracy-levers guidance, W1–W10 architecture, topology spec, frozen-benchmark separation guidance and CI workflow. Inspected `pb_live_ceiling_lining_source_closed_export.py`, `pb_live_ceiling_customer_projection.py`, `pb_live_physical_net_wall_integration.py` and `tests/test_live_ceiling_lining_source_closed_export.py` on main `65dc4684fbcf1ce36c704457d896fc7c12a651de`. Coordination claim: #3462 comment 6486277438. Separate #4120 exact-head review: 5692172916.

Observed real path: original canonical room `LiveCanonicalRoomObject` + ceiling `LiveCanonicalCeilingSurfaceObject` + source-owned `QuantityEvidence` → `build_live_ceiling_lining_source_traces` → `seal_live_ceiling_lining_run` or `project_live_ceiling_customer_rows` → commercial adapter → `seal_source_closed_run` → `verify_sealed_customer_output`. The source exporter already validates the original room-face receipt exactly. However, its room map and FIRM ceiling source check use `_clean()` to match the producer's canonical/physical room IDs, quantity metadata and ceiling room reference. Whitespace-padded or imported `str` subclass aliases can therefore match an otherwise valid FIRM ceiling area and be normalized into the customer location.

## Inference, not original-source authority

A source-like room token that matches only after trimming/coercion does not prove the original physical room identity. The same numeric ceiling area can then inherit an unauthenticated room receipt. This is a source-identity integrity defect, **not** a finding that an original Maryborough FT2/FT3 or IPF1/GRID quantity is missing. No benchmark expected values, labels, tolerances or score data were used.

## Narrow negative-only implementation

After the existing membership check, before minting a source trace, require the original producer canonical and physical room IDs to be native, nonempty, unpadded `str`; require exact native equality of the quantity's two room metadata IDs and the ceiling's canonical room reference to the producer's IDs. Preserve the existing room-face, scale, semantic, source SHA, evidence and quantity checks. Reject conflicts with `SourceClosedRunConflictError`, not a default room or a corrected label. Test padded and subclass aliases from the quantity, producer and ceiling; preserve valid source trace, sealed/customer row, area and abstention. No new FIRM quantity or promotion.

## Untouched boundaries and merge gates

Do not edit GPT2 FT2/FT3/RCP geometry, GPT MAX/Claude Wxx hosts, GPT3 signer/scorer, #4120 customer projection, original PDFs/tokens, frozen Full Plan V2, signed nine Lot16 customer bodies, Maryborough verified floor inputs, 20k primitive cap or 2.5pt snap. Exact-head Python3.13/3.14 and companion tests are necessary but not sufficient: trusted original SHA-verified production replay and signed/customer preservation remain required before merge. A skipped original-source check is not a pass. This is an integrity milestone candidate, not an accuracy gain.
