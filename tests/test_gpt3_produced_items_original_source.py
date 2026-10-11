"""GPT3 produced-items exporter uses only authentic source bytes and signed quantities."""
from dataclasses import replace
import hashlib
import json

import pytest

from test_combine_source_closed_runs_cli import quantity, trace
from pb_source_closed_run_export import (
    SourceClosedRunConflictError, seal_source_closed_run,
)
from tools.export_gpt3_produced_items import (
    export_verified_produced_items, main,
)


def _source_run(tmp_path, *, source_bytes=b"%PDF-original-source-a", entity="room-1"):
    source=tmp_path/f"{entity}.pdf"
    source.write_bytes(source_bytes)
    sha=hashlib.sha256(source_bytes).hexdigest()
    q=quantity(f"qty-{entity}",entity,sha)
    t=trace(entity,sha)
    sealed=seal_source_closed_run(
        [q],project_id="project-a",traces_by_quantity_id={q.quantity_id:t},
    )
    run_path=tmp_path/f"{entity}.sealed.json"
    run_path.write_text(sealed.to_json(),encoding="utf-8")
    return source,run_path,sha,q,t


def test_original_source_verified_items_preserve_exact_quantity_and_object(tmp_path):
    source,path,sha,q,t=_source_run(tmp_path)
    items=export_verified_produced_items(path,[source],expected_project_id="project-a")
    assert len(items)==1
    row=items[0]
    assert row["quantity_id"]==q.quantity_id
    assert row["project_id"]=="project-a"
    assert row["source_page"]==t.source_page
    assert row["viewport_id"]==t.viewport_id
    assert row["status"]=="firm"
    assert row["authority"]==q.authority
    assert row["confidence"]==q.confidence
    assert row["value"]==10.0 and row["unit"]=="m2"
    assert row["object_refs"]==["room-1"]
    assert row["source_sha256"]==sha
    assert row["trade_category"] is None
    assert row["trade_authority_status"]=="UNAVAILABLE_NOT_INFERRED"
    assert row["lineage_ok"] is True
    assert row["abstained"] is False


def test_missing_original_source_bytes_cannot_be_inferred_from_seal(tmp_path):
    _,path,_,_,_=_source_run(tmp_path)
    with pytest.raises(SourceClosedRunConflictError,match="original source files"):
        export_verified_produced_items(path,[],expected_project_id="project-a")


def test_producer_source_pdf_changed_does_not_write_quantities(tmp_path):
    source,path,_,_,_=_source_run(tmp_path)
    source.write_bytes(b"%PDF-replaced-source-a")
    output=tmp_path/"produced_items.json"
    with pytest.raises(SourceClosedRunConflictError,match="original source SHA"):
        main(["--sealed-run",str(path),"--source",str(source),
              "--project-id","project-a","--output",str(output)])
    assert not output.exists()


def test_project_identity_mismatch_rejected_before_any_produced_items(tmp_path):
    source,path,_,_,_=_source_run(tmp_path)
    with pytest.raises(SourceClosedRunConflictError,match="project identity"):
        export_verified_produced_items(path,[source],expected_project_id="other-project")


def test_missing_source_input_path_does_not_create_output(tmp_path):
    _,path,_,_,_=_source_run(tmp_path)
    output=tmp_path/"produced.json"
    with pytest.raises(FileNotFoundError):
        main(["--sealed-run",str(path),"--source",str(tmp_path/"no.pdf"),
              "--project-id","project-a","--output",str(output)])
    assert not output.exists()


def test_signed_abstention_remains_null_without_claiming_commercial_quantity(tmp_path):
    source,path,sha,q,t=_source_run(tmp_path)
    blocked=replace(q,value=None,abstained=True,status="abstained",
                    input_entity_ids=(),evidence_ids=(),
                    blocking_reasons=("metric_source_unavailable",))
    source_trace=replace(t,canonical_entity_ids=(),evidence_ids=())
    sealed=seal_source_closed_run(
        [blocked],project_id="project-a",traces_by_quantity_id={q.quantity_id:source_trace},
    )
    path.write_text(sealed.to_json(),encoding="utf-8")
    row=export_verified_produced_items(path,[source])[0]
    assert row["abstained"] is True
    assert row["value"] is None
    assert row["object_refs"]==[]


