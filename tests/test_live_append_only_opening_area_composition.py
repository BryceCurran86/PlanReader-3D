"""Production composition/seal/customer checks, independent of benchmark truth."""
from dataclasses import replace

import fitz
import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_append_only_opening_area_composition import _append_reproved_areas
from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_opening_customer_projection import project_live_opening_customer_rows
from pb_live_opening_source_closed_export import seal_live_opening_area_claim_run
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_opening_customer_projection import _opening_pdf
from tests.test_live_opening_count_quantity_publication import _floor_plan_with_schedule_quantity


@pytest.fixture(scope="module")
def original_claim(tmp_path_factory):
    # Two real producer-built native openings and their independent schedule
    # rows. A partial previous area publication is not an opening-count claim.
    path = tmp_path_factory.mktemp("append-opening") / "original.pdf"
    doc = fitz.open(stream=_opening_pdf(), filetype="pdf")
    page = doc[0]
    for a, b in (
        ((20, 200), (100, 200)), ((145, 200), (220, 200)),
        ((20, 210), (100, 210)), ((145, 210), (220, 210)),
        ((100, 200), (100, 210)), ((145, 200), (145, 210)),
        ((100, 170), (145, 170)), ((100, 170), (100, 200)),
        ((145, 170), (145, 200)),
    ):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), width=1)
    page.insert_text((112, 165), "900")
    page.insert_text((112, 206), "W2")
    for text, x in zip(("W2", "900", "2100", "900", "3000"), (50, 150, 250, 350, 550)):
        page.insert_text((x, 560), text)
    path.write_bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    full = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert len(full.opening_quantity_evidence) == 2
    return path, full


@pytest.fixture(scope="module")
def counted_claim(tmp_path_factory):
    path = tmp_path_factory.mktemp("append-counted-opening") / "counted.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert len(claim.opening_count_quantity_evidence) == 1
    return claim


def subset(full, *, include_unmeasured=False):
    old_quantity = full.opening_quantity_evidence[0]
    old_id = old_quantity.input_entity_ids[0]
    return replace(
        full, opening_quantity_evidence=(old_quantity,),
        canonical_openings=tuple(o for o in full.canonical_openings
                                 if include_unmeasured or o.canonical_opening_id == old_id),
    )


@pytest.mark.parametrize("include_unmeasured", (False, True))
def test_actual_producer_area_appends_through_sealer_and_customer_without_old_drift(
    original_claim, include_unmeasured,
):
    _, full = original_claim
    baseline = subset(full, include_unmeasured=include_unmeasured)
    before_seal = seal_live_opening_area_claim_run(baseline, workspace_id=1, project_id="source-project")
    before_rows = project_live_opening_customer_rows(baseline, workspace_id=1, project_id="source-project")
    original_objects = baseline.canonical_openings
    result = _append_reproved_areas(baseline, full.canonical_openings, full.opening_quantity_evidence)
    after = seal_live_opening_area_claim_run(result, workspace_id=1, project_id="source-project")
    rows = project_live_opening_customer_rows(result, workspace_id=1, project_id="source-project")
    assert len(after.quantities) == len(rows) == 2
    assert before_seal.quantities[0].to_dict() in [q.to_dict() for q in after.quantities]
    assert all(row in rows for row in before_rows)
    assert verify_sealed_customer_output(after, rows).valid_quantity_count == 2
    assert baseline.canonical_openings == original_objects
    assert result.opening_quantity_evidence[0] is baseline.opening_quantity_evidence[0]
    assert result.opening_area_replay_source_inventory == tuple(sorted(
        full.canonical_openings, key=lambda o: o.canonical_opening_id
    ))
    assert all(getattr(result, field) == getattr(baseline, field) for field in (
        "canonical_walls", "canonical_rooms", "canonical_floors", "canonical_ceilings",
        "opening_count_quantity_evidence", "room_area_quantity_evidence",
    ))


def test_append_retains_full_fresh_source_roster_without_publishing_unsupported_sibling(original_claim):
    _, full = original_claim
    baseline = subset(full)
    published_old = {q.quantity_id for q in baseline.opening_quantity_evidence}
    added_id = next(q.input_entity_ids[0] for q in full.opening_quantity_evidence
                    if q.quantity_id not in published_old)
    added = next(o for o in full.canonical_openings if o.canonical_opening_id == added_id)
    # A producer's unmeasured, spatially separate source observation still
    # belongs to the full replay witness. It must not become a signed row.
    sibling = replace(
        added, canonical_opening_id="original-unmeasured-candidate",
        physical_opening_id="original-unmeasured-candidate",
        representative_observation_id="original-unmeasured-observation",
        source_observation_ids=("original-unmeasured-observation",),
        source_lineage_root_ids=("other-original-wall-fragment",),
        source_geometries=((450.0, 450.0, 475.0, 450.0),),
        area_m2=None, area_basis=None, figured_area_record_id=None,
        # This rival has source ink only, not the measured opening's void.
        geometry_complete=False, wall_local_frame_id=None,
        profile_kind=None, coordinate_unit=None,
        u0=None, u1=None, z0=None, z1=None,
        width_m=None, height_m=None, opening_void_record_id=None,
    )
    fresh_roster = full.canonical_openings + (sibling,)
    result = _append_reproved_areas(baseline, fresh_roster, full.opening_quantity_evidence)
    assert result.opening_area_replay_source_inventory == tuple(
        sorted(fresh_roster, key=lambda o: o.canonical_opening_id)
    )
    assert sibling not in result.canonical_openings
    assert len(result.opening_quantity_evidence) == 2
    assert result.opening_quantity_evidence[0] is baseline.opening_quantity_evidence[0]
    assert result.canonical_openings[0] is baseline.canonical_openings[0]
    sealed = seal_live_opening_area_claim_run(result, workspace_id=1, project_id="source-project")
    rows = project_live_opening_customer_rows(result, workspace_id=1, project_id="source-project")
    assert verify_sealed_customer_output(sealed, rows).valid_quantity_count == 2


