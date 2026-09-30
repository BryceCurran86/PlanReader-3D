"""Native graphic-state provenance join for Item 35 candidates (Phase 2, shadow only).

Question studied: do member incidences of ambiguous physical-opening candidates
have source-owned graphic-state characteristics that differ from the complete
visible native primitive universe of the same source scope?

Diagnostic only.  Nothing here rejects, filters, ranks, merges, thresholds or
scores a candidate, an opening, a wall or a count, and no metadata value is a
rule (a rect edge, a short segment, a fill, a stroke width, a layer name or a
dash pattern is never treated as noise or as an opening).

Where the metadata comes from
-----------------------------
``SourceObservationRecord`` keeps only ``source_primitive_ref`` and geometry; the
graphic state (stroke, fill, width, layer, dashes) lives only in the transient
output of ``extract_native_page``.  The caller supplies the exact source bytes.
This module recomputes their SHA-256, requires exact equality with the source
hash already bound to the semantic scope (mismatch: no join at all, no
extraction), and replays the SAME producer function ``extract_native_page`` on
those bytes.  It never downloads, discovers or resolves a source and never uses
a filename, URL, project name or benchmark identity.

Exact join key
--------------
``(page_id, path_index, item_index, edge_index | None)`` parsed from the
SHA-verified ``source_primitive_ref`` (``visible:segment:d<N>i<M>[e<K>]``) and
compared with the identically-keyed replayed producer segment.  Geometry is only
an exact-equality integrity assertion on that one identity (a mismatch is a
``conflict``); it is never a lookup key.  No bbox, nearest, tolerance or
"equivalent path" matching exists.  Duplicate identities are ``conflict``;
missing identity or missing replay segment is ``unknown``; nothing is inferred.

Presence semantics are the producer's: an absent stroke / fill / width / layer /
dashes stays ``absent`` and is never turned into a colour, a no-fill class, a
named layer, a line class or a numeric zero.

Reporting guard: a ratio is shown only when at least ``RATIO_MIN_UNIQUE_PATHS``
unique page-qualified native paths contribute to its stratum and group, else
``ratio_suppressed_low_n``.  Raw counts are always reported and the denominator
is always shown.  The guard is never a production threshold and is no evidence
of significance.  Graphic state is a property of the drawing path, so path
counts (not primitive counts) are the independent-observation denominators.

No authority module is edited, no private accessor of an authority is used, no
benchmark file, expected value or tolerance is read, and production code must not
import this module.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import fitz

from pb_candidate_provenance_census import (
    REF_NATIVE_LINE,
    REF_NATIVE_RECT_EDGE,
    REF_RASTER,
    parse_visible_segment_ref,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_semantic_conflict_diagnostic import (
    CandidateStructureSummary,
    collect_semantic_scope,
    diagnose_semantic_conflicts,
)
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationResult
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)
from pb_vector_geometry_v130 import extract_native_page

JOIN_SCHEMA_VERSION = "1.0.0"
JOIN_KEY = "page_id+path_index+item_index+edge_index"
RATIO_MIN_UNIQUE_PATHS = 30
RATIO_SUPPRESSED_LOW_N = "ratio_suppressed_low_n"
VIEW_ID = None
VIEW_SCOPE_STATUS = "unavailable"

# ------------------------------------------------------------- join statuses
STATUS_JOINED = "joined"
STATUS_NOT_CORROBORATED = "unknown_not_corroborated"
STATUS_UNKNOWN_IDENTITY = "unknown_identity"
STATUS_MISSING_IN_REPLAY = "unknown_missing_in_replay"
STATUS_REPLAY_UNAVAILABLE = "unknown_replay_unavailable"
STATUS_NOT_NATIVE = "not_native_no_pdf_path"
STATUS_LINEAGE = "unknown_lineage_mismatch"
STATUS_VIEWPORT_SCOPED = "unknown_viewport_scoped"
STATUS_CONFLICT_DUPLICATE = "conflict_duplicate_identity"
STATUS_CONFLICT_GEOMETRY = "conflict_geometry"
STATUS_CONFLICT_IDENTITY_FIELDS = "conflict_identity_fields"
STATUS_CONFLICT_PATH_METADATA = "conflict_path_metadata"
JOIN_STATUSES = (
    STATUS_JOINED,
    STATUS_NOT_CORROBORATED,
    STATUS_UNKNOWN_IDENTITY,
    STATUS_MISSING_IN_REPLAY,
    STATUS_REPLAY_UNAVAILABLE,
    STATUS_NOT_NATIVE,
    STATUS_LINEAGE,
    STATUS_VIEWPORT_SCOPED,
    STATUS_CONFLICT_DUPLICATE,
    STATUS_CONFLICT_GEOMETRY,
    STATUS_CONFLICT_IDENTITY_FIELDS,
    STATUS_CONFLICT_PATH_METADATA,
)
SCOPE_STATUS_OK = "ok"
SCOPE_STATUS_SHA_MISMATCH = "no_join_sha_mismatch"
SCOPE_STATUS_ABSENT = "semantic_record_absent"

# -------------------------------------------------------------------- groups
G_PARTICIPATING = "participating_member_incidences"
G_AMBIGUOUS = "ambiguous_observations"
G_UNIVERSE_CAND_PAGES = "visible_universe_candidate_pages"
G_UNIVERSE_ALL_PAGES = "visible_universe_all_scope_pages"
G_UNIVERSE_MINUS_PART = "visible_universe_candidate_pages_minus_participating"
G_CONTROL = "non_participating_candidate_members"
GROUPS = (
    G_PARTICIPATING,
    G_AMBIGUOUS,
    G_UNIVERSE_CAND_PAGES,
    G_UNIVERSE_ALL_PAGES,
    G_UNIVERSE_MINUS_PART,
    G_CONTROL,
)
# Primary baseline is G_UNIVERSE_CAND_PAGES; the small control is secondary only.
COMPARED_AGAINST = (G_UNIVERSE_CAND_PAGES, G_UNIVERSE_MINUS_PART, G_CONTROL)
CLASSES = (REF_NATIVE_LINE, REF_NATIVE_RECT_EDGE)

# --------------------------------------------------------------- field states
FIELDS = (
    "stroke_state",
    "fill_state",
    "paint_presence",
    "width_state",
    "dash_state",
    "layer_state",
)
ABSENT = "absent"
TOP_VALUES = 25
PAGE_TOP_VALUES = 10
SIZE_BANDS = ("1", "2", "3-5", "6-10", "11-50", "51-200", "201+")
EXAMPLES = 3

_DASH_ARRAY = re.compile(r"\s*\[\s*([^\]]*?)\s*\]\s*(\S+)\s*")


def _page_order(page_id: str) -> tuple[int, Any]:
    return (0, int(page_id)) if page_id.isdigit() else (1, page_id)


def _selector(record: Any, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        observation_id=observation_id,
    )


def size_band(count: int) -> str:
    if count <= 1:
        return "1"
    if count == 2:
        return "2"
    if count <= 5:
        return "3-5"
    if count <= 10:
        return "6-10"
    if count <= 50:
        return "11-50"
    if count <= 200:
        return "51-200"
    return "201+"


# ------------------------------------------------------- producer metadata
def _color_key(value: Any) -> str:
    try:
        return "(" + ",".join(f"{float(v):.4f}" for v in value) + ")"
    except (TypeError, ValueError):
        return "unreadable:" + repr(value)[:60]


def _canonical_color(value: Any) -> Any:
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError):
        return "unreadable:" + repr(value)[:60]


def dash_state(dashes: Any, present: bool) -> str:
    """Classify the raw producer dash string without giving it a line meaning.

    ``absent`` only when the producer says absent.  ``array_empty`` is the PDF
    ``[] phase`` form (an empty dash array); it is NOT called solid or dashed.
    """
    if not present:
        return ABSENT
    raw = str(dashes)
    match = _DASH_ARRAY.fullmatch(raw)
    if match is None:
        return "unparsed:" + raw.strip()[:60]
    if not match.group(1).strip():
        return "array_empty"
    return "array:" + raw.strip()[:60]


@dataclass(frozen=True)
class GraphicState:
    """Raw producer values plus the producer's own presence flags."""

    stroke: Any
    stroke_present: bool
    fill: Any
    fill_present: bool
    width: Any
    width_present: bool
    layer: str
    layer_present: bool
    dashes: str
    dashes_present: bool

    def canonical(self) -> dict[str, Any]:
        return {
            "stroke": _canonical_color(self.stroke) if self.stroke_present else None,
            "stroke_present": self.stroke_present,
            "fill": _canonical_color(self.fill) if self.fill_present else None,
            "fill_present": self.fill_present,
            "width": (float(self.width) if self.width_present else None),
            "width_present": self.width_present,
            "layer": self.layer if self.layer_present else None,
            "layer_present": self.layer_present,
            "dashes": self.dashes if self.dashes_present else None,
            "dashes_present": self.dashes_present,
        }

    def digest(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def states(self) -> dict[str, str]:
        if self.stroke_present and self.fill_present:
            paint = "stroke_and_fill"
        elif self.stroke_present:
            paint = "stroke_only"
        elif self.fill_present:
            paint = "fill_only"
        else:
            paint = "neither_present"
        try:
            width_key = f"{float(self.width):.4f}" if self.width_present else ABSENT
        except (TypeError, ValueError):
            width_key = "unreadable:" + repr(self.width)[:60]
        return {
            "stroke_state": _color_key(self.stroke) if self.stroke_present else ABSENT,
            "fill_state": _color_key(self.fill) if self.fill_present else ABSENT,
            "paint_presence": paint,
            "width_state": width_key,
            "dash_state": dash_state(self.dashes, self.dashes_present),
            "layer_state": ("present:" + self.layer) if self.layer_present else ABSENT,
        }


def graphic_state_of(segment: Mapping[str, Any]) -> GraphicState:
    """Read the producer's graphic fields exactly as ``extract_native_page`` set them."""
    return GraphicState(
        stroke=segment.get("stroke"),
        stroke_present=segment.get("stroke_present") is True,
        fill=segment.get("fill"),
        fill_present=segment.get("fill_present") is True,
        width=segment.get("width"),
        width_present=segment.get("width_present") is True,
        layer=str(segment.get("layer") or ""),
        layer_present=segment.get("layer_present") is True,
        dashes=str(segment.get("dashes") or ""),
        dashes_present=segment.get("dashes_present") is True,
    )


# ----------------------------------------------------------------- replay
@dataclass(frozen=True)
class _ReplaySegment:
    geometry: tuple[float, float, float, float]
    state: GraphicState
    is_rect_edge: bool
    id_consistent: bool


class _PageReplay:
    """Replayed producer segments of one page keyed by exact identity."""

    def __init__(self, page_id: str) -> None:
        self.page_id = page_id
        self.by_key: dict[tuple[int, int, Optional[int]], _ReplaySegment] = {}
        self.duplicate_keys: set[tuple[int, int, Optional[int]]] = set()
        self.items_per_path: dict[int, int] = {}
        self.available = False


def _replay_page(document: Any, page_id: str) -> _PageReplay:
    replay = _PageReplay(page_id)
    try:
        page_number = int(page_id)
        page = document.load_page(page_number - 1)
        native = extract_native_page(page)
        drawings = page.get_drawings() or []
    except Exception:
        return replay
    replay.available = True
    for index, drawing in enumerate(drawings):
        items = drawing.get("items", []) if isinstance(drawing, dict) else []
        replay.items_per_path[index] = len(items)
    for segment in native.get("segments") or ():
        try:
            path_index = int(segment["path_index"])
            item_index = int(segment["item_index"])
            edge = segment.get("edge_index")
            edge_index = int(edge) if edge is not None else None
            geometry = tuple(float(segment[k]) for k in ("x1", "y1", "x2", "y2"))
        except (KeyError, TypeError, ValueError):
            continue
        key = (path_index, item_index, edge_index)
        expected_id = f"d{path_index}i{item_index}" + (
            f"e{edge_index}" if edge_index is not None else ""
        )
        if key in replay.by_key:
            replay.duplicate_keys.add(key)
            continue
        replay.by_key[key] = _ReplaySegment(
            geometry=geometry,  # type: ignore[arg-type]
            state=graphic_state_of(segment),
            is_rect_edge=str(segment.get("kind")) == "rect_edge",
            id_consistent=str(segment.get("id")) == expected_id
            and (edge_index is not None) == (str(segment.get("kind")) == "rect_edge"),
        )
    return replay


# -------------------------------------------------------------------- rows
@dataclass(frozen=True)
class JoinRow:
    observation_id: str
    page_id: Optional[str]
    raw_ref: Optional[str]
    ref_class: str
    path_index: Optional[int]
    item_index: Optional[int]
    edge_index: Optional[int]
    status: str
    state: Optional[GraphicState]
    replay_items_in_path: Optional[int]

    @property
    def joined(self) -> bool:
        return self.status == STATUS_JOINED

    @property
    def path_key(self) -> Optional[tuple[str, int]]:
        if self.page_id is None or self.path_index is None:
            return None
        return (self.page_id, self.path_index)

    def digest(self) -> str:
        return "" if self.state is None else self.state.digest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "page_id": self.page_id,
            "source_primitive_ref": self.raw_ref,
            "primitive_class": self.ref_class,
            "path_index": self.path_index,
            "item_index": self.item_index,
            "edge_index": self.edge_index,
            "join_status": self.status,
            "graphic_state": None if self.state is None else self.state.canonical(),
            "graphic_state_digest": self.digest() or None,
            "replay_items_in_path": self.replay_items_in_path,
        }


