"""Structure-adjusted graphic-state check for Item 35 candidates (Phase 2b, shadow only).

Question studied: after holding the *structure* of a native drawing path fixed
(its page and how many visible native primitives it holds, and for lines whether
it carries a fill), do paths that hold participating member primitives of
ambiguous physical-opening candidates still differ in source-owned graphic state
from the other visible native paths on the same candidate pages?

The Phase-2 join answered a marginal version of this and warned that the effects
overlap with path size and edge visibility.  This module works on the identical
per-primitive rows (``build_native_graphic_state_join_rows``) and reports the
crude difference, the difference inside the strata that can be judged, and the
direct-standardised difference side by side, so the reader can see how much of a
crude difference is path structure and how much is left.

Diagnostic only.  Nothing here rejects, filters, ranks, merges, thresholds or
scores a candidate, an opening, a wall or a count.  The only thing this could
ever establish is *residual association between graphic state and candidate
participation after conditioning on path structure*.  It cannot say a candidate
is false or real: participation is a property of how candidates are built, not a
truth label, and no independent truth source is read.  No metadata value is a
rule (a rect edge, a short path, a filled path, a stroke width, a layer name, a
colour or a dash pattern is never treated as noise or as an opening).

Unit and groups
---------------
The unit of analysis is the unique page-qualified native path, per primitive
class (``native_line`` and ``native_rect_edge`` are never pooled): graphic state
is constant per drawing path, so a path is one independent observation however
many primitives it holds.

* participating: a path holding at least one primitive that is a member of a
  participating candidate (the same primitive set as the Phase-2 join).
* baseline (PRIMARY): every other visible native path of that class on the
  candidate pages.  This is ``visible_universe_candidate_pages_minus_participating``
  at path level: a path with any participating primitive is participating, so no
  path is ever on both sides (``mixed_paths`` counts the participating paths that
  also hold non-participating primitives).
* control (SECONDARY, descriptive only): baseline paths holding a non-participating
  candidate member.  It is small; only counts are reported and it is never
  standardised against.

A path with any primitive that did not join by exact identity is excluded from
the analysis (never guessed) and counted.

Strata, standardisation and the reporting floor
-----------------------------------------------
Strata are page x visible-primitives-in-path band (x fill presence, except when
fill presence is itself the outcome).  Sensitivity plans (finer size bands, or pages
pooled so a multi-page source keeps an estimate) are labelled and never replace the
approved plans.  Standardisation is direct, to the
participating stratum mix, over the strata in which BOTH groups hold at least
``RATIO_MIN_UNIQUE_PATHS`` unique paths.  Per outcome the crude difference, the
difference restricted to those eligible strata, the standardised difference, the
share of participating paths those strata cover, the per-stratum signs and a
deterministic null-split control are all reported, with raw counts and every
denominator.  Strata where the direction reverses are listed, not hidden.  Below
the floor a ratio is ``ratio_suppressed_low_n`` and only raw counts are shown.
The floor is a reporting guard, never a production threshold and no evidence of
significance.  All arithmetic is exact rational arithmetic, rounded only on
output, so results do not depend on input order.

The null control splits the *baseline* paths into two halves by a hash of
(source SHA-256, page, path, primitive class, fixed salt).  It ignores
participation, reads no gold, mutates no row and replays identically.  It is a
calibration reference for the size of a difference with no participation effect,
not a significance test; the halves are usually larger than the participating
group, so it understates that group's sampling noise.

No authority module is edited, no private accessor of an authority is used, no
benchmark file, expected value or tolerance is read, and production code must not
import this module.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType
from typing import Any, Optional

import fitz

from pb_migration_contracts import stable_contract_id
from pb_native_graphic_state_join import (
    ABSENT,
    CLASSES,
    FIELDS,
    G_CONTROL,
    G_PARTICIPATING,
    JOIN_KEY,
    JOIN_SCHEMA_VERSION,
    JOIN_STATUSES,
    RATIO_MIN_UNIQUE_PATHS,
    RATIO_SUPPRESSED_LOW_N,
    SCOPE_STATUS_ABSENT,
    SCOPE_STATUS_OK,
    SCOPE_STATUS_SHA_MISMATCH,
    VIEW_ID,
    VIEW_SCOPE_STATUS,
    GraphicState,
    JoinRow,
    NativeJoinRows,
    build_native_graphic_state_join_rows,
    digest_of_rows,
)
from pb_semantic_conflict_diagnostic import (
    CandidateStructureSummary,
    collect_semantic_scope,
    diagnose_semantic_conflicts,
)
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationResult
from pb_source_visibility_authority import SourceVisibilityProducer

STRATIFIED_SCHEMA_VERSION = "1.0.0"
FILL_PRESENCE = "fill_presence"
FILL_PRESENT = "fill_present"
FILL_ABSENT = "fill_absent"
OTHER_VALUES = "other_values"
POOLED_PAGES = "all_pages"
MAX_VALUES = 12
MAX_FOLDED_LISTED = 50
NULL_SPLIT_SALTS = ("null_split_v1:0", "null_split_v1:1", "null_split_v1:2")
PRIMARY_BASELINE = "visible_universe_candidate_pages_minus_participating"
REQUIRED_STATE_KEYS = (*FIELDS, FILL_PRESENCE)

LINE_BANDS = ("1", "2", "3-5", "6-10", "11+")
# Sensitivity only: the approved top band is open-ended, so participation (which grows with
# path size) could leave residual size confounding inside it; these bands close it.
LINE_FINE_BANDS = ("1", "2", "3", "4", "5", "6-10", "11-20", "21-50", "51+")
RECT_BANDS = ("1-2", "3-5", "6+")
# Sensitivity only: one rect has at most four edges, so 3-5 pools a clipped rect
# with a full one; the fine bands hold that structure fixed as well.
RECT_FINE_BANDS = ("1", "2", "3", "4", "5-8", "9+")

Stratum = tuple[str, ...]


def line_band(count: int) -> str:
    if count <= 1:
        return "1"
    if count == 2:
        return "2"
    if count <= 5:
        return "3-5"
    if count <= 10:
        return "6-10"
    return "11+"


def line_fine_band(count: int) -> str:
    if count <= 5:
        return str(max(count, 1))
    if count <= 10:
        return "6-10"
    if count <= 20:
        return "11-20"
    if count <= 50:
        return "21-50"
    return "51+"


def rect_band(count: int) -> str:
    if count <= 2:
        return "1-2"
    if count <= 5:
        return "3-5"
    return "6+"


def rect_fine_band(count: int) -> str:
    if count <= 4:
        return str(max(count, 1))
    if count <= 8:
        return "5-8"
    return "9+"


def null_half(source_sha256: str, page_id: str, path_index: int, ref_class: str, salt: str) -> int:
    """Deterministic 0/1 split of one path.  Depends only on source-owned identity."""
    blob = f"{salt}|{source_sha256}|{page_id}|{path_index}|{ref_class}".encode("utf-8")
    return hashlib.sha256(blob).digest()[0] & 1


def _page_key(page_id: str) -> tuple[int, Any, str]:
    """Total order on page ids (numeric first); the id itself breaks ties such as '1' vs '01'."""
    return (0, int(page_id), page_id) if page_id.isdigit() else (1, 0, page_id)


# ------------------------------------------------------------- path records
def path_states(state: GraphicState) -> dict[str, str]:
    """The Phase-2 field states of one path plus the derived fill-presence flag."""
    out = dict(state.states())
    out[FILL_PRESENCE] = FILL_PRESENT if state.fill_present else FILL_ABSENT
    return out


@dataclass(frozen=True)
class PathRecord:
    """One page-qualified native path of one primitive class, all rows joined."""

    page_id: str
    path_index: int
    ref_class: str
    visible_primitives: int
    participating_primitives: int
    control_primitives: int
    states: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.ref_class not in CLASSES:
            raise ValueError(f"unknown primitive class {self.ref_class!r}")
        if not isinstance(self.page_id, str):
            raise ValueError("page_id must be a string")
        if self.visible_primitives < 1:
            raise ValueError("a path holds at least one visible primitive")
        if min(self.participating_primitives, self.control_primitives) < 0:
            raise ValueError("counts cannot be negative")
        if self.participating_primitives + self.control_primitives > self.visible_primitives:
            raise ValueError("a primitive is participating, control or neither, never two")
        missing = [key for key in REQUIRED_STATE_KEYS if key not in self.states]
        if missing:
            raise ValueError(f"missing state keys {missing}")
        object.__setattr__(self, "states", MappingProxyType(dict(self.states)))

    @property
    def key(self) -> tuple[str, int, str]:
        return (self.page_id, self.path_index, self.ref_class)

    @property
    def participating(self) -> bool:
        return self.participating_primitives > 0


def _record_sort_key(record: PathRecord) -> tuple[Any, ...]:
    return (_page_key(record.page_id), record.path_index, record.ref_class)


@dataclass(frozen=True)
class PathPopulation:
    records: tuple[PathRecord, ...]
    excluded_paths: Mapping[str, int]
    unjoined_rows_in_excluded_paths: Mapping[str, int]
    excluded_joined_participating_primitives: Mapping[str, int]
    excluded_path_keys: frozenset[tuple[str, int, str]]


def build_path_records(bundle: NativeJoinRows) -> PathPopulation:
    """Group the join rows of the candidate pages into (page, path, class) records.

    A path with any native row that did not join by exact identity is excluded and
    counted, never analysed on partial information.
    """
    if not bundle.ok:
        raise ValueError(f"no join rows to analyse (status {bundle.status})")
    participating = bundle.populations[G_PARTICIPATING]
    control = bundle.populations[G_CONTROL]
    grouped: dict[tuple[str, int, str], list[tuple[str, JoinRow]]] = {}
    for observation_id in sorted(bundle.rows):
        row = bundle.rows[observation_id]
        if (
            row.ref_class not in CLASSES
            or row.page_id not in bundle.candidate_pages
            or row.path_index is None
        ):
            continue
        grouped.setdefault((str(row.page_id), row.path_index, row.ref_class), []).append(
            (observation_id, row)
        )
    records: list[PathRecord] = []
    excluded: Counter = Counter()
    unjoined_status: Counter = Counter()
    excluded_participating: Counter = Counter()
    excluded_keys: set[tuple[str, int, str]] = set()
    for key in sorted(grouped, key=lambda k: (_page_key(k[0]), k[1], k[2])):
        members = grouped[key]
        unjoined = [row for _, row in members if not row.joined]
        if unjoined:
            excluded_keys.add(key)
            excluded[key[2]] += 1
            unjoined_status.update(row.status for row in unjoined)
            excluded_participating[key[2]] += sum(
                1 for oid, row in members if row.joined and oid in participating
            )
            continue
        state = members[0][1].state
        assert state is not None
        records.append(
            PathRecord(
                page_id=key[0],
                path_index=key[1],
                ref_class=key[2],
                visible_primitives=len(members),
                participating_primitives=sum(1 for oid, _ in members if oid in participating),
                control_primitives=sum(1 for oid, _ in members if oid in control),
                states=MappingProxyType(path_states(state)),
            )
        )
    return PathPopulation(
        records=tuple(records),
        excluded_paths=MappingProxyType(dict(excluded)),
        unjoined_rows_in_excluded_paths=MappingProxyType(dict(unjoined_status)),
        excluded_joined_participating_primitives=MappingProxyType(dict(excluded_participating)),
        excluded_path_keys=frozenset(excluded_keys),
    )


# -------------------------------------------------------------------- plans
@dataclass(frozen=True)
class _Field:
    name: str
    fixed_values: Optional[tuple[str, ...]] = None
    fill_present_only: bool = False


@dataclass(frozen=True)
class _Plan:
    name: str
    ref_class: str
    band: Callable[[int], str]
    bands: tuple[str, ...]
    band_key: str
    with_fill: bool
    fields: tuple[_Field, ...]
    sensitivity: bool = False
    by_page: bool = True

    def __post_init__(self) -> None:
        if any(f.fill_present_only for f in self.fields) and not self.with_fill:
            raise ValueError("a fill-present-only field needs fill presence as a stratifier")

    def stratum(self, record: PathRecord) -> Stratum:
        band = self.band(record.visible_primitives)
        page = record.page_id if self.by_page else POOLED_PAGES
        if self.with_fill:
            return (page, band, record.states[FILL_PRESENCE])
        return (page, band)

    def sort_key(self, stratum: Stratum) -> tuple[Any, ...]:
        fill = (FILL_PRESENT, FILL_ABSENT).index(stratum[2]) if self.with_fill else 0
        return (_page_key(stratum[0]), self.bands.index(stratum[1]), fill)

    def describe(self, stratum: Stratum) -> dict[str, str]:
        out = {self.band_key: stratum[1]}
        if self.by_page:
            out["page_id"] = stratum[0]
        if self.with_fill:
            out["fill"] = stratum[2]
        return out


PLANS: tuple[_Plan, ...] = (
    # Fill presence is the outcome, so it is not a stratifier here.
    _Plan(
        name="lines_fill_presence",
        ref_class="native_line",
        band=line_band,
        bands=LINE_BANDS,
        band_key="visible_segments_band",
        with_fill=False,
        fields=(_Field(FILL_PRESENCE, fixed_values=(FILL_PRESENT,)),),
    ),
    _Plan(
        name="lines_conditioned_on_fill",
        ref_class="native_line",
        band=line_band,
        bands=LINE_BANDS,
        band_key="visible_segments_band",
        with_fill=True,
        fields=(
            _Field("stroke_state"),
            _Field("width_state"),
            _Field("layer_state"),
            _Field("dash_state"),
            _Field("fill_state", fill_present_only=True),
        ),
    ),
    _Plan(
        name="lines_fill_presence_fine_bands",
        ref_class="native_line",
        band=line_fine_band,
        bands=LINE_FINE_BANDS,
        band_key="visible_segments_band",
        with_fill=False,
        fields=(_Field(FILL_PRESENCE, fixed_values=(FILL_PRESENT,)),),
        sensitivity=True,
    ),
    _Plan(
        name="lines_conditioned_on_fill_fine_bands",
        ref_class="native_line",
        band=line_fine_band,
        bands=LINE_FINE_BANDS,
        band_key="visible_segments_band",
        with_fill=True,
        fields=(
            _Field("stroke_state"),
            _Field("width_state"),
            _Field("layer_state"),
            _Field("dash_state"),
            _Field("fill_state", fill_present_only=True),
        ),
        sensitivity=True,
    ),
    # Page-pooled sensitivity: page thins the strata, so a multi-page source can have no
    # stratum that reaches the floor; pooling pages keeps an estimate, at the price of
    # leaving any page-to-page difference in graphic state uncontrolled.
    _Plan(
        name="lines_fill_presence_page_pooled",
        ref_class="native_line",
        band=line_band,
        bands=LINE_BANDS,
        band_key="visible_segments_band",
        with_fill=False,
        fields=(_Field(FILL_PRESENCE, fixed_values=(FILL_PRESENT,)),),
        sensitivity=True,
        by_page=False,
    ),
    _Plan(
        name="lines_conditioned_on_fill_page_pooled",
        ref_class="native_line",
        band=line_band,
        bands=LINE_BANDS,
        band_key="visible_segments_band",
        with_fill=True,
        fields=(
            _Field("stroke_state"),
            _Field("width_state"),
            _Field("layer_state"),
            _Field("dash_state"),
            _Field("fill_state", fill_present_only=True),
        ),
        sensitivity=True,
        by_page=False,
    ),
    # Fill colour is descriptive only; nothing about it is a rule.
    _Plan(
        name="rect_edges_by_visible_edge_band",
        ref_class="native_rect_edge",
        band=rect_band,
        bands=RECT_BANDS,
        band_key="visible_edges_band",
        with_fill=False,
        fields=(_Field("fill_state"), _Field("paint_presence")),
    ),
    _Plan(
        name="rect_edges_by_visible_edge_count_fine",
        ref_class="native_rect_edge",
        band=rect_fine_band,
        bands=RECT_FINE_BANDS,
        band_key="visible_edges_band",
        with_fill=False,
        fields=(_Field("fill_state"), _Field("paint_presence")),
        sensitivity=True,
    ),
    _Plan(
        name="rect_edges_page_pooled",
        ref_class="native_rect_edge",
        band=rect_band,
        bands=RECT_BANDS,
        band_key="visible_edges_band",
        with_fill=False,
        fields=(_Field("fill_state"), _Field("paint_presence")),
        sensitivity=True,
        by_page=False,
    ),
)


# --------------------------------------------------------------- statistics
def _r(value: Fraction) -> float:
    """Round the exact rational once (half to even) and never print a negative zero."""
    rounded = float(round(value, 6))
    return 0.0 if rounded == 0 else rounded


def _ratio(numerator: int, denominator: int) -> Any:
    if denominator < RATIO_MIN_UNIQUE_PATHS:
        return RATIO_SUPPRESSED_LOW_N
    return _r(Fraction(numerator, denominator))


def _pair(labels: tuple[str, str], ka: int, na: int, kb: int, nb: int) -> dict[str, Any]:
    la, lb = labels
    difference: Any = RATIO_SUPPRESSED_LOW_N
    if na >= RATIO_MIN_UNIQUE_PATHS and nb >= RATIO_MIN_UNIQUE_PATHS:
        difference = _r(Fraction(ka, na) - Fraction(kb, nb))
    return {
        f"paths_{la}": na,
        f"k_{la}": ka,
        f"paths_{lb}": nb,
        f"k_{lb}": kb,
        f"share_{la}": _ratio(ka, na),
        f"share_{lb}": _ratio(kb, nb),
        "difference": difference,
    }


def _sign(value: Fraction) -> int:
    return (value > 0) - (value < 0)


def _compare_to_adjusted(
    reference: Optional[Fraction], adjusted: Optional[Fraction]
) -> tuple[Optional[float], str]:
    """Standardised difference as a fraction of a reference difference, and the sign relation."""
    if reference is None or adjusted is None:
        return None, "not_estimable"
    before, after = _sign(reference), _sign(adjusted)
    if before == 0 and after == 0:
        relation = "both_zero"
    elif before == 0:
        relation = "reference_zero"
    elif after == 0:
        relation = "adjusted_zero"
    else:
        relation = "same_sign" if before == after else "opposite_sign"
    return (_r(adjusted / reference) if reference != 0 else None), relation


def _summarise(
    strata: Sequence[Stratum],
    n: Mapping[tuple[Stratum, int], int],
    k: Mapping[tuple[Stratum, int], int],
    labels: tuple[str, str],
    index_of: Optional[Mapping[Stratum, int]] = None,
) -> dict[str, Any]:
    """Crude, eligible-only and directly standardised comparison of one outcome.

    ``n``/``k`` map (stratum, side) to unique-path counts (side 0 is the first
    group, side 1 the second).  Standardisation is to the first group's mix over
    strata where both groups reach the floor.
    """
    la, lb = labels
    na = {s: n.get((s, 0), 0) for s in strata}
    nb = {s: n.get((s, 1), 0) for s in strata}
    ka = {s: k.get((s, 0), 0) for s in strata}
    kb = {s: k.get((s, 1), 0) for s in strata}
    total_a, total_b = sum(na.values()), sum(nb.values())
    eligible = [
        s for s in strata if na[s] >= RATIO_MIN_UNIQUE_PATHS and nb[s] >= RATIO_MIN_UNIQUE_PATHS
    ]
    crude = _pair(labels, sum(ka.values()), total_a, sum(kb.values()), total_b)
    elig_a = sum(na[s] for s in eligible)
    elig_b = sum(nb[s] for s in eligible)
    restricted = _pair(
        labels,
        sum(ka[s] for s in eligible),
        elig_a,
        sum(kb[s] for s in eligible),
        elig_b,
    )
    per_stratum = {s: Fraction(ka[s], na[s]) - Fraction(kb[s], nb[s]) for s in eligible}
    positive = sum(1 for d in per_stratum.values() if d > 0)
    negative = sum(1 for d in per_stratum.values() if d < 0)
    zero = len(per_stratum) - positive - negative
    signed = positive + negative
    concordance: dict[str, Any] = {
        "eligible_strata": len(eligible),
        "positive": positive,
        "negative": negative,
        "zero": zero,
        f"{la}_paths_in_positive_strata": sum(na[s] for s, d in per_stratum.items() if d > 0),
        f"{la}_paths_in_negative_strata": sum(na[s] for s, d in per_stratum.items() if d < 0),
        f"{la}_paths_in_zero_strata": sum(na[s] for s, d in per_stratum.items() if d == 0),
        "dominant_sign_share": _r(Fraction(max(positive, negative), signed)) if signed else None,
        "dominant_sign_share_denominator": signed,
    }
    if eligible:
        share_a = Fraction(sum(ka[s] for s in eligible), elig_a)
        share_b = sum(
            Fraction(na[s], elig_a) * Fraction(kb[s], nb[s]) for s in eligible
        )
        adjusted_diff: Optional[Fraction] = share_a - share_b
        standardised: dict[str, Any] = {
            "state": "ok",
            f"share_{la}": _r(share_a),
            f"share_{lb}_standardised": _r(share_b),
            "difference": _r(adjusted_diff),
        }
    else:
        adjusted_diff = None
        standardised = {
            "state": "no_eligible_strata",
            f"share_{la}": None,
            f"share_{lb}_standardised": None,
            "difference": None,
        }
    coverage = {
        f"paths_{la}_in_eligible_strata": elig_a,
        f"paths_{la}_total": total_a,
        f"share_{la}": _ratio(elig_a, total_a),
        f"paths_{lb}_in_eligible_strata": elig_b,
        f"paths_{lb}_total": total_b,
        f"share_{lb}": _ratio(elig_b, total_b),
    }
    crude_diff: Optional[Fraction] = None
    if total_a >= RATIO_MIN_UNIQUE_PATHS and total_b >= RATIO_MIN_UNIQUE_PATHS:
        crude_diff = Fraction(sum(ka.values()), total_a) - Fraction(sum(kb.values()), total_b)
    eligible_diff: Optional[Fraction] = None
    if eligible:
        eligible_diff = Fraction(sum(ka[s] for s in eligible), elig_a) - Fraction(
            sum(kb[s] for s in eligible), elig_b
        )
    retained_vs_eligible, relation_vs_eligible = _compare_to_adjusted(eligible_diff, adjusted_diff)
    retained_vs_crude, relation_vs_crude = _compare_to_adjusted(crude_diff, adjusted_diff)
    out: dict[str, Any] = {
        "crude": crude,
        "eligible_strata_only": restricted,
        "standardised": standardised,
        "coverage": coverage,
        "sign_concordance": concordance,
        # standardised difference relative to the eligible-strata-only difference (isolates the
        # effect of standardising) and relative to the crude difference (adds the effect of
        # dropping ineligible strata); unbounded ratios, null when the denominator is zero
        "retained_fraction_vs_eligible_only": retained_vs_eligible,
        "sign_relation_vs_eligible_only": relation_vs_eligible,
        "retained_fraction_vs_crude": retained_vs_crude,
        "sign_relation_vs_crude": relation_vs_crude,
    }
    if index_of is not None:
        out["strata_rows"] = [
            [
                index_of[s],
                ka[s],
                kb[s],
                _r(per_stratum[s]) if s in per_stratum else None,
            ]
            for s in strata
        ]
    return out


def _shown_values(field: _Field, records: Iterable[PathRecord]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Outcome values to analyse, chosen from the whole class so they never depend on the split.

    Also returns the values folded into ``other_values`` (most common first).
    """
    if field.fixed_values is not None:
        return field.fixed_values, ()
    counts = Counter(record.states[field.name] for record in records)
    if OTHER_VALUES in counts:
        raise ValueError(f"{OTHER_VALUES!r} is reserved for folded values")
    reserved = [ABSENT] if ABSENT in counts else []
    rest = sorted((v for v in counts if v != ABSENT), key=lambda v: (-counts[v], v))
    cut = MAX_VALUES - len(reserved)
    return tuple(reserved + rest[:cut]), tuple(rest[cut:])