@pytest.fixture(scope="module", params=(False, True))
def shared_wall_partition_claim(tmp_path_factory, request):
    """Real source/host/figured issuers, with shared faces between two gaps."""
    from hashlib import sha256

    from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer

    measured_peer = request.param
    path = tmp_path_factory.mktemp("partition-append") / "shared-wall.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=760, height=650)
        for a, b in (
            ((20, 100), (100, 100)), ((140, 100), (200, 100)), ((240, 100), (320, 100)),
            ((20, 110), (100, 110)), ((140, 110), (200, 110)), ((240, 110), (320, 110)),
            ((100, 100), (100, 110)), ((140, 100), (140, 110)),
            ((200, 100), (200, 110)), ((240, 100), (240, 110)),
        ):
            page.draw_line(fitz.Point(*a), fitz.Point(*b), width=1)
        if measured_peer:
            page.insert_text((102, 108), "1521 SGW", fontsize=6)
        page.insert_text((202, 108), "0915 SGW", fontsize=6)
        payload = doc.tobytes(garbage=4, deflate=True)
    path.write_bytes(payload)
    full = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert len(full.canonical_openings) == 2
    assert len(full.opening_quantity_evidence) == 1 + measured_peer
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha256(payload).hexdigest()[:32]}",
        source_bytes=payload, source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=(1,),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    authority = composition.physical_opening_authority
    new_q = full.opening_quantity_evidence[-1]
    new = next(o for o in full.canonical_openings if o.canonical_opening_id == new_q.input_entity_ids[0])
    peer = next(o for o in full.canonical_openings if o is not new)
    assert len(set(new.source_observation_ids) & set(peer.source_observation_ids)) == 2
    baseline = replace(
        full, canonical_openings=(peer,),
        opening_quantity_evidence=tuple(q for q in full.opening_quantity_evidence if q is not new_q),
    )
    return baseline, full, authority, new, peer


@pytest.mark.parametrize("reverse_inventory", (False, True))
def test_verified_shared_wall_partition_reaches_existing_sealer_and_customer(
    shared_wall_partition_claim, reverse_inventory, monkeypatch,
):
    baseline, full, authority, new, peer = shared_wall_partition_claim
    verified = []
    verify = authority.verify_partition_receipt

    def reprove(receipt, left, right):
        verified.append(receipt)
        return verify(receipt, left, right)

    monkeypatch.setattr(authority, "verify_partition_receipt", reprove)
    roster = tuple(reversed(full.canonical_openings)) if reverse_inventory else full.canonical_openings
    quantities = tuple(reversed(full.opening_quantity_evidence)) if reverse_inventory else full.opening_quantity_evidence
    result = _append_reproved_areas(
        baseline, roster, quantities, physical_opening_authority=authority,
    )
    assert verified and all(r.partition == "partitioned" for r in verified)
    assert result.canonical_openings[0] is peer
    assert result.opening_quantity_evidence[:len(baseline.opening_quantity_evidence)] == baseline.opening_quantity_evidence
    assert new in result.canonical_openings
    sealed = seal_live_opening_area_claim_run(result, workspace_id=1, project_id="partition-source")
    rows = project_live_opening_customer_rows(result, workspace_id=1, project_id="partition-source")
    assert verify_sealed_customer_output(sealed, rows).valid_quantity_count == len(quantities)


def test_shared_wall_partition_is_not_an_implicit_caller_allowlist(shared_wall_partition_claim):
    baseline, full, _authority, _new, _peer = shared_wall_partition_claim
    with pytest.raises(SourceClosedRunConflictError):
        _append_reproved_areas(baseline, full.canonical_openings, full.opening_quantity_evidence)


@pytest.mark.parametrize("damage", (
    "source_geometries", "representative_observation_id", "source_observation_ids",
    "source_lineage_root_ids", "snapshot_id", "physical_opening_id", "viewport_id",
))
def test_partition_reproof_binds_exact_canonical_source(shared_wall_partition_claim, damage):
    from pb_live_append_only_opening_area_composition import _source_partition_proves_distinct

    _baseline, _full, authority, new, peer = shared_wall_partition_claim
    changes = {
        "source_geometries": ((10., 10., 15., 10.),),
        "representative_observation_id": "unowned-observation",
        "source_observation_ids": new.source_observation_ids + ("unowned-observation",),
        "source_lineage_root_ids": ("unowned-root",),
        "snapshot_id": "stale-source-snapshot", "physical_opening_id": "another-opening",
        "viewport_id": "another-viewport",
    }
    assert not _source_partition_proves_distinct(authority, replace(new, **{damage: changes[damage]}), peer)


@pytest.mark.parametrize("damage", ("record", "members", "scope", "untyped", "verification"))
def test_wrong_or_unverified_partition_receipt_never_releases_source_veto(
    shared_wall_partition_claim, damage, monkeypatch,
):
    from types import SimpleNamespace
    from pb_source_observation_authority import ObservationSelector

    baseline, full, authority, new, peer = shared_wall_partition_claim
    selectors = [ObservationSelector(
        o.document_id, o.revision_id, o.source_sha256, o.snapshot_id, o.representative_observation_id,
    ) for o in (new, peer)]
    receipt = authority.partition_receipt(*selectors)
    assert receipt.is_physically_distinct
    if damage == "verification":
        monkeypatch.setattr(authority, "verify_partition_receipt", lambda *_: False)
    else:
        invalid = {
            "record": lambda: replace(receipt, left_record_id="foreign-record"),
            "members": lambda: replace(receipt, left_source_observation_ids=("foreign-ink",)),
            "scope": lambda: replace(receipt, snapshot_id="foreign-snapshot"),
            "untyped": lambda: SimpleNamespace(is_physically_distinct=True),
        }[damage]()
        monkeypatch.setattr(authority, "partition_receipt", lambda *_: invalid)
    with pytest.raises(SourceClosedRunConflictError, match="partition"):
        _append_reproved_areas(
            baseline, full.canonical_openings, full.opening_quantity_evidence,
            physical_opening_authority=authority,
        )


@pytest.mark.parametrize("reverse_inventory", (False, True))
def test_partition_consumer_checks_fresh_only_unsupported_rival(
    shared_wall_partition_claim, reverse_inventory,
):
    baseline, full, authority, new, _peer = shared_wall_partition_claim
    unproven = replace(
        new, canonical_opening_id="fresh-unsupported-unproven", physical_opening_id="fresh-unsupported-unproven",
        representative_observation_id="fresh-unproven-ink", source_observation_ids=("fresh-unproven-ink",),
        source_lineage_root_ids=("fresh-unproven-lineage",), source_geometries=((600., 600., 630., 600.),),
        area_m2=None, area_basis=None, figured_area_record_id=None,
        geometry_complete=False, wall_local_frame_id=None,
    )
    roster = full.canonical_openings + (unproven,)
    if reverse_inventory:
        roster = tuple(reversed(roster))
    with pytest.raises(SourceClosedRunConflictError, match="partition"):
        _append_reproved_areas(
            baseline, roster, full.opening_quantity_evidence, physical_opening_authority=authority,
        )


