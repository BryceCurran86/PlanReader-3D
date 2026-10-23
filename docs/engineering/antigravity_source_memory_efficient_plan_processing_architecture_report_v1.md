# Architecture Report: Producer-Owned Memory-Efficient Plan Processing Shadow Authority (Item 24)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Memory-Efficient Plan Processing Shadow Authority** (`pb_source_memory_efficient_plan_processing_shadow.py`), resolving Workstream C, Item 24 of the Autonomous Core Accuracy Engineering Mission: "Improve deterministic memory-efficient processing of large plan sets."

The primary blockers addressed are:
1. **Unbounded Working Set in Large Multi-Page Plan Sets:** Commercial drawing packages often span 20 to 50 large format sheets. Holding all pages' vector primitives, raster pixmaps, text spans, and topology graphs in memory concurrently risks process exhaustion or non-deterministic garbage collection spikes on constrained runtime environments.
2. **Whole-Document Abort on Isolated Page Memory Spikes:** Previously, if a single pathological or over-dense drawing sheet consumed excessive memory, the entire extraction pipeline could abort, preventing valid downstream takeoff on otherwise well-formed pages.
3. **Producer-Owned Streaming & Chunked Spatial Indexing:** This module establishes an immutable producer/authority contract that evaluates multi-page plan sets sequentially with deterministic per-page (`max_page_memory_mb`) and per-plan (`max_plan_memory_mb`) budgets. For dense pages ($N > 2,000$ primitives), it builds a bounded $4 \times 4$ spatial chunk grid (`SpatialChunkGrid`) to eliminate quadratic pairwise search overhead, safely quarantining over-budget pages without halting multi-page execution.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure immutable writer boundaries.
- Factory method `SourceMemoryEfficientPlanProcessingProducer.create()` produces the mutable producer.
- Calling `.authority()` returns a frozen `SourceMemoryEfficientPlanProcessingAuthority` mapping selectors to results.
- Direct instantiation of records or authorities raises `PermissionError`.

### 2. Memory-Bounded Streaming & Grid Partitioning Gates
- **Sequential Page Evaluation & Working Set Deallocation:**
  - Pages are registered and evaluated sequentially.
  - Intermediate segment references are explicitly released after producing lightweight receipts (`SourcePageMemoryReceiptRecord`).
- **Deterministic Memory Budgeting:**
  - Evaluates estimated memory working sets per page.
  - Pages exceeding `max_page_memory_mb` (default 64.0 MB) are quarantined with `PAGE_MEMORY_BUDGET_EXCEEDED` (`quarantined = True`), allowing other pages to complete processing.
  - Enforces the non-negotiable 20,000 segment safety cap with `PAGE_PRIMITIVE_CAP_ENFORCED`.
  - Cumulative memory exceeding `max_plan_memory_mb` (default 256.0 MB) flags `PLAN_MEMORY_BUDGET_EXCEEDED`.
- **Chunked Spatial Grid Indexing:**
  - When primitive count exceeds 2,000 segments on a non-quarantined page, partitions the page into bounded spatial buckets.
  - Tagged with `SPATIAL_CHUNK_INDEX_APPLIED`.

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