def _folded_value_counts(
    folded: Sequence[str], groups: Sequence[Sequence[PathRecord]], field_name: str
) -> list[dict[str, Any]]:
    if not folded:
        return []
    wanted = set(folded)
    counts = [Counter(r.states[field_name] for r in group if r.states[field_name] in wanted) for group in groups]
    rows = [
        {"value": value, "paths_participating": counts[0][value], "paths_baseline": counts[1][value]}
        for value in folded
    ]
    rows.sort(key=lambda row: (-row["paths_participating"], -row["paths_baseline"], row["value"]))
    return rows


def _tally(
    plan: _Plan,
    groups: Sequence[Sequence[PathRecord]],
    shown: Mapping[str, tuple[frozenset[str], int]],
) -> tuple[Counter, dict[tuple[str, str], Counter]]:
    """Unique-path counts per (stratum, side), and per outcome (field, value).

    Outcome counts are recorded for every stratum; a field that only applies to
    fill-present strata is read through that strata filter in ``_run_plan``.
    """
    n: Counter = Counter()
    k: dict[tuple[str, str], Counter] = {}
    for side, records in enumerate(groups):
        for record in records:
            stratum = plan.stratum(record)
            n[(stratum, side)] += 1
            for field in plan.fields:
                value = record.states[field.name]
                if field.fixed_values is None and value not in shown[field.name][0]:
                    value = OTHER_VALUES
                k.setdefault((field.name, value), Counter())[(stratum, side)] += 1
    return n, k