@pytest.mark.parametrize("reverse_inventory", (False, True))
def test_source_reproved_unmeasured_representative_reissue_preserves_historical_object(
    shared_wall_partition_claim, reverse_inventory,
):
    from pb_source_observation_authority import ObservationSelector

    baseline, full, authority, new, peer = shared_wall_partition_claim
    if baseline.opening_quantity_evidence:
        # A measured peer's complete signed representation must not change.
        pytest.skip("representative reissue is only allowed for unmeasured history")
    alternatives = []
    for member in peer.source_observation_ids:
        if member == peer.representative_observation_id:
            continue
        proof = authority.prove_existence(ObservationSelector(
            peer.document_id, peer.revision_id, peer.source_sha256, peer.snapshot_id, member,
        ))
        if proof.existence_record is not None and proof.existence_record.record_id == peer.physical_opening_id:
            alternatives.append((member, proof.source_observation.observation.geometry))
    assert alternatives
    member, geometry = alternatives[0]
    reissued = replace(peer, representative_observation_id=member, source_geometries=(tuple(geometry),))
    roster = (new, reissued) if reverse_inventory else (reissued, new)
    result = _append_reproved_areas(
        baseline, roster, full.opening_quantity_evidence, physical_opening_authority=authority,
    )
    assert result.canonical_openings[0] is peer
    assert reissued in result.opening_area_replay_source_inventory
    assert peer.source_geometries != reissued.source_geometries
    sealed = seal_live_opening_area_claim_run(result, workspace_id=1, project_id="partition-reissue")
    rows = project_live_opening_customer_rows(result, workspace_id=1, project_id="partition-reissue")
    assert verify_sealed_customer_output(sealed, rows).valid_quantity_count == 1


@pytest.mark.parametrize("damage", ("unowned_old_ink", "old_geometry", "old_members", "old_lineage"))
def test_representative_reissue_cannot_authenticate_fabricated_history(shared_wall_partition_claim, damage):
    baseline, full, authority, new, peer = shared_wall_partition_claim
    if baseline.opening_quantity_evidence:
        pytest.skip("unmeasured history control; signed history has stricter retention")
    changes = {
        "unowned_old_ink": {"representative_observation_id": "unowned-historical-ink"},
        "old_geometry": {"source_geometries": ((999., 999., 1001., 999.),)},
        "old_members": {"source_observation_ids": peer.source_observation_ids + ("unowned-ink",)},
        "old_lineage": {"source_lineage_root_ids": ("unowned-lineage",)},
    }
    historical = replace(peer, **changes[damage])
    baseline = replace(baseline, canonical_openings=(historical,))
    with pytest.raises(SourceClosedRunConflictError, match="historical opening source identity"):
        _append_reproved_areas(
            baseline, (new, peer), full.opening_quantity_evidence, physical_opening_authority=authority,
        )


def test_raster_representative_reissue_uses_its_authenticated_primitive_receipt(original_claim):
    """Raster visibility returns a raw-source proposition after receipt checks."""
    from pb_live_append_only_opening_area_composition import _source_representative_reissue_is_authenticated
    from pb_page_view_class_source_adapter import page_viewport_id
    from tests.test_raster_framed_opening_g17_contract import _corroborated_records, _prepare, _selector

    producer, published = _prepare(frame_lines=2)
    record, = _corroborated_records(producer, published)
    authority = producer.physical_opening_authority()
    representatives = []
    for member in record.source_observation_ids:
        proof = authority.prove_existence(_selector(published, member))
        if proof.existence_record is not None and proof.existence_record.record_id == record.record_id:
            representatives.append((member, tuple(proof.source_observation.observation.geometry)))
    assert len(representatives) >= 2
    template = original_claim[1].canonical_openings[0]
    # These objects exercise source reproof only, and never issue a quantity.
    fields = {name: getattr(record, name) for name in (
        "document_id", "revision_id", "source_sha256", "snapshot_id", "page_id",
        "semantic_class", "structural_pattern", "source_observation_ids", "source_lineage_root_ids",
    )}
    previous = replace(
        template, **fields, canonical_opening_id=record.record_id, physical_opening_id=record.record_id,
        viewport_id=record.viewport_id or page_viewport_id(record.page_id),
        representative_observation_id=representatives[0][0], source_geometries=(representatives[0][1],),
        area_m2=None, area_basis=None, figured_area_record_id=None,
    )
    current = replace(previous, representative_observation_id=representatives[1][0], source_geometries=(representatives[1][1],))
    assert _source_representative_reissue_is_authenticated(authority, previous, current)
    assert not _source_representative_reissue_is_authenticated(
        authority, replace(previous, source_geometries=((999., 999., 1000., 999.),)), current,
    )


@pytest.mark.parametrize("collision", (
    "same_source_observations", "partial_source_observation_overlap", "same_physical_geometry",
))
@pytest.mark.parametrize("reverse_inventory", (False, True))
def test_fresh_only_unmeasured_source_rival_cannot_hide_a_new_opening_area(
    original_claim, collision, reverse_inventory,
):
    _, full = original_claim
    baseline = subset(full)
    published_old = {q.quantity_id for q in baseline.opening_quantity_evidence}
    added_id = next(q.input_entity_ids[0] for q in full.opening_quantity_evidence
                    if q.quantity_id not in published_old)
    added = next(o for o in full.canonical_openings if o.canonical_opening_id == added_id)
    sibling = replace(
        added, canonical_opening_id="fresh-only-unsupported",
        physical_opening_id="fresh-only-unsupported",
        area_m2=None, area_basis=None, figured_area_record_id=None,
        source_observation_ids=(
            added.source_observation_ids if collision == "same_source_observations"
            else added.source_observation_ids + ("fresh-only-independent-observation",)
            if collision == "partial_source_observation_overlap"
            else ("distinct-original-observation",)
        ),
        source_geometries=(
            added.source_geometries if collision == "same_physical_geometry"
            else ((500.0, 500.0, 550.0, 500.0),)
        ),
    )
    assert added.source_observation_ids
    roster = full.canonical_openings + (sibling,)
    if reverse_inventory:
        roster = tuple(reversed(roster))
    with pytest.raises(SourceClosedRunConflictError, match="unmeasured opening rival"):
        _append_reproved_areas(baseline, roster, full.opening_quantity_evidence)


