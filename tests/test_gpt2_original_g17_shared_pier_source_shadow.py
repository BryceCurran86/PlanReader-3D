"""Source-owned *candidate*, not a W4 host: real archived two-END G17 pier.

The immutable original-producer receipt ledger is evidence only, never frozen
benchmark gold. Full, latest original private-PDF replay and cross-resolution
W4 physical wall proof remain independent publication requirements.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt2_g17_opening_source_band_ownership_shadow import (
    OriginalG17OpeningFlankOwnership,
    quarantine_overlapping_g17_physical_source_claims_shadow,
)
from pb_gpt2_raster_opening_parent_source_shadow import (
    AuthenticatedRasterOpeningParentLine,
    RasterOpeningParentSourceHandoff,
)
from pb_gpt2_original_g17_shared_pier_shadow import (
    audit_gpt2_original_g17_shared_piers_shadow,
)

_LEDGER = (
    Path(__file__).resolve().parents[1]
    / "docs/engineering/gptmax_lot16_host_source_queue_20261016.json"
)
_PINNED = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
_IDS = (
    "physical_opening_existence_81a45c3a33c2a4c0bfdf243aa45a780d",
    "physical_opening_existence_f819752382d44a00d9f28feca4b00787",
)


def _original_pair():
    j = json.loads(_LEDGER.read_text(encoding="utf8"))
    assert j["source_sha256"] == _PINNED
    cases = {v["physical_opening_id"]: v for v in j["case_evidence"]}
    result = {}
    for physical_id in _IDS:
        assert physical_id in cases
        original = cases[physical_id]["source_g17_observations"]
        lines = tuple(AuthenticatedRasterOpeningParentLine(
            parent_observation_id=item["source_lineage_parent_ids"][0],
            visible_observation_id=item["observation_id"],
            observation_kind=item["observation_kind"],
            original_source_primitive_ref=item["source_primitive_ref"],
            page_id="3",
            geometry_pdf_points=tuple(item["geometry_pdf_pts"]),
        ) for item in original)
        assert len(lines) == 8
        assert len({x.parent_observation_id for x in lines}) == 8
        visible = tuple(sorted(x.visible_observation_id for x in lines))
        parents = tuple(sorted(x.parent_observation_id for x in lines))
        ends = tuple(sorted(x.parent_observation_id for x in lines
                            if x.observation_kind == "raster_wall_band_end"))
        band_ids = tuple(sorted(x.visible_observation_id for x in lines
                                if x.observation_kind in (
                                    "raster_wall_band_face",
                                    "raster_wall_band_end",
                                )))
        proof = OriginalG17OpeningFlankOwnership(
            EvidenceResolutionStatus.CORROBORATED,
            ("original_archived_producer_source_ledger_only",),
            physical_id, _PINNED, visible, ends, band_ids,
            authenticated_source_parent_ids=parents,
        )
        handoff = RasterOpeningParentSourceHandoff(
            "SOURCE_ONLY_CANDIDATE", _PINNED, parents, lines, (),
            ("source_parent_ledger_previous_original_replay",),
        )
        result[physical_id] = (proof, handoff)
    return result


def test_archived_original_two_openings_retain_shared_pier_alternative():
    owned = _original_pair()
    report = audit_gpt2_original_g17_shared_piers_shadow(owned)
    assert report.status == "SOURCE_ONLY_SHARED_PIER_CANDIDATE"
    assert report.source_sha256 == _PINNED
    assert len(report.source_sharing_pairs) == 1
    one = report.source_sharing_pairs[0]
    assert one["opening_ids"] == list(_IDS)
    assert one["source_closed_pier_candidate"] is True
    assert one["reason"] == "complete_own_source_two_end_pier_geometry"
    assert len(one["shared_face_ids"]) == 2
    assert len(one["source_closed_source_observation_ids"]) == 4
    assert one["source_closed_pier_geometry_candidate"]["axis"] == "vertical"
    assert report.entire_original_opening_universe_authenticated is False
    assert report.third_original_owner_excluded is False
    assert not report.physical_instance_conflict_exempted
    assert not report.w4_structural_wall_granted
    assert not report.opening_host_granted
    assert not report.opening_count_granted
    assert not report.metric_area_granted
    # The original GPT2 physical conflict quarantine MUST remain unchanged.
    exclusive = quarantine_overlapping_g17_physical_source_claims_shadow(
        tuple(x[0] for x in owned.values())
    )
    assert len(exclusive) == 2
    assert all(x.status is EvidenceResolutionStatus.CONFLICT for x in exclusive)


def test_archived_original_pier_order_is_not_a_first_owner_tiebreaker():
    owned = _original_pair()
    old = audit_gpt2_original_g17_shared_piers_shadow(owned)
    flipped = {
        key: (owner, replace(parent, lines=tuple(reversed(parent.lines))))
        for key, (owner, parent) in reversed(list(owned.items()))
    }
    assert audit_gpt2_original_g17_shared_piers_shadow(flipped) == old


def test_unverified_source_owner_does_not_nominate_pier():
    owned = _original_pair()
    key = _IDS[1]
    owner, source = owned[key]
    owned[key] = (replace(owner, status=EvidenceResolutionStatus.CONFLICT), source)
    report = audit_gpt2_original_g17_shared_piers_shadow(owned)
    assert report.status == "ABSTAIN"
    assert not report.source_sharing_pairs


def test_shared_face_alone_without_distinct_other_end_does_not_nominate():
    owned = _original_pair()
    physical = _IDS[1]
    owner, source = owned[physical]
    end = next(x for x in source.lines
               if x.observation_kind == "raster_wall_band_end"
               and x.visible_observation_id not in
               {line.visible_observation_id for line in owned[_IDS[0]][1].lines})
    shifted = replace(end, geometry_pdf_points=(
        end.geometry_pdf_points[0] + 0.5, end.geometry_pdf_points[1],
        end.geometry_pdf_points[2] + 0.5, end.geometry_pdf_points[3],
    ))
    modified_lines = tuple(shifted if x is end else x for x in source.lines)
    owned[physical] = (owner, replace(source, lines=modified_lines))
    report = audit_gpt2_original_g17_shared_piers_shadow(owned)
    assert report.status == "SOURCE_ONLY_SHARED_FACE_CONFLICT"
    assert all(not p.get("source_closed_pier_candidate")
               for p in report.source_sharing_pairs)


def test_third_competing_owner_of_shared_faces_never_gets_positive():
    owned = _original_pair()
    owner, source = owned[_IDS[1]]
    third = "physical_opening_existence_ambiguous_third"
    owned[third] = (replace(owner, physical_opening_id=third), source)
    report = audit_gpt2_original_g17_shared_piers_shadow(owned)
    assert report.status == "SOURCE_ONLY_SHARED_FACE_CONFLICT"
    assert all(not p.get("source_closed_pier_candidate")
               for p in report.source_sharing_pairs)


def test_foreign_sha_or_spliced_original_parent_receipt_cannot_be_approved():
    owned = _original_pair()
    key = _IDS[1]
    owner, source = owned[key]
    owned[key] = (replace(owner, source_sha256="f" * 64),
                  replace(source, source_sha256="f" * 64))
    assert audit_gpt2_original_g17_shared_piers_shadow(owned).status == "ABSTAIN"
    owned = _original_pair()
    owner, source = owned[key]
    owned[key] = (owner, replace(source, requested_parent_ids=(
        *source.requested_parent_ids[:-1], "foreign-original-parent",
    )))
    assert audit_gpt2_original_g17_shared_piers_shadow(owned).status == "ABSTAIN"

def test_spliced_original_end_parent_and_face_support_do_not_create_pier():
    owned = _original_pair()
    key = _IDS[1]
    owner, source = owned[key]
    owned[key] = (replace(
        owner, authenticated_flank_end_parent_ids=("foreign-owned-cap",)
    ), source)
    assert audit_gpt2_original_g17_shared_piers_shadow(owned).status == "ABSTAIN"
    owned = _original_pair()
    owner, source = owned[key]
    owned[key] = (replace(
        owner, authenticated_flank_source_visible_ids=("foreign-source-face",)
    ), source)
    assert audit_gpt2_original_g17_shared_piers_shadow(owned).status == "ABSTAIN"


def test_mixed_original_source_pages_not_silently_united_as_one_pier():
    owned = _original_pair()
    key = _IDS[1]
    owner, source = owned[key]
    changed = tuple(
        replace(line, page_id="4") if i == 1 else line
        for i, line in enumerate(source.lines)
    )
    owned[key] = (owner, replace(source, lines=changed))
    result = audit_gpt2_original_g17_shared_piers_shadow(owned)
    assert result.status == "ABSTAIN"
    assert result.source_sharing_pairs == ()


def test_entire_other_owner_on_foreign_page_cannot_nominate_a_shared_pier():
    # Both owners are internally page-consistent. A same-SHA page-3 and
    # page-4 geometry match is NOT a physical original shared pier.
    owned = _original_pair()
    key = _IDS[1]
    owner, source = owned[key]
    owned[key] = (owner, replace(
        source, lines=tuple(replace(line, page_id="4") for line in source.lines),
    ))
    result = audit_gpt2_original_g17_shared_piers_shadow(owned)
    assert result.status == "ABSTAIN"
    assert result.source_sharing_pairs == ()
    assert result.reason_codes == ("original_g17_cross_owner_page_scope_conflict",)
    assert not result.opening_host_granted and not result.metric_area_granted


@pytest.mark.parametrize(("target", "authority_flag"), (
    ("owner", "whole_wall_frame_granted"),
    ("owner", "customer_publication_granted"),
    ("parent", "whole_wall_frame_granted"),
    ("parent", "metric_quantity_granted"),
    ("parent", "customer_publication_granted"),
))
def test_already_authoritative_input_cannot_enter_source_only_pier(
    target, authority_flag,
):
    owned = _original_pair()
    key = _IDS[1]
    owner, source = owned[key]
    if target == "owner":
        owner = replace(owner, **{authority_flag: True})
    else:
        source = replace(source, **{authority_flag: True})
    owned[key] = (owner, source)
    result = audit_gpt2_original_g17_shared_piers_shadow(owned)
    assert result.status == "ABSTAIN"
    assert result.source_sharing_pairs == ()
    assert result.reason_codes == ("original_g17_source_owner_not_reproved",)
    assert not result.w4_structural_wall_granted
    assert not result.opening_host_granted
    assert not result.customer_release_granted


def test_noncanonical_zero_padded_page_is_not_source_page_identity():
    owned = _original_pair()
    key = _IDS[1]
    owner, source = owned[key]
    owned[key] = (owner, replace(
        source, lines=tuple(replace(line, page_id="03") for line in source.lines),
    ))
    report = audit_gpt2_original_g17_shared_piers_shadow(owned)
    assert report.status == "ABSTAIN"
    assert report.source_sharing_pairs == ()
