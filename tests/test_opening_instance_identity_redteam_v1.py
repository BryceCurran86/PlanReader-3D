from __future__ import annotations

from dataclasses import dataclass, fields
from unittest.mock import patch

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import (
    ObservationSelector,
    SNAPSHOT_MISMATCH,
    SOURCE_HASH_MISMATCH,
    STALE_REVISION,
    SourceObservationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.g17_phase2_test_support import make_resolved, selector as raw_selector


_VALIDATOR_BASE_SHA = "62a161519e617cdf9ce23069820dbf7c68aaf521"
_IDENTITIES_DISTINCT = "physical_opening_identities_distinct"
_IDENTITY_SCOPE_MISMATCH = "physical_opening_identity_scope_mismatch"
_IDENTITY_EXISTENCE_REQUIRED = "physical_opening_identity_existence_required"


@dataclass(frozen=True)
class _CallerIdentityClaim:
    selector: ObservationSelector
    opening_id: str
    record_id: str
    geometry: tuple[float, float, float, float]


def _opening_segments(*, x0: float, y: float):
    left = x0 + 80.0
    right = x0 + 120.0
    far_right = x0 + 200.0
    upper = y
    lower = y + 10.0
    return (
        ((x0, upper), (left, upper)),
        ((right, upper), (far_right, upper)),
        ((x0, lower), (left, lower)),
        ((right, lower), (far_right, lower)),
        ((left, upper), (left, lower)),
        ((right, upper), (right, lower)),
    )


def _pdf_bytes(
    *,
    openings_by_page: tuple[tuple[tuple[float, float], ...], ...],
    text_by_page: tuple[tuple[tuple[float, float, str], ...], ...] = (),
    marker: str = "",
    segment_order: tuple[int, ...] = (0, 1, 2, 3, 4, 5),
    reverse_endpoints: bool = False,
    clip_prefix: bytes | None = None,
) -> bytes:
    doc = fitz.open()
    for page_index, page_openings in enumerate(openings_by_page):
        page = doc.new_page(width=800, height=800)
        for x0, y in page_openings:
            segments = _opening_segments(x0=x0, y=y)
            for index in segment_order:
                first, second = segments[index]
                if reverse_endpoints:
                    first, second = second, first
                page.draw_line(first, second, color=(0, 0, 0), width=1)
        if page_index < len(text_by_page):
            for x, y, text in text_by_page[page_index]:
                page.insert_text((x, y), text, fontsize=10)
        if clip_prefix is not None:
            contents = page.get_contents()
            assert contents
            original = b"\n".join(doc.xref_stream(xref) for xref in contents)
            doc.update_stream(contents[0], b"q\n" + clip_prefix + b"\n" + original + b"\nQ\n")
            for xref in contents[1:]:
                doc.update_stream(xref, b"")
    if marker:
        doc.set_metadata({"title": marker})
    payload = doc.tobytes()
    doc.close()
    return payload


def _rectangle_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=240, height=240)
    for first, second in (
        ((100, 100), (140, 100)),
        ((100, 110), (140, 110)),
        ((100, 100), (100, 110)),
        ((140, 100), (140, 110)),
    ):
        page.draw_line(first, second, color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _ambiguous_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    for y in (100.0, 110.0, 120.0):
        page.draw_line((20, y), (100, y), color=(0, 0, 0), width=1)
        page.draw_line((140, y), (220, y), color=(0, 0, 0), width=1)
    for first, second in (
        ((100, 100), (100, 110)),
        ((140, 100), (140, 110)),
        ((100, 100), (100, 120)),
        ((140, 100), (140, 120)),
    ):
        page.draw_line(first, second, color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _visible_fixture(
    payload: bytes,
    *,
    document_id: str,
    producer: SourceVisibilityProducer | None = None,
):
    producer = producer or SourceVisibilityProducer(
        producer_method="opening-instance-identity-redteam-v1",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    physical = PhysicalOpeningAuthority(producer.authority())
    return producer, published, physical


def _resolved_groups(physical: PhysicalOpeningAuthority, published):
    groups: dict[str, list[ObservationSelector]] = {}
    records = {}
    for observation_id in published.visible_observation_ids:
        selector = _selector(published, observation_id)
        existence = physical.prove_existence(selector)
        if existence.proposition != PHYSICAL_OPENING_EXISTS:
            continue
        assert existence.status is EvidenceResolutionStatus.CORROBORATED
        assert existence.existence_record is not None
        record = existence.existence_record
        groups.setdefault(record.record_id, []).append(selector)
        records[record.record_id] = record
    return groups, records


def _single_opening_fixture(*, document_id: str = "identity-single"):
    producer, published, physical = _visible_fixture(
        _pdf_bytes(openings_by_page=(((20.0, 100.0),),)),
        document_id=document_id,
    )
    groups, records = _resolved_groups(physical, published)
    assert len(groups) == 1
    record_id, supports = next(iter(groups.items()))
    assert len(supports) == 6
    return producer, published, physical, record_id, supports, records[record_id]


def _two_opening_fixture(
    *,
    document_id: str,
    text: tuple[tuple[float, float, str], ...] = (),
):
    _, published, physical = _visible_fixture(
        _pdf_bytes(
            openings_by_page=(((20.0, 100.0), (20.0, 300.0)),),
            text_by_page=(text,),
        ),
        document_id=document_id,
    )
    groups, records = _resolved_groups(physical, published)
    assert len(groups) == 2
    ordered = sorted(groups.items())
    return published, physical, ordered, records


def _assert_unresolved(result) -> None:
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


def test_attack_01_same_opening_different_visible_supports_is_positive_control() -> None:
    """Two different producer-visible supports for one G17 record are one instance."""
    _, _, physical, record_id, supports, _ = _single_opening_fixture(
        document_id="attack-01-positive-control"
    )

    result = physical.compare_identity(supports[0], supports[-1])

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is True
    assert result.physical_opening_identity == record_id


def test_attack_02_same_selector_replay_is_deterministic() -> None:
    """Repeated comparison of one legitimate selector returns one stable identity."""
    _, _, physical, record_id, supports, _ = _single_opening_fixture(
        document_id="attack-02-replay"
    )

    results = tuple(physical.compare_identity(supports[0], supports[0]) for _ in range(3))

    assert results[0] == results[1] == results[2]
    assert results[0].status is EvidenceResolutionStatus.CORROBORATED
    assert results[0].proven_same is True
    assert results[0].physical_opening_identity == record_id


def test_attack_03_nearby_proven_openings_never_merge_by_centroid() -> None:
    """Two nearby openings on one wall/page remain distinct local instances."""
    _, physical, ordered, _ = _two_opening_fixture(document_id="attack-03-nearby")

    result = physical.compare_identity(ordered[0][1][0], ordered[1][1][0])

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is False
    assert result.physical_opening_identity == _IDENTITIES_DISTINCT


def test_attack_04_repeated_d01_tag_does_not_collapse_instances() -> None:
    """Equal D-01 text beside two openings is irrelevant to physical identity."""
    _, physical, ordered, _ = _two_opening_fixture(
        document_id="attack-04-repeated-tag",
        text=((250.0, 105.0, "D-01"), (250.0, 305.0, "D-01")),
    )

    result = physical.compare_identity(ordered[0][1][0], ordered[1][1][0])

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is False
    assert result.physical_opening_identity == _IDENTITIES_DISTINCT


def test_attack_05_one_schedule_row_cannot_collapse_multiple_instances() -> None:
    """One D-01 schedule row with quantity two cannot become instance identity."""
    _, physical, ordered, _ = _two_opening_fixture(
        document_id="attack-05-schedule-collapse",
        text=((500.0, 100.0, "DOOR SCHEDULE"), (500.0, 120.0, "D-01 QTY 2")),
    )

    result = physical.compare_identity(ordered[0][1][0], ordered[1][1][0])

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is False
    assert result.physical_opening_identity == _IDENTITIES_DISTINCT


def test_attack_06_ocr_text_similarity_cannot_establish_instance_equality() -> None:
    """D-01, D01 and D-O1-like text variants never merge physical openings."""
    _, physical, ordered, _ = _two_opening_fixture(
        document_id="attack-06-ocr-variants",
        text=((250.0, 105.0, "D01"), (250.0, 305.0, "D-O1")),
    )

    result = physical.compare_identity(ordered[0][1][0], ordered[1][1][0])

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is False
    assert result.physical_opening_identity == _IDENTITIES_DISTINCT


def test_attack_07_caller_opening_id_and_record_id_spoofing_have_no_authority() -> None:
    """compare_identity must independently call prove_existence for both selectors."""
    _, physical, ordered, _ = _two_opening_fixture(document_id="attack-07-id-spoof")
    left = ordered[0][1][0]
    right = ordered[1][1][0]
    spoofed_left = _CallerIdentityClaim(left, "same-id", "same-record", (0, 0, 1, 1))
    spoofed_right = _CallerIdentityClaim(right, "same-id", "same-record", (0, 0, 1, 1))

    with pytest.raises(TypeError):
        physical.compare_identity(spoofed_left, spoofed_right)  # type: ignore[arg-type]

    with patch.object(physical, "prove_existence", wraps=physical.prove_existence) as prove:
        result = physical.compare_identity(left, right)

    assert [call.args for call in prove.call_args_list] == [(left,), (right,)]
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is False


def test_attack_08_caller_geometry_cannot_override_producer_identity() -> None:
    """Identical caller boxes/centroids for distinct openings have no authority."""
    _, physical, ordered, _ = _two_opening_fixture(document_id="attack-08-geometry-spoof")
    left = ordered[0][1][0]
    right = ordered[1][1][0]
    same_geometry = (100.0, 100.0, 140.0, 110.0)
    left_claim = _CallerIdentityClaim(left, "left", "left-record", same_geometry)
    right_claim = _CallerIdentityClaim(right, "right", "right-record", same_geometry)

    with pytest.raises(TypeError):
        physical.compare_identity(left_claim, right_claim)  # type: ignore[arg-type]
    result = physical.compare_identity(left, right)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is False


def test_attack_09_identical_geometry_in_different_documents_abstains() -> None:
    """No cross-document equality exists without a separate equivalence authority."""
    producer = SourceVisibilityProducer(
        producer_method="opening-instance-identity-redteam-v1",
        producer_version="1.0",
    )
    payload = _pdf_bytes(openings_by_page=(((20.0, 100.0),),))
    _, left_published, _ = _visible_fixture(payload, document_id="attack-09-doc-a", producer=producer)
    _, right_published, physical = _visible_fixture(payload, document_id="attack-09-doc-b", producer=producer)
    left_groups, _ = _resolved_groups(physical, left_published)
    right_groups, _ = _resolved_groups(physical, right_published)

    result = physical.compare_identity(
        next(iter(left_groups.values()))[0],
        next(iter(right_groups.values()))[0],
    )

    _assert_unresolved(result)
    assert _IDENTITY_SCOPE_MISMATCH in result.reason_codes


def test_attack_10_identical_geometry_on_different_pages_abstains() -> None:
    """No cross-page equality exists without an independent reference authority."""
    _, published, physical = _visible_fixture(
        _pdf_bytes(openings_by_page=(((20.0, 100.0),), ((20.0, 100.0),))),
        document_id="attack-10-pages",
    )
    groups, records = _resolved_groups(physical, published)
    by_page = {records[record_id].page_id: supports[0] for record_id, supports in groups.items()}
    assert len(by_page) == 2
    selectors = [selector for _, selector in sorted(by_page.items())]

    result = physical.compare_identity(selectors[0], selectors[1])

    _assert_unresolved(result)
    assert _IDENTITY_SCOPE_MISMATCH in result.reason_codes


def test_attack_11_revision_laundering_abstains() -> None:
    """Same apparent geometry in two revisions does not imply one instance."""
    producer = SourceVisibilityProducer(
        producer_method="opening-instance-identity-redteam-v1",
        producer_version="1.0",
    )
    first = producer.ingest_native_pdf_bytes(
        document_id="attack-11-revision",
        source_bytes=_pdf_bytes(openings_by_page=(((20.0, 100.0),),), marker="revision-a"),
        source_locator="memory://attack-11-a.pdf",
    )
    first_physical = PhysicalOpeningAuthority(producer.authority())
    first_groups, _ = _resolved_groups(first_physical, first)
    assert len(first_groups) == 1
    first_selector = next(iter(first_groups.values()))[0]
    second = producer.ingest_native_pdf_bytes(
        document_id="attack-11-revision",
        source_bytes=_pdf_bytes(openings_by_page=(((20.0, 100.0),),), marker="revision-b"),
        source_locator="memory://attack-11-b.pdf",
    )
    physical = PhysicalOpeningAuthority(producer.authority())
    second_groups, _ = _resolved_groups(physical, second)
    assert len(second_groups) == 1

    result = physical.compare_identity(
        first_selector,
        next(iter(second_groups.values()))[0],
    )

    _assert_unresolved(result)
    assert STALE_REVISION in result.reason_codes
    assert _IDENTITY_EXISTENCE_REQUIRED in result.reason_codes
    assert _IDENTITY_SCOPE_MISMATCH not in result.reason_codes


def test_attack_12_source_sha_laundering_fails_closed() -> None:
    """A caller cannot pair a valid observation with incompatible source bytes."""
    _, published, physical, _, supports, _ = _single_opening_fixture(
        document_id="attack-12-source-sha"
    )
    left = supports[0]
    forged = ObservationSelector(
        document_id=left.document_id,
        revision_id=left.revision_id,
        source_sha256="f" * 64,
        snapshot_id=left.snapshot_id,
        observation_id=left.observation_id,
    )

    result = physical.compare_identity(left, forged)

    _assert_unresolved(result)
    assert SOURCE_HASH_MISMATCH in result.reason_codes
    assert _IDENTITY_EXISTENCE_REQUIRED in result.reason_codes
    assert _IDENTITY_SCOPE_MISMATCH not in result.reason_codes


def test_attack_13_snapshot_laundering_fails_closed() -> None:
    """A valid support cannot be replayed under an incompatible snapshot owner."""
    _, _, physical, _, supports, _ = _single_opening_fixture(
        document_id="attack-13-snapshot"
    )
    left = supports[0]
    forged = ObservationSelector(
        document_id=left.document_id,
        revision_id=left.revision_id,
        source_sha256=left.source_sha256,
        snapshot_id="caller-forged-snapshot",
        observation_id=left.observation_id,
    )

    result = physical.compare_identity(left, forged)

    _assert_unresolved(result)
    assert SNAPSHOT_MISMATCH in result.reason_codes
    assert _IDENTITY_EXISTENCE_REQUIRED in result.reason_codes
    assert _IDENTITY_SCOPE_MISMATCH not in result.reason_codes


def test_attack_14_raw_native_geometry_cannot_establish_identity() -> None:
    """Raw-native-only geometry has no G17 existence and therefore no identity."""
    payload = _pdf_bytes(openings_by_page=(((20.0, 100.0),),))
    producer = SourceObservationProducer(
        producer_method="opening-instance-identity-redteam-raw",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="attack-14-raw",
        source_bytes=payload,
        source_locator="memory://attack-14-raw.pdf",
    )
    physical = PhysicalOpeningAuthority(producer.authority())
    raw_ids = list(published.snapshot.observation_ids)
    assert len(raw_ids) >= 2

    result = physical.compare_identity(
        _selector(published, raw_ids[0]),
        _selector(published, raw_ids[1]),
    )

    _assert_unresolved(result)
    assert _IDENTITY_EXISTENCE_REQUIRED in result.reason_codes


def test_attack_15_caller_derived_structural_semantics_cannot_create_identity() -> None:
    """Legacy wall-face/jamb labels remain non-authoritative for identity."""
    _, published, _, physical, _, snapshot_id = make_resolved()

    result = physical.compare_identity(
        raw_selector(published, snapshot_id, "face-a"),
        raw_selector(published, snapshot_id, "jamb-left"),
    )

    _assert_unresolved(result)


def test_attack_16_rectangle_only_non_opening_cannot_acquire_identity() -> None:
    """A closed rectangle without wall continuation is not an opening instance."""
    _, published, physical = _visible_fixture(
        _rectangle_pdf_bytes(), document_id="attack-16-rectangle"
    )
    assert len(published.visible_observation_ids) == 4

    result = physical.compare_identity(
        _selector(published, published.visible_observation_ids[0]),
        _selector(published, published.visible_observation_ids[1]),
    )

    _assert_unresolved(result)


@pytest.mark.parametrize(
    "clip_prefix",
    (
        b"0 0 20 20 re W n",
        b"90 120 m 150 120 l 120 170 l h W n",
    ),
)
def test_attack_17_clipped_or_unresolved_geometry_cannot_acquire_identity(
    clip_prefix: bytes,
) -> None:
    """Fully clipped and unresolved non-rectangular clipping both fail closed."""
    _, published, physical = _visible_fixture(
        _pdf_bytes(
            openings_by_page=(((20.0, 100.0),),),
            clip_prefix=clip_prefix,
        ),
        document_id=f"attack-17-{len(clip_prefix)}",
    )
    assert published.visible_observation_ids == ()
    forged = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id="caller-replayed-clipped-support",
    )

    result = physical.compare_identity(forged, forged)

    _assert_unresolved(result)


def test_attack_18_shared_or_replayed_support_cannot_manufacture_instances() -> None:
    """Repackaging one support cannot create two records; the source selector stays one."""
    _, _, physical, record_id, supports, _ = _single_opening_fixture(
        document_id="attack-18-replayed-support"
    )
    support = supports[0]
    first_claim = _CallerIdentityClaim(support, "derived-a", "caller-record-a", (0, 0, 1, 1))
    second_claim = _CallerIdentityClaim(support, "derived-b", "caller-record-b", (2, 2, 3, 3))

    with pytest.raises(TypeError):
        physical.compare_identity(first_claim, second_claim)  # type: ignore[arg-type]
    result = physical.compare_identity(support, support)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is True
    assert result.physical_opening_identity == record_id


def test_attack_19_source_primitive_input_order_is_deterministic() -> None:
    """Shuffling native primitive order preserves the same within-snapshot identity result."""
    outcomes = []
    for label, order in (
        ("forward", (0, 1, 2, 3, 4, 5)),
        ("shuffled", (4, 1, 5, 0, 3, 2)),
    ):
        _, published, physical = _visible_fixture(
            _pdf_bytes(
                openings_by_page=(((20.0, 100.0),),),
                segment_order=order,
            ),
            document_id=f"attack-19-{label}",
        )
        groups, _ = _resolved_groups(physical, published)
        assert len(groups) == 1
        record_id, supports = next(iter(groups.items()))
        result = physical.compare_identity(supports[0], supports[-1])
        outcomes.append((result.status, result.proven_same, result.physical_opening_identity == record_id))

    assert outcomes == [
        (EvidenceResolutionStatus.CORROBORATED, True, True),
        (EvidenceResolutionStatus.CORROBORATED, True, True),
    ]


def test_attack_20_endpoint_direction_reversal_preserves_identity_result() -> None:
    """Reversing every equivalent line endpoint preserves G17 and identity."""
    outcomes = []
    for label, reversed_endpoints in (("normal", False), ("reversed", True)):
        _, published, physical = _visible_fixture(
            _pdf_bytes(
                openings_by_page=(((20.0, 100.0),),),
                reverse_endpoints=reversed_endpoints,
            ),
            document_id=f"attack-20-{label}",
        )
        groups, _ = _resolved_groups(physical, published)
        assert len(groups) == 1
        record_id, supports = next(iter(groups.items()))
        result = physical.compare_identity(supports[0], supports[-1])
        outcomes.append((result.status, result.proven_same, result.physical_opening_identity == record_id))

    assert outcomes == [
        (EvidenceResolutionStatus.CORROBORATED, True, True),
        (EvidenceResolutionStatus.CORROBORATED, True, True),
    ]


def test_attack_21_ambiguous_existence_conflict_is_preserved() -> None:
    """Competing G17 candidates must not be resolved by first/nearest/smallest."""
    _, published, physical = _visible_fixture(
        _ambiguous_pdf_bytes(), document_id="attack-21-ambiguous"
    )
    conflicts = []
    for observation_id in published.visible_observation_ids:
        selector = _selector(published, observation_id)
        existence = physical.prove_existence(selector)
        if existence.status is EvidenceResolutionStatus.CONFLICT:
            conflicts.append(selector)
            assert AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES in existence.reason_codes
    assert conflicts

    result = physical.compare_identity(conflicts[0], conflicts[0])

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.proven_same is False
    assert AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES in result.reason_codes


def test_attack_22_cross_view_similarity_does_not_create_equivalence() -> None:
    """A similar plan and elevation/detail opening require cross-view authority."""
    _, published, physical = _visible_fixture(
        _pdf_bytes(
            openings_by_page=(((20.0, 100.0),), ((20.0, 100.0),)),
            text_by_page=(((500.0, 50.0, "PLAN"),), ((500.0, 50.0, "ELEVATION"),)),
        ),
        document_id="attack-22-cross-view",
    )
    groups, records = _resolved_groups(physical, published)
    by_page = {records[record_id].page_id: supports[0] for record_id, supports in groups.items()}
    selectors = [selector for _, selector in sorted(by_page.items())]
    assert len(selectors) == 2

    result = physical.compare_identity(selectors[0], selectors[1])

    _assert_unresolved(result)
    assert _IDENTITY_SCOPE_MISMATCH in result.reason_codes


def test_attack_23_identity_does_not_open_any_downstream_firewall() -> None:
    """Identity alone leaves dimensions, type, host, void, quantity and publication closed."""
    assert _VALIDATOR_BASE_SHA == "62a161519e617cdf9ce23069820dbf7c68aaf521"
    _, _, physical, _, supports, existence_record = _single_opening_fixture(
        document_id="attack-23-downstream-firewall"
    )

    identity = physical.compare_identity(supports[0], supports[1])

    assert identity.status is EvidenceResolutionStatus.CORROBORATED
    assert identity.proven_same is True
    assert physical.capabilities() == {
        "physical_opening_existence": True,
        "physical_opening_identity": True,
        "opening_universe_complete": False,
        "opening_dimensions": False,
        "host_identity": False,
        "host_binding": False,
        "physical_void": False,
        "net_wall_area": False,
    }

    forbidden_fields = {
        "physical_opening_identity",
        "width",
        "height",
        "area",
        "type",
        "type_id",
        "schedule_identity",
        "host",
        "host_id",
        "host_wall_id",
        "host_binding",
        "opening_universe_complete",
        "physical_void",
        "deduction",
        "deduction_authority",
        "net_wall_area",
        "firm",
        "firm_quantity",
        "commercial_publication",
        "jobhub_publication",
        "publishable",
    }
    assert {field.name for field in fields(existence_record)}.isdisjoint(forbidden_fields)
    for forbidden_method in (
        "resolve_dimensions",
        "resolve_type_properties",
        "bind_host",
        "deduct_wall_area",
        "publish_firm_quantity",
        "publish_commercial",
        "publish_to_jobhub",
        "jobhub_publish",
    ):
        assert not hasattr(physical, forbidden_method)


