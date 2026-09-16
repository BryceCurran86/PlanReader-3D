"""Production regressions for schedule-row and physical-opening height authority."""
from __future__ import annotations

import dataclasses
import inspect

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_height_authority import (
    OpeningHeightAuthority,
    OpeningHeightProducer,
    OpeningHeightSelector,
)
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_schedule_opening_instance_binding_authority import (
    BINDING_AMBIGUOUS_ROWS,
    ScheduleOpeningInstanceBindingProducer,
)
from pb_schedule_row_height_authority import (
    HEIGHT_BASIS_UNPROVEN,
    HEIGHT_FIELD_UNAVAILABLE,
    HEIGHT_ROW_UNAVAILABLE,
    HEIGHT_UNITS_CONFLICT,
    HEIGHT_UNITS_UNPROVEN,
    ScheduleRowHeightAuthority,
    ScheduleRowHeightProducer,
    ScheduleRowHeightSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_schedule_opening_instance_binding_authority_v1 import (
    _ingest,
    _opening_selector,
    _tag_pdf,
)

# Compact headings are deliberate: SourceVisibilityProducer exposes native words,
# so one source token must carry the column meaning rather than tests relying on
# caller-side phrase grouping. The schedule parser explicitly supports RO+WDTH/HT.
VALID_MM_SCHEDULE = (
    ("MARK", "ROWDTH-MM", "ROHT-MM"),
    ("W1", "900", "2100"),
)
VALID_EXPLICIT_M_SCHEDULE = (
    ("MARK", "ROWDTH-M", "ROHT-M"),
    ("W1", "0.9m", "2.1m"),
)


def _fixture(schedule_rows=VALID_MM_SCHEDULE):
    payload = _tag_pdf(schedule_rows=schedule_rows)
    src = SourceVisibilityProducer(
        producer_method="height-production-test",
        producer_version="1.0",
    )
    published = _ingest(src, payload, "height-production-test")
    observation_selector = _opening_selector(published, src.authority())
    physical = PhysicalOpeningAuthority(src.authority()).prove_existence(
        observation_selector
    )
    assert physical.existence_record is not None

    binding_producer = (
        ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    )
    binding_result = binding_producer.publish_scope(
        opening_selector=observation_selector,
        decision_scope_id="height-scope",
    )

    height_selector = OpeningHeightSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id="height-scope",
        opening_record_id=physical.existence_record.record_id,
    )
    row_height_producer = ScheduleRowHeightProducer.from_source_visibility_producer(src)
    return (
        src,
        binding_producer,
        binding_result,
        row_height_producer,
        height_selector,
    )


def _publish_row(binding_result, row_height_producer):
    assert binding_result.record is not None
    selector = ScheduleRowHeightSelector(
        document_id=binding_result.record.document_id,
        revision_id=binding_result.record.revision_id,
        source_sha256=binding_result.record.source_sha256,
        snapshot_id=binding_result.record.snapshot_id,
        schedule_page_id=binding_result.record.schedule_page_id,
        schedule_row_observation_ids=binding_result.record.schedule_row_observation_ids,
    )
    return selector, row_height_producer.publish_scope(selector)


def _height_producer(src, binding_producer, row_height_producer):
    return OpeningHeightProducer.from_authorities(
        src,
        binding_producer.authority(),
        row_height_producer.authority(),
    )


def test_producers_and_authorities_are_sealed() -> None:
    src = SourceVisibilityProducer(producer_method="seal-test", producer_version="1.0")
    with pytest.raises(TypeError):
        ScheduleRowHeightProducer(src)
    with pytest.raises(ValueError):
        ScheduleRowHeightAuthority({}, _seal=object())
    with pytest.raises(ValueError):
        OpeningHeightAuthority({}, _seal=object())


def test_opening_height_surface_has_no_caller_height_or_evidence_input() -> None:
    params = set(inspect.signature(OpeningHeightProducer.publish_scope).parameters)
    assert params == {"self", "selector"}
    assert not ({"height", "height_mm", "evidence", "units", "basis"} & params)


def test_fake_upstream_authorities_are_rejected_by_exact_type() -> None:
    src, binding, binding_result, row_height, _selector = _fixture()
    _publish_row(binding_result, row_height)
    with pytest.raises(TypeError):
        OpeningHeightProducer.from_authorities(src, object(), row_height.authority())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        OpeningHeightProducer.from_authorities(src, binding.authority(), object())  # type: ignore[arg-type]


def test_explicit_rough_opening_mm_height_resolves_and_replays() -> None:
    src, binding, binding_result, row_height, selector = _fixture()
    row_selector, row_result = _publish_row(binding_result, row_height)
    assert row_result.status is EvidenceResolutionStatus.CORROBORATED
    assert row_result.evidence is not None
    assert row_result.evidence.height_mm == 2100.0
    assert row_result.evidence.units == "mm"
    assert row_result.evidence.source_units == "mm"
    assert row_result.evidence.dimension_basis == "rough_opening"
    assert row_result.evidence.header_observation_ids
    assert row_height.authority().resolve(row_selector) == row_result

    producer = _height_producer(src, binding, row_height)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.height_mm == 2100.0
    assert result.evidence.units == "mm"
    assert result.evidence.dimension_basis == "rough_opening"
    assert result.evidence.schedule_header_observation_ids
    assert producer.authority().resolve(selector) == result


