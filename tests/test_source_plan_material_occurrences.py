"""Real source PDFs at the bounded-view / material occurrence boundary."""

from dataclasses import replace

import fitz
import pytest

import pb_source_material_semantic_authority as semantic
from pb_migration_contracts import EvidenceResolutionStatus
from pb_cross_view_floor_finish_authority import _occurrences_on_page
from pb_viewport_segmentation import segment_source_page_viewports
from test_source_owned_physical_plan_view import _sheet, _source


def _drawing(
    *,
    hidden=False,
    unrelated_hidden=False,
    crossing=False,
    occluded=False,
    no_dictionary=False,
    conflict=False,
    **layout,
):
    data = _sheet(role="FLOOR FINISH PLAN", **layout)
    with fitz.open(stream=data, filetype="pdf") as pdf:
        page = pdf[0]
        scale, dx, dy = layout.get("scale", 1), layout.get("dx", 0), layout.get("dy", 0)
        rotation = layout.get("rotation", 0)
        width = (1000 if layout.get("expanded") else 850) * scale + dx

        def point(x, y):
            x, y = x * scale + dx, y * scale + dy
            return (y, width - x) if rotation == 90 else (x, y)

        def text(x, y, value, *, invisible=False):
            page.insert_text(
                point(x, y),
                value,
                fontsize=8 * scale,
                rotate=rotation,
                render_mode=3 if invisible else 0,
            )

        if not no_dictionary:
            text(430, 50, "FINISH SCHEDULE")
            text(430, 70, "FT9 Porcelain floor tile")
            text(430, 85, "PT9 Acrylic paint")
            if conflict:
                text(430, 100, "FT9 Vinyl floor covering")
        text(
            320 if crossing else 170,
            210,
            "FT9 SECRET" if crossing or occluded else "FT9",
            invisible=hidden,
        )
        if occluded:
            # Original source paint hides only the second word of the same line.
            page.draw_rect(fitz.Rect(186, 201, 223, 213), fill=(1, 1, 1), color=None)
        text(700, 120, "FT9")  # A real mark outside the proven drawing component.
        if unrelated_hidden:
            text(170, 320, "UNREADABLE", invisible=True)
        return pdf.tobytes()


def _publish(data, *, enabled=True, page_ids=("1",)):
    source, published = _source(data)
    factory = semantic.SourceMaterialSemanticProducer
    producer = (
        factory.for_physical_plan_view_shadow(source, page_ids=page_ids)
        if enabled
        else factory.from_source_visibility_producer(source)
    )
    authority = producer.publish(published.revision.revision_id)
    return source, published, producer, authority


def _records(producer):
    return tuple(
        record
        for scope in producer.published_occurrence_results()
        for record in scope.records
    )


def test_source_plan_consumption_is_opt_in_and_preserves_native_source():
    data = _drawing()
    _, _, default, _ = _publish(data, enabled=False)
    assert default.published_plan_viewports() == ()
    assert _records(default) == ()
    source, published, producer, authority = _publish(data)
    assert (
        source.published_snapshot_for_revision(published.revision.revision_id)
        == published
    )
    assert len(producer.published_plan_viewports()) == 1
    (scope,) = producer.published_occurrence_results()
    (mark,) = scope.records
    assert (
        scope.status is EvidenceResolutionStatus.CORROBORATED and scope.scope_complete
    )
    assert scope.source_viewport_ownership_id
    assert scope.unresolved_source_text_observation_ids == ()
    assert mark.code == "FT9" and mark.semantic_finish == "tile"
    assert (
        mark.page_id == "1"
        and mark.viewport_id == producer.published_plan_viewports()[0].view_id
    )
    assert mark.source_sha256 == published.revision.source_sha256
    assert mark.source_text_observation_ids and mark.bbox_pdf_pts[2] < 350
    assert (
        producer.published_plan_viewports()[0].provenance[
            "whole_sheet_plan_universe_proven"
        ]
        is False
    )
    selector = semantic.SourceMaterialOccurrenceSelector(
        published.revision.document_id,
        published.revision.revision_id,
        published.revision.source_sha256,
        published.snapshot.snapshot_id,
        "1",
        mark.viewport_id,
    )
    assert authority.resolve_occurrences(selector) == scope
    assert (
        producer.publish(published.revision.revision_id).resolve_occurrences(selector)
        == scope
    )
    assert (
        authority.resolve_occurrences(replace(selector, source_sha256="f" * 64)).records
        == ()
    )