@pytest.mark.parametrize("reverse_inventory", (False, True))
@pytest.mark.parametrize("source_overlap", (False, True))
def test_archived_unmeasured_rival_is_checked_against_new_area(
    original_claim, source_overlap, reverse_inventory,
):
    """An old unsupported sibling is not exempt from the fresh source census.

    Replaying its complete exact observation roster must veto the new area
    when the same original source member is shared. A disjoint old unsupported
    sibling remains in canonical output and negative inventory, never as a
    new published quantity. Neither path invents a physical SAME identity.
    """
    _, full = original_claim
    baseline = subset(full)
    old_qty = baseline.opening_quantity_evidence[0]
    added_id = next(q.input_entity_ids[0] for q in full.opening_quantity_evidence
                    if q.quantity_id != old_qty.quantity_id)
    added = next(o for o in full.canonical_openings
                 if o.canonical_opening_id == added_id)
    assert added.source_observation_ids
    historical_rival = replace(
        added,
        canonical_opening_id="archived-unmeasured-opening-rival",
        physical_opening_id="archived-unmeasured-opening-rival",
        representative_observation_id="archived-unmeasured-observation",
        source_observation_ids=(
            added.source_observation_ids[:1] + ("archived-independent-source-member",)
            if source_overlap else ("archived-independent-source-member",)
        ),
        source_lineage_root_ids=("archived-independent-lineage",),
        source_geometries=((610.0, 510.0, 655.0, 510.0),),
        geometry_complete=False, wall_local_frame_id=None,
        profile_kind=None, coordinate_unit=None,
        u0=None, u1=None, z0=None, z1=None,
        width_m=None, height_m=None, opening_void_record_id=None,
        area_m2=None,
        area_basis=None,
        figured_area_record_id=None,
    )
    baseline = replace(
        baseline,
        canonical_openings=baseline.canonical_openings + (historical_rival,),
    )
    roster = full.canonical_openings + (historical_rival,)
    if reverse_inventory:
        roster = tuple(reversed(roster))
    if source_overlap:
        with pytest.raises(SourceClosedRunConflictError, match="unmeasured opening rival"):
            _append_reproved_areas(baseline, roster, full.opening_quantity_evidence)
        return
    result = _append_reproved_areas(baseline, roster, full.opening_quantity_evidence)
    assert result.canonical_openings[:2] == baseline.canonical_openings
    assert result.canonical_openings[1] is historical_rival
    assert result.opening_quantity_evidence[0] is old_qty
    assert historical_rival in result.opening_area_replay_source_inventory
    assert len(result.opening_quantity_evidence) == 2
    sealed = seal_live_opening_area_claim_run(
        result, workspace_id=1, project_id="source-project",
    )
    rows = project_live_opening_customer_rows(
        result, workspace_id=1, project_id="source-project",
    )
    assert verify_sealed_customer_output(sealed, rows).valid_quantity_count == 2


@pytest.mark.parametrize("reverse_inventory", (False, True))
@pytest.mark.parametrize("overlap", (False, True))
def test_measured_opening_rival_requires_independent_source_partition(
    original_claim, overlap, reverse_inventory,
):
    """No second measured aperture may borrow an original source member.

    A new physical ID and a genuine issuer-shaped QuantityEvidence do not
    authenticate independent physical identity. Separate source observations
    still preserve the old signed area and reach the real customer projector.
    """
    _, full = original_claim
    baseline = subset(full)
    old = next(o for o in baseline.canonical_openings
               if o.canonical_opening_id == baseline.opening_quantity_evidence[0].input_entity_ids[0])
    assert old.source_observation_ids
    previous_ids = {q.quantity_id for q in baseline.opening_quantity_evidence}
    new_q = next(q for q in full.opening_quantity_evidence
                 if q.quantity_id not in previous_ids)
    new = next(o for o in full.canonical_openings
               if o.canonical_opening_id == new_q.input_entity_ids[0])
    assert not set(old.source_observation_ids) & set(new.source_observation_ids)

    if overlap:
        # Retain original source geometry, host and figure; forge only a
        # borrowed original member and rederive the real issuer-shaped
        # quantity. Both the old signed body and different IDs stay intact.
        new = replace(
            new,
            source_observation_ids=tuple(dict.fromkeys(
                old.source_observation_ids[:1] + new.source_observation_ids
            )),
        )
        rebuilt = _opening_quantity(new)
        assert rebuilt is not None
        quantities = tuple(
            rebuilt if q.quantity_id == new_q.quantity_id else q
            for q in full.opening_quantity_evidence
        )
    else:
        quantities = full.opening_quantity_evidence
    roster = tuple(new if o.canonical_opening_id == new.canonical_opening_id else o
                   for o in full.canonical_openings)
    if reverse_inventory:
        roster = tuple(reversed(roster))
        quantities = tuple(reversed(quantities))
    if overlap:
        with pytest.raises(
            SourceClosedRunConflictError,
            match="measured opening rival requires source-owned physical partition",
        ):
            _append_reproved_areas(baseline, roster, quantities)
        assert baseline.opening_quantity_evidence[0] is full.opening_quantity_evidence[0]
        return

    result = _append_reproved_areas(baseline, roster, quantities)
    assert result.opening_quantity_evidence[0] is baseline.opening_quantity_evidence[0]
    assert result.canonical_openings[0] is baseline.canonical_openings[0]
    sealed = seal_live_opening_area_claim_run(
        result, workspace_id=1, project_id="source-project",
    )
    rows = project_live_opening_customer_rows(
        result, workspace_id=1, project_id="source-project",
    )
    assert verify_sealed_customer_output(sealed, rows).valid_quantity_count == 2


@pytest.mark.parametrize("reverse_inventory", (False, True))
def test_replay_cannot_erase_archived_unmeasured_competitor(
    original_claim, reverse_inventory,
):
    """A fresh roster is not complete if an old unsupported rival vanished.

    The archived source object is not a measured quantity, but its existence
    remains independent negative evidence against a newly issued area.
    """
    _, full = original_claim
    baseline = subset(full)
    old_qty = baseline.opening_quantity_evidence[0]
    new_qty = next(q for q in full.opening_quantity_evidence
                   if q.quantity_id != old_qty.quantity_id)
    new_opening = next(o for o in full.canonical_openings
                       if o.canonical_opening_id == new_qty.input_entity_ids[0])
    historical = replace(
        new_opening,
        canonical_opening_id="archived-unsupported-not-in-fresh-replay",
        physical_opening_id="archived-unsupported-not-in-fresh-replay",
        representative_observation_id="historic-source-only-observation",
        source_observation_ids=("historic-source-only-observation",),
        source_lineage_root_ids=("historic-source-only-lineage",),
        source_geometries=((520.0, 405.0, 550.0, 405.0),),
        area_m2=None, area_basis=None, figured_area_record_id=None,
    )
    baseline = replace(
        baseline, canonical_openings=baseline.canonical_openings + (historical,)
    )
    assert historical.canonical_opening_id not in {
        o.canonical_opening_id for o in full.canonical_openings
    }
    fresh = full.canonical_openings
    quantities = full.opening_quantity_evidence
    if reverse_inventory:
        fresh = tuple(reversed(fresh))
        quantities = tuple(reversed(quantities))
    with pytest.raises(
        SourceClosedRunConflictError,
        match="historical opening competitor missing from complete source replay",
    ):
        _append_reproved_areas(baseline, fresh, quantities)
    assert baseline.canonical_openings[-1] is historical
    assert baseline.opening_quantity_evidence[0] is old_qty