def _unjoined(observation_id: str, status: str, **fields: Any) -> JoinRow:
    values: dict[str, Any] = {
        "page_id": None,
        "raw_ref": None,
        "ref_class": "unresolved",
        "path_index": None,
        "item_index": None,
        "edge_index": None,
    }
    values.update(fields)
    return JoinRow(
        observation_id=observation_id,
        status=status,
        state=None,
        replay_items_in_path=None,
        **values,
    )


def _join_one(
    visible: Any, observation_id: str, record: Any, replays: dict[str, _PageReplay], document: Any
) -> JoinRow:
    observation = visible.observation
    if visible.status is not EvidenceResolutionStatus.CORROBORATED or observation is None:
        return _unjoined(observation_id, STATUS_NOT_CORROBORATED)
    page_id = str(observation.page_id)
    raw_ref = observation.source_primitive_ref
    parsed = parse_visible_segment_ref(raw_ref)
    common = {
        "page_id": page_id,
        "raw_ref": raw_ref if isinstance(raw_ref, str) else None,
        "ref_class": parsed.ref_class,
        "path_index": parsed.path_index,
        "item_index": parsed.item_index,
        "edge_index": parsed.edge_index,
    }
    if (
        observation.document_id != record.document_id
        or observation.revision_id != record.revision_id
        or observation.source_sha256 != record.source_sha256
        or observation.snapshot_id != record.snapshot_id
    ):
        return _unjoined(observation_id, STATUS_LINEAGE, **common)
    if observation.viewport_id is not None:
        return _unjoined(observation_id, STATUS_VIEWPORT_SCOPED, **common)
    if parsed.ref_class == REF_RASTER:
        return _unjoined(observation_id, STATUS_NOT_NATIVE, **common)
    if parsed.ref_class not in CLASSES or observation.observation_kind != NATIVE_PDF_VISIBLE_SEGMENT:
        return _unjoined(observation_id, STATUS_UNKNOWN_IDENTITY, **common)
    replay = replays.get(page_id)
    if replay is None:
        replay = replays[page_id] = _replay_page(document, page_id)
    if not replay.available:
        return _unjoined(observation_id, STATUS_REPLAY_UNAVAILABLE, **common)
    key = (int(parsed.path_index), int(parsed.item_index), parsed.edge_index)  # type: ignore[arg-type]
    if key in replay.duplicate_keys:
        return _unjoined(observation_id, STATUS_CONFLICT_DUPLICATE, **common)
    segment = replay.by_key.get(key)
    if segment is None:
        return _unjoined(observation_id, STATUS_MISSING_IN_REPLAY, **common)
    if not segment.id_consistent or segment.is_rect_edge != (parsed.edge_index is not None):
        return _unjoined(observation_id, STATUS_CONFLICT_IDENTITY_FIELDS, **common)
    if tuple(float(v) for v in observation.geometry) != segment.geometry:
        return _unjoined(observation_id, STATUS_CONFLICT_GEOMETRY, **common)
    return JoinRow(
        observation_id=observation_id,
        status=STATUS_JOINED,
        state=segment.state,
        replay_items_in_path=replay.items_per_path.get(int(parsed.path_index)),  # type: ignore[arg-type]
        **common,
    )


