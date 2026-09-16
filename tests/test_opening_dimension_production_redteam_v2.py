"""Executable red-team gate for producer-bound opening figured dimensions.

Validator base: 4b7b7412eecb7c7d434ac0732184314f97c85678
Production candidate is intentionally not imported on the validator base.

The tests are controlled XFAIL only while SourceVisibilityProducer lacks the
public producer-bound factory. The same blob runs normally, without marker
suppression, when replayed on a production candidate that provides the factory.
"""
from __future__ import annotations

import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


BASE_SHA = "4b7b7412eecb7c7d434ac0732184314f97c85678"
HAS_DIMENSION_AUTHORITY = callable(
    getattr(SourceVisibilityProducer, "opening_dimension_authority", None)
)
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_DIMENSION_AUTHORITY,
    strict=True,
    reason="producer-bound opening dimension authority is absent on validator base",
)


def _transform(point: tuple[float, float], *, rotate90: bool) -> tuple[float, float]:
    if not rotate90:
        return point
    x, y = point
    return (300.0 - y, x + 20.0)


def _draw_line(page, first, second, *, rotate90=False, width=0.5):
    page.draw_line(
        fitz.Point(*_transform(first, rotate90=rotate90)),
        fitz.Point(*_transform(second, rotate90=rotate90)),
        color=(0, 0, 0),
        width=width,
    )


def _opening_pdf(
    *,
    label: str = "900",
    text_color: tuple[float, float, float] = (0.0, 0.0, 0.0),
    witnesses: bool = True,
    dimension_line: bool = True,
    second_label: str | None = None,
    second_dimension: bool = False,
    diagonal_dimension: bool = False,
    rotate90: bool = False,
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=700)
    for first, second in (
        ((20.0, 100.0), (100.0, 100.0)),
        ((140.0, 100.0), (220.0, 100.0)),
        ((20.0, 110.0), (100.0, 110.0)),
        ((140.0, 110.0), (220.0, 110.0)),
        ((100.0, 100.0), (100.0, 110.0)),
        ((140.0, 100.0), (140.0, 110.0)),
    ):
        _draw_line(page, first, second, rotate90=rotate90, width=1.0)

    dim_left = (100.0, 70.0)
    dim_right = (140.0, 80.0 if diagonal_dimension else 70.0)
    if dimension_line:
        _draw_line(page, dim_left, dim_right, rotate90=rotate90)
    if witnesses:
        _draw_line(page, dim_left, (100.0, 100.0), rotate90=rotate90)
        _draw_line(page, dim_right, (140.0, 100.0), rotate90=rotate90)

    label_point = _transform((112.0, 65.0), rotate90=rotate90)
    page.insert_text(
        fitz.Point(*label_point),
        label,
        color=text_color,
        rotate=90 if rotate90 else 0,
    )
    if second_label is not None:
        second_point = _transform((118.0, 65.0), rotate90=rotate90)
        page.insert_text(
            fitz.Point(*second_point),
            second_label,
            color=(0, 0, 0),
            rotate=90 if rotate90 else 0,
        )

    if second_dimension:
        _draw_line(page, (100.0, 45.0), (140.0, 45.0), rotate90=rotate90)
        _draw_line(page, (100.0, 45.0), (100.0, 100.0), rotate90=rotate90)
        _draw_line(page, (140.0, 45.0), (140.0, 100.0), rotate90=rotate90)
        point = _transform((112.0, 40.0), rotate90=rotate90)
        page.insert_text(
            fitz.Point(*point),
            "820",
            color=(0, 0, 0),
            rotate=90 if rotate90 else 0,
        )

    payload = doc.tobytes()
    doc.close()
    return payload


