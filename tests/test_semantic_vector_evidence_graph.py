"""Tests for the Phase D shadow semantic evidence graph
(pb_semantic_vector_evidence_graph.py).

Two tiers, matching the module's own two entry points:
  1. Synthetic, hand-built cases -- one per deterministic rule, proving each
     rule fires (or correctly abstains) on an unambiguous constructed input.
  2. Real committed-drawing snapshots -- qualitative validation only (no
     benchmark quantities, no project-name conditionals, no per-segment
     ground truth asserted), checking the properties the standing mandate
     asks for: obvious walls get wall-positive evidence, repeated short
     geometry gets non-wall evidence, metadata-excluded segments get their
     corresponding label, and the classifier actually abstains sometimes
     rather than forcing every primitive into a class.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pb_semantic_vector_evidence_graph import (
    EvidenceStrength,
    SemanticClass,
    classify_excluded_segment_evidence,
    classify_wall_graph_evidence,
)
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport


def _seg(id_, x1, y1, x2, y2, **kw) -> Dict[str, Any]:
    base = {
        "id": id_, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        "width": 0.5, "stroke": (0, 0, 0), "fill": None, "layer": "", "dashes": "",
    }
    base.update(kw)
    return base


class TestSyntheticRules:
    def test_isolated_long_paired_segments_get_physical_wall_probable(self):
        # A hollow double-rectangle (two nested, offset closed loops) -- the
        # standard way two-line CAD wall linework represents wall thickness:
        # each wall face is a long run between two degree-2 corners, and has
        # a parallel partner (the opposite face) at a plausible offset.
        outer = [(0, 0), (200, 0), (200, 100), (0, 100)]
        inner = [(10, 10), (190, 10), (190, 90), (10, 90)]

        def _loop_segments(points, prefix):
            segs = []
            for i in range(len(points)):
                x1, y1 = points[i]
                x2, y2 = points[(i + 1) % len(points)]
                segs.append(_seg(f"{prefix}{i}", x1, y1, x2, y2))
            return segs

        segments = _loop_segments(outer, "outer") + _loop_segments(inner, "inner")
        graph = build_wall_graph_for_viewport(segments)
        evidence = classify_wall_graph_evidence(graph)
        labels = {e.label for e in evidence}
        assert SemanticClass.PHYSICAL_WALL_PROBABLE in labels

    def test_dense_short_repeated_ticks_get_hatch(self):
        # A field of short, similarly-oriented, closely-spaced ticks next to
        # a couple of long wall-like runs -- the documented real hatch-tick
        # convention (see architecture doc): median length must reflect a
        # real long/short split, which a pure all-ticks population would not.
        segments = [_seg("wallA", 0, -20, 300, -20), _seg("wallB", 0, 60, 300, 60)]
        for i in range(12):
            x = i * 4.0
            segments.append(_seg(f"tick{i}", x, 0, x + 2.0, 2.0))
        graph = build_wall_graph_for_viewport(segments)
        evidence = classify_wall_graph_evidence(graph)
        hatch_count = sum(1 for e in evidence if e.label == SemanticClass.HATCH)
        assert hatch_count >= 1

    def test_dashed_line_gets_dimension_annotation(self):
        # A dashed segment is excluded by Stage A's own metadata pre-filter
        # before it ever becomes a graph edge -- so its evidence comes from
        # the excluded-segment population, not the wall graph's edges.
        segments = [_seg("dim1", 0, 0, 50, 0, dashes="[3 2] 0")]
        excluded_only = _run_excluded(segments)
        assert excluded_only[0].label == SemanticClass.DIMENSION_ANNOTATION
        assert excluded_only[0].strength in (EvidenceStrength.WEAK, EvidenceStrength.STRONG)

    def test_dimension_layer_name_gets_strong_dimension_annotation(self):
        segments = [_seg("dim2", 0, 0, 50, 0, layer="Dimension - Linear")]
        excluded_only = _run_excluded(segments)
        assert len(excluded_only) == 1
        assert excluded_only[0].label == SemanticClass.DIMENSION_ANNOTATION
        assert excluded_only[0].strength == EvidenceStrength.STRONG

    def test_hatch_layer_name_gets_strong_hatch(self):
        segments = [_seg("h1", 0, 0, 5, 5, layer="Hatch - Concrete")]
        excluded_only = _run_excluded(segments)
        assert excluded_only[0].label == SemanticClass.HATCH
        assert excluded_only[0].strength == EvidenceStrength.STRONG

    def test_text_frame_layer_abstains_rather_than_guessing(self):
        segments = [_seg("t1", 0, 0, 30, 0, layer="Text Frame Border")]
        excluded_only = _run_excluded(segments)
        assert excluded_only[0].label == SemanticClass.UNKNOWN
        assert excluded_only[0].strength == EvidenceStrength.ABSTAIN

    def test_isolated_unremarkable_segment_abstains(self):
        segments = [_seg("lonely", 500, 500, 530, 505)]
        graph = build_wall_graph_for_viewport(segments)
        evidence = classify_wall_graph_evidence(graph)
        assert evidence[0].label == SemanticClass.UNKNOWN
        assert evidence[0].strength == EvidenceStrength.ABSTAIN

    def test_lineage_present_reports_source_primitive_count(self):
        segments = [_seg("a", 0, 0, 10, 0), _seg("b", 0, 0, 10, 0)]  # exact duplicate
        graph = build_wall_graph_for_viewport(segments)
        evidence = classify_wall_graph_evidence(graph)
        assert all(e.features.source_primitive_count is not None for e in evidence)
        assert any(e.features.source_primitive_count >= 2 for e in evidence)

def _run_excluded(segments: List[Dict[str, Any]]):
    graph = build_wall_graph_for_viewport(segments)
    return classify_excluded_segment_evidence(graph["excluded_segments"])


# ---------------------------------------------------------------------------
# Real committed drawing snapshots -- qualitative validation only.
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "hosted_opening_geometry"
_BAGHAU_SNAPSHOT_PATH = _FIXTURES_DIR / "baghau_p36.json"
_DUNGICHA_SNAPSHOT_PATH = _FIXTURES_DIR / "dungicha_p134.json"


class _Pt:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class _Rect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.width = x1 - x0
        self.height = y1 - y0


class _FakePage:
    def __init__(self, drawings, rect=None, number=0):
        self._drawings = drawings
        self.rect = rect or _Rect(0, 0, 2000, 2000)
        self.number = number

    def get_drawings(self):
        return self._drawings

    def get_text(self, *_a, **_kw):
        return ""


def _load_snapshot(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _snapshot_page(snapshot: dict):
    drawings = []
    for d in snapshot["drawings"]:
        items = []
        for item in d["items"]:
            op = item[0]
            items.append((op, *[_Pt(x, y) for x, y in item[1:]]))
        drawings.append(
            {
                "color": tuple(d["color"]) if d["color"] is not None else None,
                "fill": tuple(d["fill"]) if d["fill"] is not None else None,
                "width": d["width"],
                "rect": _Rect(*d["rect"]) if d["rect"] is not None else None,
                "items": items,
            }
        )
    page_rect = _Rect(*snapshot["page_rect"])
    return _FakePage(drawings, rect=page_rect, number=snapshot["source"]["pdf_page_0based"])


def _real_graph(snapshot_path: Path) -> Dict[str, Any]:
    from pb_vector_geometry_v130 import extract_native_page

    page = _snapshot_page(_load_snapshot(snapshot_path))
    native = extract_native_page(page)
    return build_wall_graph_for_viewport(native["segments"])


class TestRealDrawingQualitativeValidation:
    """No benchmark quantities, no per-segment ground truth, no project-name
    conditionals: these assert only the qualitative properties the standing
    mandate names -- some positive wall evidence exists, some non-wall
    evidence exists, and the classifier genuinely abstains on some
    fraction of real, messy geometry rather than forcing every primitive
    into a class."""

    def test_baghau_real_drawing_produces_mixed_evidence_with_abstentions(self):
        graph = _real_graph(_BAGHAU_SNAPSHOT_PATH)
        evidence = classify_wall_graph_evidence(graph)
        labels = [e.label for e in evidence]
        assert SemanticClass.PHYSICAL_WALL_PROBABLE in labels, "expected at least one wall-positive edge on a real floor plan"
        assert SemanticClass.UNKNOWN in labels, "expected genuine abstentions on real, messy geometry -- forcing every edge into a class would be a red flag"
        abstain_count = sum(1 for e in evidence if e.strength == EvidenceStrength.ABSTAIN)
        assert 0 < abstain_count < len(evidence), "abstention rate should be a genuine fraction, not 0% or 100%"

    def test_dungicha_real_drawing_produces_mixed_evidence_with_abstentions(self):
        graph = _real_graph(_DUNGICHA_SNAPSHOT_PATH)
        evidence = classify_wall_graph_evidence(graph)
        labels = [e.label for e in evidence]
        assert SemanticClass.PHYSICAL_WALL_PROBABLE in labels
        assert SemanticClass.UNKNOWN in labels
        abstain_count = sum(1 for e in evidence if e.strength == EvidenceStrength.ABSTAIN)
        assert 0 < abstain_count < len(evidence)

    def test_baghau_hatch_tick_field_gets_predominantly_non_wall_evidence(self):
        """Baghau's floor plan draws masonry as a field of short, solid,
        untagged 45-degree hatch ticks between two continuous wall-face
        lines (documented in tests/test_hosted_opening_geometry.py's own
        module docstring). Because these ticks are solid and carry no
        identifiable hatch/dimension layer name, Stage A's OWN metadata-only
        pre-filter (Section 6.11) does not exclude them -- they survive as
        "structural candidates" despite being hatch marks, a known,
        documented limitation of that filter. This is the genuinely
        independent cross-check this module can offer: using ONLY geometric
        repetition (never layer name or dash pattern) on the population the
        metadata filter already let through, do short, densely-repeated
        edges get kept out of PHYSICAL_WALL_PROBABLE? This does not require
        or assert that every tick is correctly labelled HATCH -- only that
        the wall-positive label is not being handed out indiscriminately to
        short, highly-repeated geometry.
        """
        graph = _real_graph(_BAGHAU_SNAPSHOT_PATH)
        evidence = classify_wall_graph_evidence(graph)
        lengths = sorted(e.features.length_pt for e in evidence)
        median_length = lengths[len(lengths) // 2]
        short_highly_repeated = [
            e for e in evidence
            if e.features.length_pt < median_length and e.features.repetition_neighbor_count >= 4
        ]
        assert short_highly_repeated, "expected at least some short, densely-repeated real edges (the hatch-tick field) to exist in this drawing"
        wall_labelled = [e for e in short_highly_repeated if e.label == SemanticClass.PHYSICAL_WALL_PROBABLE]
        assert len(wall_labelled) == 0, (
            "short, densely-repeated real edges should never receive PHYSICAL_WALL_PROBABLE -- "
            f"got {len(wall_labelled)}/{len(short_highly_repeated)}"
        )

    def test_excluded_segments_with_hatch_or_dimension_metadata_get_matching_label(self):
        for snapshot_path in (_BAGHAU_SNAPSHOT_PATH, _DUNGICHA_SNAPSHOT_PATH):
            graph = _real_graph(snapshot_path)
            excluded_evidence = classify_excluded_segment_evidence(graph["excluded_segments"])
            for evidence in excluded_evidence:
                if "hatch_layer_excluded" in evidence.features.reason_codes:
                    assert evidence.label == SemanticClass.HATCH
                if "dimension_layer_excluded" in evidence.features.reason_codes:
                    assert evidence.label == SemanticClass.DIMENSION_ANNOTATION
