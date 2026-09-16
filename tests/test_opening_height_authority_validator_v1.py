"""Opening-height authority validator v1.

TEST ONLY / EXPECTED RED / DO NOT MERGE.

The positive proposition requires the merged #383 exact opening->schedule-row
binding plus a separate producer-owned proof that the bound row contains an
explicit rough/structural-opening HEIGHT with explicit source units.
"""
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

# Each semantic heading is one native source token. This avoids caller-side
# phrase grouping and exercises the schedule parser's documented RO+WDTH/HT
# vocabulary directly.
VALID_MM_SCHEDULE = (
    ("MARK", "ROWDTH-MM", "ROHT-MM"),
    ("W1", "900", "2100"),
)
VALID_M_SCHEDULE = (
    ("MARK", "ROWDTH-M", "ROHT-M"),
    ("W1", "0.9m", "2.1m"),
)


def _fixture(schedule_rows=VALID_MM_SCHEDULE):
    payload = _tag_pdf(schedule_rows=schedule_rows)
    src = SourceVisibilityProducer(
        producer_method="height-validator-v1",
        producer_version="1.0",
    )
    published = _ingest(src, payload, "height-validator-v1")
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
        decision_scope_id="height-validator-scope",
    )
    selector = OpeningHeightSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id="height-validator-scope",
        opening_record_id=physical.existence_record.record_id,
    )
    row_producer = ScheduleRowHeightProducer.from_source_visibility_producer(src)
    return src, binding_producer, binding_result, row_producer, selector


def _row_selector(binding_result):
    assert binding_result.record is not None
    return ScheduleRowHeightSelector(
        document_id=binding_result.record.document_id,
        revision_id=binding_result.record.revision_id,
        source_sha256=binding_result.record.source_sha256,
        snapshot_id=binding_result.record.snapshot_id,
        schedule_page_id=binding_result.record.schedule_page_id,
        schedule_row_observation_ids=binding_result.record.schedule_row_observation_ids,
    )


def _height_producer(src, binding_producer, row_producer):
    return OpeningHeightProducer.from_authorities(
        src,
        binding_producer.authority(),
        row_producer.authority(),
    )


# ---------------------------------------------------------------------------
# Structural firewall: these pass before production exists.
# ---------------------------------------------------------------------------

def test_public_height_surface_is_selector_only() -> None:
    params = set(inspect.signature(OpeningHeightProducer.publish_scope).parameters)
    assert params == {"self", "selector"}
    forbidden = {
        "height", "height_mm", "units", "dimension_basis", "basis",
        "raw_text", "schedule_row", "tag", "confidence", "nearest",
        "radius", "authenticated", "complete", "evidence",
    }
    assert not params & forbidden


def test_public_row_height_surface_is_selector_only() -> None:
    params = set(inspect.signature(ScheduleRowHeightProducer.publish_scope).parameters)
    assert params == {"self", "selector"}
    selector_params = set(inspect.signature(ScheduleRowHeightSelector).parameters)
    forbidden = {
        "height", "height_mm", "units", "dimension_basis", "basis",
        "raw_text", "header_text", "confidence", "nearest", "radius",
        "authenticated", "complete",
    }
    assert not selector_params & forbidden


def test_producers_cannot_be_directly_constructed() -> None:
    src = SourceVisibilityProducer(producer_method="seal", producer_version="1")
    binding = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    row = ScheduleRowHeightProducer.from_source_visibility_producer(src)
    with pytest.raises(TypeError):
        ScheduleRowHeightProducer(src)
    with pytest.raises(TypeError):
        OpeningHeightProducer(src, binding.authority(), row.authority())


def test_authorities_cannot_be_caller_minted() -> None:
    with pytest.raises(ValueError):
        ScheduleRowHeightAuthority({}, _seal=object())
    with pytest.raises(ValueError):
        OpeningHeightAuthority({}, _seal=object())


def test_fake_upstream_authority_objects_are_rejected() -> None:
    src, binding, _binding_result, row, _selector = _fixture()
    with pytest.raises(TypeError):
        OpeningHeightProducer.from_authorities(src, object(), row.authority())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        OpeningHeightProducer.from_authorities(src, binding.authority(), object())  # type: ignore[arg-type]