def _run_plan(
    plan: _Plan,
    participating: Sequence[PathRecord],
    baseline: Sequence[PathRecord],
    source_sha256: str,
) -> dict[str, Any]:
    labels = ("participating", "baseline")
    everything = [*participating, *baseline]
    strata_all = sorted({plan.stratum(r) for r in everything}, key=plan.sort_key)
    index_of = {stratum: i for i, stratum in enumerate(strata_all)}
    shown: dict[str, tuple[frozenset[str], int]] = {}
    outcome_values: dict[str, list[str]] = {}
    folded_values: dict[str, tuple[str, ...]] = {}
    for field in plan.fields:
        pool = [
            r
            for r in everything
            if not (field.fill_present_only and r.states[FILL_PRESENCE] != FILL_PRESENT)
        ]
        values, folded = _shown_values(field, pool)
        shown[field.name] = (frozenset(values), len(folded))
        folded_values[field.name] = folded
        outcome_values[field.name] = [*values, *([OTHER_VALUES] if folded else [])]

    n, k = _tally(plan, (participating, baseline), shown)
    null_runs = []
    for salt in NULL_SPLIT_SALTS:
        halves: tuple[list[PathRecord], list[PathRecord]] = ([], [])
        for record in baseline:
            half = null_half(source_sha256, record.page_id, record.path_index, record.ref_class, salt)
            halves[half].append(record)
        null_n, null_k = _tally(plan, halves, shown)
        null_runs.append((salt, halves, null_n, null_k))

    eligible_flags = {
        s: n.get((s, 0), 0) >= RATIO_MIN_UNIQUE_PATHS and n.get((s, 1), 0) >= RATIO_MIN_UNIQUE_PATHS
        for s in strata_all
    }
    total_p, total_b = len(participating), len(baseline)
    p_in = sum(n.get((s, 0), 0) for s, ok in eligible_flags.items() if ok)
    b_in = sum(n.get((s, 1), 0) for s, ok in eligible_flags.items() if ok)
    fields_out: dict[str, Any] = {}
    for field in plan.fields:
        applicable = [
            s for s in strata_all if not (field.fill_present_only and s[2] != FILL_PRESENT)
        ]
        outcomes: dict[str, Any] = {}
        for value in outcome_values[field.name]:
            entry = _summarise(
                applicable, n, k.get((field.name, value), Counter()), labels, index_of
            )
            splits: dict[str, list[Any]] = {
                "difference_crude": [],
                "difference_adjusted": [],
                "eligible_strata": [],
                "coverage_share_half_a": [],
            }
            for _, _, null_n, null_k in null_runs:
                null = _summarise(
                    applicable,
                    null_n,
                    null_k.get((field.name, value), Counter()),
                    ("half_a", "half_b"),
                )
                splits["difference_crude"].append(null["crude"]["difference"])
                splits["difference_adjusted"].append(null["standardised"]["difference"])
                splits["eligible_strata"].append(null["sign_concordance"]["eligible_strata"])
                splits["coverage_share_half_a"].append(null["coverage"]["share_half_a"])
            entry["null_control"] = splits
            outcomes[value] = entry
        listed = _folded_value_counts(
            folded_values[field.name],
            (participating, baseline),
            field.name,
        )
        fields_out[field.name] = {
            "fill_present_strata_only": field.fill_present_only,
            "values_analysed": outcome_values[field.name],
            "distinct_values_folded_into_other": shown[field.name][1],
            # the folded values themselves, participating-heavy first, so a rare value that
            # only participating paths use is visible even though it has no outcome of its own
            "folded_values": listed[:MAX_FOLDED_LISTED],
            "folded_values_omitted": max(0, len(listed) - MAX_FOLDED_LISTED),
            "outcomes": outcomes,
        }
    return {
        "plan": plan.name,
        "sensitivity_only": plan.sensitivity,
        "stratifiers": [
            *(["page_id"] if plan.by_page else []),
            plan.band_key,
            *(["fill"] if plan.with_fill else []),
        ],
        "band_scheme": list(plan.bands),
        "strata": {
            "total": len(strata_all),
            "eligible": sum(eligible_flags.values()),
            "participating_paths_total": total_p,
            "participating_paths_in_eligible_strata": p_in,
            "participating_coverage": _ratio(p_in, total_p),
            "baseline_paths_total": total_b,
            "baseline_paths_in_eligible_strata": b_in,
            "baseline_coverage": _ratio(b_in, total_b),
            "columns": ["index", "stratum", "paths_participating", "paths_baseline", "eligible"],
            "table": [
                [
                    index_of[s],
                    plan.describe(s),
                    n.get((s, 0), 0),
                    n.get((s, 1), 0),
                    eligible_flags[s],
                ]
                for s in strata_all
            ],
        },
        "fields": fields_out,
        "null_control": {
            "design": "hash split of the baseline paths; ignores participation; calibration only",
            "salts": list(NULL_SPLIT_SALTS),
            "halves": [
                {"salt": salt, "paths_half_a": len(halves[0]), "paths_half_b": len(halves[1])}
                for salt, halves, _, _ in null_runs
            ],
        },
        "strata_row_columns": ["index", "k_participating", "k_baseline", "difference"],
    }


