"""Opening-height authority validator v1.

TEST ONLY / EXPECTED RED / DO NOT MERGE.

The frozen base already contains #383 exact physical-opening -> schedule-row
binding.  This validator requires a separate producer-owned semantic-height
layer and a sealed opening-height authority; neither production module exists
on the frozen base.  Missing production is asserted behaviorally (not through
an uncaught ImportError), so --runxfail exposes a genuine expected RED.
"""
from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import inspect
from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_schedule_opening_instance_binding_authority import (
    BINDING_AMBIGUOUS_ROWS,
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_schedule_opening_instance_binding_authority_v1 import (
    _ingest,
    _opening_selector,
    _tag_pdf,
)

VALID_MM_SCHEDULE = (("MARK", "ROWDTH-MM", "ROHT-MM"), ("W1", "900", "2100"))
VALID_M_SCHEDULE = (("MARK", "ROWDTH-M", "ROHT-M"), ("W1", "0.9m", "2.1m"))


def _source_fixture(schedule_rows=VALID_MM_SCHEDULE):
    payload = _tag_pdf(schedule_rows=schedule_rows)
    src = SourceVisibilityProducer(
        producer_method="height-validator-v1",
        producer_version="1.0",
    )
    published = _ingest(src, payload, "height-validator-v1")
    opening_selector = _opening_selector(published, src.authority())
    physical = PhysicalOpeningAuthority(src.authority()).prove_existence(opening_selector)
    assert physical.existence_record is not None
    binder = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    binding = binder.publish_scope(
        opening_selector=opening_selector,
        decision_scope_id="height-validator-scope",
    )
    return src, published, binder, binding, physical.existence_record


def _api():
    assert importlib.util.find_spec("pb_schedule_row_height_authority") is not None, (
        "schedule-row semantic-height production is absent"
    )
    assert importlib.util.find_spec("pb_opening_height_authority") is not None, (
        "opening-height production is absent"
    )
    row = importlib.import_module("pb_schedule_row_height_authority")
    opening = importlib.import_module("pb_opening_height_authority")
    return SimpleNamespace(row=row, opening=opening)


def _row_selector(api, binding):
    assert binding.record is not None
    return api.row.ScheduleRowHeightSelector(
        document_id=binding.record.document_id,
        revision_id=binding.record.revision_id,
        source_sha256=binding.record.source_sha256,
        snapshot_id=binding.record.snapshot_id,
        schedule_page_id=binding.record.schedule_page_id,
        schedule_row_observation_ids=binding.record.schedule_row_observation_ids,
    )


def _opening_selector_from_record(api, published, record):
    return api.opening.OpeningHeightSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id="height-validator-scope",
        opening_record_id=record.record_id,
    )


def _producers(api, src, binder, binding):
    row_prod = api.row.ScheduleRowHeightProducer.from_source_visibility_producer(src)
    if binding.record is not None:
        row_prod.publish_scope(_row_selector(api, binding))
    height_prod = api.opening.OpeningHeightProducer.from_authorities(
        src,
        binder.authority(),
        row_prod.authority(),
    )
    return row_prod, height_prod


# Baseline sanity: upstream #383 fixtures must be healthy before height production.
def test_frozen_base_positive_route_b_fixture_is_valid() -> None:
    _src, _published, _binder, binding, _record = _source_fixture()
    assert binding.status is EvidenceResolutionStatus.CORROBORATED
    assert binding.record is not None
    assert binding.record.schedule_row_height_mm == 2100


def test_frozen_base_duplicate_rows_are_already_conflict() -> None:
    _src, _published, _binder, binding, _record = _source_fixture(
        (
            ("MARK", "ROWDTH-MM", "ROHT-MM"),
            ("W1", "900", "2100"),
            ("W1", "900", "2100"),
        )
    )
    assert binding.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in binding.reason_codes


@pytest.mark.xfail(reason="height production modules absent on frozen base")
def test_required_modules_and_sealed_selector_only_factories_exist() -> None:
    api = _api()
    assert set(inspect.signature(api.opening.OpeningHeightProducer.publish_scope).parameters) == {
        "self", "selector"
    }
    assert set(inspect.signature(api.row.ScheduleRowHeightProducer.publish_scope).parameters) == {
        "self", "selector"
    }
    src = SourceVisibilityProducer(producer_method="seal", producer_version="1")
    with pytest.raises(TypeError):
        api.row.ScheduleRowHeightProducer(src)


@pytest.mark.xfail(reason="semantic height production absent on frozen base")
def test_explicit_rough_opening_mm_height_may_publish() -> None:
    api = _api()
    src, published, binder, binding, record = _source_fixture()
    row_prod, height_prod = _producers(api, src, binder, binding)
    row_result = row_prod.authority().resolve(_row_selector(api, binding))
    assert row_result.status is EvidenceResolutionStatus.CORROBORATED
    assert row_result.evidence.height_mm == 2100.0
    assert row_result.evidence.units == "mm"
    assert row_result.evidence.dimension_basis == "rough_opening"
    selector = _opening_selector_from_record(api, published, record)
    result = height_prod.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence.height_mm == 2100.0
    assert height_prod.authority().resolve(selector) == result


