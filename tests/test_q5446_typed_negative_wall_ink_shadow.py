"""Tests for typed negative non-wall ink filtering and Q5446 complexity elimination."""
from pathlib import Path
import pytest

from pb_filtered_native_primitive_receipts import FilteredNativePrimitiveReceipt
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_COMPLEXITY_EXCEEDED,
    PhysicalWallCandidateProducer,
    _filter_repeated_non_physical_drafting_primitives,
    filtered_wall_topology_source_segment_count,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_vector_geometry_v130 import extract_native_page
import fitz

BLACK = (0.0, 0.0, 0.0)


def _seg(ident, x1, y1, x2, y2, *, width=0.96, stroke=BLACK, dashes="[] 0", path=None, fill=None):
    return {
        "id": ident,
        "x1": float(x1),
        "y1": float(y1),
        "x2": float(x2),
        "y2": float(y2),
        "kind": "line",
        "stroke": stroke,
        "stroke_present": stroke is not None,
        "width": width,
        "width_present": True,
        "dashes": dashes,
        "fill": fill,
        "fill_present": fill is not None,
        "path_index": ident if path is None else path,
    }


def _strip(prefix, x0, y0, x1, y1, **kw):
    return [
        _seg(f"{prefix}.a", x0, y0, x1, y0, path=f"{prefix}", **kw),
        _seg(f"{prefix}.b", x1, y0, x1, y1, path=f"{prefix}", **kw),
        _seg(f"{prefix}.c", x1, y1, x0, y1, path=f"{prefix}", **kw),
        _seg(f"{prefix}.d", x0, y1, x0, y0, path=f"{prefix}", **kw),
    ]


def _building(ox=100.0, oy=100.0, w=300.0, h=200.0, t=2.6, **kw):
    out = []
    out += _strip("top", ox, oy, ox + w, oy + t, **kw)
    out += _strip("bot", ox, oy + h - t, ox + w, oy + h, **kw)
    out += _strip("left", ox, oy + t, ox + t, oy + h - t, **kw)
    out += _strip("right", ox + w - t, oy + t, ox + w, oy + h - t, **kw)
    return out


def _letter(prefix, bx, by):
    # A small 3-segment character
    return [
        _seg(f"{prefix}.1", bx, by, bx + 1.0, by - 6.0, path=prefix),
        _seg(f"{prefix}.2", bx + 1.0, by - 6.0, bx + 2.0, by, path=prefix),
        _seg(f"{prefix}.3", bx + 0.5, by - 3.0, bx + 1.5, by - 3.0, path=prefix),
    ]


def test_typed_negative_filter_requires_explicit_boolean():
    with pytest.raises(TypeError, match="filter_typed_negative_non_wall_ink_shadow requires an explicit boolean"):
        from pb_physical_wall_candidate_authority import _assemble_scope_result
        _assemble_scope_result(
            source_producer=None,
            published=None,
            page_id="1",
            selector=None,
            segments=[],
            source_observation_ids=[],
            page_width=500.0,
            page_height=500.0,
            source_bytes=b"",
            filter_typed_negative_non_wall_ink_shadow="true",  # type: ignore
        )


def test_synthetic_building_and_glyph_run_filtering():
    walls = _building()
    # 5 letters along a baseline
    glyphs = []
    for i in range(5):
        glyphs.extend(_letter(f"L{i}", 400.0 + 8.0 * i, 450.0))

    all_segs = walls + glyphs

    # Without typed negative filter: glyphs are not singletons (each is 3 segments), so retained
    retained_default = _filter_repeated_non_physical_drafting_primitives(
        all_segs, page_width=842.0, page_height=595.0, filter_typed_negative_non_wall_ink_shadow=False
    )
    assert len(retained_default) == len(all_segs)

    # With typed negative filter: glyph run is excluded as NOT_WALL_INK
    retained_filtered = _filter_repeated_non_physical_drafting_primitives(
        all_segs, page_width=842.0, page_height=595.0, filter_typed_negative_non_wall_ink_shadow=True
    )
    assert len(retained_filtered) == len(walls)
    retained_ids = {s["id"] for s in retained_filtered}
    assert all(w["id"] in retained_ids for w in walls)
    assert not any(g["id"] in retained_ids for g in glyphs)