def analyse_paths(records: Iterable[PathRecord], *, source_sha256: str) -> dict[str, Any]:
    """Pure stratified comparison of path records; never mutates them, order-free."""
    ordered = sorted(records, key=_record_sort_key)
    if len({record.key for record in ordered}) != len(ordered):
        raise ValueError("duplicate page-qualified native path")
    if not isinstance(source_sha256, str) or not source_sha256:
        raise ValueError("source_sha256 is required for the null split")
    out: dict[str, Any] = {}
    for klass in CLASSES:
        native = [r for r in ordered if r.ref_class == klass]
        participating = [r for r in native if r.participating]
        baseline = [r for r in native if not r.participating]
        control = [r for r in baseline if r.control_primitives > 0]
        mixed = [r for r in participating if r.participating_primitives < r.visible_primitives]
        plans = {
            plan.name: _run_plan(plan, participating, baseline, source_sha256)
            for plan in PLANS
            if plan.ref_class == klass
        }
        out[klass] = {
            "population": {
                "participating_paths": len(participating),
                "participating_primitives": sum(r.participating_primitives for r in participating),
                "baseline_paths": len(baseline),
                "baseline_group": PRIMARY_BASELINE,
                "mixed_paths": len(mixed),
                "mixed_paths_note": (
                    "participating paths that also hold non-participating primitives; "
                    "they count as participating and are absent from the baseline"
                ),
                "control_paths": len(control),
                "control_description": "counts_only",
                "control_paths_at_or_above_floor": len(control) >= RATIO_MIN_UNIQUE_PATHS,
                "pages_with_participating_paths": len({r.page_id for r in participating}),
            },
            "plans": plans,
        }
    return out