def test_tampered_signed_quantity_value_cannot_be_exported(tmp_path):
    source,path,_,_,_=_source_run(tmp_path)
    payload=json.loads(path.read_text())
    payload["quantities"][0]["value"]=500
    path.write_text(json.dumps(payload),encoding="utf-8")
    with pytest.raises(SourceClosedRunConflictError,match="fingerprint"):
        export_verified_produced_items(path,[source])


def test_exporter_preserves_original_bytes_and_writes_deterministic_array(tmp_path):
    source,path,sha,q,_=_source_run(tmp_path)
    output=tmp_path/"produced_items.json"
    original=path.read_bytes(),source.read_bytes()
    assert main(["--sealed-run",str(path),"--source",str(source),
                 "--project-id","project-a","--output",str(output)])==0
    assert (path.read_bytes(),source.read_bytes())==original
    assert json.loads(output.read_text())[0]["quantity_id"]==q.quantity_id
    assert not list(tmp_path.glob(".produced_items.json.*.tmp"))


@pytest.mark.parametrize("which",["seal","source"])
def test_produced_output_never_overwrites_original_source(which,tmp_path):
    source,path,_,_,_=_source_run(tmp_path)
    target=path if which=="seal" else source
    before=target.read_bytes()
    with pytest.raises(ValueError,match="must not overwrite"):
        main(["--sealed-run",str(path),"--source",str(source),
              "--project-id","project-a","--output",str(target)])
    assert target.read_bytes()==before



def test_source_replaced_after_initial_sha_check_never_publishes(tmp_path,monkeypatch):
    from tools import export_gpt3_produced_items as module
    source,path,_,_,_=_source_run(tmp_path)
    original=module.export_verified_produced_items
    def rotate_after_verifying(*args,**kwargs):
        items=original(*args,**kwargs)
        source.write_bytes(b"%PDF-changed-between-read-and-publication")
        return items
    monkeypatch.setattr(module,"export_verified_produced_items",rotate_after_verifying)
    out=tmp_path/"produced_items.json"
    with pytest.raises(SourceClosedRunConflictError,match="original source changed during"):
        main(["--sealed-run",str(path),"--source",str(source),
              "--project-id","project-a","--output",str(out)])
    assert not out.exists()


def test_sealed_run_swapped_after_verification_never_rekeys_produced_items(tmp_path,monkeypatch):
    from tools import export_gpt3_produced_items as module
    source,path,sha,_,_=_source_run(tmp_path)
    original=module.export_verified_produced_items
    def rotate_signed_receipt(*args,**kwargs):
        items=original(*args,**kwargs)
        q=quantity("qty-substituted","room-1",sha)
        new=seal_source_closed_run(
            [q],project_id="project-a",
            traces_by_quantity_id={q.quantity_id:trace("room-1",sha)},
        )
        path.write_text(new.to_json(),encoding="utf-8")
        return items
    monkeypatch.setattr(module,"export_verified_produced_items",rotate_signed_receipt)
    out=tmp_path/"produced_items.json"
    with pytest.raises(SourceClosedRunConflictError,match="sealed run changed during"):
        main(["--sealed-run",str(path),"--source",str(source),
              "--project-id","project-a","--output",str(out)])
    assert not out.exists()



@pytest.mark.parametrize("old_status",["provisional","review_required","candidate","pending","shadow"])
def test_historically_signed_review_quantity_is_not_a_firm_produced_item(
    old_status,tmp_path
):
    source,path,sha,q,t=_source_run(tmp_path)
    provisional=replace(q,status=old_status)
    sealed=seal_source_closed_run(
        [provisional],project_id="project-a",
        traces_by_quantity_id={q.quantity_id:t},
    )
    path.write_text(sealed.to_json(),encoding="utf-8")
    with pytest.raises(SourceClosedRunConflictError,match="nonfirm"):
        export_verified_produced_items(path,[source])


def test_genuinely_corroborated_original_quantity_is_still_exportable(tmp_path):
    source,path,sha,q,t=_source_run(tmp_path)
    corroborated=replace(q,status="corroborated")
    sealed=seal_source_closed_run(
        [corroborated],project_id="project-a",
        traces_by_quantity_id={q.quantity_id:t},
    )
    path.write_text(sealed.to_json(),encoding="utf-8")
    items=export_verified_produced_items(path,[source])
    assert items[0]["value"]==q.value
    assert items[0]["lineage_ok"] is True



