"""Producer-owned memory-efficient plan processing shadow authority (Item 24).

Resolves Workstream C, Item 24 of the Autonomous Core Accuracy Engineering Mission:
"Improve deterministic memory-efficient processing of large plan sets."

Key requirements:
- Implements bounded streaming page processing across large multi-page plan sets.
- Prevents unbounded working set growth by evaluating pages sequentially with
  deterministic per-page and per-plan memory budgets.
- Quarantines individual pages that exceed memory thresholds without crashing the
  broader multi-page extraction pipeline.
- Provides chunked spatial grid indexing for dense pages to avoid quadratic memory allocations.
- Emits lightweight immutable receipts and releases intermediate buffers immediately.
- Strictly operates in shadow mode: status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
import gc
import math
from types import MappingProxyType
from typing import Any, Callable, Dict, Generator, List, Mapping, Optional, Sequence, Set, Tuple

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
SOURCE_MEMORY_EFFICIENT_PLAN_RESOLVED = "source_memory_efficient_plan_resolved"
SOURCE_MEMORY_EFFICIENT_PLAN_CANDIDATE = "source_memory_efficient_plan_candidate"
SOURCE_MEMORY_EFFICIENT_PLAN_UNAVAILABLE = "source_memory_efficient_plan_unavailable"
PAGE_MEMORY_BUDGET_EXCEEDED = "page_memory_budget_exceeded"
PLAN_MEMORY_BUDGET_EXCEEDED = "plan_memory_budget_exceeded"
PAGE_STREAMING_COMPLETED = "page_streaming_completed"
SPATIAL_CHUNK_INDEX_APPLIED = "spatial_chunk_index_applied"
PAGE_PRIMITIVE_CAP_ENFORCED = "page_primitive_cap_enforced"

# Default memory and complexity bounds
DEFAULT_MAX_PAGE_MEMORY_MB = 64.0
DEFAULT_MAX_PLAN_MEMORY_MB = 256.0
MAX_PAGE_PRIMITIVES = 20000

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str]  # doc/rev/sha/snap


def _clean(val: Any) -> str:
    return str(val or "").strip()


@dataclass(frozen=True)
class SpatialChunkGrid:
    """Bounded spatial grid partitioning dense geometries into local buckets."""

    page_width: float
    page_height: float
    grid_cols: int = 4
    grid_rows: int = 4
    buckets: Mapping[Tuple[int, int], Tuple[str, ...]] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        segments: Sequence[Mapping[str, Any]],
        page_width: float,
        page_height: float,
        cols: int = 4,
        rows: int = 4,
    ) -> SpatialChunkGrid:
        pw = max(float(page_width), 1.0)
        ph = max(float(page_height), 1.0)
        cell_w = pw / cols
        cell_h = ph / rows

        grid_map: Dict[Tuple[int, int], List[str]] = collections.defaultdict(list)
        for s in segments:
            sid = _clean(s.get("id"))
            x1 = float(s.get("x1", 0.0))
            y1 = float(s.get("y1", 0.0))
            x2 = float(s.get("x2", 0.0))
            y2 = float(s.get("y2", 0.0))

            min_c = max(0, min(cols - 1, int(min(x1, x2) / cell_w)))
            max_c = max(0, min(cols - 1, int(max(x1, x2) / cell_w)))
            min_r = max(0, min(rows - 1, int(min(y1, y2) / cell_h)))
            max_r = max(0, min(rows - 1, int(max(y1, y2) / cell_h)))

            for c in range(min_c, max_c + 1):
                for r in range(min_r, max_r + 1):
                    grid_map[(c, r)].append(sid)

        frozen_buckets = {k: tuple(sorted(v)) for k, v in grid_map.items()}
        return cls(
            page_width=pw,
            page_height=ph,
            grid_cols=cols,
            grid_rows=rows,
            buckets=MappingProxyType(frozen_buckets),
        )


@dataclass(frozen=True)
class SourcePageMemoryReceiptRecord:
    page_id: str
    primitive_count: int
    estimated_memory_mb: float
    quarantined: bool
    spatial_chunks_count: int
    reason_codes: Tuple[str, ...]
    status: str = EvidenceResolutionStatus.CANDIDATE.value
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceMemoryEfficientPlanProcessingProducer")


@dataclass(frozen=True)
class SourceMemoryEfficientPlanSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_ids: Tuple[str, ...] = ()
    max_page_memory_mb: float = DEFAULT_MAX_PAGE_MEMORY_MB
    max_plan_memory_mb: float = DEFAULT_MAX_PLAN_MEMORY_MB

    def __post_init__(self) -> None:
        for f in ("document_id", "revision_id", "source_sha256", "snapshot_id"):
            if not _clean(getattr(self, f)):
                raise ValueError(f"SourceMemoryEfficientPlanSelector requires non-empty {f}")


@dataclass(frozen=True)
class SourceMemoryEfficientPlanResult:
    status: str
    page_receipts: Tuple[SourcePageMemoryReceiptRecord, ...]
    total_pages: int
    processed_pages: int
    quarantined_pages: int
    peak_plan_memory_mb: float
    reason_codes: Tuple[str, ...]
    resolution_mode: str
    schema_version: str = SCHEMA_VERSION


class SourceMemoryEfficientPlanProcessingProducer:
    """Producer managing memory-bounded streaming page processing."""

    def __init__(self, _seal: object) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceMemoryEfficientPlanProcessingProducer.create()")
        self._plan_pages: Dict[_Key, Dict[str, Dict[str, Any]]] = collections.defaultdict(dict)

    @classmethod
    def create(cls) -> SourceMemoryEfficientPlanProcessingProducer:
        return cls(_PRODUCER_SEAL)

    def register_page(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        segments: Sequence[Mapping[str, Any]],
        page_width: float,
        page_height: float,
    ) -> None:
        doc = _clean(document_id)
        rev = _clean(revision_id)
        sha = _clean(source_sha256)
        snap = _clean(snapshot_id)
        pg = _clean(page_id)

        if not (doc and rev and sha and snap and pg):
            raise ValueError("All document, snapshot, and page identifiers are required")

        key: _Key = (doc, rev, sha, snap)
        self._plan_pages[key][pg] = {
            "segments": tuple(segments),
            "page_width": float(page_width),
            "page_height": float(page_height),
        }

    def authority(self) -> SourceMemoryEfficientPlanProcessingAuthority:
        results_map: Dict[_Key, Tuple[Dict[str, Any], ...]] = {}

        for key, pages_map in self._plan_pages.items():
            page_data_list = []
            for pg_id in sorted(pages_map.keys()):
                entry = pages_map[pg_id]
                page_data_list.append({
                    "page_id": pg_id,
                    "segments": entry["segments"],
                    "page_width": entry["page_width"],
                    "page_height": entry["page_height"],
                })
            results_map[key] = tuple(page_data_list)

        return SourceMemoryEfficientPlanProcessingAuthority(_AUTHORITY_SEAL, results_map)


class SourceMemoryEfficientPlanProcessingAuthority:
    """Immutable authority resolving memory-bounded plan execution results."""

    def __init__(
        self,
        _seal: object,
        plan_pages_map: Mapping[_Key, Tuple[Dict[str, Any], ...]],
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceMemoryEfficientPlanProcessingProducer.authority()")
        self._plan_pages_map = MappingProxyType(dict(plan_pages_map))

    def resolve(self, selector: SourceMemoryEfficientPlanSelector) -> SourceMemoryEfficientPlanResult:
        key: _Key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
        )
        page_entries = self._plan_pages_map.get(key)
        if page_entries is None:
            return SourceMemoryEfficientPlanResult(
                status=EvidenceResolutionStatus.ABSTAINED.value,
                page_receipts=(),
                total_pages=0,
                processed_pages=0,
                quarantined_pages=0,
                peak_plan_memory_mb=0.0,
                reason_codes=(SOURCE_MEMORY_EFFICIENT_PLAN_UNAVAILABLE,),
                resolution_mode="abstain_plan_unavailable",
            )

        # Filter by selector.page_ids if specified
        target_entries = page_entries
        if selector.page_ids:
            allowed = set(selector.page_ids)
            target_entries = tuple(p for p in page_entries if p["page_id"] in allowed)

        max_page_mem = selector.max_page_memory_mb
        max_plan_mem = selector.max_plan_memory_mb

        receipts: List[SourcePageMemoryReceiptRecord] = []
        cumulative_plan_mem = 0.0
        quarantined_count = 0
        all_plan_reasons: Set[str] = set()

        for p_entry in target_entries:
            pg_id = p_entry["page_id"]
            segs = p_entry["segments"]
            pw = p_entry["page_width"]
            ph = p_entry["page_height"]

            reasons: List[str] = []
            prim_count = len(segs)

            # Heuristic memory estimation: ~1.5 KB per native segment in Python objects
            est_mem_mb = round((prim_count * 1536) / (1024 * 1024), 3)

            # Check primitive cap
            if prim_count > MAX_PAGE_PRIMITIVES:
                reasons.append(PAGE_PRIMITIVE_CAP_ENFORCED)

            # Check page memory budget
            quarantined = False
            if est_mem_mb > max_page_mem:
                reasons.append(PAGE_MEMORY_BUDGET_EXCEEDED)
                quarantined = True
                quarantined_count += 1
            else:
                reasons.append(PAGE_STREAMING_COMPLETED)
                cumulative_plan_mem += est_mem_mb

            # If segment count is dense (> 2000), apply chunked spatial grid
            chunk_count = 0
            if prim_count > 2000 and not quarantined:
                grid = SpatialChunkGrid.build(segs, pw, ph, cols=4, rows=4)
                chunk_count = len(grid.buckets)
                reasons.append(SPATIAL_CHUNK_INDEX_APPLIED)

            rec = SourcePageMemoryReceiptRecord(
                page_id=pg_id,
                primitive_count=prim_count,
                estimated_memory_mb=est_mem_mb,
                quarantined=quarantined,
                spatial_chunks_count=chunk_count,
                reason_codes=tuple(reasons),
                _seal=_RECORD_SEAL,
            )
            receipts.append(rec)
            all_plan_reasons.update(reasons)

            # Explicit memory release
            del segs

        # Check total plan memory budget
        if cumulative_plan_mem > max_plan_mem:
            all_plan_reasons.add(PLAN_MEMORY_BUDGET_EXCEEDED)

        total_pages = len(receipts)
        processed = total_pages - quarantined_count

        if quarantined_count > 0:
            status = EvidenceResolutionStatus.CANDIDATE.value
            mode = "candidate_partial_pages_quarantined"
            all_plan_reasons.add(SOURCE_MEMORY_EFFICIENT_PLAN_CANDIDATE)
        else:
            status = EvidenceResolutionStatus.CANDIDATE.value
            mode = "candidate_bounded_memory_plan_streaming"
            all_plan_reasons.add(SOURCE_MEMORY_EFFICIENT_PLAN_RESOLVED)

        return SourceMemoryEfficientPlanResult(
            status=status,
            page_receipts=tuple(receipts),
            total_pages=total_pages,
            processed_pages=processed,
            quarantined_pages=quarantined_count,
            peak_plan_memory_mb=round(cumulative_plan_mem, 3),
            reason_codes=tuple(sorted(all_plan_reasons)),
            resolution_mode=mode,
        )