def _mark_path_conflicts(rows: dict[str, JoinRow]) -> dict[str, JoinRow]:
    """Graphic state is per drawing path: two joined rows of one path that differ conflict."""
    digests: dict[tuple[str, int], set[str]] = {}
    for row in rows.values():
        if row.joined and row.path_key is not None:
            digests.setdefault(row.path_key, set()).add(row.digest())
    bad = {key for key, values in digests.items() if len(values) > 1}
    if not bad:
        return rows
    out = {}
    for oid, row in rows.items():
        if row.joined and row.path_key in bad:
            out[oid] = _unjoined(
                oid,
                STATUS_CONFLICT_PATH_METADATA,
                page_id=row.page_id,
                raw_ref=row.raw_ref,
                ref_class=row.ref_class,
                path_index=row.path_index,
                item_index=row.item_index,
                edge_index=row.edge_index,
            )
        else:
            out[oid] = row
    return out


# --------------------------------------------------------------- summaries
def _top(counter: Counter, limit: int) -> tuple[list[str], int]:
    ordered = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [key for key, _ in ordered[:limit]], len(ordered)


class _Cell:
    """Rows of one group / class (/ page); path-level state is constant per path."""

    def __init__(self) -> None:
        self.rows: list[JoinRow] = []
        self.weights: dict[str, int] = {}

    def add(self, row: JoinRow, weight: int = 1) -> None:
        self.rows.append(row)
        self.weights[row.observation_id] = weight

    def summary(self, limit: int, path_sizes: Mapping[tuple[str, int], int]) -> dict[str, Any]:
        statuses = Counter(row.status for row in self.rows)
        joined = [row for row in self.rows if row.joined]
        path_state: dict[tuple[str, int], dict[str, str]] = {}
        path_prims: Counter = Counter()
        path_items: dict[tuple[str, int], Optional[int]] = {}
        for row in joined:
            key = row.path_key
            assert key is not None and row.state is not None
            path_state.setdefault(key, row.state.states())
            path_prims[key] += 1
            path_items.setdefault(key, row.replay_items_in_path)
        histograms: dict[str, Any] = {}
        for field in FIELDS:
            paths: Counter = Counter()
            prims: Counter = Counter()
            for key, states in path_state.items():
                paths[states[field]] += 1
                prims[states[field]] += path_prims[key]
            keep, distinct = _top(prims, limit)
            histograms[field] = {
                "distinct_values": distinct,
                "values": {
                    value: {"paths": paths[value], "primitives": prims[value]} for value in keep
                },
                "other": {
                    "paths": sum(paths.values()) - sum(paths[v] for v in keep),
                    "primitives": sum(prims.values()) - sum(prims[v] for v in keep),
                },
            }
        size = Counter(size_band(count) for count in path_prims.values())
        visible_in_path = Counter(
            size_band(path_sizes[key]) if key in path_sizes else "unknown" for key in path_state
        )
        items = Counter(
            size_band(count) if count is not None else "unknown" for count in path_items.values()
        )
        return {
            "primitives": len(self.rows),
            "incidences": sum(self.weights.values()),
            "joined_primitives": len(joined),
            "unique_paths": len(path_state),
            "join_status_counts": {s: statuses[s] for s in JOIN_STATUSES if statuses[s]},
            "histograms": histograms,
            "group_primitives_per_path": {b: size[b] for b in SIZE_BANDS if size[b]},
            # Source-owned size of the whole path on its page (all visible native
            # segments of that path, whatever the group); a path is one independent
            # graphic-state observation however many primitives it holds.
            "visible_segments_in_path": {
                b: visible_in_path[b] for b in (*SIZE_BANDS, "unknown") if visible_in_path[b]
            },
            "replay_items_per_path": {
                b: items[b] for b in (*SIZE_BANDS, "unknown") if items[b]
            },
        }