# ------------------------------------------------------------- sealed record
@dataclass(frozen=True)
class StratifiedGraphicStateCheck:
    record_id: str
    payload_json: str
    commercial_authority_granted: bool = False

    def __post_init__(self) -> None:
        if self.commercial_authority_granted is not False:
            raise ValueError("a diagnostic never grants commercial authority")
        payload = json.loads(self.payload_json)
        if payload.get("commercial_authority_granted") is not False:
            raise ValueError("the payload of a diagnostic never grants commercial authority")
        expected = stable_contract_id("native_graphic_state_stratified", payload, digest_chars=32)
        if self.record_id != expected:
            raise ValueError("record_id does not match the check content")

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self.payload_json)
        payload["record_id"] = self.record_id
        return payload


def _seal(payload: dict[str, Any]) -> StratifiedGraphicStateCheck:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload = json.loads(canonical)
    return StratifiedGraphicStateCheck(
        record_id=stable_contract_id("native_graphic_state_stratified", payload, digest_chars=32),
        payload_json=canonical,
    )


def _header(bundle: NativeJoinRows, status: str) -> dict[str, Any]:
    record, published = bundle.record, bundle.published
    return {
        "schema_version": STRATIFIED_SCHEMA_VERSION,
        "join_schema_version": JOIN_SCHEMA_VERSION,
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
            "supplied_bytes_sha256": bundle.computed_sha,
            "snapshot_id": record.snapshot_id,
            "semantic_record_id": record.record_id,
            "producer_method": None if published is None else published.revision.producer_method,
            "producer_version": None if published is None else published.revision.producer_version,
            "pymupdf_version": fitz.VersionBind,
            "extractor": "pb_vector_geometry_v130.extract_native_page",
        },
        "semantic_status": str(bundle.semantic_result.status.value),
        "commercial_authority_granted": False,
    }