def test_positive_mark_survives_unrelated_unreadable_text_without_complete_scope():
    _, _, producer, _ = _publish(_drawing(unrelated_hidden=True))
    (scope,) = producer.published_occurrence_results()
    assert len(scope.records) == 1
    assert scope.status is EvidenceResolutionStatus.ABSTAINED
    assert (
        scope.scope_complete is False and scope.unresolved_source_text_observation_ids
    )
    assert semantic.SOURCE_MATERIAL_SCOPE_INCOMPLETE in scope.reason_codes
    assert _occurrences_on_page((scope,), page_id="1") == ()


@pytest.mark.parametrize(
    "change", ["hidden", "crossing", "occluded", "no_dictionary", "conflict"]
)
def test_hidden_partial_unowned_or_unconfirmed_lines_do_not_publish(change):
    _, _, producer, _ = _publish(_drawing(**{change: True}))
    assert _records(producer) == ()
    if change in {"hidden", "crossing", "occluded", "conflict"}:
        (scope,) = producer.published_occurrence_results()
        assert scope.scope_complete is False


@pytest.mark.parametrize(
    "layout",
    [
        {"dx": 12, "dy": 18},
        {"scale": 1.4},
        {"rotation": 90},
        {"reverse": True},
        {"split": True},
        {"expanded": True, "unrelated": True},
    ],
)
def test_source_plan_material_metamorphic_controls(layout):
    _, _, producer, _ = _publish(_drawing(**layout))
    (record,) = _records(producer)
    assert record.code == "FT9" and record.semantic_finish == "tile"
    (scope,) = producer.published_occurrence_results()
    assert scope.scope_complete and scope.source_viewport_ownership_id


def test_competing_incomplete_view_family_abstains():
    _, _, producer, _ = _publish(_drawing(second=True, second_incomplete=True))
    assert producer.published_plan_viewports() == ()
    assert _records(producer) == ()


@pytest.mark.parametrize("mode", ["copy", "foreign", "stale"])
def test_borrowed_or_stale_view_does_not_supply_material_ownership(monkeypatch, mode):
    source, published = _source(_drawing())
    views = segment_source_page_viewports(
        source,
        revision_id=published.revision.revision_id,
        page_id="1",
        physical_plan_view_shadow=True,
    )
    if mode == "copy":
        views = tuple(
            replace(v, _producer_token=None, _producer_fingerprint="") for v in views
        )
    elif mode == "foreign":
        source, published = _source(_drawing(dx=5))
    else:
        source.ingest_native_pdf_bytes(
            document_id=published.revision.document_id,
            source_bytes=_drawing(dx=5),
            source_locator="memory:new.pdf",
            page_ids=("1",),
        )
        # Use the real reader for stale source; it must not resurrect the old view.
        views = None
    if views is not None:
        monkeypatch.setattr(
            semantic, "segment_source_page_viewports", lambda *a, **k: views
        )
    producer = semantic.SourceMaterialSemanticProducer.for_physical_plan_view_shadow(
        source, page_ids=("1",)
    )
    if mode == "stale":
        with pytest.raises(ValueError, match="stale"):
            producer.publish(published.revision.revision_id)
    else:
        producer.publish(published.revision.revision_id)
    assert _records(producer) == () and producer.published_plan_viewports() == ()


@pytest.mark.parametrize("page_ids", [(), "1", ("01",), ("0",), (1,), ("-1",)])
def test_shadow_requires_canonical_explicit_source_pages(page_ids):
    source, _ = _source(_drawing())
    with pytest.raises(ValueError):
        semantic.SourceMaterialSemanticProducer.for_physical_plan_view_shadow(
            source, page_ids=page_ids
        )


def test_unknown_page_does_not_expand_requested_scope():
    _, _, producer, _ = _publish(_drawing(), page_ids=("2",))
    assert producer.published_plan_viewports() == () and _records(producer) == ()


