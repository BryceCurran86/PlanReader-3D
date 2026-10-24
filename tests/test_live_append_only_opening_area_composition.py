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
    assert all(getattr(result, field) == getattr(baseline, field) for field in (
        "canonical_walls", "canonical_rooms", "canonical_floors", "canonical_ceilings",
        "opening_count_quantity_evidence", "room_area_quantity_evidence",
    ))


def test_reissued_old_host_receipts_do_not_replace_original_object_or_quantity(original_claim):
    _, full = original_claim
    baseline = subset(full)
    old = baseline.canonical_openings[0]
    fresh = replace(
        old, snapshot_id="another-real-producer-scope",
        host_binding_record_id="new-host-receipt",
        evidence_ids=tuple("new-host-receipt" if x == old.host_binding_record_id else x
                           for x in old.evidence_ids),
    )
    fresh_quantity = _opening_quantity(fresh)
    assert fresh_quantity is not None and fresh_quantity.to_dict() != baseline.opening_quantity_evidence[0].to_dict()
    objects = tuple(fresh if o.canonical_opening_id == old.canonical_opening_id else o
                    for o in full.canonical_openings)
    quantities = tuple(fresh_quantity if q.quantity_id == fresh_quantity.quantity_id else q
                       for q in full.opening_quantity_evidence)
    result = _append_reproved_areas(baseline, objects, quantities)
    assert result.canonical_openings[0] is old
    assert result.opening_quantity_evidence[0] is baseline.opening_quantity_evidence[0]


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


@pytest.mark.parametrize("flag", (None, 1, "true", []))
def test_recovery_flag_never_coerces_truthy_values(original_claim, flag):
    path, _ = original_claim
    with pytest.raises(ValueError, match="explicit boolean"):
        collect_live_physical_net_wall_claim(path, pages=(0,), recover_additional_opening_areas=flag)


@pytest.mark.parametrize("pages", ((True,), (0, 0), (0, 99), ("0",)))
def test_recovery_never_silently_discards_malformed_page_scope(original_claim, pages):
    path, _ = original_claim
    with pytest.raises(ValueError, match="page indices"):
        collect_live_physical_net_wall_claim(path, pages=pages, recover_additional_opening_areas=True)


def test_default_false_retains_the_existing_source_output(original_claim):
    path, full = original_claim
    repeated = collect_live_physical_net_wall_claim(path, pages=(0,), recover_additional_opening_areas=False)
    assert repeated == full


def test_real_source_recovery_without_new_measurements_keeps_original_claim(original_claim):
    path, full = original_claim
    recovered = collect_live_physical_net_wall_claim(
        path, pages=(0,), recover_additional_opening_areas=True,
    )
    assert recovered == full