def _definitions() -> dict[str, Any]:
    return {
        "unit_of_analysis": "unique page-qualified native path, per primitive class",
        "classes_pooled": False,
        "participating": "path holding at least one participating member primitive",
        "baseline": PRIMARY_BASELINE + " (path level; participating paths removed whole)",
        "control": "baseline paths holding a non-participating candidate member (descriptive only)",
        "difference_sign": "participating minus baseline",
        "floor": {
            "unique_paths": RATIO_MIN_UNIQUE_PATHS,
            "state": RATIO_SUPPRESSED_LOW_N,
            "applies_to": "every share and difference, per group and per stratum",
            "is_a_production_threshold": False,
            "meaning": (
                "group-size reporting guard; not a significance level and not evidence "
                "that a group is large enough to support a conclusion"
            ),
        },
        "standardisation": (
            "direct, to the participating stratum mix, over strata where both groups "
            "reach the floor; standardised participating share equals its eligible-strata share"
        ),
        "null_control": (
            "hash split of baseline paths; calibration reference, not a significance test; "
            "each half is usually much larger than the participating group and has its own "
            "eligible strata, so its spread understates the sampling noise of the observed comparison"
        ),
        "value_cap": MAX_VALUES,
        "reading_notes": [
            "a participating path holds at least one participating primitive; a long path may "
            "hold many primitives of which few participate (see mixed_paths)",
            "size bands are open-ended at the top; the *_fine_bands and fine-count plans are "
            "sensitivity checks on that resolution",
            "the null control is a calibration reference, not a significance test, and its "
            "halves are usually larger than the participating group",
            "retained_fraction_* are unbounded ratios of the standardised difference to a "
            "reference difference; they are null when that reference is zero",
            "differences are rounded to 6 places for output; sign_concordance and sign_relation_* "
            "use the exact sign, so a tiny difference can print 0.0 yet count as positive",
            "coverage can be 0 for a multi-page source (page thins the strata below the floor); "
            "the page-pooled plans are sensitivity checks that keep an estimate and leave "
            "page-to-page differences uncontrolled",
            "dominant_sign_share is only meaningful with a denominator above a few strata",
            "a field with one value in both groups (e.g. every layer absent) has a difference of "
            "0.0 that carries no information; check values_analysed",
            "folded_values lists the values that have no outcome of their own, participating-heavy first",
        ],
        "conclusion_limit": (
            "residual association between graphic state and candidate participation after "
            "conditioning on path structure; never that a candidate is false or real"
        ),
    }