@pytest.mark.xfail(reason="semantic height production absent on frozen base")
def test_explicit_metres_normalize_only_when_source_states_metres() -> None:
    api = _api()
    src, _published, binder, binding, _record = _source_fixture(VALID_M_SCHEDULE)
    row_prod, _height_prod = _producers(api, src, binder, binding)
    result = row_prod.authority().resolve(_row_selector(api, binding))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence.height_mm == 2100.0
    assert result.evidence.source_units == "m"


@pytest.mark.xfail(reason="semantic height production absent on frozen base")
def test_generic_height_column_does_not_prove_rough_opening_basis() -> None:
    api = _api()
    src, _published, binder, binding, _record = _source_fixture(
        (("MARK", "WIDTH-MM", "HEIGHT-MM"), ("W1", "900", "2100"))
    )
    row_prod, _height_prod = _producers(api, src, binder, binding)
    result = row_prod.authority().resolve(_row_selector(api, binding))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "schedule_row_height_basis_unproven" in result.reason_codes


@pytest.mark.xfail(reason="semantic height production absent on frozen base")
def test_rough_opening_without_explicit_units_does_not_assume_mm() -> None:
    api = _api()
    src, _published, binder, binding, _record = _source_fixture(
        (("MARK", "ROWDTH", "ROHT"), ("W1", "900", "2100"))
    )
    row_prod, _height_prod = _producers(api, src, binder, binding)
    result = row_prod.authority().resolve(_row_selector(api, binding))
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
@pytest.mark.xfail(reason="semantic height production absent on frozen base")
def test_non_void_dimension_basis_is_rejected(width_heading: str, height_heading: str) -> None:
    api = _api()
    src, _published, binder, binding, _record = _source_fixture(
        (("MARK", width_heading, height_heading), ("W1", "900", "2100"))
    )
    row_prod, _height_prod = _producers(api, src, binder, binding)
    result = row_prod.authority().resolve(_row_selector(api, binding))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "schedule_row_height_basis_unproven" in result.reason_codes


@pytest.mark.xfail(reason="semantic height production absent on frozen base")
def test_missing_height_never_defaults_2040_or_2100() -> None:
    api = _api()
    src, _published, binder, binding, _record = _source_fixture(
        (("MARK", "ROWDTH-MM", "ROHT-MM"), ("W1", "900", ""))
    )
    row_prod, _height_prod = _producers(api, src, binder, binding)
    result = row_prod.authority().resolve(_row_selector(api, binding))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert "opening_height_missing_field" in result.reason_codes


@pytest.mark.xfail(reason="semantic height production absent on frozen base")
def test_typical_text_cannot_become_height() -> None:
    api = _api()
    src, _published, binder, binding, _record = _source_fixture(
        (("MARK", "ROWDTH-MM", "ROHT-MM"), ("W1", "900", "TYPICAL"))
    )
    row_prod, _height_prod = _producers(api, src, binder, binding)
    result = row_prod.authority().resolve(_row_selector(api, binding))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None


@pytest.mark.xfail(reason="semantic height production absent on frozen base")
def test_conflicting_explicit_units_fail_closed() -> None:
    api = _api()
    src, _published, binder, binding, _record = _source_fixture(
        (("MARK", "ROWDTH-MM", "ROHT-MM"), ("W1", "0.9m", "2.1m"))
    )
    row_prod, _height_prod = _producers(api, src, binder, binding)
    result = row_prod.authority().resolve(_row_selector(api, binding))
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert "opening_height_ambiguous_units" in result.reason_codes


@pytest.mark.xfail(reason="opening height production absent on frozen base")
def test_wrong_lineage_and_opening_all_abstain() -> None:
    api = _api()
    src, published, binder, binding, record = _source_fixture()
    _row_prod, height_prod = _producers(api, src, binder, binding)
    selector = _opening_selector_from_record(api, published, record)
    for tampered in (
        dataclasses.replace(selector, opening_record_id="wrong-opening"),
        dataclasses.replace(selector, revision_id="wrong-revision"),
        dataclasses.replace(selector, source_sha256="wrong-sha"),
        dataclasses.replace(selector, snapshot_id="wrong-snapshot"),
    ):
        result = height_prod.publish_scope(tampered)
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.evidence is None


@pytest.mark.xfail(reason="semantic height production absent on frozen base")
def test_caller_invented_row_identity_cannot_mint_height() -> None:
    api = _api()
    src, _published, _binder, binding, _record = _source_fixture()
    assert binding.record is not None
    row_prod = api.row.ScheduleRowHeightProducer.from_source_visibility_producer(src)
    invented = api.row.ScheduleRowHeightSelector(
        document_id=binding.record.document_id,
        revision_id=binding.record.revision_id,
        source_sha256=binding.record.source_sha256,
        snapshot_id=binding.record.snapshot_id,
        schedule_page_id=binding.record.schedule_page_id,
        schedule_row_observation_ids=("caller-invented-row",),
    )
    result = row_prod.publish_scope(invented)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
