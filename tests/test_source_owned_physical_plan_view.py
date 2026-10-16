"""Source-owned view proof: synthetic geometry, competitors and source integrity."""

from copy import deepcopy
from dataclasses import replace

import fitz
import pytest

from pb_migration_provider_envelope import ProviderContext
from pb_source_plan_view_authority import _raster_plane_extent
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_migration_adapter import adapt_f07_viewport_to_migration
from pb_viewport_segmentation import (
    SegmentedViewport,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segment_page_viewports,
    segment_source_page_viewports,
)


def _sheet(
    *,
    dx=0.0,
    dy=0.0,
    scale=1.0,
    rotation=0,
    reverse=False,
    split=False,
    no_frame=False,
    no_dimensions=False,
    one_axis=False,
    partial=False,
    second=False,
    second_incomplete=False,
    table=False,
    hidden_role=False,
    unrelated=False,
    expanded=False,
    role="FLOOR PLAN",
):
    doc = fitz.open()
    visual_w = (1000.0 if expanded else 850.0) * scale + dx
    visual_h = (700.0 if expanded else 500.0) * scale + dy
    page = doc.new_page(
        width=visual_h if rotation in (90, 270) else visual_w,
        height=visual_w if rotation in (90, 270) else visual_h,
    )
    ops = []

    def point(p):
        x, y = p[0] * scale + dx, p[1] * scale + dy
        return (
            (y, visual_w - x)
            if rotation == 90
            else (visual_h - y, x)
            if rotation == 270
            else (x, y)
        )

    def line(a, b):
        ops.append(
            lambda a=a, b=b: page.draw_line(point(a), point(b), width=0.3 * scale)
        )

    def text(p, t, *, rotate=0, size=10.0, invisible=False):
        ops.append(
            lambda p=p, t=t, rotate=rotate, size=size, invisible=invisible: (
                page.insert_text(
                    point(p),
                    t,
                    fontsize=size * scale,
                    rotate=(rotate + rotation) % 360,
                    render_mode=3 if invisible else 0,
                )
            )
        )

    def plan(x=0.0, incomplete=False):
        if not no_frame:
            ops.append(
                lambda x=x: page.draw_rect(
                    fitz.Rect(
                        *point((50.0 + x, 50.0)), *point((350.0 + x, 350.0))
                    ).normalize(),
                    width=0.3 * scale,
                )
            )
        text((140.0 + x, 170.0), "KITCHEN")
        text((235.0 + x, 250.0), "BATH")
        if no_dimensions or incomplete:
            return
        for vertical in (False, True):
            if one_axis and vertical:
                continue
            a, b = (
                ((90.0 + x, 110.0), (90.0 + x, 300.0))
                if vertical
                else ((110.0 + x, 90.0), (300.0 + x, 90.0))
            )
            if split:
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                line(a, m)
                line(m, b)
            else:
                line(a, b)
            for n, p in enumerate((a, b)):
                line(p, (p[0] + 12.0, p[1]) if vertical else (p[0], p[1] + 12.0))
                for sign in (-1, 1):
                    if partial and n == 1 and sign == -1:
                        continue
                    line(p, (p[0] + 3.0 * sign, p[1] + 3.0 * sign))
            text(
                (97.0 + x, 218.0) if vertical else (180.0 + x, 87.0),
                "3210",
                rotate=90 if vertical else 0,
                size=8.0,
            )

    plan()
    if second:
        plan(370.0, incomplete=second_incomplete)
    if table:
        for y in (50.0, 100.0, 150.0, 200.0, 250.0, 300.0):
            for x in (50.0, 100.0, 150.0, 200.0, 250.0, 300.0):
                ops.append(
                    lambda x=x, y=y: page.draw_rect(
                        fitz.Rect(
                            *point((x, y)), *point((x + 50.0, y + 50.0))
                        ).normalize(),
                        width=0.3 * scale,
                    )
                )
    text((430.0, 410.0), "DRAWING TITLE", size=7.0, invisible=hidden_role)
    text((430.0, 425.0), role, invisible=hidden_role)
    text((560.0, 410.0), "SCALE", size=7.0)
    text((620.0, 410.0), "DATE", size=7.0)
    text((680.0, 410.0), "DRAWING NO", size=7.0)
    if unrelated:
        text((730.0, 50.0), "GENERAL NOTES")
        line((740.0, 80.0), (795.0, 80.0))
    for op in reversed(ops) if reverse else ops:
        op()
    page.set_rotation(rotation)
    data = doc.tobytes()
    doc.close()
    return data