def _shares(summary: Mapping[str, Any], field: str, value: str) -> dict[str, Any]:
    paths_total = summary["unique_paths"]
    prims_total = summary["joined_primitives"]
    entry = summary["histograms"][field]["values"].get(value)
    paths = entry["paths"] if entry else 0
    prims = entry["primitives"] if entry else 0
    out: dict[str, Any] = {
        "paths": paths,
        "paths_denominator": paths_total,
        "primitives": prims,
        "primitives_denominator": prims_total,
    }
    if paths_total < RATIO_MIN_UNIQUE_PATHS:
        out["path_share"] = RATIO_SUPPRESSED_LOW_N
        out["primitive_share"] = RATIO_SUPPRESSED_LOW_N
    else:
        out["path_share"] = round(paths / paths_total, 6)
        out["primitive_share"] = round(prims / prims_total, 6)
    return out


def _compare(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in FIELDS:
        values = sorted(
            {*a["histograms"][field]["values"], *b["histograms"][field]["values"]}
        )
        rows = []
        for value in values:
            left, right = _shares(a, field, value), _shares(b, field, value)
            entry: dict[str, Any] = {"value": value, "participating": left, "baseline": right}
            if RATIO_SUPPRESSED_LOW_N in (left["path_share"], right["path_share"]):
                entry["path_share_difference"] = RATIO_SUPPRESSED_LOW_N
            else:
                entry["path_share_difference"] = round(
                    left["path_share"] - right["path_share"], 6
                )
            rows.append(entry)
        out[field] = rows
    return out


@dataclass(frozen=True)
class NativeGraphicStateJoin:
    record_id: str
    payload_json: str
    commercial_authority_granted: bool = False

    def __post_init__(self) -> None:
        if self.commercial_authority_granted is not False:
            raise ValueError("a diagnostic never grants commercial authority")
        expected = stable_contract_id(
            "native_graphic_state_join", json.loads(self.payload_json), digest_chars=32
        )
        if self.record_id != expected:
            raise ValueError("record_id does not match the join content")

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self.payload_json)
        payload["record_id"] = self.record_id
        return payload


