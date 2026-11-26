"""Read-only ring-leak census: why wall rings do not close, for the canonical preview's ring builder and the layered builder.

Counts, lengths and offsets only. No words, coordinates, room names, quantities or benchmark values are printed or written, so the output is
safe to quote publicly for a private source (the source is identified by a 16 character hash prefix only). Keep ``--json-out`` outside the
repository; the tool refuses a path inside it.

For each requested page it runs the real builder under throwaway spies on that builder's private functions (restored whatever happens),
rebuilds what the builder did from what the spies saw, and asks ``pb_ring_leak_census.census_report`` for the census: the ink class and
length bucket of every unclosed raw gap, which gaps touch a ring, how many rings closing a chosen set of gaps would add, which raw gaps are
one aperture seen more than once, and what happened to every native arc swing. Two replication checks (the unresolved collinear count and
the ring count recomputed from the captured barrier must equal the builder's own) guard every ring figure; when they fail the tool says so,
withholds those figures and exits non-zero.

Two builders, two inputs:

* ``preview`` runs the canonical preview (``source_native_trace_preview``) and censuses the fork it calls (``pb_next_wall_ring_preview``).
* ``layered`` censuses ``pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings`` with ``dark_painted_wall_source``,
  the module the room-face scope consumes (``layered_ring_scope_overrides`` reads the page's raw ``get_drawings()`` rows, which is the default
  here). ``--layered-rows preview-scoped`` feeds it the rows the preview scoped instead (needs the preview run).

This module changes no production behaviour and grants no authority. Every figure is a topology diagnostic; nothing here is a wall, an
opening, a closure, a room, a quantity or a score.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import fitz
from shapely.geometry import Polygon, box

import pb_layered_wall_doorway_room_ring_shadow as layered
import pb_next_wall_ring_preview as preview
import pb_ring_leak_census as census
from pb_source_segmented_door_swing_shadow import collect_source_black_segmented_door_swings

NOTE = "counts, lengths and offsets only; no coordinates, words or names; source identified by a hash prefix"
RASTER_ROUTE = "tiled_raster_underlay"
# The flags the canonical preview passes its ring builder, mirrored so a row-level capture reproduces the preview's own run (a test pins them
# against the real call; ``source_words`` and the viewport tiles are inputs, not flags).
CANONICAL_PREVIEW_FLAGS = {
    "sliding_leaf_frame_closure": True,
    "panel_lift_label_closure": True,
    "source_native_cs_jamb_closure": False,
    "source_native_internal_swing_closure": False,
    "stroke_pair_wall_faces": True,
}

# Functions both builder modules call that the spies wrap, with the leading parameter names the capture relies on.
_COMMON_CONTRACT = {
    "_collect_strips": ("drawings",),
    "_gaps": ("strips", "union", "domain"),
    "_swing_arcs": ("drawings",),
    "_place_swings": ("arcs", "gaps"),
    "_closed_union": ("polygons",),
}
_LAYERED_CONTRACT = {
    **_COMMON_CONTRACT,
    "_lining_face_wall_strips": ("drawings", "gaps"),
    "_source_unresolved_gap_witnesses": ("unresolved",),
}
_ACTIVE_FAMILIES: set[str] = set()
_FAMILIES = {
    census.BUILDER_PREVIEW_FORK: {"module": preview, "contract": _COMMON_CONTRACT, "ring_rule": census.PREVIEW_RING_RULE},
    census.BUILDER_LAYERED: {"module": layered, "contract": _LAYERED_CONTRACT, "ring_rule": census.LAYERED_RING_RULE},
}


class CensusContractError(RuntimeError):
    """A builder function the spies depend on is missing or changed its leading parameters: the census would read the wrong thing."""


def check_spy_contract(family: str) -> None:
    spec = _FAMILIES[family]
    module = spec["module"]
    for name, expected in spec["contract"].items():
        fn = getattr(module, name, None)
        if not callable(fn):
            raise CensusContractError(f"{module.__name__}.{name} is missing")
        params = tuple(inspect.signature(fn).parameters)
        if params[: len(expected)] != expected:
            raise CensusContractError(f"{module.__name__}.{name} leading parameters are {params[:len(expected)]}, expected {expected}")
    for attr in ("NOISE_PT", "_polygon_parts"):
        if not hasattr(module, attr):
            raise CensusContractError(f"{module.__name__}.{attr} is missing")
    touch = _touch_function(module)
    if touch is None:
        raise CensusContractError(f"{module.__name__} has no unresolved collinear gap veto")


def _touch_function(module: Any):
    return getattr(module, "_unresolved_collinear_gap_breaches_outer_ring", None) or getattr(module, "_original_two_end_gap_veto", None)


class BuilderSpies:
    """Throwaway spies on one builder module's private functions. Entering installs them, leaving restores every original even when the
    builder raises, and nesting a second instance on the same module is refused. Spies record only while ``building()`` is active, so
    other callers of the same functions (a preview that renders overlays, say) are never mistaken for the builder."""

    def __init__(self, family: str) -> None:
        if family not in _FAMILIES:
            raise ValueError(f"unknown builder family {family!r}")
        self.family = family
        self.module = _FAMILIES[family]["module"]
        self.state: dict[str, Any] = {"union_calls": []}
        self.result: Any = None
        self.kwargs: dict[str, Any] = {}
        self.entry_rows: Any = None
        self._originals: dict[str, Any] = {}
        self._active = False

    def __enter__(self) -> "BuilderSpies":
        check_spy_contract(self.family)
        if self.family in _ACTIVE_FAMILIES:
            raise CensusContractError(f"spies are already installed on {self.module.__name__}")
        wrappers = {
            "_collect_strips": self._spy_collect, "_gaps": self._spy_gaps, "_swing_arcs": self._spy_arcs, "_place_swings": self._spy_place,
            "_closed_union": self._spy_union, "_lining_face_wall_strips": self._spy_lining, "_source_unresolved_gap_witnesses": self._spy_unresolved,
        }
        try:
            for name, wrapper in wrappers.items():
                if name in _FAMILIES[self.family]["contract"]:
                    self._originals[name] = getattr(self.module, name)
                    setattr(self.module, name, wrapper)
            _ACTIVE_FAMILIES.add(self.family)
        except BaseException:
            self._restore()
            raise
        return self

    def __exit__(self, *exc: Any) -> bool:
        self._restore()
        return False

    def _restore(self) -> None:
        for name, original in self._originals.items():
            setattr(self.module, name, original)
        self._originals = {}
        _ACTIVE_FAMILIES.discard(self.family)

    @contextmanager
    def building(self):
        self._active = True
        try:
            yield
        finally:
            self._active = False

    @contextmanager
    def wrap_entry(self, owner: Any, attr: str):
        """Wrap a builder entry point as another module bound it (the preview imports the builder by name): record its first call's rows,
        keyword arguments and result, and mark the spies active for the duration of the call."""
        real = getattr(owner, attr)
        spies = self

        def entry(*args: Any, **kwargs: Any):
            with spies.building():
                result = real(*args, **kwargs)
            if spies.result is None:
                spies.result, spies.kwargs = result, dict(kwargs)
                spies.entry_rows = args[0] if args else kwargs.get("drawings")
            return result

        setattr(owner, attr, entry)
        try:
            yield
        finally:
            setattr(owner, attr, real)

    # -- spies ---------------------------------------------------------------------------------------------------------
    def _spy_collect(self, drawings, *args, **kwargs):
        if self._active and "rows" not in self.state:
            self.state["rows"] = drawings
        return self._originals["_collect_strips"](drawings, *args, **kwargs)

    def _spy_gaps(self, strips, union, domain, *args, **kwargs):
        if self._active and "strips" not in self.state:
            self.state["strips"] = list(strips)
        return self._originals["_gaps"](strips, union, domain, *args, **kwargs)

    def _spy_arcs(self, drawings, *args, **kwargs):
        arcs, rejected = self._originals["_swing_arcs"](drawings, *args, **kwargs)
        if self._active and "swing_rows" not in self.state:
            self.state["swing_rows"], self.state["arcs_rejected"] = drawings, rejected
        return arcs, rejected

    def _spy_place(self, arcs, gaps, *args, **kwargs):
        placed = self._originals["_place_swings"](arcs, gaps, *args, **kwargs)
        if self._active and "gaps_ref" not in self.state:
            self.state["gaps_ref"], self.state["arcs_ref"], self.state["placed_ref"] = gaps, arcs, placed  # references: the builder keeps appending
        return placed

    def _spy_union(self, polygons, *args, **kwargs):
        polygons = list(polygons)
        out = self._originals["_closed_union"](polygons, *args, **kwargs)
        if self._active:
            self.state["union_calls"].append((polygons, out))
        return out

    def _spy_lining(self, drawings, gaps, *args, **kwargs):
        result = self._originals["_lining_face_wall_strips"](drawings, gaps, *args, **kwargs)
        if self._active:
            self.state["face_strips"] = list(result[0])
        return result

    def _spy_unresolved(self, unresolved, *args, **kwargs):
        if self._active:
            self.state["unresolved_ref"] = unresolved
        return self._originals["_source_unresolved_gap_witnesses"](unresolved, *args, **kwargs)

    # -- the capture ---------------------------------------------------------------------------------------------------
    def capture(self, result: Any = None, kwargs: Mapping[str, Any] | None = None) -> census.BuilderCapture | None:
        """The census capture of the builder run, or ``None`` when the builder returned before its closure loop (a page over the structural
        cap, or with no wall ink). Call after the builder returned and with the spies still installed."""
        result = self.result if result is None else result
        kwargs = dict(self.kwargs if kwargs is None else kwargs)
        state = self.state
        if result is None or "gaps_ref" not in state or "rows" not in state or not state["union_calls"]:
            return None
        module, family = self.module, self.family
        original = self._originals  # the real functions, so the census never records itself
        native_gaps = list(state["gaps_ref"])
        gaps = [census.plain_gap(g) for g in native_gaps]
        if family == census.BUILDER_LAYERED:
            unresolved = state.get("unresolved_ref")
            if unresolved is None:
                return None
            unresolved_ids = {id(g) for g in unresolved}
            closed = [id(g) not in unresolved_ids for g in native_gaps]
        else:
            keys = {(c.horizontal, tuple(round(v, 3) for v in c.band), round(c.gap_interval[0], 3), round(c.gap_interval[1], 3)) for c in result.closures}
            closed = [(g.horizontal, tuple(round(v, 3) for v in g.band), round(g.lo, 3), round(g.hi, 3)) in keys for g in native_gaps]

        calls = state["union_calls"]
        barrier_inputs, barrier = calls[-1]
        barrier_ids = [id(p) for p in barrier_inputs]
        union = barrier
        for polygons, out in reversed(calls[:-1]):
            ids = [id(p) for p in polygons]
            if len(ids) <= len(barrier_ids) and barrier_ids[: len(ids)] == ids:
                union = out
                break
        domain = union.envelope.buffer(1.0, join_style=2)
        strips = list(state["strips"]) + list(state.get("face_strips", []))
        thicknesses = sorted(min(s.x1 - s.x0, s.y1 - s.y0) for s in strips)
        median = thicknesses[len(thicknesses) // 2]
        noise = float(module.NOISE_PT)
        closed_union = original.get("_closed_union", module._closed_union)

        if family == census.BUILDER_LAYERED:
            pad = float(module._STROKE_PAIR_THICK_MIN)

            def closure_rect(g: census.PlainGap):
                if g.horizontal:
                    return box(g.lo - pad, g.band[0], g.hi + pad, g.band[1])
                return box(g.band[0], g.lo - pad, g.band[1], g.hi + pad)
        else:
            def closure_rect(g: census.PlainGap):
                return g.rect()

        touch = _touch_function(module)
        rows = state["rows"]
        swing_by_gap = state["placed_ref"][0]
        arcs = list(state["arcs_ref"])
        native_arcs = [a for a in arcs if not a.get("source_segmented_polyline")]
        if family == census.BUILDER_LAYERED:
            witnesses = [a for a in arcs if a.get("source_segmented_polyline")]
            candidates = lambda arc: tuple(module._gaps_containing_swing(arc, native_gaps))  # noqa: E731
        else:
            witnesses = [
                {"centre": w["source_hinge_point_pdf_pts"], "closed_tip": w["source_closed_leaf_tip_pdf_pts"]}
                for w in collect_source_black_segmented_door_swings(state["swing_rows"])
            ]
            candidates = lambda arc: tuple(i for i, g in enumerate(gaps) if census.arc_in_gap(arc, g))  # noqa: E731
        arc_info = census.ArcInfo(
            found=len(native_arcs), rejected_by_finder=int(state.get("arcs_rejected", 0)),
            builder_unplaced=int(result.unplaced_swing_count), builder_ambiguous=int(result.ambiguous_swing_count),
            candidate_gap_indices=tuple(candidates(a) for a in native_arcs),
        )
        return census.BuilderCapture(
            builder=family, status=result.status.value, reason_codes=tuple(result.reason_codes), rows=rows, gaps=tuple(gaps), closed=tuple(closed),
            barrier=barrier, domain=domain, median_thickness=float(median), ring_rule=_FAMILIES[family]["ring_rule"], noise_pt=noise,
            closure_rect=closure_rect, closed_union=closed_union, polygon_parts=module._polygon_parts,
            ring_touch=lambda polygon, i: bool(touch(polygon, native_gaps[i])),
            builder_strip_count=int(result.wall_strip_count), builder_gap_count=int(result.wall_gap_count),
            builder_closure_count=len(result.closures), builder_unresolved_collinear=int(result.unresolved_gap_count),
            builder_rings=tuple(census.BuilderRing(r.status.value, tuple(r.reason_codes), Polygon(r.polygon_pdf_pts)) for r in result.rings),
            owner_evidence=self._owner_evidence(rows, native_gaps, swing_by_gap, kwargs),
            native_arcs=tuple(native_arcs), door_witnesses=tuple(witnesses), arc_info=arc_info, barrier_inputs=tuple(barrier_inputs),
        )

    def _owner_evidence(self, rows: Any, native_gaps: Sequence[Any], swing_by_gap: Mapping[int, Any], kwargs: Mapping[str, Any]):
        """For one unclosed gap, which of the builder's own closure evidence functions fire (so ``competing_owners`` is two or more)."""
        module = self.module
        if self.family == census.BUILDER_LAYERED:
            dark = bool(kwargs.get("dark_painted_wall_source", False))
            sliding_on = bool(kwargs.get("sliding_leaf_frame_closure", False))

            def evidence(i: int) -> tuple[str, ...]:
                gap = native_gaps[i]
                owners = []
                swing = swing_by_gap.get(i)
                if swing is not None:
                    owners.append("swing")
                host_wall = (gap.band[1] - gap.band[0]) >= module._STROKE_PAIR_THICK_MIN
                stroke = None
                if swing is None and host_wall:
                    stroke = module._stroke_closed(rows, gap, all_ink=dark)
                if stroke is None and swing is None and host_wall and dark:
                    stroke = module._jamb_cap_closed(rows, gap, all_ink=True)
                if stroke is None and swing is None and host_wall and dark and not sliding_on:
                    stroke = module._frame_pair_closed(rows, gap)
                if stroke is not None:
                    owners.append("stroke_or_jamb")
                if sliding_on and module._sliding_leaf_evidence(rows, gap) is not None:
                    owners.append("sliding")
                return tuple(owners)

            return evidence
        all_ink = bool(kwargs.get("stroke_pair_wall_faces", False))
        sliding_on = bool(kwargs.get("sliding_leaf_frame_closure", False))
        panel_on = bool(kwargs.get("panel_lift_label_closure", False))
        words = kwargs.get("source_words", ()) or ()

        def evidence_preview(i: int) -> tuple[str, ...]:
            gap = native_gaps[i]
            owners = []
            swing = swing_by_gap.get(i)
            if swing is not None:
                owners.append("swing")
            stroke = None if swing is not None else module._stroke_closed(rows, gap, all_ink=all_ink)
            if stroke is None and swing is None and all_ink:
                stroke = module._jamb_cap_closed(rows, gap, all_ink=True)
            if stroke is not None:
                owners.append("stroke_or_jamb")
            if sliding_on:
                if module._sliding_leaf_evidence(rows, gap) is not None:
                    owners.append("sliding")
                cs_words = module._cavity_slider_word_evidence(gap, words)
                leaves = module._paired_cavity_leaves(rows, gap) or module._pocket_cavity_leaves(rows, gap)
                if cs_words is not None and leaves is not None:
                    owners.append("cavity")
            if panel_on and module._panel_lift_word_evidence(gap, words) is not None:
                owners.append("panel")
            return tuple(owners)

        return evidence_preview