@pytest.mark.parametrize("reverse_inventory", (False, True))
@pytest.mark.parametrize("damage", (
    "source_geometries", "source_observation_ids", "source_lineage_root_ids",
    "representative_observation_id", "semantic_class", "physical_opening_id",
))
def test_archived_unmeasured_rival_source_identity_is_immutable(
    original_claim, damage, reverse_inventory,
):
    """Reissuing the same historic unsupported ID cannot erase its old ink."""
    _, full = original_claim
    baseline = subset(full)
    old_qty = baseline.opening_quantity_evidence[0]
    new_q = next(q for q in full.opening_quantity_evidence
                 if q.quantity_id != old_qty.quantity_id)
    new = next(o for o in full.canonical_openings
               if o.canonical_opening_id == new_q.input_entity_ids[0])
    historical = replace(
        new,
        canonical_opening_id="historic-unsupported-rival",
        physical_opening_id="historic-unsupported-rival",
        representative_observation_id="historic-observation",
        source_observation_ids=("historic-observation",),
        source_lineage_root_ids=("historic-original-lineage",),
        source_geometries=((530.0, 410.0, 561.0, 410.0),),
        area_m2=None, area_basis=None, figured_area_record_id=None,
    )
    baseline = replace(
        baseline, canonical_openings=baseline.canonical_openings + (historical,),
    )
    mutated = replace(historical, **{
        "source_geometries": {"source_geometries": ((650.0, 420.0, 699.0, 420.0),)},
        "source_observation_ids": {"source_observation_ids": ("different-original-ink",)},
        "source_lineage_root_ids": {"source_lineage_root_ids": ("different-original-lineage",)},
        "representative_observation_id": {"representative_observation_id": "different-original-representative"},
        "semantic_class": {"semantic_class": "another-opening-kind"},
        "physical_opening_id": {"physical_opening_id": "different-physical-instance"},
    }[damage])
    fresh = full.canonical_openings + (mutated,)
    quantities = full.opening_quantity_evidence
    if reverse_inventory:
        fresh = tuple(reversed(fresh))
        quantities = tuple(reversed(quantities))
    with pytest.raises(
        SourceClosedRunConflictError,
        match="historical opening source identity changed during replay",
    ):
        _append_reproved_areas(baseline, fresh, quantities)
    assert baseline.canonical_openings[-1] is historical
    assert baseline.opening_quantity_evidence[0] is old_qty


def test_historical_unmeasured_rival_allows_new_snapshot_and_host_receipt_reissue(
    original_claim,
):
    """Only receipt freshness may change; original physical source remains."""
    _, full = original_claim
    baseline = subset(full)
    previous = baseline.opening_quantity_evidence[0]
    new_q = next(q for q in full.opening_quantity_evidence
                 if q.quantity_id != previous.quantity_id)
    new = next(o for o in full.canonical_openings
               if o.canonical_opening_id == new_q.input_entity_ids[0])
    historical = replace(
        new,
        canonical_opening_id="historic-unsupported-rival",
        physical_opening_id="historic-unsupported-rival",
        representative_observation_id="historic-ink",
        source_observation_ids=("historic-ink",),
        source_lineage_root_ids=("historic-root",),
        source_geometries=((530.0, 410.0, 561.0, 410.0),),
        area_m2=None, area_basis=None, figured_area_record_id=None,
        geometry_complete=False, wall_local_frame_id=None,
        profile_kind=None, coordinate_unit=None,
        u0=None, u1=None, z0=None, z1=None,
        width_m=None, height_m=None, opening_void_record_id=None,
    )
    baseline = replace(
        baseline, canonical_openings=baseline.canonical_openings + (historical,),
    )
    reissued = tuple(
        replace(
            o, snapshot_id="fresh-original-producer-snapshot",
            **({"host_binding_record_id": "fresh-host-receipt"}
               if o.canonical_opening_id == historical.canonical_opening_id
               else {}),
        )
        for o in full.canonical_openings + (historical,)
    )
    quantities = tuple(
        q for o in reissued
        if (q := _opening_quantity(o)) is not None
    )
    result = _append_reproved_areas(baseline, reissued, quantities)
    assert result.canonical_openings[:2] == baseline.canonical_openings
    assert result.canonical_openings[1] is historical
    assert result.opening_quantity_evidence[0] is previous
    assert len(result.opening_quantity_evidence) == 2
    assert result.opening_area_replay_source_inventory == tuple(
        sorted(reissued, key=lambda opening: opening.canonical_opening_id)
    )
    sealed = seal_live_opening_area_claim_run(
        result, workspace_id=1, project_id="source-project",
    )
    rows = project_live_opening_customer_rows(
        result, workspace_id=1, project_id="source-project",
    )
    assert verify_sealed_customer_output(sealed, rows).valid_quantity_count == 2


@pytest.mark.parametrize("reverse_inventory", (False, True))
@pytest.mark.parametrize("sibling_kind", ("old_measured", "fresh_unmeasured"))
@pytest.mark.parametrize("separation", ("overlap", "separate_u", "separate_z", "touching"))
def test_source_owned_same_wall_metric_void_collision_is_negative_only(
    original_claim, reverse_inventory, sibling_kind, separation,
):
    """Two complete same-frame openings cannot occupy the same metric patch.

    This does not infer DISTINCT from disjoint source geometry or overwrite
    the real source-owned physical identity / original sealed quantity.
    """
    _, full = original_claim
    baseline = subset(full)
    old_id = baseline.opening_quantity_evidence[0].input_entity_ids[0]
    old = next(o for o in full.canonical_openings if o.canonical_opening_id == old_id)
    new = next(o for o in full.canonical_openings if o.canonical_opening_id != old_id)
    rect = dict(
        geometry_complete=True, wall_local_frame_id="authenticated-local-wall-frame",
        profile_kind="rectangular_rough_opening", coordinate_unit="metre",
    )
    a_rect = dict(**rect, u0=0.0, u1=1.0, z0=0.0, z1=2.0)
    b_rect = {
        "overlap": dict(u0=0.5, u1=1.5, z0=0.5, z1=2.5),
        "separate_u": dict(u0=2.0, u1=3.0, z0=0.5, z1=2.5),
        "separate_z": dict(u0=0.5, u1=1.5, z0=3.0, z1=5.0),
        "touching": dict(u0=1.0, u1=2.0, z0=0.5, z1=2.5),
    }[separation]
    if sibling_kind == "old_measured":
        old = replace(old, **a_rect)
        new = replace(new, **rect, **b_rect)
        old_quantity = _opening_quantity(old)
        new_quantity = _opening_quantity(new)
        assert old_quantity is not None and new_quantity is not None
        baseline = replace(
            baseline, canonical_openings=(old,), opening_quantity_evidence=(old_quantity,),
        )
        roster = (old, new)
        quantities = (old_quantity, new_quantity)
    else:
        unsupported = replace(
            new,
            canonical_opening_id="new-unmeasured-independent-ink",
            physical_opening_id="new-unmeasured-independent-ink",
            representative_observation_id="independent-ink-observation",
            source_observation_ids=("independent-ink-observation",),
            source_lineage_root_ids=("independent-ink-root",),
            source_geometries=((700.0, 700.0, 740.0, 700.0),),
            area_m2=None, area_basis=None, figured_area_record_id=None,
            **rect, **b_rect,
        )
        new = replace(new, **a_rect)
        new_quantity = _opening_quantity(new)
        assert new_quantity is not None
        roster = (old, new, unsupported)
        quantities = (baseline.opening_quantity_evidence[0], new_quantity)

    if reverse_inventory:
        roster = tuple(reversed(roster))
        quantities = tuple(reversed(quantities))
    if separation == "overlap":
        with pytest.raises(SourceClosedRunConflictError, match=(
            "measured opening rival" if sibling_kind == "old_measured"
            else "unmeasured opening rival"
        )):
            _append_reproved_areas(baseline, roster, quantities)
        return
    result = _append_reproved_areas(baseline, roster, quantities)
    assert result.opening_quantity_evidence[0] is baseline.opening_quantity_evidence[0]
    assert result.canonical_openings[0] is baseline.canonical_openings[0]
    sealed = seal_live_opening_area_claim_run(
        result, workspace_id=1, project_id="source-project",
    )
    rows = project_live_opening_customer_rows(
        result, workspace_id=1, project_id="source-project",
    )
    assert verify_sealed_customer_output(sealed, rows).valid_quantity_count == 2