def test_explicit_metres_are_normalized_only_when_source_states_metres() -> None:
    src, binding, binding_result, row_height, selector = _fixture(
        VALID_EXPLICIT_M_SCHEDULE
    )
    _row_selector, row_result = _publish_row(binding_result, row_height)
    assert row_result.status is EvidenceResolutionStatus.CORROBORATED
    assert row_result.evidence is not None
    assert row_result.evidence.height_mm == 2100.0
    assert row_result.evidence.source_units == "m"

    producer = _height_producer(src, binding, row_height)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.height_mm == 2100.0


def test_generic_width_height_headers_do_not_prove_physical_height_basis() -> None:
    src, _binding, binding_result, row_height, _selector = _fixture(
        (("MARK", "WIDTH-MM", "HEIGHT-MM"), ("W1", "900", "2100"))
    )
    del src
    _row_selector, result = _publish_row(binding_result, row_height)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert HEIGHT_BASIS_UNPROVEN in result.reason_codes


def test_rough_opening_basis_without_explicit_units_abstains() -> None:
    _src, _binding, binding_result, row_height, _selector = _fixture(
        (("MARK", "ROWDTH", "ROHT"), ("W1", "900", "2100"))
    )
    _row_selector, result = _publish_row(binding_result, row_height)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert HEIGHT_UNITS_UNPROVEN in result.reason_codes


def test_frame_height_is_not_wall_void_height() -> None:
    _src, _binding, binding_result, row_height, _selector = _fixture(
        (("MARK", "FRAMEWDTH-MM", "FRAMEHT-MM"), ("W1", "900", "2100"))
    )
    _row_selector, result = _publish_row(binding_result, row_height)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert HEIGHT_BASIS_UNPROVEN in result.reason_codes


def test_conflicting_header_and_row_units_fail_closed() -> None:
    _src, _binding, binding_result, row_height, _selector = _fixture(
        (
            ("MARK", "ROWDTH-MM", "ROHT-MM"),
            ("W1", "0.9m", "2.1m"),
        )
    )
    _row_selector, result = _publish_row(binding_result, row_height)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert HEIGHT_UNITS_CONFLICT in result.reason_codes


def test_missing_height_never_defaults_to_2040_or_2100() -> None:
    src, binding, binding_result, row_height, selector = _fixture(
        (
            ("MARK", "ROWDTH-MM", "ROHT-MM"),
            ("W1", "900", ""),
        )
    )
    _row_selector, row_result = _publish_row(binding_result, row_height)
    assert row_result.status is EvidenceResolutionStatus.ABSTAINED
    assert HEIGHT_FIELD_UNAVAILABLE in row_result.reason_codes

    producer = _height_producer(src, binding, row_height)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert HEIGHT_FIELD_UNAVAILABLE in result.reason_codes


def test_typical_text_does_not_become_height() -> None:
    _src, _binding, binding_result, row_height, _selector = _fixture(
        (
            ("MARK", "ROWDTH-MM", "ROHT-MM"),
            ("W1", "900", "TYPICAL"),
        )
    )
    _row_selector, result = _publish_row(binding_result, row_height)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert HEIGHT_FIELD_UNAVAILABLE in result.reason_codes


def test_duplicate_matching_rows_remain_upstream_conflict() -> None:
    src, binding, binding_result, row_height, selector = _fixture(
        (
            ("MARK", "ROWDTH-MM", "ROHT-MM"),
            ("W1", "900", "2100"),
            ("W1", "900", "2100"),
        )
    )
    assert binding_result.status is EvidenceResolutionStatus.CONFLICT
    producer = _height_producer(src, binding, row_height)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in result.reason_codes


def test_wrong_lineage_abstains_without_reusing_valid_height() -> None:
    src, binding, binding_result, row_height, selector = _fixture()
    _publish_row(binding_result, row_height)
    producer = _height_producer(src, binding, row_height)
    valid = producer.publish_scope(selector)
    assert valid.status is EvidenceResolutionStatus.CORROBORATED

    for tampered in (
        dataclasses.replace(selector, revision_id="wrong-revision"),
        dataclasses.replace(selector, source_sha256="wrong-sha"),
        dataclasses.replace(selector, snapshot_id="wrong-snapshot"),
        dataclasses.replace(selector, opening_record_id="wrong-opening"),
    ):
        result = producer.publish_scope(tampered)
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.evidence is None


def test_unpublished_row_selector_cannot_mint_height() -> None:
    _src, _binding, binding_result, row_height, _selector = _fixture()
    assert binding_result.record is not None
    wrong = ScheduleRowHeightSelector(
        document_id=binding_result.record.document_id,
        revision_id=binding_result.record.revision_id,
        source_sha256=binding_result.record.source_sha256,
        snapshot_id=binding_result.record.snapshot_id,
        schedule_page_id=binding_result.record.schedule_page_id,
        schedule_row_observation_ids=("caller-invented-row",),
    )
    result = row_height.publish_scope(wrong)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert HEIGHT_ROW_UNAVAILABLE in result.reason_codes