def test_raw_text_ocr_hidden_nearest_and_elevation_cannot_enter_height_api() -> None:
    height_params = set(inspect.signature(OpeningHeightProducer.publish_scope).parameters)
    row_params = set(inspect.signature(ScheduleRowHeightProducer.publish_scope).parameters)
    forbidden = {
        "text", "ocr", "hidden", "nearest", "distance", "radius",
        "elevation", "elevation_id", "wall_id", "type_mark",
    }
    assert not height_params & forbidden
    assert not row_params & forbidden


def test_cross_sheet_elevation_cannot_bypass_route_b_registration() -> None:
    factory_params = set(inspect.signature(OpeningHeightProducer.from_authorities).parameters)
    assert factory_params == {
        "source_visibility_producer", "binding_authority", "row_height_authority"
    }
    assert "elevation_authority" not in factory_params


def test_row_selector_requires_exact_nonempty_observation_identity() -> None:
    with pytest.raises(ValueError):
        ScheduleRowHeightSelector(
            document_id="d", revision_id="r", source_sha256="s",
            snapshot_id="n", schedule_page_id="1",
            schedule_row_observation_ids=(),
        )
    with pytest.raises(ValueError):
        ScheduleRowHeightSelector(
            document_id="d", revision_id="r", source_sha256="s",
            snapshot_id="n", schedule_page_id="1",
            schedule_row_observation_ids=("x", "x"),
        )


# ---------------------------------------------------------------------------
# Expected-red behavior. Each attack is a real source/lineage condition.
# ---------------------------------------------------------------------------

@pytest.mark.xfail(reason="opening-height production absent on frozen base")
def test_positive_explicit_rough_opening_mm_height_may_publish() -> None:
    src, binding, binding_result, row, selector = _fixture()
    assert binding_result.status is EvidenceResolutionStatus.CORROBORATED
    row_result = row.publish_scope(_row_selector(binding_result))
    assert row_result.status is EvidenceResolutionStatus.CORROBORATED
    assert row_result.evidence is not None
    assert row_result.evidence.height_mm == 2100.0
    assert row_result.evidence.units == "mm"
    assert row_result.evidence.dimension_basis == "rough_opening"

    producer = _height_producer(src, binding, row)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.height_mm == 2100.0
    assert result.evidence.dimension_basis == "rough_opening"


@pytest.mark.xfail(reason="schedule-row semantic production absent on frozen base")
def test_explicit_metres_may_normalize_to_mm_only_when_source_says_metres() -> None:
    _src, _binding, binding_result, row, _selector = _fixture(VALID_M_SCHEDULE)
    result = row.publish_scope(_row_selector(binding_result))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.height_mm == 2100.0
    assert result.evidence.source_units == "m"


@pytest.mark.xfail(reason="schedule-row semantic production absent on frozen base")
def test_generic_width_height_columns_do_not_prove_wall_void_basis() -> None:
    _src, _binding, binding_result, row, _selector = _fixture(
        (("MARK", "WIDTH-MM", "HEIGHT-MM"), ("W1", "900", "2100"))
    )
    result = row.publish_scope(_row_selector(binding_result))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "schedule_row_height_basis_unproven" in result.reason_codes


@pytest.mark.xfail(reason="schedule-row semantic production absent on frozen base")
def test_rough_opening_columns_without_units_do_not_assume_mm() -> None:
    _src, _binding, binding_result, row, _selector = _fixture(
        (("MARK", "ROWDTH", "ROHT"), ("W1", "900", "2100"))
    )
    result = row.publish_scope(_row_selector(binding_result))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "schedule_row_height_units_unproven" in result.reason_codes


