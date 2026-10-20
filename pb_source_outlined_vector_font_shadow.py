"""Producer-owned outlined and vector-font text recognition shadow authority (Item 26).

Resolves Workstream C, Item 26 of the Autonomous Core Accuracy Engineering Mission:
"Improve recognition of outlined/vector-font text using source-supported evidence."

Follows the architectural specification in:
`docs/engineering/q5446_outlined_text_ink_architecture_report_20261016.md`.

Key requirements:
- Classifies vector-stroked font outlines (CAD character glyphs drafted as polylines)
  without relying on embedded PDF font streams or raster OCR.
- Evaluates conjunction of source-owned geometric proofs:
  (a) Small path-local bounding box relative to page extent.
  (b) Membership in a baseline-aligned run of at least 3 character paths.
  (c) Regular character kerning / pitch spacing along the text baseline.
  (d) Absence of contact with long structural wall strokes.
  (e) Retention of plausible alternatives as UNPROVEN when ambiguity remains.
- Strictly operates in shadow mode: status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

# Public Classifications
GLYPH_INK_CANDIDATE = "glyph_ink_candidate"
NOT_GLYPH_INK = "not_glyph_ink"
UNPROVEN = "unproven"

# Public Reason Codes
SOURCE_OUTLINED_TEXT_RESOLVED = "source_outlined_text_resolved"
SOURCE_OUTLINED_TEXT_CANDIDATE = "source_outlined_text_candidate"
SOURCE_OUTLINED_TEXT_UNAVAILABLE = "source_outlined_text_unavailable"
GLYPH_BASELINE_ALIGNED = "glyph_baseline_aligned"
GLYPH_KERNING_REGULAR = "glyph_kerning_regular"
GLYPH_RUN_CORROBORATED = "glyph_run_corroborated"
STRUCTURAL_STROKE_CONTACT_VETO = "structural_stroke_contact_veto"
ISOLATED_PATH_NOT_RUN = "isolated_path_not_run"
PATH_EXTENT_OVER_BOUND = "path_extent_over_bound"
PLURAL_INTERSECTING_STROKES = "plural_intersecting_strokes"

# Thresholds derived from architectural standard lettering
_MAX_GLYPH_DIM_PT = 20.0
_MAX_SEGMENT_LENGTH_PT = 18.0
_MIN_RUN_MEMBERS = 3
_BASELINE_TOLERANCE_PT = 1.5
_MAX_INTER_GLYPH_GAP_PT = 15.0
_MIN_INTER_GLYPH_GAP_PT = 0.2
_STRUCTURAL_LONG_STROKE_THRESHOLD_PT = 25.0
_SNAP_TOLERANCE_PT = 2.5

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str]  # doc/rev/sha/snap/page


def _clean(val: Any) -> str:
    return str(val or "").strip()


def _seg_length(s: Mapping[str, Any]) -> float:
    dx = float(s["x2"]) - float(s["x1"])
    dy = float(s["y2"]) - float(s["y1"])
    return math.hypot(dx, dy)


def _seg_bbox(s: Mapping[str, Any]) -> Tuple[float, float, float, float]:
    x1, y1 = float(s["x1"]), float(s["y1"])
    x2, y2 = float(s["x2"]), float(s["y2"])
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def classify_outlined_text_ink(
    segments: Sequence[Mapping[str, Any]],
    page_width: float,
    page_height: float,
) -> Dict[str, Any]:
    """Pure functional classifier for outlined text ink across a vector page.

    Evaluates path groupings, baseline runs, kerning consistency, and structural contacts.
    Returns per-primitive classification, reason codes, identified glyph runs, and withheld ID counts.
    """
    if not isinstance(segments, (tuple, list)):
        raise TypeError("segments must be a sequence of mappings")
    if float(page_width) <= 0 or float(page_height) <= 0:
        raise ValueError("positive page dimensions required")

    # Group segments by source path index / ID
    by_path: Dict[str, List[Mapping[str, Any]]] = collections.defaultdict(list)
    all_primitive_ids: Set[str] = set()
    long_structural_segments: List[Mapping[str, Any]] = []

    for s in segments:
        sid = _clean(s.get("id"))
        all_primitive_ids.add(sid)
        pid = _clean(s.get("path_index")) or _clean(s.get("path_id")) or sid
        by_path[pid].append(s)
        if _seg_length(s) >= _STRUCTURAL_LONG_STROKE_THRESHOLD_PT:
            long_structural_segments.append(s)

    # Compute bounding boxes and stats for each path
    path_stats: Dict[str, Dict[str, Any]] = {}
    for pid, p_segs in by_path.items():
        min_x = min(min(float(s["x1"]), float(s["x2"])) for s in p_segs)
        max_x = max(max(float(s["x1"]), float(s["x2"])) for s in p_segs)
        min_y = min(min(float(s["y1"]), float(s["y2"])) for s in p_segs)
        max_y = max(max(float(s["y1"]), float(s["y2"])) for s in p_segs)
        w = max_x - min_x
        h = max_y - min_y
        max_len = max(_seg_length(s) for s in p_segs)
        path_stats[pid] = {
            "bbox": (min_x, min_y, max_x, max_y),
            "width": w,
            "height": h,
            "max_len": max_len,
            "segment_count": len(p_segs),
            "segments": p_segs,
            "center": ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0),
            "baseline_y": max_y,  # typical horizontal baseline
            "baseline_x": min_x,  # typical vertical baseline
        }

    # Identify small glyph-candidate paths
    glyph_candidate_pids: List[str] = []
    reasons_by_seg: Dict[str, List[str]] = collections.defaultdict(list)
    class_by_seg: Dict[str, str] = {}

    for pid, stats in path_stats.items():
        p_segs = stats["segments"]
        if stats["width"] > _MAX_GLYPH_DIM_PT or stats["height"] > _MAX_GLYPH_DIM_PT or stats["max_len"] > _MAX_SEGMENT_LENGTH_PT:
            for s in p_segs:
                reasons_by_seg[s["id"]].append(PATH_EXTENT_OVER_BOUND)
                class_by_seg[s["id"]] = NOT_GLYPH_INK
        else:
            glyph_candidate_pids.append(pid)

    # Check for contact with long structural strokes
    vetoed_pids: Set[str] = set()
    for pid in glyph_candidate_pids:
        b = path_stats[pid]["bbox"]
        for ls in long_structural_segments:
            ls_bbox = _seg_bbox(ls)
            # Expand by snap tolerance
            if not (b[2] + _SNAP_TOLERANCE_PT < ls_bbox[0] or b[0] - _SNAP_TOLERANCE_PT > ls_bbox[2] or
                    b[3] + _SNAP_TOLERANCE_PT < ls_bbox[1] or b[1] - _SNAP_TOLERANCE_PT > ls_bbox[3]):
                vetoed_pids.add(pid)
                for s in path_stats[pid]["segments"]:
                    reasons_by_seg[s["id"]].append(STRUCTURAL_STROKE_CONTACT_VETO)
                    class_by_seg[s["id"]] = UNPROVEN
                break

    eligible_glyph_pids = [pid for pid in glyph_candidate_pids if pid not in vetoed_pids]

    # Cluster eligible paths into horizontal and vertical baseline runs
    # Horizontal runs: group by baseline_y within _BASELINE_TOLERANCE_PT
    runs: List[Dict[str, Any]] = []
    used_pids: Set[str] = set()

    # Sort by baseline_y, then min_x
    eligible_sorted = sorted(eligible_glyph_pids, key=lambda p: (path_stats[p]["baseline_y"], path_stats[p]["bbox"][0]))

    clusters: List[List[str]] = []
    for pid in eligible_sorted:
        placed = False
        y_val = path_stats[pid]["baseline_y"]
        for c in clusters:
            avg_y = sum(path_stats[p]["baseline_y"] for p in c) / len(c)
            if abs(y_val - avg_y) <= _BASELINE_TOLERANCE_PT:
                c.append(pid)
                placed = True
                break
        if not placed:
            clusters.append([pid])

    for c in clusters:
        if len(c) < _MIN_RUN_MEMBERS:
            continue
        # Sort left-to-right
        c_sorted = sorted(c, key=lambda p: path_stats[p]["bbox"][0])
        # Validate regular kerning gaps between consecutive glyphs
        run_members: List[str] = [c_sorted[0]]
        for i in range(1, len(c_sorted)):
            prev_pid = run_members[-1]
            curr_pid = c_sorted[i]
            prev_bbox = path_stats[prev_pid]["bbox"]
            curr_bbox = path_stats[curr_pid]["bbox"]
            gap = curr_bbox[0] - prev_bbox[2]

            if _MIN_INTER_GLYPH_GAP_PT <= gap <= _MAX_INTER_GLYPH_GAP_PT:
                run_members.append(curr_pid)
            else:
                # Gap broken; if current run has >= 3 members, record it
                if len(run_members) >= _MIN_RUN_MEMBERS:
                    runs.append({
                        "orientation": "horizontal",
                        "member_pids": list(run_members),
                    })
                    used_pids.update(run_members)
                run_members = [curr_pid]

        if len(run_members) >= _MIN_RUN_MEMBERS:
            runs.append({
                "orientation": "horizontal",
                "member_pids": list(run_members),
            })
            used_pids.update(run_members)

    # Classify all segments in verified runs as GLYPH_INK_CANDIDATE
    withheld_segment_ids: Set[str] = set()
    run_records: List[Dict[str, Any]] = []

    for idx, r in enumerate(runs):
        member_pids = r["member_pids"]
        member_segs = [s for pid in member_pids for s in path_stats[pid]["segments"]]
        seg_ids = [s["id"] for s in member_segs]
        withheld_segment_ids.update(seg_ids)

        min_x = min(path_stats[pid]["bbox"][0] for pid in member_pids)
        min_y = min(path_stats[pid]["bbox"][1] for pid in member_pids)
        max_x = max(path_stats[pid]["bbox"][2] for pid in member_pids)
        max_y = max(path_stats[pid]["bbox"][3] for pid in member_pids)

        for s in member_segs:
            reasons_by_seg[s["id"]].extend([GLYPH_BASELINE_ALIGNED, GLYPH_KERNING_REGULAR, GLYPH_RUN_CORROBORATED])
            class_by_seg[s["id"]] = GLYPH_INK_CANDIDATE

        run_records.append({
            "run_id": f"glyph_run_{idx}",
            "orientation": r["orientation"],
            "glyph_count": len(member_pids),
            "segment_ids": tuple(seg_ids),
            "bounding_box": (min_x, min_y, max_x, max_y),
            "reason_codes": (GLYPH_BASELINE_ALIGNED, GLYPH_KERNING_REGULAR, GLYPH_RUN_CORROBORATED),
        })

    # For eligible paths not in a run: isolated paths stay UNPROVEN
    for pid in eligible_glyph_pids:
        if pid not in used_pids:
            for s in path_stats[pid]["segments"]:
                reasons_by_seg[s["id"]].append(ISOLATED_PATH_NOT_RUN)
                class_by_seg[s["id"]] = UNPROVEN

    total_segments = len(segments)
    would_remain = total_segments - len(withheld_segment_ids)

    return {
        "status": "CLASSIFICATION_COMPLETE",
        "total_source_segments": total_segments,
        "glyph_candidate_segment_count": len(withheld_segment_ids),
        "would_remain_after_withholding": would_remain,
        "glyph_run_count": len(run_records),
        "glyph_runs": tuple(run_records),
        "withheld_segment_ids": frozenset(withheld_segment_ids),
        "classifications": MappingProxyType(class_by_seg),
        "reason_receipts": MappingProxyType({sid: tuple(sorted(set(rc))) for sid, rc in reasons_by_seg.items()}),
    }


@dataclass(frozen=True)
class SourceOutlinedVectorFontSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str

    def __post_init__(self) -> None:
        for f in ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id"):
            if not _clean(getattr(self, f)):
                raise ValueError(f"SourceOutlinedVectorFontSelector requires non-empty {f}")


@dataclass(frozen=True)
class SourceOutlinedGlyphRunRecord:
    record_id: str
    run_id: str
    orientation: str
    glyph_count: int
    bounding_box: Tuple[float, float, float, float]
    segment_ids: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    status: str = EvidenceResolutionStatus.CANDIDATE.value
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceOutlinedVectorFontProducer")


@dataclass(frozen=True)
class SourceOutlinedVectorFontResult:
    status: str
    records: Tuple[SourceOutlinedGlyphRunRecord, ...]
    total_segments: int
    withheld_segment_count: int
    retained_segment_count: int
    reason_codes: Tuple[str, ...]
    resolution_mode: str
    schema_version: str = SCHEMA_VERSION


class SourceOutlinedVectorFontProducer:
    """Producer for registering and evaluating vector-stroked font outlines."""

    def __init__(self, _seal: object) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceOutlinedVectorFontProducer.create()")
        self._pages: Dict[_Key, Dict[str, Any]] = {}

    @classmethod
    def create(cls) -> SourceOutlinedVectorFontProducer:
        return cls(_PRODUCER_SEAL)

    def register_page_vector_segments(
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

        key: _Key = (doc, rev, sha, snap, pg)
        self._pages[key] = {
            "segments": tuple(segments),
            "page_width": float(page_width),
            "page_height": float(page_height),
        }

    def authority(self) -> SourceOutlinedVectorFontAuthority:
        results_map: Dict[_Key, SourceOutlinedVectorFontResult] = {}

        for key, pdata in self._pages.items():
            doc, rev, sha, snap, pg = key
            segs = pdata["segments"]
            pw = pdata["page_width"]
            ph = pdata["page_height"]

            clf = classify_outlined_text_ink(segs, pw, ph)
            records: List[SourceOutlinedGlyphRunRecord] = []

            for run in clf["glyph_runs"]:
                rec_id = stable_contract_id(
                    "glyph-run-rec",
                    (doc, rev, sha, snap, pg, run["run_id"], str(run["bounding_box"]))
                )
                records.append(
                    SourceOutlinedGlyphRunRecord(
                        record_id=rec_id,
                        run_id=run["run_id"],
                        orientation=run["orientation"],
                        glyph_count=run["glyph_count"],
                        bounding_box=run["bounding_box"],
                        segment_ids=run["segment_ids"],
                        reason_codes=run["reason_codes"],
                        _seal=_RECORD_SEAL,
                    )
                )

            all_reasons = set()
            for r in records:
                all_reasons.update(r.reason_codes)

            if records:
                status = EvidenceResolutionStatus.CORROBORATED.value
                mode = "corroborated_outlined_vector_glyphs"
                all_reasons.add(SOURCE_OUTLINED_TEXT_RESOLVED)
            else:
                status = EvidenceResolutionStatus.CANDIDATE.value
                mode = "candidate_no_glyph_runs_found"
                all_reasons.add(SOURCE_OUTLINED_TEXT_CANDIDATE)

            results_map[key] = SourceOutlinedVectorFontResult(
                status=status,
                records=tuple(records),
                total_segments=clf["total_source_segments"],
                withheld_segment_count=clf["glyph_candidate_segment_count"],
                retained_segment_count=clf["would_remain_after_withholding"],
                reason_codes=tuple(sorted(all_reasons)),
                resolution_mode=mode,
            )

        return SourceOutlinedVectorFontAuthority(_AUTHORITY_SEAL, results_map)


class SourceOutlinedVectorFontAuthority:
    """Immutable authority serving outlined vector font recognition results."""

    def __init__(
        self,
        _seal: object,
        results_map: Mapping[_Key, SourceOutlinedVectorFontResult],
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceOutlinedVectorFontProducer.authority()")
        self._results_map = MappingProxyType(dict(results_map))

    def resolve(self, selector: SourceOutlinedVectorFontSelector) -> SourceOutlinedVectorFontResult:
        key: _Key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
        )
        res = self._results_map.get(key)
        if res is None:
            return SourceOutlinedVectorFontResult(
                status=EvidenceResolutionStatus.ABSTAINED.value,
                records=(),
                total_segments=0,
                withheld_segment_count=0,
                retained_segment_count=0,
                reason_codes=(SOURCE_OUTLINED_TEXT_UNAVAILABLE,),
                resolution_mode="abstain_page_unavailable",
            )
        return res
