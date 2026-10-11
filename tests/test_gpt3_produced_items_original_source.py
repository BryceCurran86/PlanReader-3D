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
    assert blockers==["projection_trade_category_missing:qty-room-1"]
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