def _seal(payload: dict[str, Any]) -> NativeGraphicStateJoin:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload = json.loads(canonical)
    return NativeGraphicStateJoin(
        record_id=stable_contract_id("native_graphic_state_join", payload, digest_chars=32),
        payload_json=canonical,
    )


def _header(
    *,
    status: str,
    record: Any,
    semantic_result: SemanticOpeningEnumerationResult,
    computed_sha: str,
    published: Any,
) -> dict[str, Any]:
    return {
        "schema_version": JOIN_SCHEMA_VERSION,
        "status": status,
        "join_key": JOIN_KEY,
        "view_id": VIEW_ID,
        "view_scope_status": VIEW_SCOPE_STATUS,
        "ratio_min_unique_paths": RATIO_MIN_UNIQUE_PATHS,
        "binding": None
        if record is None
        else {
            "document_id": record.document_id,
            "revision_id": record.revision_id,
            "source_sha256": record.source_sha256,
            "supplied_bytes_sha256": computed_sha,
            "snapshot_id": record.snapshot_id,
            "semantic_record_id": record.record_id,
            "producer_method": None if published is None else published.revision.producer_method,
            "producer_version": None if published is None else published.revision.producer_version,
            "pymupdf_version": fitz.VersionBind,
            "extractor": "pb_vector_geometry_v130.extract_native_page",
        },
        "semantic_status": str(semantic_result.status.value),
        "commercial_authority_granted": False,
    }


