# Architecture: RCP bulkhead compile-receipt stays CANDIDATE

## Observed repository behavior

`SourceRcpBulkheadSoffitGeometryShadowAuthority.compile_bulkhead_receipt` sets `EvidenceResolutionStatus.CORROBORATED` whenever `len(bulkheads) > 0`. The records are caller-supplied polygons and level heights. `takeoff_eligible` and `commercial_projection_allowed` are already False.

## Inference

A non-empty caller list is not independently re-resolved SourceRoomFace / ceiling-plane ownership. Detection and local geometry bounds are not measurement authority.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty. Do not change fascia/soffit arithmetic, seals, or commercial flags.

## Benchmark observations that must not influence implementation

Frozen FREEZER / Maryborough / expected BOQ values are not inputs. GPT2 still owns original RCP word/IPF1/GRID eligibility (`#3469`, `#3493`); this PR does not touch that path.