def test_exact_source_seal_parity_is_true_but_trade_authority_still_unavailable(tmp_path):
    from pb_combine_source_closed_runs import load_verified_sealed_run
    from scripts.report_full_plan_v2_readiness import produced_sealed_parity_blockers
    source,path,_,_,_=_source_run(tmp_path)
    signed=load_verified_sealed_run(path)
    rows=export_verified_produced_items(path,[source])
    blockers=produced_sealed_parity_blockers(rows,signed.quantities)
    # Trade remains independent even when the signature/quantity is correct;
    # absent customer rows must also remain explicitly unverified.
    assert blockers==["projection_trade_category_missing:qty-room-1"] or blockers==[
        "projection_customer_output_parity_unverified:qty-room-1",
        "projection_trade_category_missing:qty-room-1",
    ]
    assert rows[0]["trade_category"] is None
    assert rows[0]["trade_authority_status"]=="UNAVAILABLE_NOT_INFERRED"



def _multi_physical_source_run(tmp_path,*, overlap=True,other_family=False):
    source=tmp_path/"multi.pdf"
    source.write_bytes(b"%PDF-original-source-two-physical-rooms")
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    first=replace(quantity("qa","room-a",sha),
                  semantic_key="area:shared",
                  input_entity_ids=("room-a","shared-parent"))
    second=replace(quantity("qb","room-b",sha),
                   semantic_key="area:shared",
                   family="ceiling_area" if other_family else "room_area",
                   input_entity_ids=("room-b","shared-parent") if overlap
                   else ("room-b","disjoint-parent"))
    ta=replace(trace("room-a",sha),canonical_entity_ids=first.input_entity_ids)
    tb=replace(trace("room-b",sha),canonical_entity_ids=second.input_entity_ids)
    run=seal_source_closed_run(
        [first,second],project_id="project-a",
        traces_by_quantity_id={"qa":ta,"qb":tb},
    )
    out=tmp_path/"multi.sealed.json"
    out.write_text(run.to_json(),encoding="utf-8")
    return source,out


def test_historically_signed_partially_overlapping_physical_claims_not_exportable(tmp_path):
    original,sealed=_multi_physical_source_run(tmp_path)
    with pytest.raises(SourceClosedRunConflictError,match="overlapping or duplicate signed physical"):
        export_verified_produced_items(sealed,[original])


def test_independent_physical_quantities_with_same_semantic_type_still_export(tmp_path):
    original,sealed=_multi_physical_source_run(tmp_path,overlap=False)
    rows=export_verified_produced_items(sealed,[original])
    assert [r["quantity_id"] for r in rows]==["qa","qb"]
    assert set(rows[0]["object_refs"]).isdisjoint(rows[1]["object_refs"])


def test_same_physical_object_may_have_distinct_floor_and_ceiling_families(tmp_path):
    original,sealed=_multi_physical_source_run(tmp_path,other_family=True)
    rows=export_verified_produced_items(sealed,[original])
    assert len(rows)==2
    assert rows[0]["family"] != rows[1]["family"]



def test_failed_produced_items_atomic_rename_preserves_existing_report_and_inputs(
    tmp_path,monkeypatch
):
    from tools import export_gpt3_produced_items as exporter
    source,sealed,_,_,_=_source_run(tmp_path)
    output=tmp_path/"produced_items.json"
    output.write_bytes(b'["existing independently verified output"]')
    previous_output=output.read_bytes()
    previous_inputs=(source.read_bytes(),sealed.read_bytes())

    def deny_publication(*_args):
        raise OSError("simulated produced-items publication failure")
    monkeypatch.setattr(exporter.os,"replace",deny_publication)
    with pytest.raises(OSError,match="simulated produced-items publication failure"):
        exporter.main([
            "--sealed-run",str(sealed),"--source",str(source),
            "--project-id","project-a","--output",str(output),
        ])
    assert output.read_bytes()==previous_output
    assert (source.read_bytes(),sealed.read_bytes())==previous_inputs
    assert not list(tmp_path.glob(".produced_items.json.*.tmp"))



def _original_projected_customer_row(q,t):
    from pb_quantity_takeoff_adapter import (
        CommercialMeasurementAuthority,quantity_evidence_to_takeoff_output_row,
    )
    return quantity_evidence_to_takeoff_output_row(
        q,trace=t,authority=CommercialMeasurementAuthority(method="direct_evidence"),
    )