# ------------------------------------------------------------------------------------------------ capturing the two builders

def capture_preview_builder(pdf: Path | str, page_index: int) -> tuple[census.BuilderCapture | None, Mapping[str, Any], Any]:
    """Run the canonical preview on one page under spies on the fork it calls. Returns the census capture (``None`` if the fork returned
    before its closure loop), the preview's own summary, and the rows the preview handed its builder."""
    import pb_new_source_trace_preview as canonical  # heavy (OCR stack): only the preview path needs it

    with BuilderSpies(census.BUILDER_PREVIEW_FORK) as spies:
        with spies.wrap_entry(canonical, "build_layered_wall_doorway_room_rings"):
            summary, _png = canonical.source_native_trace_preview(pdf, page_index)
        capture = spies.capture()
        entry_rows = spies.entry_rows
    return capture, summary, entry_rows


def capture_preview_builder_rows(
    rows: Sequence[Any], *, source_sha256: str, page_index: int, **builder_kwargs: Any,
) -> tuple[census.BuilderCapture | None, Any]:
    """Run the preview's ring builder directly on ``rows`` with the canonical preview's flags (``builder_kwargs`` override them), under
    spies. Returns the census capture (``None`` if the builder returned before its closure loop) and the builder's own result."""
    kwargs = {**CANONICAL_PREVIEW_FLAGS, **builder_kwargs}
    with BuilderSpies(census.BUILDER_PREVIEW_FORK) as spies:
        with spies.building():
            result = preview.build_layered_wall_doorway_room_rings(rows, source_sha256=source_sha256, page_index=page_index, **kwargs)
        capture = spies.capture(result=result, kwargs=kwargs)
    return capture, result