def test_definition_authority_is_identical_between_default_and_shadow():
    data = _drawing()
    _, pub, _, default = _publish(data, enabled=False)
    _, _, _, shadow = _publish(data)
    for code in ("FT9", "PT9"):
        selector = semantic.SourceMaterialDefinitionSelector(
            pub.revision.document_id,
            pub.revision.revision_id,
            pub.revision.source_sha256,
            pub.snapshot.snapshot_id,
            code,
        )
        assert shadow.resolve_definition(selector) == default.resolve_definition(
            selector
        )


def test_replay_and_page_order_produce_stable_original_occurrence_ids():
    data = _drawing(unrelated_hidden=True)
    _, _, first, _ = _publish(data)
    _, _, second, _ = _publish(data, page_ids=("1", "1"))
    assert first.published_occurrence_results() == second.published_occurrence_results()
    assert _records(first) == _records(second)


def test_original_replay_observer_retains_failed_words_and_restores_reader():
    from tools.diag_source_plan_material_occurrences import replay

    original = semantic._recover_native_material_block
    report = replay(_drawing(unrelated_hidden=True), page_number=1)
    assert semantic._recover_native_material_block is original
    assert report["positive_material_occurrence_count"] == 1
    assert report["incomplete_scopes_rejected_by_existing_floor_consumer"]
    assert (
        report["unchanged_nominated_definition_results"]["FT9"]["status"]
        is EvidenceResolutionStatus.CORROBORATED
    )
    assert {
        row["phase"] for row in report["original_native_material_block_recovery"]
    } == {"ordinary", "physical_plan_shadow"}


def test_original_replay_observer_cannot_hide_a_source_recovery_error(monkeypatch):
    from tools.diag_source_plan_material_occurrences import replay

    def failed_reader(**kwargs):
        raise RuntimeError("original-source-recovery-error")

    monkeypatch.setattr(semantic, "_recover_native_material_block", failed_reader)
    with pytest.raises(RuntimeError, match="original-source-recovery-error"):
        replay(_drawing(), page_number=1)
    assert semantic._recover_native_material_block is failed_reader



def test_consumer_source_owned_ft3_viewport_requires_private_original_f07_product():
    """The trusted material producer, not a caller bbox, owns the view."""
    from types import SimpleNamespace
    from pb_cross_view_floor_finish_authority import (
        _source_owned_floor_finish_viewports,
    )
    source, published, producer, _authority = _publish(_drawing())
    produced = producer.published_plan_viewports()
    assert len(produced) == 1
    view = produced[0]
    key = ("1", view.view_id)
    verified = _source_owned_floor_finish_viewports(
        producer, published=published, permitted_page_ids=("1",)
    )
    assert key in verified
    assert verified[key] == tuple(view.bounding_box)
    assert not _source_owned_floor_finish_viewports(
        producer, published=published, permitted_page_ids=("2",)
    )
    def fake_viewports(*views):
        return SimpleNamespace(published_plan_viewports=lambda: views)
    # An otherwise identical, unstamped caller copy is never F07 authority.
    copied = replace(view, _producer_token=None, _producer_fingerprint="")
    assert not _source_owned_floor_finish_viewports(
        fake_viewports(copied), published=published, permitted_page_ids=("1",)
    )
    assert not _source_owned_floor_finish_viewports(
        fake_viewports(view, view), published=published, permitted_page_ids=("1",)
    )
    compromised = replace(view, provenance={
        **view.provenance, "source_sha256": "0" * 64
    })
    assert not _source_owned_floor_finish_viewports(
        fake_viewports(compromised), published=published, permitted_page_ids=("1",)
    )
    # Authenticated FT9 text in an otherwise incomplete scope cannot be used
    # by the commercial floor consumer, even with a valid F07 view.
    _s, p, incomplete, _auth = _publish(_drawing(unrelated_hidden=True))
    scope = incomplete.published_occurrence_results()[0]
    assert not scope.scope_complete
    assert len(scope.records) == 1
    assert _occurrences_on_page((scope,), page_id="1") == ()
