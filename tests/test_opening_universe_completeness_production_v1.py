from __future__ import annotations

from dataclasses import dataclass

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessProducer,
    OpeningUniverseSelector,
)
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import SourceDecodeCoverageRecord


SHA = "a" * 64


@dataclass(frozen=True)
class Primitive:
    primitive_id: str
    page_id: str
    geometry: tuple[float, float, float, float]
    layer: str = ""
    clip_known: bool = True
    clip_present: bool = False
    clip: tuple[float, float, float, float] | None = None


SOURCE = (
    Primitive("a", "page-1", (0.0, 0.0, 10.0, 0.0)),
    Primitive("b", "page-1", (20.0, 0.0, 30.0, 0.0)),
)


def _coverage(*, complete: bool = True):
    return SourceDecodeCoverageRecord(
        document_id="doc",
        revision_id="R1",
        total_pages=1,
        decoded_pages=(1,) if complete else (),
        failed_pages=() if complete else (1,),
        state="complete" if complete else "partial",
    )


def _publish(
    *,
    source=SOURCE,
    enumerated=SOURCE,
    complete=True,
    viewport_id=None,
    optional_content_state="known_visible",
    truncated=False,
):
    producer = OpeningUniverseCompletenessProducer(
        producer_method="production-test", producer_version="1.0"
    )
    result = producer.publish_enumeration(
        decision_scope_id="scope",
        decision_scope_kind="opening_host_competitor_universe",
        document_id="doc",
        revision_id="R1",
        source_sha256=SHA,
        snapshot_id="snap",
        page_ids=("page-1",),
        viewport_id=viewport_id,
        coverage=_coverage(complete=complete),
        source_primitives=source,
        enumerated_primitives=enumerated,
        optional_content_state=optional_content_state,
        xobject_traversal_truncated=truncated,
    )
    selector = OpeningUniverseSelector(
        document_id="doc",
        revision_id="R1",
        source_sha256=SHA,
        snapshot_id="snap",
        decision_scope_id="scope",
    )
    return producer, result, producer.authority().resolve(selector)


def test_full_page_matching_universe_resolves_deterministically() -> None:
    producer, published, first = _publish()
    second = producer.authority().resolve(
        OpeningUniverseSelector("doc", "R1", SHA, "snap", "scope")
    )
    assert published == first == second
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert first.source_decode_complete is True
    assert first.semantic_enumeration_complete is True
    assert first.decision_scope_complete is True
    assert first.record is not None
    assert first.record.enumeration_state == "complete"


def test_missing_member_partial_decode_and_local_viewport_fail_closed() -> None:
    _p1, _r1, missing = _publish(enumerated=SOURCE[:-1])
    assert missing.status is not EvidenceResolutionStatus.CORROBORATED
    assert missing.semantic_enumeration_complete is False

    _p2, _r2, partial = _publish(complete=False)
    assert partial.status is not EvidenceResolutionStatus.CORROBORATED
    assert partial.source_decode_complete is False

    _p3, _r3, local = _publish(viewport_id="vp-local")
    assert local.status is not EvidenceResolutionStatus.CORROBORATED
    assert local.decision_scope_complete is False


def test_clip_optional_content_and_xobject_uncertainty_fail_closed() -> None:
    unknown = tuple(
        Primitive(p.primitive_id, p.page_id, p.geometry, clip_known=False)
        for p in SOURCE
    )
    assert _publish(source=unknown, enumerated=unknown)[2].status is not EvidenceResolutionStatus.CORROBORATED
    assert _publish(optional_content_state="ambiguous")[2].status is not EvidenceResolutionStatus.CORROBORATED
    assert _publish(truncated=True)[2].status is not EvidenceResolutionStatus.CORROBORATED


def test_selector_laundering_and_direct_authority_construction_fail() -> None:
    producer, _published, _resolved = _publish()
    authority = producer.authority()
    forged = OpeningUniverseSelector("doc", "R1", "b" * 64, "snap", "scope")
    assert authority.resolve(forged).status is not EvidenceResolutionStatus.CORROBORATED
    with pytest.raises(TypeError):
        OpeningUniverseCompletenessAuthority({})


def test_duplicate_members_do_not_inflate_and_segmentation_is_invariant() -> None:
    duplicates = SOURCE + SOURCE
    _p, _r, duplicate_result = _publish(enumerated=duplicates)
    assert duplicate_result.status is EvidenceResolutionStatus.CORROBORATED
    assert duplicate_result.record is not None
    assert len(duplicate_result.record.accounted_member_ids) == 2

    one = (Primitive("whole", "page-1", (0.0, 0.0, 10.0, 0.0)),)
    split = (
        Primitive("left", "page-1", (0.0, 0.0, 5.0, 0.0)),
        Primitive("right", "page-1", (5.0, 0.0, 10.0, 0.0)),
    )
    first = _publish(source=one, enumerated=one)[2]
    second = _publish(source=split, enumerated=split)[2]
    assert first.status is second.status is EvidenceResolutionStatus.CORROBORATED
    assert first.record is not None and second.record is not None
    assert first.record.universe_fingerprint == second.record.universe_fingerprint


def test_completeness_success_does_not_unlock_downstream_capabilities() -> None:
    result = _publish()[2]
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["opening_universe_complete"] is False
    assert caps["opening_dimensions"] is False
    assert caps["host_identity"] is False
    assert caps["host_binding"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
