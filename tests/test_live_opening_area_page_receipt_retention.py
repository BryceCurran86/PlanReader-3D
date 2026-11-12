"""Page receipts remain exact when unrelated source pages expand the proof."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import fitz
import pytest

from pb_live_append_only_opening_area_composition import _preserve_page_local_area_receipts
from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_opening_customer_projection import project_live_opening_customer_rows
from pb_live_opening_source_closed_export import seal_live_opening_area_claim_run
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_append_only_opening_area_composition import original_claim  # noqa: F401


@pytest.fixture(scope="module")
def page_claims(original_claim):
    _path, produced = original_claim
    local = replace(produced, opening_count_quantity_evidence=(), opening_dimension_quantity_evidence=())
    # Model a new context's receipt addresses over the actual producer's same
    # physical objects. The original acceptance below covers real page expansion.
    objects = []
    for opening in local.canonical_openings:
        host = "reissued-" + opening.host_binding_record_id if opening.host_binding_record_id else None
        frame = "reissued-" + opening.host_frame_record_id if opening.host_frame_record_id else None
        ids = tuple(host if item == opening.host_binding_record_id else
                    frame if item == opening.host_frame_record_id else item
                    for item in opening.evidence_ids)
        objects.append(replace(opening, snapshot_id="expanded-source-snapshot",
                               host_binding_record_id=host, host_frame_record_id=frame,
                               evidence_ids=ids))
    by_id = {o.canonical_opening_id: o for o in objects}
    quantities = tuple(_opening_quantity(by_id[q.input_entity_ids[0]]) for q in local.opening_quantity_evidence)
    assert all(q is not None for q in quantities)
    broad = replace(local, canonical_openings=tuple(objects), opening_quantity_evidence=quantities)
    assert broad.opening_quantity_evidence != local.opening_quantity_evidence
    return local, broad


def test_real_producer_page_receipts_survive_wider_scope_and_actual_customer_seal(page_claims):
    local, broad = page_claims
    result = _preserve_page_local_area_receipts(broad, local)
    before = seal_live_opening_area_claim_run(local, workspace_id=1, project_id="source")
    after = seal_live_opening_area_claim_run(result, workspace_id=1, project_id="source")
    assert [q.to_dict() for q in after.quantities] == [q.to_dict() for q in before.quantities]
    assert project_live_opening_customer_rows(result, workspace_id=1, project_id="source") == project_live_opening_customer_rows(local, workspace_id=1, project_id="source")
    assert result.opening_quantity_evidence == local.opening_quantity_evidence
    for field in ("canonical_walls", "canonical_rooms", "canonical_floors", "canonical_ceilings",
                  "room_area_quantity_evidence", "floor_finish_quantity_evidence",
                  "ceiling_lining_quantity_evidence"):
        assert getattr(result, field) == getattr(broad, field)


def test_wider_missing_positive_is_never_filled_from_narrow_source(page_claims):
    local, broad = page_claims
    missing = replace(broad, opening_quantity_evidence=())
    assert _preserve_page_local_area_receipts(missing, local) is missing


def test_unmeasured_broad_candidates_and_original_inputs_survive(page_claims):
    local, broad = page_claims
    before = (broad.canonical_openings, broad.opening_quantity_evidence)
    measured = broad.opening_quantity_evidence[0].input_entity_ids[0]
    extra = replace(broad.canonical_openings[0], canonical_opening_id="unmeasured-rival",
                    physical_opening_id="unmeasured-rival", area_m2=None, area_basis=None)
    expanded = replace(broad, canonical_openings=broad.canonical_openings + (extra,))
    result = _preserve_page_local_area_receipts(expanded, local)
    assert result.canonical_openings[-1] is extra
    assert len(result.opening_quantity_evidence) == len(broad.opening_quantity_evidence)
    assert (broad.canonical_openings, broad.opening_quantity_evidence) == before
    assert any(o.canonical_opening_id == measured for o in result.canonical_openings)


@pytest.mark.parametrize("field,value", [
    ("source_sha256", "f" * 64), ("revision_id", "foreign"),
    ("source_geometries", ((0.0, 0.0, 1.0, 1.0),)),
    ("source_observation_ids", ("foreign",)),
    ("source_lineage_root_ids", ("foreign",)), ("area_m2", 123.0),
])
def test_same_id_conflicts_are_rejected_instead_of_picking_page_result(page_claims, field, value):
    local, broad = page_claims
    old = next(o for o in broad.canonical_openings
               if o.canonical_opening_id == broad.opening_quantity_evidence[0].input_entity_ids[0])
    changed = replace(old, **{field: value})
    quantity = _opening_quantity(changed)
    if quantity is None:
        # Some contradictions are already rejected by the real issuer; a
        # copied old quantity must not conceal that invalid canonical source.
        quantity = broad.opening_quantity_evidence[0]
    # Keep the original id to reproduce a same-id, different-source/body claim.
    quantity = replace(quantity, quantity_id=broad.opening_quantity_evidence[0].quantity_id)
    bad = replace(broad, canonical_openings=tuple(changed if o is old else o for o in broad.canonical_openings),
                  opening_quantity_evidence=(quantity,))
    with pytest.raises(SourceClosedRunConflictError):
        _preserve_page_local_area_receipts(bad, local)


@pytest.mark.parametrize("field,value", [
    ("opening_count_quantity_evidence", ("independent-count",)),
    ("opening_dimension_quantity_evidence", ("independent-axis",)),
    ("quantity_m2", 1.0),
])
def test_independent_totals_and_axes_require_their_own_composition(page_claims, field, value):
    local, broad = page_claims
    coupled = replace(broad, **{field: value})
    assert _preserve_page_local_area_receipts(coupled, local) is coupled


def test_ambiguous_and_forged_quantities_fail_closed(page_claims):
    local, broad = page_claims
    with pytest.raises(SourceClosedRunConflictError):
        _preserve_page_local_area_receipts(
            replace(broad, canonical_openings=broad.canonical_openings * 2), local)
    q = broad.opening_quantity_evidence[0]
    with pytest.raises(SourceClosedRunConflictError):
        _preserve_page_local_area_receipts(
            replace(broad, opening_quantity_evidence=(replace(q, value=q.value + 1),)), local)


def test_input_order_and_determinism(page_claims):
    local, broad = page_claims
    expected = _preserve_page_local_area_receipts(broad, local)
    reversed_broad = replace(broad, canonical_openings=tuple(reversed(broad.canonical_openings)))
    result = _preserve_page_local_area_receipts(reversed_broad, local)
    assert {o.canonical_opening_id: o for o in result.canonical_openings} == {o.canonical_opening_id: o for o in expected.canonical_openings}
    assert _preserve_page_local_area_receipts(broad, local) == expected


def test_original_all_page_role_preserves_full_archived_signed_customer_bodies(tmp_path):
    configured = os.environ.get("PLANREADER_LOT16_ORIGINAL_PDF")
    root = Path(__file__).resolve().parents[1]
    pdf = Path(configured) if configured else root / "documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf"
    if not pdf.is_file():
        if configured:
            pytest.fail("configured original is unavailable")
        pytest.skip("source-positive original acceptance NOT RUN")
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
    from tools.run_source_closed_project_handoff import generate_project_handoff
    report = generate_project_handoff(
        pdf_path=pdf, project_id="au_qld_lot16_power", workspace_id=1,
        output_dir=tmp_path / "production", family_group="all",
        source_native_finish_text_shadow=True)
    read = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    current = read(report["combined_run_file"])["quantities"]
    customers = read(report["customer_rows_file"])
    # Prediction and customer verification finish BEFORE historical evidence is read.
    archive = root / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
    before = read(archive / "source_sealed_run.json")["quantities"]
    before_customers = read(archive / "verified_customer_rows.json")
    assert all(q in current for q in before)
    assert all(row in customers for row in before_customers)
    assert len(current) == len(customers) == len(before) + 1


@pytest.mark.parametrize("pages,support,text_optin,expected", [
    ((0,), None, False, False),
    ((0, 1), None, False, True),
    ((0,), (1,), False, True),
    ((0,), None, True, True),
])
def test_recovery_reproves_page_receipts_only_for_expanded_context(
    tmp_path, monkeypatch, page_claims, pages, support, text_optin, expected,
):
    import pb_live_physical_net_wall_integration as live
    import pb_live_append_only_opening_area_composition as append
    pdf = tmp_path / "scope.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.new_page()
        pdf.write_bytes(doc.tobytes())
    _local, broad = page_claims
    monkeypatch.setattr(live, "_collect_live_physical_net_wall_claim", lambda *a, **k: broad)
    captured = {}
    def replay(claim, payload, **kwargs):
        captured.update(kwargs)
        return claim
    monkeypatch.setattr(append, "recover_source_opening_areas", replay)
    live.collect_live_physical_net_wall_claim(
        pdf, pages=pages, topology_pages=(0,), room_area_support_pages=support,
        source_native_finish_text_shadow=text_optin, recover_additional_opening_areas=True)
    assert ("page_local_source_path" in captured) is expected
    if expected:
        assert captured["page_local_source_path"] == pdf


def test_default_collection_never_invokes_page_receipt_reproof(tmp_path, monkeypatch, page_claims):
    import pb_live_physical_net_wall_integration as live
    import pb_live_append_only_opening_area_composition as append
    _local, broad = page_claims
    monkeypatch.setattr(live, "_collect_live_physical_net_wall_claim", lambda *a, **k: broad)
    def forbidden(*args, **kwargs):
        pytest.fail("default collection cannot reprove or change opening receipts")
    monkeypatch.setattr(append, "recover_source_opening_areas", forbidden)
    assert live.collect_live_physical_net_wall_claim(tmp_path / "not-read.pdf", pages=(0, 1)) is broad