def capture_layered_builder(
    rows: Sequence[Any], *, source_sha256: str, page_index: int, sliding_leaf_frame_closure: bool = False,
    dark_painted_wall_source: bool = True, wall_end_stroke_closures: bool = False,
) -> tuple[census.BuilderCapture | None, Any]:
    """Run the layered builder on ``rows`` under spies. Returns the census capture (``None`` if the builder returned before its closure
    loop) and the builder's own result."""
    kwargs = {
        "sliding_leaf_frame_closure": sliding_leaf_frame_closure, "dark_painted_wall_source": dark_painted_wall_source,
        "wall_end_stroke_closures": wall_end_stroke_closures,
    }
    with BuilderSpies(census.BUILDER_LAYERED) as spies:
        with spies.building():
            result = layered.build_layered_wall_doorway_room_rings(rows, source_sha256=source_sha256, page_index=page_index, **kwargs)
        capture = spies.capture(result=result, kwargs=kwargs)
    return capture, result


# ------------------------------------------------------------------------------------------------ reports

def _builder_block(capture: census.BuilderCapture | None, result_status: str, reasons: Sequence[str], **extra: Any) -> dict[str, Any]:
    if capture is None:
        return {"census_available": False, "builder_status": result_status, "builder_reason_codes": list(reasons), **extra}
    return {"census_available": True, **extra}


