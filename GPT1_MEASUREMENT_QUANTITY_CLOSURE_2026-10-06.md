# GPT-1 Measurement + Quantity Closure — 2026-10-06

## Status

**GPT-1 Measurement + Quantity lane is COMPLETE on current production main.**

GPT-1 is now in **support / audit mode only** unless a new authenticated canonical object is proven to have no valid QuantityEvidence path.

## Objective completed

> Every already-authenticated canonical object that is supportable must produce valid QuantityEvidence.

The following families now have production QuantityEvidence paths when their required source authority exists:

- Room area
- Floor area
- Ceiling area
- Wall-finish surface area
- Canonical opening area
- Explicit authenticated opening count
- Slab area
- Roof covering area
- Structural member count

## Key production merges

- `#1452` — wall-finish quantities bind to exact canonical finish-surface identities.
- `#1454` — canonical room + floor quantity lifecycle.
- `#1460` — canonical slab area QuantityEvidence.
- `#1474` — source-classified support pages reach cross-view room-area authority.
- `#1485` — canonical ceilings enter live AG-09 coverage without false quantity promotion.
- `#1489` — FIRM native-scale room/floor metric authority + figured-dimension independence.
  - merge SHA: `38d929fb7fc68de5c0ab47fc81aeab40f722e9c2`
- `#1543` — canonical ceiling area QuantityEvidence.
  - merge SHA: `e02ea3b60bbdb7c67595f42b97b94d68d663a3d2`
- `#1550` — downstream source-closes canonical ceiling quantities.
  - current main at lane closure: `34f8039cab502b8a541977dbf0f1082ee91a6cf6`

## Hardened authority guarantees

### Figured dimensions

Authenticated figured/documented dimensions are an independent numeric authority.

They:
- remain valid when scale is absent;
- remain valid when scale disagrees or is conflicting;
- retain exact figured-dimension lineage;
- do not depend on title-block scale text.

### Geometry-derived quantities

Geometry-derived quantities:
- require valid source-owned scale authority;
- may use authenticated native graphic scale-bar authority;
- ABSTAIN when scale is missing, conflicting, or otherwise unauthoritative;
- never infer FIRM scale from title-block ratio text alone.

### Canonical ceiling quantities

Canonical ceiling QuantityEvidence:
- is keyed to exact canonical ceiling identity;
- reuses exact upstream FIRM room-area measurement authority;
- supports documented-dimension authority without scale;
- requires a physical scale record for PDF-scaled geometry;
- remains QuantityEvidence-only at the GPT-1 boundary;
- does not create customer rows.

### Openings

Canonical opening quantities:
- require valid physical opening identity and authenticated host/source lineage;
- support figured area, resolved physical opening geometry, authenticated elevation frame, and authenticated frame-schedule basis;
- explicit opening counts require authenticated explicit schedule quantity;
- unhosted, untyped, or unsupported openings do not manufacture quantities.

### Wall-finish surfaces

Wall-finish surface QuantityEvidence:
- binds to exact physical/canonical finish-surface identities;
- requires complete source-owned finish-face scope and net-wall quantity authority;
- incomplete finish extent remains fail-closed.

## AG-09 closure result

For supportable authenticated objects with valid measurement authority:

`AUTHENTICATED -> CANONICALIZED -> QUANTIFIED`

is now available across the GPT-1-owned quantity families.

Intentional `QUANTIFIED = 0` cases remain valid when:
- no metric measurement authority exists;
- wall height/extent is absent;
- scale is missing/conflicted for geometry-derived measurement;
- opening host/measurement basis is unresolved;
- finish extent is incomplete;
- a fixture intentionally supplies only canonical identity without measurement authority.

These are not GPT-1 plumbing dropouts.

## GPT-1 handoff contract

GPT-1 hands downstream:

- stable `QuantityEvidence`;
- exact canonical/physical identity references;
- source/revision/snapshot/page/viewport lineage;
- exact measurement authority;
- fail-closed status when authority is insufficient.

GPT-1 does **not** own:

- Maryborough room extraction;
- Lot16 raster identity;
- raster opening/host topology;
- customer-row publication;
- final sealing/reconciliation orchestration;
- benchmark scoring or truth.

Those remain in the GPT-2 / GPT-3 / GPT-4 lanes.

## Support-mode rule

GPT-1 may continue helping only by:

1. auditing newly authenticated canonical objects for missing QuantityEvidence;
2. hardening measurement authority contracts;
3. fixing generic quantity-generation regressions;
4. supplying stable typed QuantityEvidence to downstream lanes;
5. adding regression tests that preserve ABSTAIN / CONFLICT behavior.

Do not reopen extraction, identity, customer-output, or scoring ownership unless the lane assignment is explicitly changed.


## Post-closure support audit — opening quantity stack

Support audit performed after GPT-4 host-frame work.

Observed diagnostic state:
- canonical opening count: 81;
- canonical openings with resolved area: 2;
- published opening-area QuantityEvidence: 1.

This is **not** a GPT-1 quantity-generation dropout.

The two area-resolved canonical doors were:

1. **10.08 m² figured opening**
   - opening kind: door;
   - figured area record present;
   - host wall: unavailable;
   - host frame: unavailable;
   - QuantityEvidence: correctly **not** published.

2. **5.67 m² figured opening**
   - opening kind: door;
   - figured area record present;
   - authenticated host wall present;
   - QuantityEvidence: published.

Conclusion:

The remaining 10.08 m² opening is blocked upstream by authenticated host topology / physical identity authority, not by measurement or quantity publication. The existing opening QuantityEvidence publisher is behaving correctly and must remain fail-closed.

Ownership remains outside GPT-1 unless a future canonical opening satisfies the full publisher contract and still fails to produce QuantityEvidence.