def _source(data):
    source = SourceVisibilityProducer(
        producer_method="source-plan-view-test", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id="source-test",
        source_bytes=data,
        source_locator="memory://drawing.pdf",
        page_ids=("1",),
    )
    return source, published


def _views(source, published, *, enabled=True):
    return segment_source_page_viewports(
        source,
        revision_id=published.revision.revision_id,
        page_id="1",
        physical_plan_view_shadow=enabled,
    )


def _authenticated(views):
    return [v for v in views if is_authoritative_derived_viewport(v)]


def _context(pub, views, **changes):
    ids = tuple(v.view_id for v in views)
    args = {
        "run_id": "run",
        "workspace_id": "workspace",
        "project_id": "project",
        "document_id": pub.revision.document_id,
        "source_sha256": pub.revision.source_sha256,
        "revision_id": pub.revision.revision_id,
        "current_revision_id": pub.revision.revision_id,
        "selected_pages": (0,),
        "owned_viewport_ids": ids,
        "evidence_snapshot_id": pub.snapshot.snapshot_id,
        "owned_page_numbers": (1,),
        "viewport_page_ownership": tuple((i, 1) for i in ids),
    }
    return ProviderContext(**dict(args, **changes))


def test_authentic_native_component_preserves_snapshot_and_default():
    data = _sheet()
    source, pub = _source(data)
    with fitz.open(stream=data, filetype="pdf") as pdf:
        baseline = segment_page_viewports(pdf[0], page_number=1)
    assert [v.__dict__ for v in _views(source, pub, enabled=False)] == [
        v.__dict__ for v in baseline
    ]
    before = (pub, deepcopy(source._producer._store.observations))
    views = _views(source, pub)
    (plan,) = _authenticated(views)
    assert plan.bounding_box == (50.0, 50.0, 350.0, 350.0)
    assert plan.view_type == "floor_plan" and is_segment_page_viewports_product(plan)
    assert (
        plan.scale_denominator is None
        and plan.provenance["metric_authority_granted"] is False
    )
    assert plan.provenance["whole_sheet_plan_universe_proven"] is False
    assert source.published_snapshot_for_revision(pub.revision.revision_id) == before[0]
    assert source._producer._store.observations == before[1]
    replay = _authenticated(_views(source, pub))[0]
    assert replay.view_id == plan.view_id and replay.provenance == plan.provenance
    result = adapt_f07_viewport_to_migration(
        views, viewport_id=plan.view_id, context=_context(pub, views), page_no=1
    )
    assert (
        result.viewport is not None
        and result.ownership_proof is not None
        and not result.blocking_reasons
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"no_frame": True},
        {"no_dimensions": True},
        {"one_axis": True},
        {"partial": True},
        {"second": True},
        {"second": True, "second_incomplete": True},
        {"table": True},
        {"hidden_role": True},
        {"role": "FRONT ELEVATION"},
        {"role": "PROJECT FLOOR PLAN"},
    ],
)
def test_metadata_or_geometry_look_alikes_never_elect_an_owner(changes):
    source, pub = _source(_sheet(**changes))
    assert not _authenticated(_views(source, pub))


@pytest.mark.parametrize(
    "dx,dy,scale,rotation",
    [
        (17.0, 23.0, 1.0, 0),
        (0.0, 0.0, 2.0, 0),
        (0.0, 0.0, 1.0, 90),
        (9.0, 13.0, 0.5, 90),
    ],
)
def test_translation_rotation_and_scale_keep_native_ownership(dx, dy, scale, rotation):
    source, pub = _source(_sheet(dx=dx, dy=dy, scale=scale, rotation=rotation))
    (plan,) = _authenticated(_views(source, pub))
    a, b = 50.0 * scale + dx, 50.0 * scale + dy
    c, d = 350.0 * scale + dx, 350.0 * scale + dy
    expected = (
        (b, 850.0 * scale + dx - c, d, 850.0 * scale + dx - a)
        if rotation == 90
        else (500.0 * scale + dy - d, a, 500.0 * scale + dy - b, c)
        if rotation == 270
        else (a, b, c, d)
    )
    assert plan.bounding_box == pytest.approx(expected)


@pytest.mark.parametrize(
    "changes",
    [{"reverse": True}, {"split": True}, {"unrelated": True}, {"expanded": True}],
)
def test_order_splitting_unrelated_content_and_page_expansion_keep_extent(changes):
    source, pub = _source(_sheet(**changes))
    (plan,) = _authenticated(_views(source, pub))
    assert plan.bounding_box == (50.0, 50.0, 350.0, 350.0)


