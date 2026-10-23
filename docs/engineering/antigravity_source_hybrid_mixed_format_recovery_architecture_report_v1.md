# Architecture Report: Producer-Owned Hybrid Mixed-Format Geometry Recovery Shadow Authority (Item 8)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Hybrid Mixed-Format Geometry Recovery Shadow Authority** (`pb_source_hybrid_mixed_format_recovery_shadow.py`), resolving Workstream A, Item 8 of the Autonomous Core Accuracy Engineering Mission: "Improve geometric recovery from vector, raster and mixed-format PDFs."

The primary blockers addressed are:
1. **Parallel Ghost Wall Inflation in Mixed-Format Sheets:** Many architectural sheets combine native vector CAD linework with scanned raster layers (underlays, scanned title blocks, or revisions). Running naive raster line extraction alongside native vector parsing previously created collocated duplicate edges with sub-pixel offsets, leading to parallel ghost wall pairs and tripping the 20,000 primitive safety cap.
2. **Missing Raster Geometry in Vector Gaps:** When drawings possess areas drafted exclusively as raster scans (or where vector linework is missing/flattened), discarding raster primitives loses authentic physical walls and opening details.
3. **Producer-Owned Reconciliation & Modality Partitioning:** This module establishes an immutable producer/authority contract that classifies drawing page modality (`MODALITY_PURE_VECTOR`, `MODALITY_PURE_RASTER`, or `MODALITY_MIXED_HYBRID`), canonicalizes native vector strokes as primary geometry while binding collocated raster primitives as corroborating evidence without duplicate edge creation, and promotes authentic raster primitives to fill geometric gaps.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure immutable writer boundaries.
- Factory method `SourceHybridMixedFormatRecoveryProducer.create()` produces the mutable producer.
- Calling `.authority()` returns a frozen `SourceHybridMixedFormatRecoveryAuthority` mapping selectors to results.
- Direct instantiation of records or authorities raises `PermissionError`.

### 2. Hybrid Mixed-Format Geometric Reconciliation Gates
- **Page Modality Classification:**
  - Evaluates vector and raster segment counts to assign:
    - `MODALITY_PURE_VECTOR`: Vector linework present, zero raster segments.
    - `MODALITY_PURE_RASTER`: Raster segments present, zero vector linework.
    - `MODALITY_MIXED_HYBRID`: Both vector and raster primitives present on the same sheet.
  - Tagged with `HYBRID_PAGE_MODALITY_DETERMINED`.
- **Collocated Raster Duplicate Reconciliation:**
  - In mixed mode, evaluates pairwise collinearity and interval overlap between raster segments and vector strokes within standard snap tolerance ($\le 2.5$ pt).
  - Overlapping raster segments are reconciled as `RASTER_PRIMITIVE_RECONCILED_AS_CORROBORATION` (`COLLOCATED_RASTER_DUPLICATE_RECONCILED`).
  - The vector segment is canonicalized as `VECTOR_PRIMITIVE_CANONICAL`, citing the raster primitive ID in `corroborating_primitive_ids`.
  - Zero duplicate physical edges are produced.
- **Unmatched Raster Augmentation (Gap-Filling):**
  - Raster segments situated $> 2.5$ pt away from any vector stroke are promoted as `RASTER_PRIMITIVE_PROMOTED_AUGMENTATION` (`UNMATCHED_RASTER_PROMOTED`).

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