def test_full_fresh_source_inventory_rejects_a_mixed_snapshot(original_claim):
    _, full = original_claim
    baseline = subset(full)
    published_old = {q.quantity_id for q in baseline.opening_quantity_evidence}
    added_id = next(q.input_entity_ids[0] for q in full.opening_quantity_evidence
                    if q.quantity_id not in published_old)
    added = next(o for o in full.canonical_openings if o.canonical_opening_id == added_id)
    sibling = replace(
        added, canonical_opening_id="foreign-source-only",
        physical_opening_id="foreign-source-only",
        snapshot_id="different-source-snapshot",
        area_m2=None, area_basis=None, figured_area_record_id=None,
    )
    with pytest.raises(SourceClosedRunConflictError, match="replay source scope"):
        _append_reproved_areas(
            baseline, full.canonical_openings + (sibling,), full.opening_quantity_evidence
        )


def test_reissued_old_host_receipts_do_not_replace_original_object_or_quantity(original_claim):
    _, full = original_claim
    baseline = subset(full)
    old = baseline.canonical_openings[0]
    # A real source reproof owns ONE fresh snapshot across the entire
    # canonical roster. Reissue the old host receipt in that coherent scope;
    # do not fabricate a mixed-snapshot success case.
    fresh_snapshot = "another-real-producer-scope"
    objects = tuple(
        replace(
            opening,
            snapshot_id=fresh_snapshot,
            **({
                "host_binding_record_id": "new-host-receipt",
                "evidence_ids": tuple(
                    "new-host-receipt" if x == old.host_binding_record_id else x
                    for x in old.evidence_ids
                ),
            } if opening.canonical_opening_id == old.canonical_opening_id else {}),
        )
        for opening in full.canonical_openings
    )
    quantities = tuple(_opening_quantity(opening) for opening in objects)
    assert all(quantity is not None for quantity in quantities)
    fresh_old_quantity = next(
        quantity for quantity in quantities
        if quantity.input_entity_ids == (old.canonical_opening_id,)
    )
    assert fresh_old_quantity.to_dict() != baseline.opening_quantity_evidence[0].to_dict()
    result = _append_reproved_areas(baseline, objects, quantities)
    assert result.canonical_openings[0] is old
    assert result.opening_quantity_evidence[0] is baseline.opening_quantity_evidence[0]
    assert result.opening_area_replay_source_inventory == tuple(
        sorted(objects, key=lambda opening: opening.canonical_opening_id)
    )
    assert {opening.snapshot_id for opening in result.opening_area_replay_source_inventory} == {
        fresh_snapshot
    }


def test_reissued_old_host_receipt_cannot_hide_a_mixed_fresh_snapshot(original_claim):
    _, full = original_claim
    baseline = subset(full)
    old = baseline.canonical_openings[0]
    objects = tuple(
        replace(opening, snapshot_id="another-real-producer-scope")
        if opening.canonical_opening_id == old.canonical_opening_id else opening
        for opening in full.canonical_openings
    )
    quantities = tuple(_opening_quantity(opening) for opening in objects)
    assert all(quantity is not None for quantity in quantities)
    with pytest.raises(SourceClosedRunConflictError, match="replay source scope"):
        _append_reproved_areas(baseline, objects, quantities)

@pytest.mark.parametrize("damage", (
    "lost_old", "changed_value", "foreign_revision", "source_support",
    "source_geometry", "duplicate_canonical", "duplicate_quantity", "forged_measurement",
))
def test_source_conflicts_cannot_be_laundered_as_append_only(original_claim, damage):
    _, full = original_claim
    baseline = subset(full)
    objects = full.canonical_openings
    quantities = full.opening_quantity_evidence
    oid = baseline.opening_quantity_evidence[0].input_entity_ids[0]
    old = next(o for o in objects if o.canonical_opening_id == oid)
    if damage == "lost_old":
        quantities = tuple(q for q in quantities if q.input_entity_ids != (oid,))
    elif damage == "duplicate_canonical":
        objects += (old,)
    elif damage == "duplicate_quantity":
        quantities += (quantities[0],)
    elif damage == "forged_measurement":
        quantities = tuple(replace(q, value=q.value + 1) if q.input_entity_ids == (oid,) else q
                           for q in quantities)
    else:
        changes = {
            "changed_value": {"area_m2": old.area_m2 + 1},
            "foreign_revision": {"revision_id": "foreign"},
            "source_support": {"source_lineage_root_ids": ("foreign-source",)},
            "source_geometry": {"source_geometries": ((0., 0., 999., 0.),)},
        }[damage]
        changed = replace(old, **changes)
        objects = tuple(changed if o is old else o for o in objects)
        quantities = tuple(_opening_quantity(changed) if q.input_entity_ids == (oid,) else q
                           for q in quantities)
    with pytest.raises((SourceClosedRunConflictError, TypeError)):
        _append_reproved_areas(baseline, objects, quantities)