def run_census(
    pdf: Path | str, page_index: int, *, builders: Sequence[str] = ("preview", "layered"), layered_rows: str = "raw", per_gap: bool = False,
    unblocking: bool = True, layered_flags: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """One page's counts-only census (see the module docstring). ``builders`` is any of ``preview`` and ``layered``."""
    pdf = Path(pdf)
    unknown = set(builders) - {"preview", "layered"}
    if unknown or not builders:
        raise ValueError(f"builders must be a non-empty subset of preview and layered, got {tuple(builders)!r}")
    if layered_rows not in ("raw", "preview-scoped"):
        raise ValueError("layered_rows must be raw or preview-scoped")
    if layered_rows == "preview-scoped" and "preview" not in builders:
        raise ValueError("layered_rows=preview-scoped needs the preview builder to run")
    flags = dict(layered_flags or {})
    payload = pdf.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    document = fitz.open(stream=payload, filetype="pdf")
    try:
        if not 0 <= page_index < len(document):
            raise ValueError(f"page index {page_index} is outside the {len(document)} page document")
        raw_rows = document[page_index].get_drawings() if "layered" in builders and layered_rows == "raw" else None
    finally:
        document.close()
    page: dict[str, Any] = {"page_index": page_index, "builders": {}}
    entry_rows = None
    raster = False
    if "preview" in builders:
        capture, summary, entry_rows = capture_preview_builder(pdf, page_index)
        raster = (summary.get("source_modality") or {}).get("route") == RASTER_ROUTE
        extra = {
            "rows_source": "the rows the canonical preview handed its builder",
            "preview_summary": {k: summary.get(k) for k in ("wall_strip_count", "wall_gap_count", "unresolved_wall_gap_count", "candidate_enclosed_regions", "temporary_opening_closures")},
            "source_modality_route": (summary.get("source_modality") or {}).get("route"),
        }
        block = _builder_block(capture, str(summary.get("status", "")), summary.get("reason_codes", ()), **extra)
        if capture is not None:
            block.update(census.census_report(capture, per_gap=per_gap, unblocking=unblocking))
        page["builders"][census.BUILDER_PREVIEW_FORK] = block
    if "layered" in builders:
        if raster and layered_rows == "preview-scoped":
            page["builders"][census.BUILDER_LAYERED] = {"census_available": False, "skipped": "raster_underlay_page_native_vectors_are_not_architectural"}
        else:
            rows = raw_rows if layered_rows == "raw" else entry_rows
            capture, result = capture_layered_builder(rows, source_sha256=sha, page_index=page_index, **flags)
            block = _builder_block(
                capture, result.status.value, result.reason_codes,
                rows_source="the page's raw get_drawings() rows (what build_from_pdf_bytes reads)" if layered_rows == "raw" else "the rows the canonical preview handed its builder",
                flags={"dark_painted_wall_source": True, **flags},
            )
            if capture is not None:
                block.update(census.census_report(capture, per_gap=per_gap, unblocking=unblocking))
            page["builders"][census.BUILDER_LAYERED] = block
    page["source_sha256_prefix"] = sha[:16]
    return page


def build_report(pdf: Path | str, page_indices: Sequence[int], **kwargs: Any) -> dict[str, Any]:
    pages = [run_census(pdf, index, **kwargs) for index in page_indices]
    inexact = [
        {"page_index": p["page_index"], "builder": name}
        for p in pages for name, block in p["builders"].items()
        if block.get("census_available") and not block["replication"]["exact"]
    ]
    return {
        "schema_version": census.SCHEMA_VERSION,
        "tool": "tools/diag_ring_leak_census.py",
        "note": NOTE,
        "pages": pages,
        "replication_failures": inexact,
    }


def summary_lines(report: Mapping[str, Any]) -> list[str]:
    lines = []
    for page in report["pages"]:
        for name, block in page["builders"].items():
            head = f"page {page['page_index']} {name}:"
            if not block.get("census_available"):
                lines.append(f"{head} no census ({block.get('skipped') or block.get('builder_status')})")
                continue
            c, u, a = block["counts"], block["unclosed_gaps"], block["apertures"]
            unblock = block["unblocking_power"]
            lines.append(
                f"{head} strips {c['strips']} raw gaps {c['raw_gaps']} (collinear {c['raw_gaps_collinear']}) closed {c['closed']} | unclosed {u['count']} "
                f"(collinear {u['collinear']}) | rings {c['rings']} | replication {'exact' if block['replication']['exact'] else 'NOT EXACT'} | "
                f"ring-adding gaps {'n/a' if unblock is None else unblock['single_closure']['gaps_adding_a_ring']} (new space {'n/a' if unblock is None else a['new_space_gaps']}) | apertures {a['groups']} of {a['raw_gaps']}"
            )
    return lines


def _inside_repository(path: Path) -> bool:
    root = Path(__file__).resolve().parents[1]
    resolved = path.resolve()
    return resolved == root or root in resolved.parents


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page-index", type=int, action="append", required=True, help="0-based original page; repeat for several pages")
    parser.add_argument("--builder", choices=("preview", "layered", "both"), default="both")
    parser.add_argument("--layered-rows", choices=("raw", "preview-scoped"), default="raw",
                        help="rows for the layered builder: the page's raw drawings (what the room-face scope reads) or the rows the preview scoped")
    parser.add_argument("--layered-sliding-leaf", action="store_true", help="run the layered builder with sliding_leaf_frame_closure")
    parser.add_argument("--layered-wall-end-strokes", action="store_true", help="run the layered builder with wall_end_stroke_closures")
    parser.add_argument("--per-gap", action="store_true", help="add one record per unclosed gap (indices, lengths and counts only)")
    parser.add_argument("--no-unblocking", action="store_true", help="skip the ring recomputations (faster)")
    parser.add_argument("--allow-inexact", action="store_true", help="exit 0 even when a replication check fails (the ring figures are still withheld)")
    parser.add_argument("--json-out", type=Path, help="write the report here (outside the repository) and print a short summary instead")
    args = parser.parse_args(argv)
    if args.json_out is not None and _inside_repository(args.json_out):
        parser.error("--json-out must be outside the repository")
    builders = ("preview", "layered") if args.builder == "both" else (args.builder,)
    try:
        report = build_report(
            args.pdf, args.page_index, builders=builders, layered_rows=args.layered_rows, per_gap=args.per_gap, unblocking=not args.no_unblocking,
            layered_flags={"sliding_leaf_frame_closure": args.layered_sliding_leaf, "wall_end_stroke_closures": args.layered_wall_end_strokes},
        )
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    text = json.dumps(report, indent=1, sort_keys=True)
    if args.json_out is not None:
        args.json_out.write_text(text + "\n", encoding="utf-8")
        print("\n".join(summary_lines(report)))
    else:
        print(text)
    if report["replication_failures"] and not args.allow_inexact:
        print(f"replication check failed for {len(report['replication_failures'])} builder run(s)", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