@pytest.mark.parametrize(
    "width_heading,height_heading",
    [
        ("FRAMEWDTH-MM", "FRAMEHT-MM"),
        ("LEAFWDTH-MM", "LEAFHT-MM"),
        ("CLEARWDTH-MM", "CLEARHT-MM"),
    ],
)
@pytest.mark.xfail(reason="schedule-row semantic production absent on frozen base")
def test_non_void_dimension_basis_cannot_become_physical_opening_height(
    width_heading: str,
    height_heading: str,
) -> None:
    _src, _binding, binding_result, row, _selector = _fixture(
        (("MARK", width_heading, height_heading), ("W1", "900", "2100"))
    )
    result = row.publish_scope(_row_selector(binding_result))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "schedule_row_height_basis_unproven" in result.reason_codes


@pytest.mark.xfail(reason="schedule-row semantic production absent on frozen base")
def test_missing_height_field_never_defaults_to_2040_or_2100() -> None:
    _src, _binding, binding_result, row, _selector = _fixture(
        (
            ("MARK", "ROWDTH-MM", "ROHT-MM"),
            ("W1", "900", ""),
        )
    )
    result = row.publish_scope(_row_selector(binding_result))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert "opening_height_missing_field" in result.reason_codes


@pytest.mark.xfail(reason="schedule-row semantic production absent on frozen base")
def test_typical_note_cannot_become_height() -> None:
    _src, _binding, binding_result, row, _selector = _fixture(
        (
            ("MARK", "ROWDTH-MM", "ROHT-MM"),
            ("W1", "900", "TYPICAL"),
        )
    )
    result = row.publish_scope(_row_selector(binding_result))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None


@pytest.mark.xfail(reason="schedule-row semantic production absent on frozen base")
def test_conflicting_explicit_units_fail_closed() -> None:
    _src, _binding, binding_result, row, _selector = _fixture(
        (
            ("MARK", "ROWDTH-MM", "ROHT-MM"),
            ("W1", "0.9m", "2.1m"),
        )
    )
    result = row.publish_scope(_row_selector(binding_result))
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert "opening_height_ambiguous_units" in result.reason_codes


@pytest.mark.xfail(reason="opening-height production absent on frozen base")
def test_wrong_opening_revision_sha_and_snapshot_all_abstain() -> None:
    src, binding, _binding_result, row, selector = _fixture()
    producer = _height_producer(src, binding, row)
    for tampered in (
        dataclasses.replace(selector, opening_record_id="wrong-opening"),
        dataclasses.replace(selector, revision_id="wrong-revision"),
        dataclasses.replace(selector, source_sha256="wrong-sha"),
        dataclasses.replace(selector, snapshot_id="wrong-snapshot"),
    ):
        result = producer.publish_scope(tampered)
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.evidence is None


@pytest.mark.xfail(reason="opening-height production absent on frozen base")
def test_duplicate_identical_schedule_rows_remain_conflict() -> None:
    src, binding, binding_result, row, selector = _fixture(
        (
            ("MARK", "ROWDTH-MM", "ROHT-MM"),
            ("W1", "900", "2100"),
            ("W1", "900", "2100"),
        )
    )
    assert binding_result.status is EvidenceResolutionStatus.CONFLICT
    producer = _height_producer(src, binding, row)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in result.reason_codes


@pytest.mark.xfail(reason="opening-height production absent on frozen base")
def test_conflicting_height_rows_weaken_authority_monotonically() -> None:
    src, binding, binding_result, row, selector = _fixture(
        (
            ("MARK", "ROWDTH-MM", "ROHT-MM"),
            ("W1", "900", "2100"),
            ("W1", "900", "2000"),
        )
    )
    assert binding_result.status is EvidenceResolutionStatus.CONFLICT
    producer = _height_producer(src, binding, row)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.evidence is None


@pytest.mark.xfail(reason="schedule-row semantic production absent on frozen base")
def test_caller_invented_row_identity_cannot_mint_height() -> None:
    _src, _binding, binding_result, row, _selector = _fixture()
    assert binding_result.record is not None
    invented = ScheduleRowHeightSelector(
        document_id=binding_result.record.document_id,
        revision_id=binding_result.record.revision_id,
        source_sha256=binding_result.record.source_sha256,
        snapshot_id=binding_result.record.snapshot_id,
        schedule_page_id=binding_result.record.schedule_page_id,
        schedule_row_observation_ids=("caller-invented-row",),
    )
    result = row.publish_scope(invented)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