def _schedule_only_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=250)
    page.insert_text((40, 40), "DOOR SCHEDULE")
    page.insert_text((40, 70), "D-01 900 x 2100")
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest(payload: bytes, *, document_id: str):
    assert HAS_DIMENSION_AUTHORITY, "missing producer-bound dimension factory"
    producer = SourceVisibilityProducer(
        producer_method="opening-dimension-independent-redteam-v2",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published, producer.authority()


def _selector(published, observation_id: str, **changes: str) -> ObservationSelector:
    values = {
        "document_id": published.revision.document_id,
        "revision_id": published.revision.revision_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "observation_id": observation_id,
    }
    values.update(changes)
    return ObservationSelector(**values)


def _positive_selector(published, visibility) -> ObservationSelector:
    physical = PhysicalOpeningAuthority(visibility)
    positives = []
    for observation_id in published.visible_observation_ids:
        selector = _selector(published, observation_id)
        result = physical.prove_existence(selector)
        if result.proposition == PHYSICAL_OPENING_EXISTS:
            positives.append(selector)
    assert positives, "fixture must prove a physical opening"
    producer_result_ids = []
    for selector in positives:
        result = physical.prove_existence(selector)
        assert result.existence_record is not None
        producer_result_ids.append(result.existence_record.record_id)
    assert len(set(producer_result_ids)) == 1
    return positives[0]


def _assert_unresolved(result) -> None:
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.value_mm is None


@EXPECTED_RED
def test_attack01_factory_mints_read_only_selector_only_authority() -> None:
    assert BASE_SHA == "4b7b7412eecb7c7d434ac0732184314f97c85678"
    producer, _published, _visibility = _ingest(
        _opening_pdf(), document_id="odim-v2-a01"
    )
    authority = producer.opening_dimension_authority()
    assert callable(authority.resolve_width)
    assert callable(authority.resolve_height)
    assert tuple(inspect.signature(authority.resolve_width).parameters) == ("selector",)
    forbidden = (
        "ingest_native_pdf_bytes",
        "publish_derived_observation",
        "publish_dimension",
        "write",
        "deduct_wall_area",
        "publish_firm_quantity",
        "publish_commercial",
        "publish_to_jobhub",
    )
    assert all(not hasattr(authority, name) for name in forbidden)


@EXPECTED_RED
def test_attack02_visible_figured_width_with_exact_witness_topology_resolves() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(), document_id="odim-v2-a02"
    )
    selector = _positive_selector(published, visibility)
    result = producer.opening_dimension_authority().resolve_width(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.value_mm == pytest.approx(900.0)
    assert result.dimension_record_id
    assert result.opening_existence_record is not None


@EXPECTED_RED
def test_attack03_width_and_height_remain_independent() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(), document_id="odim-v2-a03"
    )
    selector = _positive_selector(published, visibility)
    authority = producer.opening_dimension_authority()
    width = authority.resolve_width(selector)
    height = authority.resolve_height(selector)
    assert width.status is EvidenceResolutionStatus.CORROBORATED
    assert width.value_mm == pytest.approx(900.0)
    _assert_unresolved(height)


@EXPECTED_RED
def test_attack04_missing_witnesses_block_nearby_numeric_text() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(witnesses=False), document_id="odim-v2-a04"
    )
    result = producer.opening_dimension_authority().resolve_width(
        _positive_selector(published, visibility)
    )
    _assert_unresolved(result)


@EXPECTED_RED
def test_attack05_hidden_white_numeric_text_cannot_resolve_width() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(text_color=(1.0, 1.0, 1.0)), document_id="odim-v2-a05"
    )
    result = producer.opening_dimension_authority().resolve_width(
        _positive_selector(published, visibility)
    )
    _assert_unresolved(result)


@EXPECTED_RED
def test_attack06_schedule_only_text_cannot_mint_instance_dimensions() -> None:
    producer, published, _visibility = _ingest(
        _schedule_only_pdf(), document_id="odim-v2-a06"
    )
    authority = producer.opening_dimension_authority()
    for observation_id in published.snapshot.observation_ids:
        _assert_unresolved(authority.resolve_width(_selector(published, observation_id)))


