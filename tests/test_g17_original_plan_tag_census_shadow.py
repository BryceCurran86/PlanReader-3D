"""Exercise the census with real source producers, never invented tag receipts."""
from copy import deepcopy
from dataclasses import replace

import fitz
import pytest

from pb_g17_original_plan_tag_census_shadow import (
    build_g17_original_plan_tag_census_shadow,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _prepare(*, dx=0.0, dy=0.0, scale=1.0, reverse=False,
             expanded=False, competing_tag=False, hidden_tag=False,
             other_page=False):
    source = SourceVisibilityProducer(
        producer_method="original-plan-tag-census-test", producer_version="1"
    )
    with fitz.open() as pdf:
        page = pdf.new_page(
            width=(900 if expanded else 700) * scale + dx,
            height=(800 if expanded else 650) * scale + dy,
        )

        def point(x, y):
            return fitz.Point(x * scale + dx, y * scale + dy)

        lines = (
            ((20, 100), (100, 100)), ((140, 100), (220, 100)),
            ((20, 110), (100, 110)), ((140, 110), (220, 110)),
            ((100, 100), (100, 110)), ((140, 100), (140, 110)),
        )
        operations = [("line", pair) for pair in lines]
        # W2 is inside the six-support envelope, outside the real aperture.
        operations += [("text", (112, 106, "W1")),
                       ("text", (190, 106, "W2")),
                       ("text", (300, 200, "870"))]
        if competing_tag:
            operations.append(("text", (126, 106, "D3")))
        for kind, value in reversed(operations) if reverse else operations:
            if kind == "line":
                a, b = value
                page.draw_line(point(*a), point(*b), width=0.3 * scale)
            else:
                x, y, text = value
                page.insert_text(point(x, y), text, fontsize=5 * scale)
        if hidden_tag:
            page.insert_text(point(113, 107), "W9", fontsize=5 * scale,
                             render_mode=3)
        if other_page:
            pdf.new_page(width=700, height=650).insert_text((112, 106), "W8")
        payload = pdf.tobytes()
    published = source.ingest_native_pdf_bytes(
        document_id="tag-census-source", source_bytes=payload,
        source_locator="memory://tag-census.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id, page_ids=("1",),
    )
    return source, published, composition


def _run(source, published, composition, **changes):
    return build_g17_original_plan_tag_census_shadow(
        source, composition, revision_id=published.revision.revision_id,
        page_id="1", **changes,
    )


def _semantics(report):
    return sorted((r["normalized_tag"], r["source_kind"],
                   len(r["contained_in_authenticated_apertures"]),
                   r["outside_all_authenticated_apertures"])
                  for r in report["tag_candidate_records"])


def _assert_no_authority(report):
    for name in (
        "actual_source_leader_topology_proven",
        "source_coverage_exhaustiveness_proven", "opening_tag_binding_granted",
        "source_schedule_binding_granted", "physical_host_granted",
        "metric_quantity_granted", "original_source_authenticated_by_report",
    ):
        assert report[name] is False
    for row in report["tag_candidate_records"]:
        assert not any(row[name] for name in (
            "unique_owner_granted", "schedule_binding_granted",
            "height_or_width_granted",
        ))


def test_real_source_aperture_and_external_lookalike_are_distinguished():
    source, published, composition = _prepare()
    result = _run(source, published, composition)
    assert result["source_decode_complete"]
    assert result["physical_opening_count"] == 1
    assert result["source_text_tag_candidates"] == 2
    assert _semantics(result) == [
        ("W1", "trusted_native", 1, False),
        ("W2", "trusted_native", 0, True),
    ]
    assert result["candidate_outside_all_apertures"] == 1
    _assert_no_authority(result)


def test_competing_contained_tags_are_all_retained_without_electing_an_owner():
    source, published, composition = _prepare(competing_tag=True)
    result = _run(source, published, composition)
    contained = [r for r in result["tag_candidate_records"]
                 if r["contained_in_authenticated_apertures"]]
    assert {r["normalized_tag"] for r in contained} == {"W1", "D3"}
    assert len({r["contained_in_authenticated_apertures"] for r in contained}) == 1
    _assert_no_authority(result)


@pytest.mark.parametrize("options", [
    {"dx": 17.0, "dy": 23.0}, {"scale": 1.5},
    {"reverse": True}, {"expanded": True},
    {"dx": 13.0, "dy": 29.0, "scale": 1.25, "reverse": True},
])
def test_input_order_transform_and_viewport_expansion_preserve_census(options):
    source, published, composition = _prepare(**options)
    result = _run(source, published, composition)
    assert _semantics(result) == [
        ("W1", "trusted_native", 1, False),
        ("W2", "trusted_native", 0, True),
    ]
    _assert_no_authority(result)


def test_invisible_text_and_other_page_cannot_become_page_owned_tags():
    source, published, composition = _prepare(hidden_tag=True, other_page=True)
    result = _run(source, published, composition)
    assert {r["normalized_tag"] for r in result["tag_candidate_records"]} == {
        "W1", "W2"
    }
    _assert_no_authority(result)


def test_replay_is_stable_and_does_not_mutate_source_or_composition():
    source, published, composition = _prepare(competing_tag=True)
    observations = deepcopy(source._producer._store.observations)
    source_bytes = deepcopy(source._producer._store.source_bytes_by_revision)
    bindings = deepcopy(composition.opening_bindings)
    result = _run(source, published, composition)
    assert _run(source, published, composition) == result
    assert source.published_snapshot_for_revision(published.revision.revision_id) == published
    assert source._producer._store.observations == observations
    assert source._producer._store.source_bytes_by_revision == source_bytes
    assert composition.opening_bindings == bindings


def test_foreign_producer_copied_report_and_wrong_scope_are_rejected():
    source, published, composition = _prepare()
    other_source, _, other_composition = _prepare()
    with pytest.raises(ValueError, match="foreign physical opening producer"):
        _run(source, published, other_composition)
    with pytest.raises(TypeError, match="original SourceVisibilityProducer"):
        _run(_run(source, published, composition), published, composition)
    with pytest.raises(ValueError, match="current authenticated decoded original page"):
        build_g17_original_plan_tag_census_shadow(
            source, composition, revision_id="foreign", page_id="1"
        )
    with pytest.raises(ValueError, match="current authenticated decoded original page"):
        build_g17_original_plan_tag_census_shadow(
            source, composition, revision_id=published.revision.revision_id,
            page_id="2",
        )
    assert other_source.physical_opening_authority() is not source.physical_opening_authority()


def test_changed_opening_identity_is_not_accepted_as_an_authentic_trace():
    source, published, composition = _prepare()
    trace, = composition.opening_bindings
    changed = replace(composition, opening_bindings=(
        replace(trace, opening_identity_id="foreign-opening"),
    ))
    with pytest.raises(RuntimeError, match="original opening existence no longer authenticates"):
        _run(source, published, changed)


def test_duplicate_opening_trace_is_not_silently_deduplicated():
    source, published, composition = _prepare()
    trace, = composition.opening_bindings
    changed = replace(composition, opening_bindings=(trace, trace))
    with pytest.raises(RuntimeError, match="duplicate physical opening identity"):
        _run(source, published, changed)