def test_original_source_and_exact_customer_row_bijection_explicitly_verified(tmp_path):
    source,sealed,sha,q,t=_source_run(tmp_path)
    customer=_original_projected_customer_row(q,t)
    produced=export_verified_produced_items(
        sealed,[source],customer_rows=[customer],
    )
    assert produced[0]["customer_output_parity_verified"] is True
    assert produced[0]["customer_output_parity_status"]=="SIGNED_CUSTOMER_BIJECTION_VERIFIED"
    assert produced[0]["trade_category"] is None


@pytest.mark.parametrize("corruption",["missing","duplicate","wrong-quantity"])
def test_missing_duplicate_or_unknown_customer_rows_block_produced_bijection(
    tmp_path,corruption
):
    from pb_customer_output_verification import CustomerOutputVerificationError
    source,sealed,_,q,t=_source_run(tmp_path)
    customer=_original_projected_customer_row(q,t)
    if corruption=="missing":
        rows=[]
    elif corruption=="duplicate":
        rows=[customer,dict(customer)]
    else:
        forged=dict(customer)
        forged["quantity_id"]="unsealed-fabricated-id"
        rows=[forged]
    with pytest.raises(CustomerOutputVerificationError):
        export_verified_produced_items(sealed,[source],customer_rows=rows)


def test_customer_rows_file_cannot_be_overwritten_by_produced_items(tmp_path):
    source,sealed,_,q,t=_source_run(tmp_path)
    customer_path=tmp_path/"customer.json"
    customer_path.write_text(json.dumps([_original_projected_customer_row(q,t)]),encoding="utf-8")
    previous=customer_path.read_bytes()
    with pytest.raises(ValueError,match="must not overwrite"):
        main([
            "--sealed-run",str(sealed),"--source",str(source),
            "--customer-rows",str(customer_path),
            "--project-id","project-a","--output",str(customer_path),
        ])
    assert customer_path.read_bytes()==previous


def test_cli_source_and_customer_verified_export_remains_unpriced_unapproved(tmp_path):
    source,sealed,_,q,t=_source_run(tmp_path)
    customer_path=tmp_path/"customer.json"
    customer_path.write_text(json.dumps([_original_projected_customer_row(q,t)]),encoding="utf-8")
    output=tmp_path/"produced_items.json"
    assert main([
        "--sealed-run",str(sealed),"--source",str(source),
        "--customer-rows",str(customer_path),
        "--project-id","project-a","--output",str(output),
    ])==0
    rows=json.loads(output.read_text())
    assert rows[0]["customer_output_parity_verified"] is True
    assert rows[0]["trade_category"] is None


def test_without_customer_rows_source_export_must_explicitly_mark_parity_unchecked(tmp_path):
    source,sealed,_,q,t=_source_run(tmp_path)
    items=export_verified_produced_items(sealed,[source])
    assert items[0]["customer_output_parity_verified"] is False
    assert items[0]["customer_output_parity_status"]=="NOT_CHECKED_SOURCE_SEAL_ONLY"



def test_duplicate_json_key_inside_embedded_machine_notes_never_counts_as_customer_proof(tmp_path):
    source,sealed,_,q,t=_source_run(tmp_path)
    row=_original_projected_customer_row(q,t)
    assert row["notes"].lstrip().startswith("{")
    forged=dict(row)
    forged["notes"]='{"adapter":"forged",'+row["notes"].lstrip()[1:]
    with pytest.raises(ValueError,match="duplicate customer provenance JSON key: adapter"):
        export_verified_produced_items(sealed,[source],customer_rows=[forged])


def test_outer_customer_json_overflow_is_not_finite_provenance(tmp_path):
    source,sealed,_,q,t=_source_run(tmp_path)
    row=_original_projected_customer_row(q,t)
    customer_path=tmp_path/"customer.json"
    data=json.dumps([row])
    assert '"quantity": 10.0' in data
    customer_path.write_text(data.replace('"quantity": 10.0','"quantity": 1e999',1),
                             encoding="utf-8")
    output=tmp_path/"produced_items.json"
    with pytest.raises(ValueError,match="out-of-range customer JSON number"):
        main([
            "--sealed-run",str(sealed),"--source",str(source),
            "--customer-rows",str(customer_path),
            "--project-id","project-a","--output",str(output),
        ])
    assert not output.exists()