def test_preserved_source_primitive_ids_never_filtered_even_if_in_negative_run():
    walls = _building()
    glyphs = []
    for i in range(5):
        glyphs.extend(_letter(f"L{i}", 400.0 + 8.0 * i, 450.0))
    all_segs = walls + glyphs

    # Preserve one glyph segment explicitly
    protected_id = "L2.1"
    retained = _filter_repeated_non_physical_drafting_primitives(
        all_segs,
        page_width=842.0,
        page_height=595.0,
        preserved_source_primitive_ids=frozenset([protected_id]),
        filter_typed_negative_non_wall_ink_shadow=True,
    )
    retained_ids = {s["id"] for s in retained}
    assert protected_id in retained_ids
    assert len(retained) == len(walls) + 1


def test_original_q5446_page_1_drops_below_cap_under_typed_negative_filter():
    p = Path("C:/Users/bryce/PlanReader-3D/documents/sources/Q5446_Standard_Plans_V1_20220320.pdf")
    if not p.is_file():
        pytest.skip("Original Q5446 PDF unavailable")
    doc = fitz.open(p)
    page = doc[0]
    native = extract_native_page(page)
    segs = native.get("segments", [])
    assert len(segs) == 47184

    # Default count trips 20,000 cap
    count_default = filtered_wall_topology_source_segment_count(
        segs, page_width=page.rect.width, page_height=page.rect.height, filter_typed_negative_non_wall_ink_shadow=False
    )
    assert count_default == 41932
    assert count_default > 20000

    # Typed negative shadow drops well below 20,000 cap!
    count_shadow = filtered_wall_topology_source_segment_count(
        segs, page_width=page.rect.width, page_height=page.rect.height, filter_typed_negative_non_wall_ink_shadow=True
    )
    assert count_shadow == 8669
    assert count_shadow < 20000


def test_original_q5446_wall_scope_resolves_under_typed_negative_shadow():
    p = Path("C:/Users/bryce/PlanReader-3D/documents/sources/Q5446_Standard_Plans_V1_20220320.pdf")
    if not p.is_file():
        pytest.skip("Original Q5446 PDF unavailable")
    pdf_bytes = p.read_bytes()

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version="1.0.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="q5446-test",
        source_bytes=pdf_bytes,
        source_locator="memory://q5446-test.pdf",
        page_ids=(1,),
    )

    # 1. Default producer: complexity exceeded
    producer_default = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source, page_ids=["1"]
    )
    scope_default = list(producer_default._scopes.values())[0]
    assert scope_default.scope_complete is False
    assert PHYSICAL_WALL_CANDIDATE_SCOPE_COMPLEXITY_EXCEEDED in scope_default.reason_codes

    # 2. Shadow producer with typed negative non-wall ink filter: complexity eliminated!
    producer_shadow = PhysicalWallCandidateProducer.from_source_visibility_typed_negative_wall_ink_shadow(
        source, page_ids=["1"]
    )
    scope_shadow = list(producer_shadow._scopes.values())[0]
    # The complexity exceeded reason code MUST NOT be present!
    assert PHYSICAL_WALL_CANDIDATE_SCOPE_COMPLEXITY_EXCEEDED not in scope_shadow.reason_codes
    assert len(scope_shadow.filtered_native_primitive_receipts) > 10000


def test_opening_local_supplemental_scope_result_signature_and_execution():
    from pb_physical_wall_candidate_authority import (
        _build_opening_local_supplemental_scope_result,
    )
    import inspect
    sig = inspect.signature(_build_opening_local_supplemental_scope_result)
    assert "filter_typed_negative_non_wall_ink_shadow" in sig.parameters
    assert sig.parameters["filter_typed_negative_non_wall_ink_shadow"].default is False
