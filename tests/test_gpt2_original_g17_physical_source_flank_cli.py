"""Read-only private-original G17 source CLI call-path tests, no PDF fixtures."""
from hashlib import sha256
from types import SimpleNamespace as NS
import pytest

from pb_gpt2_g17_opening_source_band_ownership_shadow import (
    OriginalG17OpeningFlankOwnership,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import RASTER_FRAMED_WALL_BAND_INTERRUPTION
from pb_gpt2_raster_source_flank_band_shadow import (
    RasterSourceFlankBandCandidate,
)
from tools import diag_gpt2_original_g17_physical_source_flanks as cli

_SOURCE = b"%PDF-synthetic-API-test"
_SHA = sha256(_SOURCE).hexdigest()


def _stub_pipeline(monkeypatch, *, support=("visible-1", "visible-2"),
                   trace_identity="physical-original-1"):
    state = dict(revision="rev", sha=_SHA, observed=[],
                 compose_calls=0, source_calls=0, owned_calls=0)
    published = NS(
        revision=NS(revision_id="rev",
                    document_id="live-source:" + _SHA[:32],
                    source_sha256=_SHA),
        snapshot=NS(snapshot_id="snap"),
    )
    record = NS(
        record_id=trace_identity, page_id="3", source_sha256=_SHA,
        snapshot_id="snap", source_observation_ids=tuple(support),
        structural_pattern=RASTER_FRAMED_WALL_BAND_INTERRUPTION,
    )
    class Source:
        def __init__(self, *, producer_method, producer_version):
            assert producer_method and producer_version
        def ingest_native_pdf_bytes(self, *, document_id, source_bytes,
                                    source_locator, page_ids):
            assert source_bytes == _SOURCE
            assert page_ids == (3,)
            assert document_id == published.revision.document_id
            return NS(revision=NS(revision_id="rev"))
        def published_snapshot_for_revision(self, revision_id):
            assert revision_id == "rev"
            return published
        def authority(self):
            return self
        def resolve_raster_opening_primitive(self, selector):
            state["source_calls"] += 1
            if selector.observation_id not in support:
                return NS(status=EvidenceResolutionStatus.ABSTAINED,
                          observation=None)
            return NS(
                status=EvidenceResolutionStatus.CORROBORATED,
                observation=NS(
                    page_id="3",
                    derivation_parent_ids=("parent-" + selector.observation_id,),
                ),
            )
    class Physical:
        def prove_existence(self, selector):
            state["observed"].append(selector.observation_id)
            return NS(status=EvidenceResolutionStatus.CORROBORATED,
                      existence_record=record)
    def compose(*, source_visibility_producer, revision_id, page_ids):
        state["compose_calls"] += 1
        return NS(
            revision_id="rev", page_ids=("3",),
            physical_opening_authority=Physical(),
            opening_bindings=(
                NS(opening_identity_id=trace_identity,
                   representative_observation_id="visible-1",
                   status=EvidenceResolutionStatus.ABSTAINED,
                   record_id=None, host_wall_id=None,
                   reason_codes=(
                       "raster_source_band_left_source_primitive_unmapped",
                   )),
            ),
        )
    def recover(source, *, revision_id, snapshot_id, page_id,
                required_parent_ids):
        state["parents"] = tuple(sorted(required_parent_ids))
        return "source-parent-source-only"
    def owner(*args, **kwargs):
        state["owned_calls"] += 1
        assert kwargs["parent_source"] == "source-parent-source-only"
        return OriginalG17OpeningFlankOwnership(
            EvidenceResolutionStatus.CORROBORATED,
            ("source_only",), trace_identity, _SHA,
            tuple(sorted(support)), ("parent-end-a", "parent-end-b"),
            tuple(sorted(support)),
        )
    monkeypatch.setattr(cli, "SourceVisibilityProducer", Source)
    monkeypatch.setattr(cli, "compose_live_wall_opening_authority", compose)
    monkeypatch.setattr(cli, "recover_original_raster_opening_parent_lines_shadow", recover)
    source_bands = NS(candidates=(
        RasterSourceFlankBandCandidate(
            page_id="3",
            face_parent_chains=(("left-face-a",), ("left-face-b",)),
            end_parent_id="parent-end-a",
            near_center_pdf_pt=(0., 1.2),
            far_center_pdf_pt=(-20., 1.2),
            original_source_visible_ids=("left-a", "left-b", "left-end"),
        ),
        RasterSourceFlankBandCandidate(
            page_id="3",
            face_parent_chains=(("right-face-a",), ("right-face-b",)),
            end_parent_id="parent-end-b",
            near_center_pdf_pt=(30., 1.2),
            far_center_pdf_pt=(50., 1.2),
            original_source_visible_ids=("right-a", "right-b", "right-end"),
        ),
    ))
    monkeypatch.setattr(cli, "reconstruct_raster_source_flank_bands_shadow",
                        lambda source: source_bands)
    monkeypatch.setattr(cli, "bind_original_g17_flanks_to_physical_opening_shadow",
                        owner)
    return state, record


def test_real_original_source_call_path_reproves_each_physically_owned_support(monkeypatch):
    state, _ = _stub_pipeline(monkeypatch)
    result = cli.original_physical_g17_source_flank_report(
        _SOURCE, expected_sha256=_SHA, page_id="3",
    )
    assert state["compose_calls"] == 1
    assert state["source_calls"] == 2
    assert state["observed"] == ["visible-1"]
    assert state["parents"] == ("parent-visible-1", "parent-visible-2")
    assert state["owned_calls"] == 1
    assert result["original_source_owned_two_flank_count"] == 1
    assert result["host_abstained_g17_candidate_physical_count"] == 1
    assert result["hostless_g17_source_roster_complete"] is True
    original_bands = result["source_owned_flank_bands_by_physical_opening"]
    assert tuple(sorted(original_bands)) == ("physical-original-1",)
    assert len(original_bands["physical-original-1"]) == 2
    assert {band["end_parent_id"] for band in original_bands["physical-original-1"]} == {
        "parent-end-a", "parent-end-b",
    }
    assert all(not band["structural_wall_granted"]
               and not band["host_binding_granted"]
               for band in original_bands["physical-original-1"])
    assert result["source_owner_claims"][0]["physical_opening_id"] == "physical-original-1"
    assert result["shadow_only"] and not result["structural_host_granted"]
    assert not result["metric_quantity_granted"] and not result["benchmark_score_granted"]


def test_foreign_source_sha_rejected_before_producer_ingest(monkeypatch):
    state, _ = _stub_pipeline(monkeypatch)
    with pytest.raises(ValueError):
        cli.original_physical_g17_source_flank_report(
            _SOURCE, expected_sha256="0" * 64, page_id="3",
        )
    assert state["compose_calls"] == 0


def test_corrupted_physical_g17_source_receipts_never_skip_as_non_raster(monkeypatch):
    state, record = _stub_pipeline(monkeypatch)
    record.source_observation_ids = ("missing",)
    result = cli.original_physical_g17_source_flank_report(
        _SOURCE, expected_sha256=_SHA, page_id="3",
    )
    assert result["host_abstained_g17_candidate_physical_count"] == 0
    assert state["owned_calls"] == 0
    assert result["source_owned_flank_bands_by_physical_opening"] == {}
    assert result["unresolved"] == [{
        "physical_opening_id": "physical-original-1",
        "reason": "original_g17_raster_source_support_unavailable",
    }]


def test_incomplete_source_support_not_laundered_as_positive(monkeypatch):
    state, record = _stub_pipeline(monkeypatch)
    record.source_observation_ids = ("visible-1", "missing")
    result = cli.original_physical_g17_source_flank_report(
        _SOURCE, expected_sha256=_SHA, page_id="3",
    )
    assert result["original_source_owned_two_flank_count"] == 0
    assert state["owned_calls"] == 0
    assert result["unresolved"][0]["reason"] == (
        "original_g17_source_support_incomplete_or_ambiguous"
    )


@pytest.mark.parametrize("page", ["0", "03", "three", "", "4.0"])
def test_original_source_page_scope_must_be_exact_positive_integer(monkeypatch, page):
    state, _ = _stub_pipeline(monkeypatch)
    with pytest.raises(ValueError):
        cli.original_physical_g17_source_flank_report(
            _SOURCE, expected_sha256=_SHA, page_id=page,
        )
    assert state["compose_calls"] == 0

def test_hosted_opening_cannot_leak_into_unhosted_source_handoff(monkeypatch):
    state, record = _stub_pipeline(monkeypatch)
    original_composer = cli.compose_live_wall_opening_authority
    def hosted(**kwargs):
        result = original_composer(**kwargs)
        row = result.opening_bindings[0]
        row.host_wall_id = "already-signed-wall"
        return result
    monkeypatch.setattr(cli, "compose_live_wall_opening_authority", hosted)
    report = cli.original_physical_g17_source_flank_report(
        _SOURCE, expected_sha256=_SHA, page_id="3",
    )
    assert report["host_abstained_g17_candidate_physical_count"] == 0
    assert state["owned_calls"] == 0


def test_unrelated_nonflank_abstention_cannot_enter_g17_source_handoff(monkeypatch):
    state, _ = _stub_pipeline(monkeypatch)
    original_composer = cli.compose_live_wall_opening_authority
    def unrelated(**kwargs):
        result = original_composer(**kwargs)
        result.opening_bindings[0].reason_codes = ("missing_door_height",)
        return result
    monkeypatch.setattr(cli, "compose_live_wall_opening_authority", unrelated)
    report = cli.original_physical_g17_source_flank_report(
        _SOURCE, expected_sha256=_SHA, page_id="3",
    )
    assert report["host_abstained_g17_candidate_physical_count"] == 0
    assert state["owned_calls"] == 0


def test_non_raster_physical_opening_cannot_be_laundered_through_flank_roster(monkeypatch):
    state, original = _stub_pipeline(monkeypatch)
    original.structural_pattern = "jamb_bounded_two_face_interruption"
    report = cli.original_physical_g17_source_flank_report(
        _SOURCE, expected_sha256=_SHA, page_id="3",
    )
    assert report["host_abstained_g17_candidate_physical_count"] == 0
    assert report["unresolved"][0]["reason"] == (
        "original_g17_physical_existence_unproven"
    )
    assert state["owned_calls"] == 0

def test_original_hostless_roster_conflicting_duplicate_is_not_silently_deduplicated(
    monkeypatch,
):
    state, _ = _stub_pipeline(monkeypatch)
    original_composer = cli.compose_live_wall_opening_authority
    def duplicate(**kwargs):
        result = original_composer(**kwargs)
        row = result.opening_bindings[0]
        return NS(
            **{**vars(result), "opening_bindings": (row, row)}
        )
    monkeypatch.setattr(cli, "compose_live_wall_opening_authority", duplicate)
    with pytest.raises(RuntimeError, match="repeated identity decisions"):
        cli.original_physical_g17_source_flank_report(
            _SOURCE, expected_sha256=_SHA, page_id="3",
        )
    assert state["owned_calls"] == 0


def test_empty_hostless_original_page_scope_never_claims_completed_roster(monkeypatch):
    state, _ = _stub_pipeline(monkeypatch)
    original_composer = cli.compose_live_wall_opening_authority
    def empty(**kwargs):
        result = original_composer(**kwargs)
        return NS(**{**vars(result), "opening_bindings": ()})
    monkeypatch.setattr(cli, "compose_live_wall_opening_authority", empty)
    report = cli.original_physical_g17_source_flank_report(
        _SOURCE, expected_sha256=_SHA, page_id="3",
    )
    assert report["hostless_g17_source_roster_complete"] is False
    assert report["original_source_owned_two_flank_count"] == 0
    assert state["owned_calls"] == 0


def test_corrupt_support_explicitly_blocks_local_scope_completeness(monkeypatch):
    state, record = _stub_pipeline(monkeypatch)
    record.source_observation_ids = ("visible-1", "missing")
    result = cli.original_physical_g17_source_flank_report(
        _SOURCE, expected_sha256=_SHA, page_id="3",
    )
    assert result["hostless_g17_source_roster_complete"] is False
    assert result["unresolved"]

def test_same_physical_opening_hosted_and_abstained_rosters_conflict(monkeypatch):
    state, _ = _stub_pipeline(monkeypatch)
    original_composer = cli.compose_live_wall_opening_authority
    def contradictory(**kwargs):
        result = original_composer(**kwargs)
        row = result.opening_bindings[0]
        hosted = NS(**{
            **vars(row),
            "status": EvidenceResolutionStatus.CORROBORATED,
            "record_id": "original-hosted-wall-binding",
            "host_wall_id": "physical-W4-wall",
            "reason_codes": (),
        })
        return NS(**{
            **vars(result), "opening_bindings": (hosted, row),
        })
    monkeypatch.setattr(
        cli, "compose_live_wall_opening_authority", contradictory,
    )
    with pytest.raises(RuntimeError,
                       match="repeated identity decisions"):
        cli.original_physical_g17_source_flank_report(
            _SOURCE, expected_sha256=_SHA, page_id="3",
        )
    assert state["owned_calls"] == 0