def participating_accounting(bundle: NativeJoinRows, population: PathPopulation) -> dict[str, Any]:
    """Where every distinct participating primitive went; nothing may be dropped silently.

    A participating primitive is analysed (it sits in an analysed native path), or it is
    counted as one of: no join row, not a native class (raster / unresolved), outside the
    candidate pages, or in an excluded path (joined or itself unjoined).
    """
    rows = bundle.rows
    counts: dict[str, Counter] = {
        name: Counter()
        for name in (
            "analysed",
            "in_excluded_paths_joined",
            "in_excluded_paths_unjoined",
            "native_outside_candidate_pages",
            "not_native_class",
        )
    }
    without_row = 0
    for oid in sorted(bundle.participating_weight):
        row = rows.get(oid)
        if row is None:
            without_row += 1
        elif row.ref_class not in CLASSES:
            counts["not_native_class"][row.ref_class] += 1
        elif row.page_id not in bundle.candidate_pages or row.path_index is None:
            counts["native_outside_candidate_pages"][row.ref_class] += 1
        elif (str(row.page_id), row.path_index, row.ref_class) in population.excluded_path_keys:
            counts["in_excluded_paths_joined" if row.joined else "in_excluded_paths_unjoined"][
                row.ref_class
            ] += 1
        else:
            counts["analysed"][row.ref_class] += 1
    out: dict[str, Any] = {
        "distinct_participating_primitives": len(bundle.participating_weight),
        "without_join_row": without_row,
        **{name: dict(sorted(counter.items())) for name, counter in counts.items()},
    }
    out["fully_accounted"] = (
        without_row + sum(sum(counter.values()) for counter in counts.values())
        == len(bundle.participating_weight)
    )
    return out