def test_same_physical_opening_cannot_append_a_second_area_under_new_quantity_id(original_claim):
    _, full = original_claim
    baseline = subset(full)
    old = baseline.canonical_openings[0]
    alias = replace(old, figured_area_record_id="another-measurement")
    # A changed receipt cannot make one physical object contribute two areas.
    q = replace(baseline.opening_quantity_evidence[0], quantity_id="another-quantity")
    with pytest.raises(SourceClosedRunConflictError):
        _append_reproved_areas(baseline, (old, alias), (baseline.opening_quantity_evidence[0], q))


def test_order_of_new_source_inventory_does_not_select_a_different_addition(original_claim):
    _, full = original_claim
    baseline = subset(full)
    a = _append_reproved_areas(baseline, full.canonical_openings, full.opening_quantity_evidence)
    b = _append_reproved_areas(baseline, tuple(reversed(full.canonical_openings)),
                              tuple(reversed(full.opening_quantity_evidence)))
    assert a == b
    assert _append_reproved_areas(baseline, baseline.canonical_openings,
                                 baseline.opening_quantity_evidence) is baseline


@pytest.mark.parametrize("published_scope", ("count", "net_wall"))
def test_area_append_cannot_silently_stale_other_opening_dependent_publications(
    original_claim, counted_claim, published_scope,
):
    _, full = original_claim
    baseline = subset(full, include_unmeasured=True)
    if published_scope == "count":
        # A genuine count receipt from a separately authenticated producer
        # cannot ride an area-only enrichment without its own scope reproof.
        # In particular, a foreign count must not survive by being ignored.
        baseline = replace(baseline, opening_count_quantity_evidence=counted_claim.opening_count_quantity_evidence)
    else:
        # Exercise the collector's published-total field, not a new issuer.
        baseline = replace(baseline, opening_count_quantity_evidence=(), quantity_m2=12.0)
    with pytest.raises(SourceClosedRunConflictError, match="reproof of published"):
        _append_reproved_areas(baseline, full.canonical_openings, full.opening_quantity_evidence)
    assert _append_reproved_areas(baseline, baseline.canonical_openings,
                                 baseline.opening_quantity_evidence) is baseline


@pytest.mark.parametrize("option", ("recover_additional_opening_areas", "recover_supported_opening_areas"))
@pytest.mark.parametrize("flag", (None, 1, "true", []))
def test_recovery_flag_never_coerces_truthy_values(original_claim, flag, option):
    path, _ = original_claim
    with pytest.raises(ValueError, match="explicit boolean"):
        collect_live_physical_net_wall_claim(path, pages=(0,), **{option: flag})


@pytest.mark.parametrize("option", ("recover_additional_opening_areas", "recover_supported_opening_areas"))
@pytest.mark.parametrize("pages", ((True,), (0, 0), (0, 99), ("0",)))
def test_recovery_never_silently_discards_malformed_page_scope(original_claim, pages, option):
    path, _ = original_claim
    with pytest.raises(ValueError, match="page indices"):
        collect_live_physical_net_wall_claim(path, pages=pages, **{option: True})


def test_default_false_retains_the_existing_source_output(original_claim):
    path, full = original_claim
    repeated = collect_live_physical_net_wall_claim(path, pages=(0,), recover_additional_opening_areas=False)
    assert repeated == full
    assert repeated.opening_area_replay_source_inventory == ()


def test_real_source_recovery_without_new_measurements_keeps_original_claim(original_claim):
    path, full = original_claim
    recovered = collect_live_physical_net_wall_claim(
        path, pages=(0,), recover_additional_opening_areas=True,
    )
    assert recovered == full


def test_supported_native_recovery_keeps_real_issuer_and_customer_output(original_claim):
    path, full = original_claim
    recovered = collect_live_physical_net_wall_claim(
        path, pages=(0,), recover_supported_opening_areas=True,
    )
    assert recovered == full
    sealed = seal_live_opening_area_claim_run(recovered, workspace_id=1, project_id="source-project")
    rows = project_live_opening_customer_rows(recovered, workspace_id=1, project_id="source-project")
    assert verify_sealed_customer_output(sealed, rows).valid_quantity_count == 2


@pytest.mark.parametrize("published_scope", ("count", "net_wall", "zero_net_wall"))
def test_application_recovery_preserves_scopes_requiring_independent_reproof(
    original_claim, counted_claim, published_scope, monkeypatch,
):
    path, full = original_claim
    if published_scope == "count":
        baseline = replace(full, opening_count_quantity_evidence=counted_claim.opening_count_quantity_evidence)
    else:
        baseline = replace(full, quantity_m2=0.0 if published_scope == "zero_net_wall" else 12.0)
    monkeypatch.setattr(
        "pb_live_physical_net_wall_integration._collect_live_physical_net_wall_claim",
        lambda *args, **kwargs: baseline,
    )

    def forbidden_replay(*args, **kwargs):
        pytest.fail("area-only application recovery attempted an independently published scope")

    monkeypatch.setattr("pb_live_append_only_opening_area_composition.recover_source_opening_areas", forbidden_replay)
    assert collect_live_physical_net_wall_claim(
        path, pages=(0,), recover_supported_opening_areas=True,
    ) is baseline


def test_application_recovery_keeps_the_entire_multi_page_topology(tmp_path, original_claim, monkeypatch):
    path, _ = original_claim
    with fitz.open(path) as doc:
        doc.new_page()
        multi = tmp_path / "two-topology-pages.pdf"
        multi.write_bytes(doc.tobytes())
    baseline = collect_live_physical_net_wall_claim(multi, pages=(0, 1))

    def forbidden_replay(*args, **kwargs):
        pytest.fail("application recovery narrowed a multi-page topology universe")

    monkeypatch.setattr("pb_live_append_only_opening_area_composition.recover_source_opening_areas", forbidden_replay)
    assert collect_live_physical_net_wall_claim(
        multi, pages=(0, 1), recover_supported_opening_areas=True,
    ) == baseline


def test_strict_and_supported_recovery_cannot_be_combined(original_claim):
    path, _ = original_claim
    with pytest.raises(ValueError, match="choose one"):
        collect_live_physical_net_wall_claim(
            path, pages=(0,), recover_additional_opening_areas=True,
            recover_supported_opening_areas=True,
        )


@pytest.mark.parametrize("classification", ("unproven", "unavailable"))
def test_application_recovery_needs_a_positive_original_floor_plan_role(
    original_claim, monkeypatch, classification,
):
    from types import SimpleNamespace

    path, baseline = original_claim

    def classify(*args, **kwargs):
        if classification == "unavailable":
            raise RuntimeError("source classification unavailable")
        return SimpleNamespace(floor_plan_page_indices=())

    def forbidden_replay(*args, **kwargs):
        pytest.fail("an unproven source-page role enabled opening recovery")

    monkeypatch.setattr("pb_source_floor_plan_page_scope.source_floor_plan_topology_scope", classify)
    monkeypatch.setattr("pb_live_append_only_opening_area_composition.recover_source_opening_areas", forbidden_replay)
    assert collect_live_physical_net_wall_claim(
        path, pages=(0,), recover_supported_opening_areas=True,
    ) == baseline


