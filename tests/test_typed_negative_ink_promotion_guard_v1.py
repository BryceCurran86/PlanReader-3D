"""Default-off typed negative ink promotion guard (#4764 7215037181, geometry task C05). Synthetic only."""
from __future__ import annotations

import fitz
import pytest

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    TYPED_NEGATIVE_NON_WALL_INK,
    _withhold_typed_negative_ink,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
    _decision_scope_id,
)
from pb_physical_wall_identity import PhysicalWallIdentity, resolve_physical_wall_equivalence
from pb_source_visibility_authority import SourceVisibilityProducer

BLACK, GREEN, GREY = (0.0, 0.0, 0.0), (0.0, 0.6, 0.0), (0.55, 0.55, 0.55)


def _pdf(*, dx=0.0, scale=1.0, reverse=False):
    """Four lines that never overlap lengthwise, so none compete: black, green, grey and a black horizontal."""
    document = fitz.open()
    page = document.new_page(width=900 * scale + dx, height=800 * scale)
    strokes = [((50, 50), (50, 180), BLACK), ((250, 220), (250, 380), GREEN), ((450, 420), (450, 580), GREY),
               ((550, 700), (800, 700), BLACK)]
    for start, end, colour in (reversed(strokes) if reverse else strokes):
        page.draw_line((start[0] * scale + dx, start[1] * scale), (end[0] * scale + dx, end[1] * scale),
                       color=colour, width=1)
    data = document.tobytes()
    document.close()
    return data


def _scope(data, guard=None):
    source = SourceVisibilityProducer(producer_method="negative-ink-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="negative-ink", source_bytes=data,
                                               source_locator="memory://ink.pdf", page_ids=("1",))
    authority = (PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=("1",)) if guard is None
                 else PhysicalWallCandidateProducer.from_source_visibility_typed_negative_ink_guard_shadow(
                     source, guard=guard, page_ids=("1",))).authority()
    return authority.resolve_scope(PhysicalWallCandidateSelector(
        document_id="negative-ink", revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id, page_id="1",
        decision_scope_id=_decision_scope_id("1")))


def _published_x(scope, data_dx=0.0, scale=1.0):
    """Source x of each published wall's first point, back in the unmoved frame."""
    records = {r.wall_candidate_id: r for r in scope.records}
    return sorted(round((records[w].wall_candidate.centerline_pts[0][0] - data_dx) / scale)
                  for w in scope.equivalence.representative_wall_ids)


def test_default_off_publishes_every_ink_and_the_records_never_change():
    data = _pdf()
    plain = _scope(data)
    guarded = _scope(data, "unfilled_non_wall_ink")
    assert _published_x(plain) == [50, 250, 450, 550]
    assert [r.wall_candidate_id for r in plain.records] == [r.wall_candidate_id for r in guarded.records]
    assert plain.equivalence.pair_classifications == guarded.equivalence.pair_classifications


@pytest.mark.parametrize("guard, withheld", [("owner_green_ink", {250}), ("unfilled_non_wall_ink", {250, 450})])
def test_each_mode_withholds_only_its_ink_with_a_typed_reason(guard, withheld):
    data = _pdf()
    plain, guarded = _scope(data), _scope(data, guard)
    assert set(_published_x(plain)) - set(_published_x(guarded)) == withheld
    assert set(guarded.equivalence.representative_wall_ids) < set(plain.equivalence.representative_wall_ids)
    demoted = set(plain.equivalence.representative_wall_ids) - set(guarded.equivalence.representative_wall_ids)
    for wall_id in demoted:
        assert TYPED_NEGATIVE_NON_WALL_INK in guarded.equivalence.blocking_reasons_by_wall_id[wall_id]
        assert wall_id in guarded.equivalence.abstained_wall_ids


@pytest.mark.parametrize("kwargs", [dict(dx=37.5), dict(scale=2.0), dict(reverse=True)], ids=["move", "scale", "order"])
def test_the_guard_is_invariant_to_moving_scaling_and_order(kwargs):
    guarded = _scope(_pdf(**kwargs), "unfilled_non_wall_ink")
    base = _scope(_pdf(), "unfilled_non_wall_ink")
    assert _published_x(guarded, kwargs.get("dx", 0.0), kwargs.get("scale", 1.0)) == _published_x(base)


def test_an_unknown_mode_is_refused_and_the_composer_forwards_the_guard():
    with pytest.raises(ValueError):
        _scope(_pdf(), "black_only")
    data = _pdf()
    source = SourceVisibilityProducer(producer_method="negative-ink-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="negative-ink", source_bytes=data,
                                               source_locator="memory://ink.pdf", page_ids=("1",))
    results = []
    for guard in (None, "unfilled_non_wall_ink"):
        composition = compose_live_wall_opening_authority(
            source_visibility_producer=source, revision_id=published.revision.revision_id, page_ids=("1",),
            typed_negative_ink_promotion_guard=guard)
        (trace,) = composition.wall_scopes
        selector = PhysicalWallCandidateSelector(
            document_id="negative-ink", revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=source.published_snapshot_for_revision(published.revision.revision_id).snapshot.snapshot_id,
            page_id="1", decision_scope_id=_decision_scope_id("1"))
        results.append(len(composition.physical_wall_candidate_authority.resolve_scope(selector)
                           .equivalence.representative_wall_ids))
    assert results[1] == results[0] - 2


def test_only_a_wall_drawn_entirely_with_negative_ink_is_withheld():
    def wall(wall_id, x, *primitives):  # x ranges never overlap, so the walls do not compete
        return PhysicalWallIdentity(wall_candidate_id=wall_id, viewport_id="vp", candidate_identity_id=f"c-{wall_id}",
                                    path_fingerprint=((x, 0.0), (x + 50.0, 0.0)), source_primitive_ids=primitives,
                                    edge_ids=tuple(f"e-{p}" for p in primitives),
                                    status=EvidenceResolutionStatus.CORROBORATED, level_id=None)

    identities = [wall("mixed", 0.0, "d0i0", "d1i0"), wall("negative", 900.0, "d2i0")]
    equivalence = resolve_physical_wall_equivalence(identities)
    assert equivalence.representative_wall_ids == ("mixed", "negative")
    result = _withhold_typed_negative_ink(equivalence, identities, frozenset({"d1i0", "d2i0"}))
    assert result.representative_wall_ids == ("mixed",)
