"""Only the original G17 physical opening can own its two source flanks."""
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest

from pb_gpt2_g17_opening_source_band_ownership_shadow import (
    bind_original_g17_flanks_to_physical_opening_shadow,
    OriginalG17OpeningFlankOwnership,
    quarantine_overlapping_g17_physical_source_claims_shadow,
)
from pb_gpt2_raster_source_flank_band_shadow import (
    reconstruct_raster_source_flank_bands_shadow,
)
from pb_gpt2_raster_opening_parent_source_shadow import (
    RasterOpeningParentSourceHandoff,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PhysicalOpeningAuthority, PhysicalOpeningExistenceRecord,
    PHYSICAL_OPENING_EXISTS,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority

from test_gpt2_raster_source_flank_band_shadow import (
    _handoff, _solid_left, _solid_right,
)


def _context(monkeypatch):
    parents = _handoff((*_solid_left(), *_solid_right()))
    bands = reconstruct_raster_source_flank_bands_shadow(parents)
    observations = tuple(row.visible_observation_id for row in parents.lines)
    selector = ObservationSelector(
        document_id="doc", revision_id="rev",
        source_sha256="e" * 64,
        snapshot_id="snapshot", observation_id=observations[0],
    )
    record = PhysicalOpeningExistenceRecord(
        record_id="physical-G17-1",
        source_observation_ids=observations,
        source_lineage_root_ids=tuple(sorted(
            line.parent_observation_id for line in parents.lines
        )),
        document_id="doc", revision_id="rev",
        source_sha256="e" * 64, snapshot_id="snapshot",
        page_id="3", viewport_id=None,
        semantic_class="raster-framed-opening",
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=PHYSICAL_OPENING_EXISTS,
        structural_pattern="raster_wall_band_interruption",
        diagnostic_confidence=1.0, blocking_reasons=(),
        structural_reason_codes=(), producer_method="source-owned",
        producer_version="1.0.0", producer_generation=1,
    )
    owner = object.__new__(PhysicalOpeningAuthority)
    visibility = object.__new__(SourceVisibilityAuthority)
    by_visible = {
        row.visible_observation_id: row for row in parents.lines
    }
    state = {"record": record, "status": EvidenceResolutionStatus.CORROBORATED,
             "spoof": None}
    monkeypatch.setattr(
        PhysicalOpeningAuthority, "prove_existence",
        lambda self, selected: NS(
            status=state["status"], existence_record=state["record"],
        ),
    )
    monkeypatch.setattr(
        PhysicalOpeningAuthority, "source_visibility_authority",
        lambda self: visibility,
    )
    def resolved(self, selected):
        row = by_visible.get(selected.observation_id)
        if row is None:
            return NS(status=EvidenceResolutionStatus.ABSTAINED, observation=None)
        data = dict(
            observation_id=row.visible_observation_id,
            page_id=row.page_id,
            document_id=selector.document_id, revision_id=selector.revision_id,
            source_sha256=selector.source_sha256, snapshot_id=selector.snapshot_id,
            observation_kind=row.observation_kind,
            source_primitive_ref=row.original_source_primitive_ref,
            derivation_parent_ids=(row.parent_observation_id,),
            geometry=row.geometry_pdf_points,
        )
        if state["spoof"] is not None and selected.observation_id == observations[0]:
            data.update(state["spoof"])
        return NS(status=EvidenceResolutionStatus.CORROBORATED,
                  observation=NS(**data))
    monkeypatch.setattr(SourceVisibilityAuthority,
                        "resolve_raster_opening_primitive", resolved)
    return owner, selector, parents, bands, record, state


def _run(context, parents=None, bands=None):
    authority, selector, original_parents, original_bands, _, _ = context
    return bind_original_g17_flanks_to_physical_opening_shadow(
        authority, original_selector=selector,
        parent_source=original_parents if parents is None else parents,
        source_bands=original_bands if bands is None else bands,
    )


def test_positive_six_real_source_strokes_are_owned_by_one_physical_opening(monkeypatch):
    c = _context(monkeypatch)
    record = _run(c)
    assert record.status is EvidenceResolutionStatus.CORROBORATED
    assert record.physical_opening_id == "physical-G17-1"
    assert len(record.authenticated_flank_end_parent_ids) == 2
    assert len(record.authenticated_flank_source_visible_ids) == 6
    assert record.source_sha256 == "e" * 64
    assert record.shadow_only and not record.w4_wall_membership_granted
    assert not record.host_binding_granted and not record.firm_area_granted
    assert not record.opening_count_granted and not record.customer_publication_granted


@pytest.mark.parametrize("damage", [
    lambda r: replace(r, snapshot_id="old"),
    lambda r: replace(r, source_sha256="0" * 64),
    lambda r: replace(r, document_id="other"),
    lambda r: replace(r, page_id="4"),
    lambda r: replace(r, status=EvidenceResolutionStatus.CANDIDATE),
    lambda r: replace(r, proposition="invented"),
    lambda r: replace(r, source_observation_ids=()),
    lambda r: replace(r, source_lineage_root_ids=()),
    lambda r: replace(r, source_lineage_root_ids=("foreign-parent",)),
    lambda r: replace(r, source_lineage_root_ids=r.source_lineage_root_ids[:-1]),
    lambda r: replace(r, source_lineage_root_ids=(
        *r.source_lineage_root_ids, r.source_lineage_root_ids[0],
    )),
    lambda r: replace(r, source_observation_ids=r.source_observation_ids[:-1]),
    lambda r: replace(r, source_observation_ids=(*r.source_observation_ids, "foreign")),
    lambda r: replace(r, source_observation_ids=(
        *r.source_observation_ids, r.source_observation_ids[0],
    )),
])
def test_foreign_physical_existence_or_support_cannot_claim_bands(monkeypatch, damage):
    c = _context(monkeypatch)
    c[-1]["record"] = damage(c[4])
    assert _run(c).status is EvidenceResolutionStatus.ABSTAINED


@pytest.mark.parametrize("mutation", [
    {"snapshot_id": "old"},
    {"source_sha256": "0" * 64},
    {"document_id": "other"},
    {"derivation_parent_ids": ("wrong-parent",)},
    {"geometry": (0., 0., 0., 7.)},
    {"observation_kind": "raster_pdf_visible_segment"},
    {"source_primitive_ref": "visible:wrong-source-kind"},
])
def test_reauthenticated_raster_primitive_must_be_identical(monkeypatch, mutation):
    c = _context(monkeypatch)
    c[-1]["spoof"] = mutation
    assert _run(c).status is EvidenceResolutionStatus.ABSTAINED


def test_missing_one_source_band_never_yields_an_opening_host(monkeypatch):
    c = _context(monkeypatch)
    broken_bands = replace(c[3], candidates=c[3].candidates[:1])
    result = _run(c, bands=broken_bands)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert not result.w4_wall_membership_granted and not result.host_binding_granted


def test_swapped_original_root_quarantines_even_if_area_looks_same(monkeypatch):
    c = _context(monkeypatch)
    forged = replace(c[2], source_sha256="0" * 64)
    assert _run(c, parents=forged).status is EvidenceResolutionStatus.ABSTAINED


def test_source_band_geometry_payload_swap_cannot_bypass_independent_replay(monkeypatch):
    c = _context(monkeypatch)
    bands = replace(c[3], candidates=tuple(
        replace(x, near_center_pdf_pt=(100., 100.)) for x in c[3].candidates
    ))
    assert _run(c, bands=bands).status is EvidenceResolutionStatus.ABSTAINED


def test_invalid_untyped_source_authority_rejected(monkeypatch):
    c = _context(monkeypatch)
    monkeypatch.setattr(PhysicalOpeningAuthority, "source_visibility_authority",
                        lambda self: None)
    assert _run(c).status is EvidenceResolutionStatus.ABSTAINED

def _owner_record(physical, observations, *, digest="f" * 64,
                  status=EvidenceResolutionStatus.CORROBORATED):
    return OriginalG17OpeningFlankOwnership(
        status, ("source_owned",), physical, digest,
        tuple(observations), (f"end:{physical}",),
        tuple(observations),
    )


def test_two_disjoint_physical_g17_openings_remain_independently_authored():
    a = _owner_record("physical-a", ("a1", "a2"))
    b = _owner_record("physical-b", ("b1", "b2"))
    actual = quarantine_overlapping_g17_physical_source_claims_shadow((b, a))
    assert actual == (a, b)
    assert all(x.status is EvidenceResolutionStatus.CORROBORATED for x in actual)


def test_two_different_physical_g17_openings_may_not_claim_same_ink():
    a = _owner_record("physical-a", ("same-ink", "a2"))
    b = _owner_record("physical-b", ("same-ink", "b2"))
    actual = quarantine_overlapping_g17_physical_source_claims_shadow((b, a))
    assert len(actual) == 2
    assert all(x.status is EvidenceResolutionStatus.CONFLICT for x in actual)
    assert set(x.physical_opening_id for x in actual) == {"physical-a", "physical-b"}
    assert not any(x.host_binding_granted or x.firm_area_granted for x in actual)


def test_repeated_identical_physical_claim_is_still_a_conflict():
    one = _owner_record("physical-a", ("a1", "a2"))
    assert all(
        x.status is EvidenceResolutionStatus.CONFLICT
        for x in quarantine_overlapping_g17_physical_source_claims_shadow((one, one))
    )


def test_shared_observation_ids_from_different_original_pdfs_do_not_interfere():
    first = _owner_record("physical-a", ("same-ink",), digest="f" * 64)
    second = _owner_record("physical-b", ("same-ink",), digest="e" * 64)
    result = quarantine_overlapping_g17_physical_source_claims_shadow((first, second))
    assert all(x.status is EvidenceResolutionStatus.CORROBORATED for x in result)


def test_one_blocked_source_claim_never_suppresses_independent_firm_source_candidate():
    bad = _owner_record("physical-b", ("same-ink",),
                        status=EvidenceResolutionStatus.ABSTAINED)
    good = _owner_record("physical-a", ("same-ink",))
    result = quarantine_overlapping_g17_physical_source_claims_shadow((bad, good))
    assert [x.status for x in result] == [
        EvidenceResolutionStatus.CORROBORATED,
        EvidenceResolutionStatus.ABSTAINED,
    ]


def test_whole_opening_universe_reconciliation_is_order_invariant():
    a = _owner_record("physical-a", ("same-ink",))
    b = _owner_record("physical-b", ("same-ink",))
    before = (a, b)
    first = quarantine_overlapping_g17_physical_source_claims_shadow(before)
    second = quarantine_overlapping_g17_physical_source_claims_shadow((b, a))
    assert first == second
    assert before == (a, b)

def test_source_lineage_root_permutation_is_canonical_and_accepted(monkeypatch):
    c = _context(monkeypatch)
    c[-1]["record"] = replace(
        c[4], source_lineage_root_ids=tuple(reversed(c[4].source_lineage_root_ids)),
    )
    result = _run(c)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert not result.host_binding_granted and not result.firm_area_granted


def test_spliced_support_from_another_physical_opening_rejected(monkeypatch):
    c = _context(monkeypatch)
    # The correct visible words alone are not evidence that the physical
    # candidate has the same independent original derivation parents.
    c[-1]["record"] = replace(
        c[4], source_lineage_root_ids=("foreign-parent",),
    )
    result = _run(c)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == ("source_g17_original_parent_lineage_unbound",)
