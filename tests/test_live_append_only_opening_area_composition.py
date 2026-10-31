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


@pytest.mark.parametrize("collision", ("same_source_observations", "same_physical_geometry"))
def test_fresh_only_unmeasured_source_rival_cannot_hide_a_new_opening_area(original_claim, collision):
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
            else ("distinct-original-observation",)
        ),
        source_geometries=(
            added.source_geometries if collision == "same_physical_geometry"
            else ((500.0, 500.0, 550.0, 500.0),)
        ),
    )
    with pytest.raises(SourceClosedRunConflictError, match="unmeasured opening rival"):
        _append_reproved_areas(
            baseline, full.canonical_openings + (sibling,), full.opening_quantity_evidence
        )


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
