"""Drawing-path provenance census of physical-opening candidates (Item 35, shadow only).

For the candidates that ``PhysicalOpeningAuthority.visible_candidate_structures``
discovers on the pages of a published semantic scope, this module describes
WHERE their member observations come from, using only the producer-owned
``SourceObservationRecord.source_primitive_ref``.

Grammar of a visible segment ref (minted by ``extract_native_page`` and
``SourceVisibilityProducer``; ``resolve_visible`` already fails closed unless the
ref equals ``"visible:" + parent.source_primitive_ref`` with a native parent on
the same page and geometry):

  visible:segment:d<N>i<M>                        native visible segment (line item)
  visible:segment:d<N>i<M>e<K>   (K = 0..3)       native visible segment (rect edge)
  visible:raster_segment:<sha256>:<detector>:<i>  raster visible segment (no PDF path)

Both native forms carry ``observation_kind == native_pdf_visible_segment``.  The
rect-edge subclass is derived from the verified ``e<K>`` REF SYNTAX only; it is
not carried by ``observation_kind``.  ``N`` is ``enumerate(page.get_drawings())``
and is therefore per page: native path identity is always ``(page_id, N)``,
never the bare index.

Diagnostic only.  Nothing here rejects, filters, ranks, merges or thresholds a
candidate; length bands are fixed REPORTING bins; a candidate whose members share
a path is not called contaminated and one spanning many paths is not called
independent (path order and proximity prove neither authorship, physical
identity nor independence).  Provenance that cannot be resolved or parsed is
reported as ``provenance_incomplete`` with reason codes and is never guessed.
The raw ``source_primitive_ref`` is preserved verbatim wherever it is shown.
No authority module is edited, no private accessor is used, no benchmark file,
expected value or tolerance is read, and production code must not import this
module.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,
    PHYSICAL_OPENING_DISPOSITION_CONFLICT,
    PhysicalOpeningAuthority,
)
from pb_semantic_conflict_diagnostic import (
    CandidateStructureSummary,
    collect_semantic_scope,
    diagnose_semantic_conflicts,
)
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationResult
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)

CENSUS_SCHEMA_VERSION = "1.0.0"
PATH_IDENTITY = "page_id+path_index"

# ------------------------------------------------------------------ ref classes
REF_NATIVE_LINE = "native_line"
REF_NATIVE_RECT_EDGE = "native_rect_edge"
REF_RASTER = "raster"
REF_UNPARSEABLE = "unparseable"
REF_UNRESOLVED = "unresolved"
REF_CLASSES = (
    REF_NATIVE_LINE,
    REF_NATIVE_RECT_EDGE,
    REF_RASTER,
    REF_UNPARSEABLE,
    REF_UNRESOLVED,
)

# Reason codes (a member with any of these makes its candidate provenance_incomplete).
REASON_REF_NOT_A_STRING = "ref_not_a_string"
REASON_REF_PREFIX_UNRECOGNIZED = "ref_prefix_unrecognized"
REASON_REF_GRAMMAR_MISMATCH = "ref_grammar_mismatch"
REASON_REF_KIND_MISMATCH = "ref_kind_mismatch"
REASON_OBSERVATION_NOT_CORROBORATED = "observation_not_corroborated"
REASON_OBSERVATION_LINEAGE_MISMATCH = "observation_lineage_mismatch"
REASON_OBSERVATION_PAGE_MISMATCH = "observation_page_mismatch"
REASON_OBSERVATION_VIEWPORT_SCOPED = "observation_viewport_scoped"

# Path classes of a candidate with complete provenance.
PATH_CLASS_SINGLE = "single_path"
PATH_CLASS_TWO = "two_paths"
PATH_CLASS_THREE_PLUS = "three_plus_paths"
PATH_CLASS_RASTER = "raster_involved"
PATH_CLASSES = (PATH_CLASS_SINGLE, PATH_CLASS_TWO, PATH_CLASS_THREE_PLUS, PATH_CLASS_RASTER)

# Concentration classes of an ambiguous observation's candidates.
CONC_ALL_SINGLE = "all_single_path"
CONC_MIXED = "mixed"
CONC_NONE_SINGLE = "none_single_path"
CONC_CLASSES = (CONC_ALL_SINGLE, CONC_MIXED, CONC_NONE_SINGLE)

GROUP_PARTICIPATING = "participating"
GROUP_CONTROL = "control"

# Fixed REPORTING bins (PDF units).  Not thresholds: nothing is filtered by them.
BAND_BELOW_HALF = "<0.5"
BAND_UNKNOWN = "unknown"
LENGTH_BANDS = (
    BAND_BELOW_HALF,
    "[0.5,1)",
    "[1,2)",
    "[2,5)",
    "[5,10)",
    "[10,25)",
    "[25,100)",
    "[100,∞)",
    BAND_UNKNOWN,
)
_BAND_EDGES = (0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 100.0)
# Finer reporting grid for the tiny lengths (additive histogram; same status).
FINE_BANDS = (
    "<0.5",
    "[0.5,0.6)",
    "[0.6,0.7)",
    "[0.7,0.8)",
    "[0.8,0.9)",
    "[0.9,1)",
    "[1,1.25)",
    "[1.25,1.5)",
    "[1.5,2)",
    "[2,∞)",
    BAND_UNKNOWN,
)
_FINE_EDGES = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.25, 1.5, 2.0)

_NATIVE_REF = re.compile(
    r"visible:segment:d(0|[1-9][0-9]*)i(0|[1-9][0-9]*)(?:e([0-3]))?"
)
_RASTER_REF = re.compile(
    r"visible:raster_segment:([0-9a-f]{64}):([0-9A-Za-z][0-9A-Za-z._-]*):(0|[1-9][0-9]*)"
)

EXAMPLES_PER_CELL = 3
DOMINANT_CELLS = 5
ANOMALY_EXAMPLES = 5


# ------------------------------------------------------------------ pure helpers
@dataclass(frozen=True)
class RefParse:
    ref_class: str
    path_index: Optional[int] = None
    item_index: Optional[int] = None
    edge_index: Optional[int] = None
    reason: Optional[str] = None


def parse_visible_segment_ref(raw_ref: Any) -> RefParse:
    """Parse a visible segment ``source_primitive_ref``; never guess.

    The whole string must match one of the three producer forms (ASCII digits,
    canonical integers without leading zeros).  Anything else is
    ``unparseable`` with a reason code.
    """
    if not isinstance(raw_ref, str):
        return RefParse(REF_UNPARSEABLE, reason=REASON_REF_NOT_A_STRING)
    native = _NATIVE_REF.fullmatch(raw_ref)
    if native is not None:
        edge = native.group(3)
        return RefParse(
            REF_NATIVE_RECT_EDGE if edge is not None else REF_NATIVE_LINE,
            path_index=int(native.group(1)),
            item_index=int(native.group(2)),
            edge_index=int(edge) if edge is not None else None,
        )
    if _RASTER_REF.fullmatch(raw_ref) is not None:
        return RefParse(REF_RASTER)
    if raw_ref.startswith(("visible:segment:", "visible:raster_segment:")):
        return RefParse(REF_UNPARSEABLE, reason=REASON_REF_GRAMMAR_MISMATCH)
    return RefParse(REF_UNPARSEABLE, reason=REASON_REF_PREFIX_UNRECOGNIZED)


def length_band(length: Optional[float]) -> str:
    if length is None or not math.isfinite(length):
        return BAND_UNKNOWN
    for index, edge in enumerate(_BAND_EDGES):
        if length < edge:
            return LENGTH_BANDS[index]
    return LENGTH_BANDS[len(_BAND_EDGES)]


def fine_length_band(length: Optional[float]) -> str:
    if length is None or not math.isfinite(length):
        return BAND_UNKNOWN
    for index, edge in enumerate(_FINE_EDGES):
        if length < edge:
            return FINE_BANDS[index]
    return FINE_BANDS[len(_FINE_EDGES)]


def _segment_length(geometry: Sequence[Any]) -> Optional[float]:
    if len(geometry) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(value) for value in geometry)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
        return None
    return math.hypot(x2 - x1, y2 - y1)


def _band_index(band: str) -> int:
    return LENGTH_BANDS.index(band)


def _quantiles(values: list[float]) -> Optional[dict[str, float]]:
    if not values:
        return None
    ordered = sorted(values)

    def pick(q: float) -> float:
        return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))], 3)

    return {
        "n": len(ordered),
        "min": round(ordered[0], 3),
        "p50": pick(0.5),
        "p90": pick(0.9),
        "max": round(ordered[-1], 3),
    }


def _sorted_counts(counter: Mapping[Any, int]) -> dict[str, int]:
    def key(item: Any) -> tuple[int, Any]:
        text = str(item)
        return (0, int(text)) if text.lstrip("-").isdigit() else (1, text)

    return {str(k): int(counter[k]) for k in sorted(counter, key=key)}


def _fixed_counts(counter: Mapping[str, int], keys: Sequence[str]) -> dict[str, int]:
    return {key: int(counter.get(key, 0)) for key in keys}


def _selector(record: Any, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        observation_id=observation_id,
    )


@dataclass(frozen=True)
class _Member:
    observation_id: str
    page_id: Optional[str]
    raw_ref: Optional[str]
    ref_class: str
    path_index: Optional[int]
    item_index: Optional[int]
    edge_index: Optional[int]
    observation_kind: Optional[str]
    geometry: tuple[float, ...]
    length: Optional[float]
    band: str
    reasons: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.reasons

    @property
    def path_key(self) -> Optional[tuple[str, int]]:
        # Native path identity is ALWAYS page-qualified.
        if self.ref_class in (REF_NATIVE_LINE, REF_NATIVE_RECT_EDGE) and self.complete:
            return (str(self.page_id), int(self.path_index))  # type: ignore[arg-type]
        return None

    @property
    def item_key(self) -> Optional[tuple[str, int, int]]:
        key = self.path_key
        return None if key is None else (key[0], key[1], int(self.item_index))  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "page_id": self.page_id,
            "source_primitive_ref": self.raw_ref,
            "ref_class": self.ref_class,
            "path_index": self.path_index,
            "item_index": self.item_index,
            "edge_index": self.edge_index,
            "observation_kind": self.observation_kind,
            "geometry": [round(v, 3) for v in self.geometry],
            "length": None if self.length is None else round(self.length, 3),
            "length_band": self.band,
            "reason_codes": list(self.reasons),
        }


def _expected_kind(ref_class: str) -> Optional[str]:
    if ref_class in (REF_NATIVE_LINE, REF_NATIVE_RECT_EDGE):
        return NATIVE_PDF_VISIBLE_SEGMENT
    if ref_class == REF_RASTER:
        return RASTER_PDF_VISIBLE_SEGMENT
    return None


def _member_from_visible(visible: Any, observation_id: str, record: Any) -> _Member:
    observation = visible.observation
    if visible.status is not EvidenceResolutionStatus.CORROBORATED or observation is None:
        return _Member(
            observation_id, None, None, REF_UNRESOLVED, None, None, None, None, (), None,
            BAND_UNKNOWN, (REASON_OBSERVATION_NOT_CORROBORATED,),
        )
    raw_ref = observation.source_primitive_ref
    parsed = parse_visible_segment_ref(raw_ref)
    geometry = tuple(float(v) for v in observation.geometry) if observation.geometry else ()
    length = _segment_length(geometry)
    reasons: list[str] = []
    if parsed.reason is not None:
        reasons.append(parsed.reason)
    expected = _expected_kind(parsed.ref_class)
    if expected is not None and observation.observation_kind != expected:
        reasons.append(REASON_REF_KIND_MISMATCH)
    if (
        observation.document_id != record.document_id
        or observation.revision_id != record.revision_id
        or observation.source_sha256 != record.source_sha256
        or observation.snapshot_id != record.snapshot_id
    ):
        reasons.append(REASON_OBSERVATION_LINEAGE_MISMATCH)
    if observation.viewport_id is not None:
        reasons.append(REASON_OBSERVATION_VIEWPORT_SCOPED)
    return _Member(
        observation_id=observation_id,
        page_id=str(observation.page_id),
        raw_ref=raw_ref if isinstance(raw_ref, str) else None,
        ref_class=parsed.ref_class,
        path_index=parsed.path_index,
        item_index=parsed.item_index,
        edge_index=parsed.edge_index,
        observation_kind=str(observation.observation_kind),
        geometry=geometry,
        length=length,
        band=length_band(length),
        reasons=tuple(reasons),
    )


# -------------------------------------------------------------------- tallies
class _GroupTally:
    def __init__(self) -> None:
        self.candidates_total = 0
        self.complete = 0
        self.incomplete = 0
        self.incomplete_reasons: Counter = Counter()
        self.path_class: Counter = Counter()
        self.distinct_paths: Counter = Counter()
        self.distinct_items: Counter = Counter()
        self.members_per_path: Counter = Counter()
        self.max_members_one_path: Counter = Counter()
        self.incidences = 0
        self.by_ref_class: Counter = Counter()
        self.path_index_span: Counter = Counter()
        self.draw_order: Counter = Counter()
        self.band_incidences: Counter = Counter()
        self.fine_incidences: Counter = Counter()
        self.lengths: list[float] = []
        self.cross_min: Counter = Counter()
        self.cross_max: Counter = Counter()
        self.band_by_multiplicity: Counter = Counter()
        self.involved_paths: set[tuple[str, int]] = set()

    def to_dict(self, path_sizes: Mapping[tuple[str, int], int]) -> dict[str, Any]:
        return {
            "candidates_total": self.candidates_total,
            "complete": self.complete,
            "provenance_incomplete": self.incomplete,
            "incomplete_reasons": _sorted_counts(self.incomplete_reasons),
            "path_class": _fixed_counts(self.path_class, PATH_CLASSES),
            "distinct_paths_per_candidate": _sorted_counts(self.distinct_paths),
            "distinct_items_per_candidate": _sorted_counts(self.distinct_items),
            "members_per_path": _sorted_counts(self.members_per_path),
            "max_members_from_one_path": _sorted_counts(self.max_members_one_path),
            "member_incidences": {
                "total": self.incidences,
                REF_NATIVE_LINE: self.by_ref_class.get(REF_NATIVE_LINE, 0),
                REF_NATIVE_RECT_EDGE: self.by_ref_class.get(REF_NATIVE_RECT_EDGE, 0),
                REF_RASTER: self.by_ref_class.get(REF_RASTER, 0),
            },
            "path_index_span": _sorted_counts(self.path_index_span),
            "draw_order": {
                "single_path": self.draw_order.get("single_path", 0),
                "contiguous_run": self.draw_order.get("contiguous_run", 0),
                "non_contiguous": self.draw_order.get("non_contiguous", 0),
            },
            "length": {
                "band_incidences": _fixed_counts(self.band_incidences, LENGTH_BANDS),
                "fine_band_incidences": _fixed_counts(self.fine_incidences, FINE_BANDS),
                "length_quantiles": _quantiles(self.lengths),
                "path_class_by_shortest_member_band": _sorted_counts(self.cross_min),
                "path_class_by_longest_member_band": _sorted_counts(self.cross_max),
                "member_band_by_path_multiplicity": _sorted_counts(self.band_by_multiplicity),
            },
            "path_size_context": {
                "involved_paths_by_visible_segment_count": _sorted_counts(
                    Counter(path_sizes.get(key, 0) for key in self.involved_paths)
                ),
            },
        }


class _ObservationTally:
    def __init__(self) -> None:
        self.assessed = 0
        self.agree = 0
        self.mismatch = 0
        self.incomplete = 0
        self.raster = 0
        self.concentration: Counter = Counter()
        self.own_path_size: Counter = Counter()
        self.union_paths: Counter = Counter()
        self.band_by_conc: Counter = Counter()
        self.band_incidences: Counter = Counter()
        self.fine_incidences: Counter = Counter()

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessed": self.assessed,
            "accessor_disposition_agree": self.agree,
            "accessor_disposition_mismatch": self.mismatch,
            "provenance_incomplete": self.incomplete,
            "raster_involved": self.raster,
            "complete_native": sum(self.concentration.values()),
            "path_concentration": _fixed_counts(self.concentration, CONC_CLASSES),
            "own_path_visible_segment_count": _sorted_counts(self.own_path_size),
            "distinct_paths_in_union_of_its_candidates": _sorted_counts(self.union_paths),
            "own_length_band_by_path_concentration": _sorted_counts(self.band_by_conc),
            "own_length_band": _fixed_counts(self.band_incidences, LENGTH_BANDS),
            "own_fine_length_band": _fixed_counts(self.fine_incidences, FINE_BANDS),
        }


# -------------------------------------------------------------------- the census
@dataclass(frozen=True)
class CandidateProvenanceCensus:
    """Immutable, deterministic census of one published semantic scope."""

    record_id: str
    payload_json: str
    commercial_authority_granted: bool = False

    def __post_init__(self) -> None:
        if self.commercial_authority_granted is not False:
            raise ValueError("a diagnostic never grants commercial authority")
        expected = stable_contract_id(
            "candidate_provenance_census", json.loads(self.payload_json), digest_chars=32
        )
        if self.record_id != expected:
            raise ValueError("record_id does not match the census content")

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self.payload_json)
        payload["record_id"] = self.record_id
        return payload


def _seal(payload: dict[str, Any]) -> CandidateProvenanceCensus:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload = json.loads(canonical)
    return CandidateProvenanceCensus(
        record_id=stable_contract_id("candidate_provenance_census", payload, digest_chars=32),
        payload_json=canonical,
    )


def _empty_group() -> dict[str, Any]:
    return _GroupTally().to_dict({})


def _empty_observations() -> dict[str, Any]:
    return _ObservationTally().to_dict()


def _absent_census(status: Optional[str], reason_codes: Iterable[str]) -> CandidateProvenanceCensus:
    return _seal(
        {
            "schema_version": CENSUS_SCHEMA_VERSION,
            "status": "semantic_record_absent",
            "semantic_status": status,
            "semantic_reason_codes": sorted({str(code) for code in reason_codes}),
            "path_identity": PATH_IDENTITY,
            "length_bands": list(LENGTH_BANDS),
            "binding": None,
            "pages": {"enumerated": 0, "unavailable": 0, "unavailable_detail": []},
            "inventory": None,
            "groups": {GROUP_PARTICIPATING: _empty_group(), GROUP_CONTROL: _empty_group()},
            "ambiguous_observations": _empty_observations(),
            "by_page": {},
            "anomalies": None,
            "examples": {"candidates": {}, "ambiguous_observations": {}},
            "consistency": {"all_checks_passed": None, "checks": {}},
            "commercial_authority_granted": False,
        }
    )


def _page_order(page_id: str) -> tuple[int, Any]:
    return (0, int(page_id)) if page_id.isdigit() else (1, page_id)


def build_candidate_provenance_census(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    semantic_result: SemanticOpeningEnumerationResult,
    reference_structure: Optional[CandidateStructureSummary] = None,
) -> CandidateProvenanceCensus:
    """Describe the drawing-path provenance of the candidates of one semantic scope.

    Read-only.  ``reference_structure`` (the #1059 ``candidate_structure`` of the
    same scope) enables the cross-checks against it; without it those checks are
    reported ``None`` (not checked), never assumed to pass.
    """
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if not isinstance(semantic_result, SemanticOpeningEnumerationResult):
        raise TypeError("semantic_result must be a SemanticOpeningEnumerationResult")
    if reference_structure is not None and not isinstance(
        reference_structure, CandidateStructureSummary
    ):
        raise TypeError("reference_structure must be a CandidateStructureSummary")

    record = semantic_result.record
    if record is None:
        return _absent_census(
            str(semantic_result.status.value), semantic_result.reason_codes
        )
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

    visibility = source_visibility_producer.authority()
    physical = PhysicalOpeningAuthority(visibility)  # private; only its memo caches fill

    member_cache: dict[str, _Member] = {}

    def member(observation_id: str) -> _Member:
        cached = member_cache.get(observation_id)
        if cached is None:
            cached = _member_from_visible(
                visibility.resolve_visible(_selector(record, observation_id)),
                observation_id,
                record,
            )
            member_cache[observation_id] = cached
        return cached

    # Pages: those holding a diagnosed observation (same rule as the #1059 diagnostic).
    diagnosed = sorted(
        {*record.conflict_observation_ids, *record.residual_visible_observation_ids}
    )
    seed_by_page: dict[str, str] = {}
    for observation_id in diagnosed:
        visible = visibility.resolve_visible(_selector(record, observation_id))
        if (
            visible.status is EvidenceResolutionStatus.CORROBORATED
            and visible.observation is not None
        ):
            seed_by_page.setdefault(str(visible.observation.page_id), observation_id)

    structures: dict[str, Any] = {}
    unavailable_detail: list[dict[str, Any]] = []
    for page_id in sorted(seed_by_page, key=_page_order):
        result = physical.visible_candidate_structures(
            _selector(record, seed_by_page[page_id])
        )
        if result.status is not EvidenceResolutionStatus.CANDIDATE or result.page_id != page_id:
            unavailable_detail.append(
                {
                    "page_id": page_id,
                    "status": str(result.status.value),
                    "reason_codes": sorted({str(c) for c in result.reason_codes}),
                }
            )
            continue
        structures[page_id] = result.candidates

    # Page-wide inventory of visible segments (denominator for path sizes).
    enumerated_pages = set(structures)
    inventory_classes: Counter = Counter()
    inventory_reasons: Counter = Counter()
    inventory_band: Counter = Counter()
    path_sizes: Counter = Counter()
    anomalies: dict[str, list[_Member]] = {
        "native_line_below_0_5": [],
        "native_rect_edge_below_0_5": [],
        "raster_below_0_5": [],
    }
    anomaly_counts: Counter = Counter()
    inventory_total = 0
    visible_ids_unresolved = 0
    for observation_id in sorted(record.visible_observation_ids):
        item = member(observation_id)
        if item.ref_class == REF_UNRESOLVED:
            # Page unknown, so it cannot be placed in any page inventory: count it.
            visible_ids_unresolved += 1
            continue
        if item.page_id not in enumerated_pages:
            continue
        inventory_total += 1
        inventory_classes[item.ref_class] += 1
        inventory_reasons.update(item.reasons)
        inventory_band[f"{item.ref_class}|{item.band}"] += 1
        if item.path_key is not None:
            path_sizes[item.path_key] += 1
        if item.band == BAND_BELOW_HALF:
            name = {
                REF_NATIVE_LINE: "native_line_below_0_5",
                REF_NATIVE_RECT_EDGE: "native_rect_edge_below_0_5",
                REF_RASTER: "raster_below_0_5",
            }.get(item.ref_class)
            if name is not None:
                anomaly_counts[name] += 1
                if len(anomalies[name]) < ANOMALY_EXAMPLES:
                    anomalies[name].append(item)
    bare_index_pages: dict[int, set[str]] = {}
    for page_id, path_index in path_sizes:
        bare_index_pages.setdefault(path_index, set()).add(page_id)

    tallies = {GROUP_PARTICIPATING: _GroupTally(), GROUP_CONTROL: _GroupTally()}
    obs_tally = _ObservationTally()
    by_page: dict[str, dict[str, Any]] = {}
    cell_examples: dict[str, dict[str, list[tuple[str, dict[str, Any]]]]] = {
        GROUP_PARTICIPATING: {},
        GROUP_CONTROL: {},
    }
    obs_cell_examples: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    members_outside_inventory = 0
    failed_resolution_reasons: Counter = Counter()
    accessor_multi_obs = 0
    accessor_obs_in_candidates = 0
    candidates_total = 0

    def keep_smallest(store: list, key: str, entry: dict[str, Any]) -> None:
        store.append((key, entry))
        store.sort(key=lambda pair: pair[0])
        del store[EXAMPLES_PER_CELL:]

    conflict_ids_by_page: dict[str, list[str]] = {}
    for observation_id in sorted(record.conflict_observation_ids):
        item = member(observation_id)
        if item.ref_class != REF_UNRESOLVED and item.page_id is not None:
            conflict_ids_by_page.setdefault(item.page_id, []).append(observation_id)

    for page_id in sorted(structures, key=_page_order):
        candidates = sorted(structures[page_id], key=lambda c: c.candidate_id)
        candidates_total += len(candidates)
        members_of = [tuple(sorted(c.source_observation_ids)) for c in candidates]
        by_observation: dict[str, list[int]] = {}
        for index, ids in enumerate(members_of):
            for observation_id in ids:
                by_observation.setdefault(observation_id, []).append(index)
        accessor_obs_in_candidates += len(by_observation)
        accessor_multi_obs += sum(1 for v in by_observation.values() if len(v) > 1)
        page_tallies = {GROUP_PARTICIPATING: _GroupTally(), GROUP_CONTROL: _GroupTally()}
        class_of: dict[int, str] = {}

        for index, candidate in enumerate(candidates):
            items = [member(observation_id) for observation_id in members_of[index]]
            participating = any(len(by_observation[oid]) > 1 for oid in members_of[index])
            group = GROUP_PARTICIPATING if participating else GROUP_CONTROL
            reasons: list[str] = []
            for item in items:
                reasons.extend(item.reasons)
                if item.page_id is not None and item.page_id != page_id:
                    reasons.append(REASON_OBSERVATION_PAGE_MISMATCH)
                if item.path_key is not None and item.path_key not in path_sizes:
                    members_outside_inventory += 1
            for tally in (tallies[group], page_tallies[group]):
                tally.candidates_total += 1
            if reasons:
                unique_reasons = sorted(set(reasons))
                for tally in (tallies[group], page_tallies[group]):
                    tally.incomplete += 1
                    tally.incomplete_reasons.update(unique_reasons)
                failed_resolution_reasons.update(unique_reasons)
                class_of[index] = "provenance_incomplete"
                continue

            native = [item for item in items if item.path_key is not None]
            raster_involved = len(native) != len(items)  # complete + not native => raster
            if raster_involved:
                path_class = PATH_CLASS_RASTER
                per_path: Counter = Counter()
            else:
                per_path = Counter(item.path_key for item in native)
                count = len(per_path)
                path_class = (
                    PATH_CLASS_SINGLE
                    if count == 1
                    else PATH_CLASS_TWO if count == 2 else PATH_CLASS_THREE_PLUS
                )
            class_of[index] = path_class
            bands = [item.band for item in items]
            shortest = min(bands, key=_band_index_or_last)
            longest = max(bands, key=_band_index_or_first)
            for tally in (tallies[group], page_tallies[group]):
                tally.complete += 1
                tally.path_class[path_class] += 1
                tally.incidences += len(items)
                for item in items:
                    tally.by_ref_class[item.ref_class] += 1
                    tally.band_incidences[item.band] += 1
                    tally.fine_incidences[fine_length_band(item.length)] += 1
                    if item.length is not None:
                        tally.lengths.append(item.length)
                tally.cross_min[f"{path_class}|{shortest}"] += 1
                tally.cross_max[f"{path_class}|{longest}"] += 1
                if not raster_involved:
                    tally.distinct_paths[len(per_path)] += 1
                    tally.distinct_items[len({item.item_key for item in native})] += 1
                    tally.max_members_one_path[max(per_path.values())] += 1
                    for multiplicity in per_path.values():
                        tally.members_per_path[multiplicity] += 1
                    for item in items:
                        tally.band_by_multiplicity[
                            f"{item.band}|{per_path[item.path_key]}"
                        ] += 1
                    indices = sorted({key[1] for key in per_path})
                    tally.path_index_span[indices[-1] - indices[0]] += 1
                    if len(indices) == 1:
                        tally.draw_order["single_path"] += 1
                    elif indices[-1] - indices[0] + 1 == len(indices):
                        tally.draw_order["contiguous_run"] += 1
                    else:
                        tally.draw_order["non_contiguous"] += 1
                    tally.involved_paths.update(per_path)
            cell = f"{path_class}|{shortest}"
            keep_smallest(
                cell_examples[group].setdefault(cell, []),
                candidate.candidate_id,
                {
                    "candidate_id": candidate.candidate_id,
                    "page_id": page_id,
                    "structural_pattern": candidate.structural_pattern,
                    "path_class": path_class,
                    "distinct_paths": None if raster_involved else len(per_path),
                    "members": [item.to_dict() for item in items],
                },
            )

        by_page[page_id] = {
            "candidates_total": len(candidates),
            GROUP_PARTICIPATING: {
                "candidates_total": page_tallies[GROUP_PARTICIPATING].candidates_total,
                "provenance_incomplete": page_tallies[GROUP_PARTICIPATING].incomplete,
                "path_class": _fixed_counts(
                    page_tallies[GROUP_PARTICIPATING].path_class, PATH_CLASSES
                ),
                "distinct_paths_per_candidate": _sorted_counts(
                    page_tallies[GROUP_PARTICIPATING].distinct_paths
                ),
            },
            GROUP_CONTROL: {
                "candidates_total": page_tallies[GROUP_CONTROL].candidates_total,
                "provenance_incomplete": page_tallies[GROUP_CONTROL].incomplete,
                "path_class": _fixed_counts(
                    page_tallies[GROUP_CONTROL].path_class, PATH_CLASSES
                ),
                "distinct_paths_per_candidate": _sorted_counts(
                    page_tallies[GROUP_CONTROL].distinct_paths
                ),
            },
        }

        # Ambiguous conflicting observations on this page (disposition-based, as #1059).
        candidate_ids = [c.candidate_id for c in candidates]
        for observation_id in conflict_ids_by_page.get(page_id, ()):
            item = member(observation_id)
            if REASON_OBSERVATION_LINEAGE_MISMATCH in item.reasons:
                continue
            disposition = physical.classify_disposition(_selector(record, observation_id))
            if not (
                (
                    disposition.status is EvidenceResolutionStatus.CONFLICT
                    or disposition.disposition == PHYSICAL_OPENING_DISPOSITION_CONFLICT
                )
                and AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES in disposition.reason_codes
            ):
                continue
            obs_tally.assessed += 1
            containing = by_observation.get(observation_id, [])
            if {candidate_ids[i] for i in containing} != set(disposition.candidate_ids):
                obs_tally.mismatch += 1
                continue
            obs_tally.agree += 1
            classes = [class_of[i] for i in containing]
            if (
                not item.complete
                or any(name == "provenance_incomplete" for name in classes)
            ):
                obs_tally.incomplete += 1
                continue
            if item.ref_class == REF_RASTER or any(name == PATH_CLASS_RASTER for name in classes):
                obs_tally.raster += 1
                continue
            single = sum(1 for name in classes if name == PATH_CLASS_SINGLE)
            conc = (
                CONC_ALL_SINGLE
                if single == len(classes)
                else CONC_NONE_SINGLE if single == 0 else CONC_MIXED
            )
            union: set[tuple[str, int]] = set()
            for i in containing:
                union.update(
                    member(oid).path_key for oid in members_of[i]  # type: ignore[misc]
                )
            obs_tally.concentration[conc] += 1
            obs_tally.own_path_size[path_sizes.get(item.path_key, 0)] += 1
            obs_tally.union_paths[len(union)] += 1
            obs_tally.band_by_conc[f"{item.band}|{conc}"] += 1
            obs_tally.band_incidences[item.band] += 1
            obs_tally.fine_incidences[fine_length_band(item.length)] += 1
            keep_smallest(
                obs_cell_examples.setdefault(f"{conc}|{item.band}", []),
                observation_id,
                {
                    "observation": item.to_dict(),
                    "candidates": len(containing),
                    "own_path_visible_segment_count": path_sizes.get(item.path_key, 0),
                    "distinct_paths_in_union": len(union),
                    "path_concentration": conc,
                },
            )

    # ---------------------------------------------------------------- assembly
    group_dicts = {name: tally.to_dict(path_sizes) for name, tally in tallies.items()}
    participating = tallies[GROUP_PARTICIPATING]
    control = tallies[GROUP_CONTROL]

    def dominant(cells: Mapping[str, int]) -> list[str]:
        if not cells:
            return []
        ranked = sorted(cells, key=lambda name: (-cells[name], name))
        cutoff = cells[ranked[min(DOMINANT_CELLS, len(ranked)) - 1]]
        return [name for name in ranked if cells[name] >= cutoff]

    examples: dict[str, Any] = {"candidates": {}, "ambiguous_observations": {}}
    for group, tally in tallies.items():
        cells = dict(tally.cross_min)
        examples["candidates"][group] = {
            "dominant_cells": dominant(cells),
            "by_cell": {
                cell: [entry for _key, entry in cell_examples[group].get(cell, [])]
                for cell in dominant(cells)
            },
        }
    obs_cells = dict(obs_tally.band_by_conc)
    obs_cells_keyed = {f"{k.split('|')[1]}|{k.split('|')[0]}": v for k, v in obs_cells.items()}
    examples["ambiguous_observations"] = {
        "dominant_cells": dominant(obs_cells_keyed),
        "by_cell": {
            cell: [entry for _key, entry in obs_cell_examples.get(cell, [])]
            for cell in dominant(obs_cells_keyed)
        },
    }

    total_pcs = participating.candidates_total + control.candidates_total
    total_incidences = participating.incidences + control.incidences
    checks: dict[str, Optional[bool]] = {
        "candidates_total_matches_structure_reference": (
            None if reference_structure is None
            else candidates_total == reference_structure.candidates_total
        ),
        "ambiguous_observations_match_structure_reference": (
            None if reference_structure is None
            else obs_tally.assessed == reference_structure.ambiguous_observations_assessed
        ),
        "observations_in_multiple_candidates_match_structure_reference": (
            None if reference_structure is None
            else accessor_multi_obs == reference_structure.observations_in_multiple_candidates
        ),
        "observations_in_candidates_match_structure_reference": (
            None if reference_structure is None
            else accessor_obs_in_candidates == reference_structure.observations_in_candidates
        ),
        "participating_plus_control_equals_total": total_pcs == candidates_total,
        "complete_plus_incomplete_equals_group_total": all(
            t.complete + t.incomplete == t.candidates_total for t in tallies.values()
        ),
        "path_class_bins_sum_to_complete": all(
            sum(t.path_class.values()) == t.complete for t in tallies.values()
        ),
        "length_band_sums_match_member_incidences": all(
            sum(t.band_incidences.values()) == t.incidences
            and sum(t.fine_incidences.values()) == t.incidences
            for t in tallies.values()
        ) and sum(obs_tally.band_incidences.values()) == sum(obs_tally.concentration.values()),
        "candidate_and_member_ids_agree_with_accessor": obs_tally.mismatch == 0,
        "native_path_identity_is_page_qualified": all(
            isinstance(key, tuple) and len(key) == 2 and isinstance(key[0], str)
            for key in path_sizes
        ),
        "no_unavailable_pages": not unavailable_detail,
        "no_failed_provenance_resolutions": not failed_resolution_reasons
        and not inventory_reasons
        and visible_ids_unresolved == 0,
        "no_members_outside_page_inventory": members_outside_inventory == 0,
    }
    verdicts = [value for value in checks.values() if value is not None]
    payload = {
        "schema_version": CENSUS_SCHEMA_VERSION,
        "status": "ok",
        "semantic_status": str(semantic_result.status.value),
        "semantic_reason_codes": sorted({str(c) for c in record.reason_codes}),
        "path_identity": PATH_IDENTITY,
        "length_bands": list(LENGTH_BANDS),
        "binding": {
            "semantic_record_id": record.record_id,
            "document_id": record.document_id,
            "revision_id": record.revision_id,
            "source_sha256": record.source_sha256,
            "snapshot_id": record.snapshot_id,
            "decision_scope_id": record.decision_scope_id,
            "decision_scope_kind": record.decision_scope_kind,
            "page_ids": [str(p) for p in record.page_ids],
        },
        "pages": {
            "enumerated": len(structures),
            "unavailable": len(unavailable_detail),
            "unavailable_detail": unavailable_detail,
        },
        "inventory": {
            "visible_segments_on_enumerated_pages": inventory_total,
            "by_ref_class": _fixed_counts(inventory_classes, REF_CLASSES),
            "reason_codes": _sorted_counts(inventory_reasons),
            "length_band_by_ref_class": _sorted_counts(inventory_band),
            "native_paths": len(path_sizes),
            "native_paths_by_visible_segment_count": _sorted_counts(
                Counter(path_sizes.values())
            ),
            "bare_path_indices_shared_by_several_pages": sum(
                1 for pages in bare_index_pages.values() if len(pages) > 1
            ),
            "members_outside_page_inventory": members_outside_inventory,
            "visible_ids_unresolved": visible_ids_unresolved,
        },
        "groups": group_dicts,
        "ambiguous_observations": {
            **obs_tally.to_dict(),
            "observations_in_multiple_candidates": accessor_multi_obs,
            "observations_in_candidates": accessor_obs_in_candidates,
        },
        "by_page": {page: by_page[page] for page in sorted(by_page, key=_page_order)},
        "anomalies": {
            "counts": {
                name: anomaly_counts.get(name, 0) for name in sorted(anomalies)
            },
            "note": (
                "reported, never filtered; the visibility authority rejects native "
                "segments shorter than 0.5 (VISIBILITY_GEOMETRY_INVALID), so a native "
                "visible record below 0.5 contradicts the producer"
            ),
            "examples": {
                name: [item.to_dict() for item in items]
                for name, items in sorted(anomalies.items())
            },
        },
        "examples": examples,
        "consistency": {
            "checks": checks,
            "all_checks_passed": (all(verdicts) if verdicts else None),
            "candidates_total": candidates_total,
            "member_incidences_total": total_incidences,
        },
        "commercial_authority_granted": False,
    }
    return _seal(payload)


def _band_index_or_last(band: str) -> int:
    # `unknown` never wins "shortest" against a known band.
    return _band_index(band) if band != BAND_UNKNOWN else len(LENGTH_BANDS) + 1


def _band_index_or_first(band: str) -> int:
    # `unknown` never wins "longest" against a known band.
    return _band_index(band) if band != BAND_UNKNOWN else -1


def collect_candidate_provenance_census(
    pdf_path: Path | str,
    *,
    document_id: str,
    pages: Optional[Sequence[int]] = None,
    source_bytes: Optional[bytes] = None,
    with_reference: bool = True,
) -> CandidateProvenanceCensus:
    """Publish the Item 35 semantic scope and census it.

    With ``with_reference`` the #1059 diagnostic runs on the SAME published scope
    and its ``candidate_structure`` is the cross-check reference.
    """
    source, result = collect_semantic_scope(
        pdf_path, document_id=document_id, pages=pages, source_bytes=source_bytes
    )
    reference = None
    if with_reference and result.record is not None:
        reference = diagnose_semantic_conflicts(
            source_visibility_producer=source, semantic_result=result
        ).candidate_structure
    return build_candidate_provenance_census(
        source_visibility_producer=source,
        semantic_result=result,
        reference_structure=reference,
    )


# ---------------------------------------------------------------- aggregation
_ADDITIVE_GROUP_KEYS = (
    "candidates_total",
    "complete",
    "provenance_incomplete",
)
_HISTOGRAM_GROUP_KEYS = (
    "incomplete_reasons",
    "path_class",
    "distinct_paths_per_candidate",
    "distinct_items_per_candidate",
    "members_per_path",
    "max_members_from_one_path",
    "path_index_span",
)


def _add(dst: dict[str, Any], src: Mapping[str, Any]) -> None:
    for key, value in src.items():
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, Mapping):
            _add(dst.setdefault(key, {}), value)
        elif isinstance(value, (int, float)):
            dst[key] = dst.get(key, 0) + value


def aggregate_candidate_provenance_censuses(
    censuses: Iterable[CandidateProvenanceCensus],
) -> dict[str, Any]:
    """Deterministic, order-invariant sum of censuses.

    Counts and histograms add.  Quantiles and examples do not add and stay per
    scope.  Consistency checks are combined with AND (``None`` if never checked).
    """
    items = list(censuses)
    if not all(isinstance(item, CandidateProvenanceCensus) for item in items):
        raise TypeError("censuses must be CandidateProvenanceCensus instances")
    ordered = sorted(items, key=lambda item: item.record_id)
    dicts = [item.to_dict() for item in ordered]
    live = [d for d in dicts if d["status"] == "ok"]

    total: dict[str, Any] = {"groups": {}, "ambiguous_observations": {}, "inventory": {}}
    for d in live:
        for group, block in d["groups"].items():
            scrubbed = json.loads(json.dumps(block))
            scrubbed["length"].pop("length_quantiles", None)
            _add(total["groups"].setdefault(group, {}), scrubbed)
        _add(total["ambiguous_observations"], d["ambiguous_observations"])
        _add(total["inventory"], d["inventory"])
    total["pages"] = {
        "enumerated": sum(d["pages"]["enumerated"] for d in live),
        "unavailable": sum(d["pages"]["unavailable"] for d in live),
    }
    total["anomalies"] = {}
    for d in live:
        _add(total["anomalies"], d["anomalies"]["counts"])

    check_names = sorted({name for d in live for name in d["consistency"]["checks"]})
    checks: dict[str, Optional[bool]] = {}
    for name in check_names:
        values = [d["consistency"]["checks"].get(name) for d in live]
        known = [v for v in values if v is not None]
        checks[name] = all(known) if known else None
    verdicts = [v for v in checks.values() if v is not None]
    payload: dict[str, Any] = {
        "schema_version": CENSUS_SCHEMA_VERSION,
        "scope_count": len(dicts),
        "scopes_without_semantic_record": len(dicts) - len(live),
        "census_record_ids": [d["record_id"] for d in dicts],
        "path_identity": PATH_IDENTITY,
        "length_bands": list(LENGTH_BANDS),
        **total,
        "consistency": {
            "checks": checks,
            "all_checks_passed": (all(verdicts) if verdicts else None),
        },
        "commercial_authority_granted": False,
    }
    payload["record_id"] = stable_contract_id(
        "candidate_provenance_census_summary", payload, digest_chars=32
    )
    return payload


__all__ = [
    "CENSUS_SCHEMA_VERSION",
    "CandidateProvenanceCensus",
    "FINE_BANDS",
    "LENGTH_BANDS",
    "PATH_CLASSES",
    "PATH_IDENTITY",
    "RefParse",
    "aggregate_candidate_provenance_censuses",
    "build_candidate_provenance_census",
    "collect_candidate_provenance_census",
    "fine_length_band",
    "length_band",
    "parse_visible_segment_ref",
]