# GPT3 reproof/seal interaction with MAX's append-only source snapshots.
# Synthetic typed openings stand in for source-proved candidates; real original
# evidence remains mandatory for the owner-private production acceptance test.
def _two_snapshot_area_claim(original_claim):
    from dataclasses import replace as dc_replace
    _, full = original_claim
    old, fresh = full.opening_quantity_evidence
    oid = fresh.input_entity_ids[0]
    originals = tuple(full.canonical_openings)
    opening = next(o for o in originals if o.canonical_opening_id == oid)
    new_opening = dc_replace(opening, snapshot_id="independently-reproved-source-snapshot")
    new_quantity = _opening_quantity(new_opening)
    assert new_quantity is not None
    amended = dc_replace(
        full,
        canonical_openings=tuple(new_opening if o.canonical_opening_id == oid else o for o in originals),
        opening_quantity_evidence=(old, new_quantity),
    )
    return full, amended


def test_strict_default_seal_still_rejects_two_original_producer_snapshots(original_claim):
    _, amended = _two_snapshot_area_claim(original_claim)
    with pytest.raises(SourceClosedRunConflictError, match="conflicting explicit source snapshot"):
        seal_live_opening_area_claim_run(
            amended, workspace_id=1, project_id="source-project",
        )


def test_explicit_source_reproved_append_joins_independent_snapshot_seals_without_old_drift(
    original_claim,
):
    from dataclasses import replace as dc_replace
    from pb_source_closed_run_export import combine_source_closed_runs
    _, amended = _two_snapshot_area_claim(original_claim)
    old = amended.opening_quantity_evidence[0]
    original = dc_replace(
        amended,
        opening_quantity_evidence=(old,),
        canonical_openings=tuple(
            o for o in amended.canonical_openings if o.canonical_opening_id == old.input_entity_ids[0]
        ),
    )
    baseline = seal_live_opening_area_claim_run(
        original, workspace_id=1, project_id="source-project",
    )
    combined = seal_live_opening_area_claim_run(
        amended, workspace_id=1, project_id="source-project",
        source_reproved_append_only=True,
    )
    customer = project_live_opening_customer_rows(
        amended, workspace_id=1, project_id="source-project",
        source_reproved_append_only=True,
    )
    assert len(combined.quantities) == len(customer) == 2
    assert baseline.quantities[0].to_dict() in [row.to_dict() for row in combined.quantities]
    assert verify_sealed_customer_output(combined, customer).valid_quantity_count == 2
    # Combined result uses the EXISTING sealer and duplicate claim consumer,
    # not a second re-signing vocabulary or hand-authored fingerprint.
    newonly = dc_replace(
        amended,
        opening_quantity_evidence=(amended.opening_quantity_evidence[1],),
    )
    newseal = seal_live_opening_area_claim_run(
        newonly, workspace_id=1, project_id="source-project",
    )
    independently_combined = combine_source_closed_runs(
        (baseline, newseal), project_id="source-project",
    )
    assert combined.to_dict() == independently_combined.to_dict()


@pytest.mark.parametrize("flag", (None, 1, "true", [], {}))
def test_untyped_cross_snapshot_seal_permit_fails(original_claim, flag):
    _, amended = _two_snapshot_area_claim(original_claim)
    with pytest.raises(ValueError, match="explicitly boolean"):
        seal_live_opening_area_claim_run(
            amended, workspace_id=1, project_id="source-project",
            source_reproved_append_only=flag,
        )


def test_source_reproved_append_rejects_foreign_original_root(original_claim):
    from dataclasses import replace as dc_replace
    _, amended = _two_snapshot_area_claim(original_claim)
    opening = next(
        o for o in amended.canonical_openings
        if o.canonical_opening_id == amended.opening_quantity_evidence[1].input_entity_ids[0]
    )
    foreign = dc_replace(opening, revision_id="unrelated-source-revision")
    forged = dc_replace(
        amended,
        canonical_openings=tuple(
            foreign if o.canonical_opening_id == opening.canonical_opening_id else o
            for o in amended.canonical_openings
        ),
        opening_quantity_evidence=(
            amended.opening_quantity_evidence[0], _opening_quantity(foreign)
        ),
    )
    with pytest.raises(SourceClosedRunConflictError, match="original source roots"):
        seal_live_opening_area_claim_run(
            forged, workspace_id=1, project_id="source-project",
            source_reproved_append_only=True,
        )


def test_reproved_append_refuses_source_alias_and_stale_dependents(original_claim, counted_claim):
    from dataclasses import replace as dc_replace
    _, amended = _two_snapshot_area_claim(original_claim)
    with pytest.raises(SourceClosedRunConflictError, match="stale opening count"):
        seal_live_opening_area_claim_run(
            dc_replace(amended, opening_count_quantity_evidence=counted_claim.opening_count_quantity_evidence),
            workspace_id=1, project_id="source-project", source_reproved_append_only=True,
        )
    # Select the two ACTUALLY measured physical identities. Original source
    # production may also carry unmeasured canonical opening candidates.
    by_id = {o.canonical_opening_id: o for o in amended.canonical_openings}
    old = by_id[amended.opening_quantity_evidence[0].input_entity_ids[0]]
    fresh = by_id[amended.opening_quantity_evidence[1].input_entity_ids[0]]
    copied = dc_replace(
        fresh,
        source_observation_ids=old.source_observation_ids,
        source_lineage_root_ids=old.source_lineage_root_ids,
        source_geometries=old.source_geometries,
    )
    # Keep matching typed issuer output so it reaches the cross-scope collision
    # guard rather than failing a simple quantity-to-opening-dict comparison.
    # Copying original source receipts invalidates the typed quantity producer.
    # Retain the previously issued new quantity to test that copied physical
    # source receipts cannot be projected as an authenticated append.
    q = amended.opening_quantity_evidence[1]
    assert _opening_quantity(copied) is None
    forged = dc_replace(
        amended,
        canonical_openings=tuple(
            copied if o.canonical_opening_id == fresh.canonical_opening_id else o
            for o in amended.canonical_openings
        ),
        opening_quantity_evidence=(amended.opening_quantity_evidence[0], q),
    )
    with pytest.raises((SourceClosedRunConflictError, ValueError)):
        seal_live_opening_area_claim_run(
            forged, workspace_id=1, project_id="source-project",
            source_reproved_append_only=True,
        )
