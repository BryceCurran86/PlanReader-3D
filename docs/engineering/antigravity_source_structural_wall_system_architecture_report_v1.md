# Architecture Report: Producer-Owned Structural Wall System Shadow Authority (Item 1)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Structural Wall System Shadow Authority** (`pb_source_structural_wall_system_shadow.py`), resolving Workstream A, Item 1 of the Autonomous Core Accuracy Engineering Mission: "Recover complete, source-authenticated structural wall systems from complicated architectural drawings."

The primary blockers addressed are:
1. **Linework Fragmentation into Isolated Segments:** In complex architectural drawings, structural walls are frequently fragmented by dimension ticks, hatch intersections, and CAD drafting breaks. Traditional extraction processes frequently leave these pieces as isolated, disconnected single-line strokes, lacking continuous structural system identity.
2. **Artificial Severing of Continuous Walls by Openings:** Door and window voids were previously handled by physically splitting wall centerlines into tiny stub segments, corrupting wall continuity and misidentifying continuous through-walls as separate entities.
3. **Producer-Owned Structural System Synthesis:** This module establishes an immutable producer/authority contract that links collinear wall segments across junctions and opening voids, proves paired wall faces (Face A / Face B) with physical thickness ($T_{\text{wall}} \in [0.07, 0.45]$ m), integrates corner L- and T-junctions without double-counting junction mass, embeds opening voids cleanly into the host wall run, and outputs unified OGC WKB polygon and multipolygon geometry for downstream 3D spatial projection.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure immutable writer boundaries.
- Factory method `SourceStructuralWallSystemProducer.create()` produces the mutable producer.
- Calling `.authority()` returns a frozen `SourceStructuralWallSystemAuthority` mapping selectors to results.
- Direct instantiation of records or authorities raises `PermissionError`.

### 2. Structural Wall System Geometric Gates
- **Continuous Wall Run Assembly:**
  - Evaluates continuous runs of structural walls (`WallRunMember`), tracking centerline geometry, wall type (`external` or `internal`), length ($m$), and physical thickness ($m$).
  - Tagged with `WALL_RUN_CONTINUITY_PROVEN`.
- **Paired Face & Thickness Corroboration:**
  - Both Face A and Face B segment IDs must be proven (`PAIRED_FACES_PROVEN`).
  - Wall thickness must fall within physical architectural bounds ($0.07 \text{ m} \le T_{\text{wall}} \le 0.45 \text{ m}$). Out-of-bounds thickness fails with `WALL_THICKNESS_OUT_OF_BOUNDS`.
  - Tagged with `WALL_THICKNESS_CORROBORATED`.
- **Junction & Opening Embedding:**
  - Embeds corner L-junctions and T-junctions into the continuous wall system without double-counting corner junction mass (`JUNCTIONS_INTEGRATED`).
  - Embeds door and window openings into host wall runs without splitting continuous wall identity (`OPENINGS_EMBEDDED`).
- **Unified Spatial Footprint:**
  - Performs 2D unary union of wall run polygons via Shapely to produce the unified structural footprint, serialized as standard OGC WKB hex.

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
