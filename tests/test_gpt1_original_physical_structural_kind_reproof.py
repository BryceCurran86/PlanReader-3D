"""A G17 original producer existence record may independently prove KIND in shadow."""
from copy import deepcopy
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    GAP_CORROBORATED_DOOR_JAMB_LEAF, GAP_CORROBORATED_WINDOW_JAMB_PAIR,
    PHYSICAL_OPENING_EXISTS,
)
from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows


_ROOT = dict(document_id="doc", revision_id="revision", source_sha256="a"*64,
             snapshot_id="snapshot", page_id="3")
_PHYSICAL = "physical_opening_existence_original"


def _inventory(kind="door", structural_pattern=GAP_CORROBORATED_DOOR_JAMB_LEAF):
    decision = {"physical_opening_id": _PHYSICAL, "first_remaining_gate": "kind",
                "prior_signed_quantity_id": None}
    canonical = {"physical_opening_id": _PHYSICAL, "opening_kind": kind,
                 "structural_pattern": structural_pattern, **_ROOT,
                 "evidence_ids": [_PHYSICAL, "obs-original", "figured-pair-1"],
                 "width_record_id": None, "height_record_id": None,
                 "width_m": None, "height_m": None,
                 "geometry_complete": False}
    record = {"record_id": _PHYSICAL, "structural_pattern": structural_pattern,
              "status": EvidenceResolutionStatus.CORROBORATED,
              "proposition": PHYSICAL_OPENING_EXISTS,
              "source_observation_ids": ("obs-original",), **_ROOT}
    observed = {"physical_existence_record": record,
                "original_label_dimension_result": {"evidence": {
                    "opening_record_id": _PHYSICAL, "evidence_id": "figured-pair-1",
                    "dimension_values_mm": [1200,1800], "area_m2": 2.16,
                    "axis_order_resolved": False}}}
    return [decision], {_PHYSICAL: canonical}, {_PHYSICAL: observed}


def _report(bundle):
    d,c,o = bundle
    return attach_kind_and_axis_shadows(
        opening_decisions=d, canonical_by_id=c, observe_rows_by_id=o,
    )


def test_original_structural_door_kind_can_be_reproved_without_figured_kind_alias():
    r=_report(_inventory())
    row=r["openings"][0]
    assert row["original_structural_kind_source_reproved"]
    assert row["kind_shadow"]["source_kind_evidence_ids"] == [_PHYSICAL]
    assert row["kind_shadow"]["filling_kind_source_supported"]
    assert row["kind_shadow"]["measurement_published"] is False
    assert not r["customer_seal_granted"] and not r["benchmark_score_granted"]


def test_source_owned_structural_window_kind_can_be_reproved():
    r=_report(_inventory(kind="window", structural_pattern=GAP_CORROBORATED_WINDOW_JAMB_PAIR))
    assert r["openings"][0]["original_structural_kind_source_reproved"]
    assert r["openings"][0]["kind_shadow"]["opening_kind"] == "window"


@pytest.mark.parametrize("change", [
    lambda d,c,o: o[_PHYSICAL].pop("physical_existence_record"),
    lambda d,c,o: o[_PHYSICAL]["physical_existence_record"].update(record_id="other"),
    lambda d,c,o: o[_PHYSICAL]["physical_existence_record"].update(
        proposition="gap_guess"),
    lambda d,c,o: o[_PHYSICAL]["physical_existence_record"].update(
        status=EvidenceResolutionStatus.CANDIDATE),
    lambda d,c,o: o[_PHYSICAL]["physical_existence_record"].update(
        revision_id="old-revision"),
    lambda d,c,o: o[_PHYSICAL]["physical_existence_record"].update(
        source_sha256="b"*64),
    lambda d,c,o: o[_PHYSICAL]["physical_existence_record"].update(
        structural_pattern=GAP_CORROBORATED_WINDOW_JAMB_PAIR),
    lambda d,c,o: o[_PHYSICAL]["physical_existence_record"].update(
        source_observation_ids=("unowned-source",)),
    lambda d,c,o: c[_PHYSICAL]["evidence_ids"].remove(_PHYSICAL),
    lambda d,c,o: c[_PHYSICAL].update(opening_kind="window"),
    lambda d,c,o: c[_PHYSICAL].update(
        structural_pattern="raster_framed_wall_band_interruption"),
])
def test_missing_foreign_or_contradictory_physical_receipt_never_authorizes_kind(change):
    d,c,o=_inventory()
    change(d,c,o)
    r=_report((d,c,o))
    row=r["openings"][0]
    assert not row["original_structural_kind_source_reproved"]
    assert not row["kind_shadow"]["filling_kind_source_supported"]
    assert row["kind_shadow"]["first_remaining_gate"] == (
        "opening_filling_kind_evidence_unproven"
    )


def test_figured_dimension_only_does_not_invent_a_structural_kind():
    d,c,o=_inventory()
    del o[_PHYSICAL]["physical_existence_record"]
    original=deepcopy((d,c,o))
    report=_report((d,c,o))
    assert not report["openings"][0]["original_structural_kind_source_reproved"]
    assert report["openings"][0]["kind_shadow"]["source_kind_evidence_ids"] == []
    assert (d,c,o)==original
    assert not report["measurement_published"]