def build_stratified_graphic_state_check(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    semantic_result: SemanticOpeningEnumerationResult,
    source_bytes: bytes,
    reference_structure: Optional[CandidateStructureSummary] = None,
) -> StratifiedGraphicStateCheck:
    """Structure-adjusted graphic-state comparison of one semantic scope.

    Read-only.  ``source_bytes`` must hash to the source SHA-256 bound to the
    scope, otherwise nothing is extracted or analysed.  ``reference_structure`` is
    the optional independent #1059 candidate-structure summary, used only to cross
    check the candidate count.
    """
    if reference_structure is not None and not isinstance(
        reference_structure, CandidateStructureSummary
    ):
        raise TypeError("reference_structure must be a CandidateStructureSummary")
    bundle = build_native_graphic_state_join_rows(
        source_visibility_producer=source_visibility_producer,
        semantic_result=semantic_result,
        source_bytes=source_bytes,
    )
    if bundle.status == SCOPE_STATUS_ABSENT:
        payload = _header(bundle, SCOPE_STATUS_ABSENT)
        payload["semantic_reason_codes"] = sorted(
            str(c) for c in semantic_result.reason_codes
        )
        return _seal(payload)
    if bundle.status == SCOPE_STATUS_SHA_MISMATCH:
        return _seal(_header(bundle, SCOPE_STATUS_SHA_MISMATCH))

    population = build_path_records(bundle)
    record = bundle.record
    analysis = analyse_paths(population.records, source_sha256=record.source_sha256)
    status_counts = Counter(row.status for row in bundle.rows.values())
    participating = bundle.populations[G_PARTICIPATING]
    incidences = {
        klass: sum(
            weight for oid, weight in participating.items() if bundle.rows[oid].ref_class == klass
        )
        for klass in CLASSES
    }
    primitives_in_records = {
        klass: sum(r.participating_primitives for r in population.records if r.ref_class == klass)
        for klass in CLASSES
    }
    joined_participating = {
        klass: sum(
            1
            for oid in participating
            if bundle.rows[oid].ref_class == klass and bundle.rows[oid].joined
        )
        for klass in CLASSES
    }
    nothing_excluded = not population.excluded_paths
    accounting = participating_accounting(bundle, population)
    checks: dict[str, bool] = {
        "every_candidate_member_has_a_row": not bundle.missing_rows,
        "no_unavailable_candidate_pages": not bundle.unavailable_pages,
        "no_path_excluded_for_an_unjoined_row": nothing_excluded,
        # every joined participating primitive is in an analysed path or a counted excluded one
        "participating_primitives_match_join_rows": all(
            primitives_in_records[k] + population.excluded_joined_participating_primitives.get(k, 0)
            == joined_participating[k]
            for k in CLASSES
        ),
        "participating_members_fully_accounted": accounting["fully_accounted"]
        and all(
            accounting["analysed"].get(k, 0) == primitives_in_records[k] for k in CLASSES
        ),
        "every_record_is_in_exactly_one_group": all(
            analysis[k]["population"]["participating_paths"]
            + analysis[k]["population"]["baseline_paths"]
            == sum(1 for r in population.records if r.ref_class == k)
            for k in CLASSES
        ),
    }
    if reference_structure is not None:
        checks["candidate_total_matches_structure_reference"] = (
            reference_structure.candidates_total == bundle.candidates_total
        )
    checks["all_checks_passed"] = all(checks.values())
    if bundle.unavailable_pages:
        analysis_state = "incomplete_unavailable_candidate_pages"
    elif bundle.missing_rows:
        analysis_state = "incomplete_candidate_members_without_row"
    elif not nothing_excluded:
        analysis_state = "incomplete_paths_excluded"
    elif not bundle.candidate_pages:
        analysis_state = "no_candidate_pages"
    else:
        analysis_state = "complete"
    payload = _header(bundle, SCOPE_STATUS_OK)
    payload.update(
        {
            "definitions": _definitions(),
            "integrity": {
                "rows_digest": digest_of_rows(bundle.rows),
                "rows_total": len(bundle.rows),
                "join_status_counts": {
                    s: status_counts[s] for s in JOIN_STATUSES if status_counts[s]
                },
                "candidate_pages": sorted(bundle.candidate_pages, key=_page_key),
                "candidates_total": bundle.candidates_total,
                "participating_candidates": bundle.participating_candidates,
                "replay": {
                    "pages_replayed": bundle.pages_replayed,
                    "pages_unavailable": list(bundle.pages_unavailable),
                    "duplicate_replay_identities": bundle.duplicate_replay_identities,
                },
                "unavailable_pages": [
                    {**entry, "reason_codes": list(entry["reason_codes"])}
                    for entry in bundle.unavailable_pages
                ],
                "participating_incidences_native": incidences,
                "participating_primitives_native": joined_participating,
                "analysis_state": analysis_state,
                "analysis_complete": analysis_state == "complete",
                "structure_reference": "supplied" if reference_structure is not None else "not_supplied",
                "participating_members_accounting": accounting,
                "excluded_paths": dict(population.excluded_paths),
                "unjoined_rows_in_excluded_paths": dict(population.unjoined_rows_in_excluded_paths),
                "excluded_joined_participating_primitives": dict(
                    population.excluded_joined_participating_primitives
                ),
                "checks": checks,
            },
            "classes": analysis,
        }
    )
    return _seal(payload)


def collect_stratified_graphic_state_check(
    pdf_path: Path | str,
    *,
    document_id: str,
    pages: Optional[Sequence[int]] = None,
    source_bytes: Optional[bytes] = None,
    with_reference: bool = True,
) -> StratifiedGraphicStateCheck:
    """Publish the Item 35 semantic scope from ``source_bytes`` and run the check.

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
    return build_stratified_graphic_state_check(
        source_visibility_producer=source,
        semantic_result=result,
        source_bytes=source_bytes,
        reference_structure=reference,
    )
