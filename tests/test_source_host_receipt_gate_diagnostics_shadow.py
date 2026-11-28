"""Read-only host-receipt gate diagnostics (donor piece C'). Synthetic only."""
from __future__ import annotations

import copy
import dataclasses
from types import SimpleNamespace

import pytest

from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject
from pb_live_wall_opening_authority_composition import LiveOpeningHostTrace
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_host_receipt_gate_diagnostics_shadow import (
    first_failing_host_publish_gate,
    first_failing_live_host_trace_gate,
)


def opening(**values):
    required = {f.name: None for f in dataclasses.fields(LiveCanonicalOpeningObject)
                if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING}
    required.update(physical_opening_id="opening-1", page_id="3", representative_observation_id="obs-1", **values)
    return LiveCanonicalOpeningObject(**required)


def trace(**values):
    base = {"opening_identity_id": "opening-1", "representative_observation_id": "obs-1", "page_id": "3",
            "status": Status.CORROBORATED, "reason_codes": (), "record_id": "r", "host_wall_id": "w",
            "member_wall_candidate_ids": ()}
    base.update(values)
    return LiveOpeningHostTrace(**base)


def result(status=Status.CORROBORATED, record_id="r", host_wall_id="w", reasons=()):
    record = None if record_id is None else SimpleNamespace(record_id=record_id, host_wall_id=host_wall_id)
    return SimpleNamespace(status=status, record=record, reason_codes=reasons)


@pytest.mark.parametrize("value,expected", [
    (None, "opening_host_binding_producer_publish_not_called"),
    (result(), ""),
    (result(status=Status.ABSTAINED, record_id=None, reasons=("first", "second")), "first"),
    (result(record_id=" "), "opening_host_binding_unavailable"),
    (result(host_wall_id=""), "opening_host_binding_unavailable"),
    (result(status=Status.CONFLICT), "opening_host_binding_unavailable"),
])
def test_publish_gate(value, expected):
    assert first_failing_host_publish_gate(value) == expected


@pytest.mark.parametrize("traces,expected", [
    ([], "opening_host_trace_missing"),
    ([trace(opening_identity_id="other")], "opening_host_trace_missing"),
    ([trace(page_id="4")], "opening_host_trace_page_mismatch"),
    ([trace(representative_observation_id="obs-2")], "opening_host_trace_observation_mismatch"),
    ([trace()], "opening_host_trace_not_producer_receipt"),
    ([trace(status=Status.ABSTAINED, reason_codes=("band_missing",))], "band_missing"),
    ([trace(status=Status.ABSTAINED, record_id=None)], "opening_host_binding_unavailable"),
])
def test_trace_gate_never_accepts_a_trace_as_a_receipt(traces, expected):
    item = opening()
    before = copy.deepcopy(traces)
    assert first_failing_live_host_trace_gate(item, traces) == expected
    assert traces == before


def test_only_a_real_opening_object_is_accepted():
    with pytest.raises(TypeError):
        first_failing_live_host_trace_gate(SimpleNamespace(), [])