def test_duplicate_outer_customer_quantity_id_does_not_last_write_win(tmp_path):
    source,sealed,_,q,t=_source_run(tmp_path)
    row=_original_projected_customer_row(q,t)
    customer_path=tmp_path/"customer.json"
    data=json.dumps([row])
    assert '"quantity_id": "qty-room-1"' in data
    customer_path.write_text(data.replace(
        '"quantity_id": "qty-room-1"',
        '"quantity_id": "forged", "quantity_id": "qty-room-1"',1,
    ),encoding="utf-8")
    output=tmp_path/"produced_items.json"
    with pytest.raises(ValueError,match="duplicate customer provenance JSON key: quantity_id"):
        main([
            "--sealed-run",str(sealed),"--source",str(source),
            "--customer-rows",str(customer_path),
            "--project-id","project-a","--output",str(output),
        ])
    assert not output.exists()



def test_customer_provenance_changed_after_signed_verification_cannot_publish(
    tmp_path,monkeypatch
):
    from tools import export_gpt3_produced_items as exporter
    source,sealed,_,q,t=_source_run(tmp_path)
    customer_path=tmp_path/"customer.json"
    customer_path.write_text(
        json.dumps([_original_projected_customer_row(q,t)]),encoding="utf-8"
    )
    original=exporter.export_verified_produced_items
    def rotate_customer_after_proof(*args,**kwargs):
        rows=original(*args,**kwargs)
        customer_path.write_text('[]',encoding="utf-8")
        return rows
    monkeypatch.setattr(exporter,"export_verified_produced_items",rotate_customer_after_proof)
    output=tmp_path/"produced_items.json"
    with pytest.raises(SourceClosedRunConflictError,match="customer rows changed during"):
        main([
            "--sealed-run",str(sealed),"--source",str(source),
            "--customer-rows",str(customer_path),
            "--project-id","project-a","--output",str(output),
        ])
    assert not output.exists()



@pytest.mark.parametrize("location",["outer","embedded-notes"])
def test_huge_json_integer_cannot_overflow_authenticated_customer_receipts(
    tmp_path,location
):
    source,sealed,_,q,t=_source_run(tmp_path)
    row=_original_projected_customer_row(q,t)
    customer=tmp_path/"customer.json"
    huge_int="1"+"0"*500
    if location=="outer":
        original=json.dumps([row])
        assert '"workspace_id": 1' in original
        forged=original.replace('"workspace_id": 1',
            '"workspace_id": '+huge_int,1)
    else:
        assert '"workspace_id":1' in row["notes"]
        row["notes"]=row["notes"].replace('"workspace_id":1',
            '"workspace_id":'+huge_int,1)
        forged=json.dumps([row])
    customer.write_text(forged,encoding="utf-8")
    destination=tmp_path/"produced_items.json"
    with pytest.raises(ValueError,match="out-of-range customer JSON integer"):
        main(["--sealed-run",str(sealed),"--source",str(source),
              "--customer-rows",str(customer),"--project-id","project-a",
              "--output",str(destination)])
    assert not destination.exists()



def test_outer_customer_json_depth_limit_fails_before_quantity_output(tmp_path):
    source,sealed,_,_,_=_source_run(tmp_path)
    customer=tmp_path/"customer.json"
    customer.write_text("["*513+"0"+"]"*513,encoding="utf-8")
    output=tmp_path/"produced_items.json"
    with pytest.raises(ValueError,match="customer JSON nesting exceeds safe parser depth"):
        main(["--sealed-run",str(sealed),"--source",str(source),
              "--customer-rows",str(customer),"--project-id","project-a",
              "--output",str(output)])
    assert not output.exists()


def test_machine_notes_json_depth_limit_fails_before_signed_customer_bijection(tmp_path):
    source,sealed,_,q,t=_source_run(tmp_path)
    row=_original_projected_customer_row(q,t)
    row["notes"]="{"*513+"0"+"}"*513
    with pytest.raises(ValueError,match="customer JSON nesting exceeds safe parser depth"):
        export_verified_produced_items(sealed,[source],customer_rows=[row])


def test_quoted_brackets_and_escaped_quotes_do_not_consume_provenance_depth_budget():
    from tools.export_gpt3_produced_items import _strict_customer_json
    notes="["*1200+('source says "'+' and }')*1200
    assert _strict_customer_json(json.dumps({"notes":notes}))=={"notes":notes}