def test_caller_copy_changed_payload_and_foreign_context_cannot_create_authority():
    source, pub = _source(_sheet())
    views = _views(source, pub)
    (plan,) = _authenticated(views)
    forged = SegmentedViewport(
        **{k: v for k, v in plan.__dict__.items() if not k.startswith("_")}
    )
    assert not is_authoritative_derived_viewport(forged)
    changed = replace(plan, bounding_box=(0.0, 0.0, 850.0, 500.0))
    assert not is_authoritative_derived_viewport(changed)
    for key, val in (
        ("document_id", "foreign"),
        ("source_sha256", "f" * 64),
        ("evidence_snapshot_id", "foreign"),
    ):
        result = adapt_f07_viewport_to_migration(
            views,
            viewport_id=plan.view_id,
            context=_context(pub, views, **{key: val}),
            page_no=1,
        )
        assert result.viewport is None


def test_source_mutation_stale_revision_and_page_aliases_fail_closed():
    source, pub = _source(_sheet())
    _views(source, pub)
    source._producer._store.source_bytes_by_revision[pub.revision.revision_id] = (
        b"corrupt"
    )
    with pytest.raises(RuntimeError, match="immutable_bytes"):
        _views(source, pub)
    source, pub = _source(_sheet())
    source.ingest_native_pdf_bytes(
        document_id="source-test",
        source_bytes=_sheet(unrelated=True),
        source_locator="memory://new.pdf",
    )
    with pytest.raises(ValueError, match="stale"):
        _views(source, pub)
    for page in ("0", "01", "1.0", "2", 1):
        with pytest.raises(ValueError):
            segment_source_page_viewports(
                source,
                revision_id=source._producer.current_revision_id("source-test"),
                page_id=page,
                physical_plan_view_shadow=True,
            )
    with pytest.raises(TypeError):
        segment_source_page_viewports(object(), revision_id="r", page_id="1")
    source, pub = _source(_sheet(rotation=270))
    assert not _authenticated(_views(source, pub))


def test_raster_planes_retain_all_supports_and_abstain_for_competitors():
    labels = (
        ((110.0, 110.0, 120.0, 120.0), ("label0",), "KITCHEN"),
        ((180.0, 180.0, 190.0, 190.0), ("label1",), "BATH"),
    )
    facts = (
        (
            "horizontal",
            (100.0, 80.0, 220.0, 80.0),
            (98.0, 78.0, 222.0, 92.0),
            ("h",),
            "hw",
        ),
        (
            "vertical",
            (80.0, 100.0, 80.0, 220.0),
            (78.0, 98.0, 92.0, 222.0),
            ("v",),
            "vw",
        ),
    )
    physical = (
        {
            "physical_opening_id": "p0",
            "source_observation_ids": ("a", "b"),
            "support_bbox_pdf_pts": (130.0, 130.0, 140.0, 140.0),
        },
        {
            "physical_opening_id": "p1",
            "source_observation_ids": ("c", "d"),
            "support_bbox_pdf_pts": (150.0, 150.0, 160.0, 160.0),
        },
    )
    before = deepcopy((labels, facts, physical))
    result = _raster_plane_extent(labels, facts, physical)
    assert result is not None and result[0] == (78.0, 78.0, 222.0, 222.0)
    assert len(result[3]["isolated_raster_support_receipts"]) == 2
    assert (labels, facts, physical) == before
    reordered = _raster_plane_extent(
        tuple(reversed(labels)), tuple(reversed(facts)), tuple(reversed(physical))
    )
    assert reordered[0] == result[0]
    assert _raster_plane_extent(labels, facts, physical[:1]) is None
    assert _raster_plane_extent(labels, facts[:1], physical) is None
    # A second room-bearing source plane remains a competitor even without
    # proved physical openings; it cannot disappear before election.
    other = tuple(
        ((b[0] + 400, b[1] + 400, b[2] + 400, b[3] + 400), ids, t)
        for b, ids, t in labels
    )
    otherfacts = tuple(
        (axis, tuple(x + 400 for x in b), tuple(x + 400 for x in s), ids, w)
        for axis, b, s, ids, w in facts
    )
    assert (
        _raster_plane_extent((*labels, *other), (*facts, *otherfacts), physical) is None
    )