@EXPECTED_RED
def test_attack07_source_revision_snapshot_and_document_laundering_fail_closed() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(), document_id="odim-v2-a07"
    )
    selector = _positive_selector(published, visibility)
    authority = producer.opening_dimension_authority()
    assert authority.resolve_width(selector).status is EvidenceResolutionStatus.CORROBORATED
    for changes in (
        {"document_id": "other-document"},
        {"revision_id": "other-revision"},
        {"source_sha256": "0" * 64},
        {"snapshot_id": "other-snapshot"},
    ):
        forged = ObservationSelector(
            document_id=changes.get("document_id", selector.document_id),
            revision_id=changes.get("revision_id", selector.revision_id),
            source_sha256=changes.get("source_sha256", selector.source_sha256),
            snapshot_id=changes.get("snapshot_id", selector.snapshot_id),
            observation_id=selector.observation_id,
        )
        _assert_unresolved(authority.resolve_width(forged))


@EXPECTED_RED
def test_attack08_diagonal_line_with_jamb_projected_endpoints_is_not_a_dimension() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(diagonal_dimension=True), document_id="odim-v2-a08"
    )
    result = producer.opening_dimension_authority().resolve_width(
        _positive_selector(published, visibility)
    )
    _assert_unresolved(result)


@EXPECTED_RED
def test_attack09_conflicting_bound_numeric_labels_block() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(second_label="820"), document_id="odim-v2-a09"
    )
    result = producer.opening_dimension_authority().resolve_width(
        _positive_selector(published, visibility)
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.value_mm is None


@EXPECTED_RED
def test_attack10_competing_complete_dimension_topologies_block() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(second_dimension=True), document_id="odim-v2-a10"
    )
    result = producer.opening_dimension_authority().resolve_width(
        _positive_selector(published, visibility)
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.value_mm is None


@EXPECTED_RED
def test_attack11_geometric_gap_and_numeric_text_without_dimension_line_do_not_self_certify() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(dimension_line=False, witnesses=False), document_id="odim-v2-a11"
    )
    result = producer.opening_dimension_authority().resolve_width(
        _positive_selector(published, visibility)
    )
    _assert_unresolved(result)


@EXPECTED_RED
def test_attack12_rotated_equivalent_preserves_figured_width_authority() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(rotate90=True), document_id="odim-v2-a12"
    )
    result = producer.opening_dimension_authority().resolve_width(
        _positive_selector(published, visibility)
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.value_mm == pytest.approx(900.0)


@EXPECTED_RED
def test_attack13_same_selector_is_deterministic() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(), document_id="odim-v2-a13"
    )
    selector = _positive_selector(published, visibility)
    authority = producer.opening_dimension_authority()
    first = authority.resolve_width(selector)
    second = authority.resolve_width(selector)
    assert first == second
    assert first.status is EvidenceResolutionStatus.CORROBORATED


@EXPECTED_RED
def test_attack14_caller_cannot_construct_positive_authority_from_readers() -> None:
    producer, _published, _visibility = _ingest(
        _opening_pdf(), document_id="odim-v2-a14"
    )
    import pb_opening_dimension_authority as module

    with pytest.raises(TypeError):
        module.OpeningDimensionAuthority(
            producer.authority(), producer.text_integrity_authority()
        )


@EXPECTED_RED
def test_attack15_non_numeric_and_non_positive_labels_cannot_become_widths() -> None:
    for index, label in enumerate(("D-01", "0", "-900", "900x2100")):
        producer, published, visibility = _ingest(
            _opening_pdf(label=label), document_id=f"odim-v2-a15-{index}"
        )
        _assert_unresolved(
            producer.opening_dimension_authority().resolve_width(
                _positive_selector(published, visibility)
            )
        )


@EXPECTED_RED
def test_attack16_width_success_does_not_unlock_downstream_capabilities() -> None:
    producer, published, visibility = _ingest(
        _opening_pdf(), document_id="odim-v2-a16"
    )
    selector = _positive_selector(published, visibility)
    width = producer.opening_dimension_authority().resolve_width(selector)
    assert width.status is EvidenceResolutionStatus.CORROBORATED
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_existence"] is True
    assert caps["physical_opening_identity"] is True
    assert caps["opening_dimensions"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["host_identity"] is False
    assert caps["host_binding"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