def build_native_graphic_state_join(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    semantic_result: SemanticOpeningEnumerationResult,
    source_bytes: bytes,
    reference_structure: Optional[CandidateStructureSummary] = None,
) -> NativeGraphicStateJoin:
    """Join producer graphic state to the visible primitives of one semantic scope.

    Read-only.  ``source_bytes`` are caller-supplied and must hash to the source
    SHA-256 already bound to the scope, otherwise nothing is extracted or joined.
    """
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if not isinstance(semantic_result, SemanticOpeningEnumerationResult):
        raise TypeError("semantic_result must be a SemanticOpeningEnumerationResult")
    if not isinstance(source_bytes, (bytes, bytearray)):
        raise TypeError("source_bytes must be bytes")
    if reference_structure is not None and not isinstance(
        reference_structure, CandidateStructureSummary
    ):
        raise TypeError("reference_structure must be a CandidateStructureSummary")

    record = semantic_result.record
    computed_sha = hashlib.sha256(bytes(source_bytes)).hexdigest()
    if record is None:
        payload = _header(
            status=SCOPE_STATUS_ABSENT,
            record=None,
            semantic_result=semantic_result,
            computed_sha=computed_sha,
            published=None,
        )
        payload["semantic_reason_codes"] = sorted(str(c) for c in semantic_result.reason_codes)
        return _seal(payload)
    published = source_visibility_producer.published_snapshot_for_revision(record.revision_id)
    if (
        published is None
        or published.revision.document_id != record.document_id
        or published.revision.source_sha256 != record.source_sha256
        or published.snapshot.snapshot_id != record.snapshot_id
    ):
        raise ValueError(
            "semantic record does not belong to this producer's authenticated snapshot"
        )
    if computed_sha != record.source_sha256:
        return _seal(
            _header(
                status=SCOPE_STATUS_SHA_MISMATCH,
                record=record,
                semantic_result=semantic_result,
                computed_sha=computed_sha,
                published=published,
            )
        )

    visibility = source_visibility_producer.authority()
    physical = PhysicalOpeningAuthority(visibility)  # private; only its memo caches fill

    diagnosed = sorted({*record.conflict_observation_ids, *record.residual_visible_observation_ids})
    seed_by_page: dict[str, str] = {}
    for observation_id in diagnosed:
        visible = visibility.resolve_visible(_selector(record, observation_id))
        if (
            visible.status is EvidenceResolutionStatus.CORROBORATED
            and visible.observation is not None
        ):
            seed_by_page.setdefault(str(visible.observation.page_id), observation_id)
    structures: dict[str, Any] = {}
    unavailable_pages: list[dict[str, Any]] = []
    for page_id in sorted(seed_by_page, key=_page_order):
        result = physical.visible_candidate_structures(_selector(record, seed_by_page[page_id]))
        if result.status is not EvidenceResolutionStatus.CANDIDATE or result.page_id != page_id:
            unavailable_pages.append(
                {
                    "page_id": page_id,
                    "status": str(result.status.value),
                    "reason_codes": sorted({str(c) for c in result.reason_codes}),
                }
            )
            continue
        structures[page_id] = result.candidates

    document = fitz.open(stream=bytes(source_bytes), filetype="pdf")
    try:
        replays: dict[str, _PageReplay] = {}
        rows: dict[str, JoinRow] = {}
        for observation_id in sorted(record.visible_observation_ids):
            rows[observation_id] = _join_one(
                visibility.resolve_visible(_selector(record, observation_id)),
                observation_id,
                record,
                replays,
                document,
            )
    finally:
        document.close()
    rows = _mark_path_conflicts(rows)

    # ---- populations, from producer identity and the accessor only
    candidate_pages = set(structures)
    participating_weight: Counter = Counter()
    control_members: set[str] = set()
    candidate_count = 0
    ambiguous: set[str] = set()
    participating_candidates = 0
    for page_id in structures:
        candidates = sorted(structures[page_id], key=lambda c: c.candidate_id)
        candidate_count += len(candidates)
        members_of = [tuple(sorted(c.source_observation_ids)) for c in candidates]
        count_in: Counter = Counter()
        for ids in members_of:
            count_in.update(ids)
        ambiguous.update(oid for oid, n in count_in.items() if n > 1)
        for ids in members_of:
            if any(count_in[oid] > 1 for oid in ids):
                participating_candidates += 1
                participating_weight.update(ids)
            else:
                control_members.update(ids)
    missing_rows = sorted(
        oid for oid in {*participating_weight, *ambiguous, *control_members} if oid not in rows
    )

    def in_candidate_pages(row: JoinRow) -> bool:
        return row.page_id in candidate_pages

    populations: dict[str, dict[str, int]] = {
        G_PARTICIPATING: {oid: participating_weight[oid] for oid in participating_weight if oid in rows},
        G_AMBIGUOUS: {oid: 1 for oid in ambiguous if oid in rows},
        G_UNIVERSE_CAND_PAGES: {
            oid: 1 for oid, row in rows.items() if in_candidate_pages(row) and _in_universe(row)
        },
        G_UNIVERSE_ALL_PAGES: {oid: 1 for oid, row in rows.items() if _in_universe(row)},
        G_CONTROL: {oid: 1 for oid in control_members if oid in rows},
    }
    populations[G_UNIVERSE_MINUS_PART] = {
        oid: 1
        for oid in populations[G_UNIVERSE_CAND_PAGES]
        if oid not in participating_weight
    }

    def cells_for(group: str) -> dict[str, dict[str, _Cell]]:
        by_class: dict[str, dict[str, _Cell]] = {c: {} for c in CLASSES}
        unclassed = _Cell()
        for oid, weight in sorted(populations[group].items()):
            row = rows[oid]
            if row.ref_class in by_class:
                cells = by_class[row.ref_class]
                cells.setdefault("*", _Cell()).add(row, weight)
                cells.setdefault(str(row.page_id), _Cell()).add(row, weight)
            else:
                unclassed.add(row, weight)
        by_class["unclassified"] = {"*": unclassed} if unclassed.rows else {}
        return by_class

    path_sizes: Counter = Counter(
        row.path_key for row in rows.values() if row.ref_class in CLASSES and row.path_key is not None
    )
    cells = {group: cells_for(group) for group in GROUPS}
    doc_groups: dict[str, Any] = {}
    page_groups: dict[str, Any] = {}
    for group in GROUPS:
        doc_groups[group] = {
            klass: (by["*"].summary(TOP_VALUES, path_sizes) if "*" in by else None)
            for klass, by in cells[group].items()
            if by or klass in CLASSES
        }
    pages_with_participating = sorted(
        {p for by in cells[G_PARTICIPATING].values() for p in by if p != "*"}, key=_page_order
    )
    for page_id in pages_with_participating:
        page_groups[page_id] = {
            group: {
                klass: (cells[group][klass][page_id].summary(PAGE_TOP_VALUES, path_sizes)
                        if page_id in cells[group].get(klass, {}) else None)
                for klass in CLASSES
            }
            for group in GROUPS
        }

    comparisons: dict[str, Any] = {}
    page_comparisons: dict[str, Any] = {}
    for klass in CLASSES:
        part = doc_groups[G_PARTICIPATING].get(klass)
        comparisons[klass] = {}
        for other in COMPARED_AGAINST:
            base = doc_groups[other].get(klass)
            comparisons[klass][other] = (
                None if part is None or base is None else _compare(part, base)
            )
    for page_id in pages_with_participating:
        page_comparisons[page_id] = {}
        for klass in CLASSES:
            part = page_groups[page_id][G_PARTICIPATING][klass]
            base = page_groups[page_id][G_UNIVERSE_CAND_PAGES][klass]
            page_comparisons[page_id][klass] = (
                None if part is None or base is None else _compare(part, base)
            )

    # ---- status counts over EVERY row (nothing silently dropped)
    all_status = Counter(row.status for row in rows.values())
    replay_summary = {
        "pages_replayed": len(replays),
        "pages_unavailable": sorted(
            (p for p, r in replays.items() if not r.available), key=_page_order
        ),
        "duplicate_replay_identities": sum(len(r.duplicate_keys) for r in replays.values()),
        "joined_rows": all_status[STATUS_JOINED],
        "rows_total": len(rows),
    }
    rows_digest = hashlib.sha256(
        json.dumps(
            [[oid, row.status, row.digest()] for oid, row in sorted(rows.items())],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    examples: dict[str, list[dict[str, Any]]] = {}
    for group in (G_PARTICIPATING, G_UNIVERSE_CAND_PAGES):
        picked = sorted(populations[group])[:EXAMPLES]
        examples[group] = [rows[oid].to_dict() for oid in picked]
    conflicts = sorted(
        (oid for oid, row in rows.items() if row.status.startswith("conflict")),
    )[:EXAMPLES * 3]
    examples["conflicts"] = [rows[oid].to_dict() for oid in conflicts]

    checks: dict[str, Optional[bool]] = {
        "participating_incidences_match_accessor": sum(participating_weight.values())
        == sum(populations[G_PARTICIPATING].values())
        if not missing_rows
        else False,
        "every_candidate_member_has_a_row": not missing_rows,
        "control_disjoint_from_participating": not (control_members & set(participating_weight)),
        "ambiguous_subset_of_participating": ambiguous <= set(participating_weight),
        "native_participating_within_universe": {
            o for o in populations[G_PARTICIPATING] if rows[o].ref_class in CLASSES
        }
        <= set(populations[G_UNIVERSE_CAND_PAGES]),
        "universe_all_pages_superset_of_candidate_pages": set(populations[G_UNIVERSE_CAND_PAGES])
        <= set(populations[G_UNIVERSE_ALL_PAGES]),
        "candidate_total_matches_structure_reference": None
        if reference_structure is None
        else reference_structure.candidates_total == candidate_count,
        "no_unavailable_candidate_pages": not unavailable_pages,
    }
    checks["all_checks_passed"] = (
        None
        if any(v is None for v in checks.values())
        else all(v for v in checks.values())
    )

    payload = _header(
        status=SCOPE_STATUS_OK,
        record=record,
        semantic_result=semantic_result,
        computed_sha=computed_sha,
        published=published,
    )
    payload.update(
        {
            "scope": {
                "candidate_pages": sorted(candidate_pages, key=_page_order),
                "candidates_total": candidate_count,
                "participating_candidates": participating_candidates,
                "unavailable_pages": unavailable_pages,
                "primitive_classes_stratified": list(CLASSES),
                "primary_baseline": G_UNIVERSE_CAND_PAGES,
                "secondary_descriptive_only": G_CONTROL,
            },
            "replay": replay_summary,
            "join_status_counts": {s: all_status[s] for s in JOIN_STATUSES if all_status[s]},
            "rows_digest": rows_digest,
            "groups": doc_groups,
            "comparisons_vs_participating": comparisons,
            "by_page": page_groups,
            "by_page_comparisons_vs_candidate_page_universe": page_comparisons,
            "examples": examples,
            "consistency": checks,
        }
    )
    return _seal(payload)


def _in_universe(row: JoinRow) -> bool:
    """Complete visible NATIVE primitive universe: every native visible record.

    Rows that could not be joined stay in the universe (with their status); only
    raster / unresolved records have no native identity and are outside it.
    """
    return row.ref_class in CLASSES


def collect_native_graphic_state_join(
    pdf_path: Path | str,
    *,
    document_id: str,
    pages: Optional[Sequence[int]] = None,
    source_bytes: Optional[bytes] = None,
    with_reference: bool = True,
) -> NativeGraphicStateJoin:
    """Publish the Item 35 semantic scope from ``source_bytes`` and join graphic state.

    The bytes that are published are the bytes that are hashed and replayed.
    """
    if source_bytes is None:
        source_bytes = Path(pdf_path).read_bytes()
    source, result = collect_semantic_scope(
        pdf_path, document_id=document_id, pages=pages, source_bytes=source_bytes
    )
    reference = None
    if with_reference and result.record is not None:
        reference = diagnose_semantic_conflicts(
            source_visibility_producer=source, semantic_result=result
        ).candidate_structure
    return build_native_graphic_state_join(
        source_visibility_producer=source,
        semantic_result=result,
        source_bytes=source_bytes,
        reference_structure=reference,
    )
