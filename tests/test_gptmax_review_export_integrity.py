"""Review exports remain nonpublishing, create-only and failure-atomic."""
from copy import deepcopy
from pathlib import Path
import csv
import io
import zipfile

import pytest

from tests.symlink_test_support import symlink_or_skip
import tools.build_opening_source_review_package as export
from pb_opening_source_review_shadow import nominal_opening_obj_shadow


@pytest.fixture(scope="module")
def report():
    from test_gptmax_source_geometry_recovery_batch import source
    from tools.recover_source_preserving_openings_shadow import recover_source_preserving_openings_shadow
    producer, published = source()
    return recover_source_preserving_openings_shadow(producer,
        revision_id=published.revision.revision_id, page_ids=("1",))


@pytest.mark.parametrize("damage", ["report-list", "truthy-authority", "customer-authority",
    "signed-reissue", "score-claim", "foreign-source", "bad-receipt", "bad-packets",
    "packet-takeoff", "packet-deduction", "foreign-selector", "bad-page", "formula-blocker",
    "lineage-import"])
def test_invalid_export_is_rejected_before_output_creation(report, tmp_path, damage):
    data = deepcopy(report)
    p = data["original_opening_review_packets"][0]
    if damage == "report-list": data = []
    elif damage == "truthy-authority": data["new_authority_promotion_granted"] = 0
    elif damage == "customer-authority": data["customer_publication_granted"] = True
    elif damage == "signed-reissue": data["original_signed_rows_reissued"] = True
    elif damage == "score-claim": data["official_benchmark_executed"] = True
    elif damage == "foreign-source": data["original_source_sha256"] = "0"*64
    elif damage == "bad-receipt": data["original_receipt"]["frames"] = "not records"
    elif damage == "bad-packets": data["original_opening_review_packets"] = "not packets"
    elif damage == "packet-takeoff": p["takeoff_eligible"] = 0
    elif damage == "packet-deduction": p["deduction_authority"] = True
    elif damage == "foreign-selector": p["selector"]["source_sha256"] = "0"*64
    elif damage == "bad-page": p["page_id"] = "01"
    elif damage == "formula-blocker": p["next_required_evidence"] = ["=external_link()"]
    elif damage == "lineage-import": p["source_lineage"]["authority_import_allowed"] = True
    output = tmp_path/"nested"/"review.zip"
    with pytest.raises(ValueError):
        export.build_opening_source_review_package(data, output)
    assert not output.exists()
    assert not output.parent.exists()


def test_existing_evidence_is_never_overwritten(report, tmp_path):
    output = tmp_path/"review.zip"
    output.write_bytes(b"existing evidence")
    with pytest.raises(FileExistsError):
        export.build_opening_source_review_package(report, output)
    assert output.read_bytes() == b"existing evidence"


@pytest.mark.parametrize("target_exists", [False, True])
def test_output_symlink_cannot_alias_another_evidence_file(report, tmp_path, target_exists):
    target, output = tmp_path/"target.zip", tmp_path/"review.zip"
    if target_exists: target.write_bytes(b"target evidence")
    symlink_or_skip(output, target)
    with pytest.raises(FileExistsError):
        export.build_opening_source_review_package(report, output)
    assert output.is_symlink()
    assert target.read_bytes() == b"target evidence" if target_exists else not target.exists()


def test_archive_write_failure_never_leaves_partial_export(report, tmp_path, monkeypatch):
    original = export.zipfile.ZipFile.writestr
    calls = 0
    def fail_during_write(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2: raise OSError("simulated interrupted archive")
        return original(self,*args,**kwargs)
    monkeypatch.setattr(export.zipfile.ZipFile,"writestr",fail_during_write)
    output = tmp_path/"review.zip"
    with pytest.raises(OSError):
        export.build_opening_source_review_package(report,output)
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("identifier", ["object\nf 5 6 7", "../model", "object with space", "", "a"*257])
def test_nominal_obj_cannot_inject_additional_records(identifier):
    from test_opening_label_dimension_authority import _pdf,_ingest,_opening_selector
    from pb_nominal_opening_canonical_shadow import build_nominal_opening_canonical_shadow
    producer,published = _ingest(_pdf(labels=((88.,124.,"2127 STACKER"),)),"safe-obj")
    canonical = build_nominal_opening_canonical_shadow(producer,_opening_selector(producer,published))
    assert canonical is not None
    canonical.id = identifier
    with pytest.raises(ValueError,match="identifier"):
        nominal_opening_obj_shadow(canonical)


@pytest.mark.parametrize("damage", ["addition-publication", "local-positive", "local-whole-length"])
def test_subordinate_review_records_cannot_override_top_level_nonpublication(report,tmp_path,damage):
    data = deepcopy(report)
    p = data["original_opening_review_packets"][0]
    if damage == "addition-publication":
        data["quantity_addition_review"]["commercial_projection_allowed"] = True
    else:
        p["local_aperture_frame"] = {"status":"candidate", "evidence":{
            "whole_wall_frame_id":None, "whole_wall_length_pt":None}}
        if damage == "local-positive":p["local_aperture_frame"]["status"]="corroborated"
        else:p["local_aperture_frame"]["evidence"]["whole_wall_length_pt"]=100.
    with pytest.raises(ValueError): export.build_opening_source_review_package(data,tmp_path/"bad.zip")
    assert not (tmp_path/"bad.zip").exists()


def test_work_queue_retains_each_objects_first_gate_and_all_missing_evidence(report,tmp_path):
    output = tmp_path/"review.zip"
    export.build_opening_source_review_package(report,output)
    with zipfile.ZipFile(output) as archive:
        rows = list(csv.DictReader(io.StringIO(archive.read("source-evidence-work-queue.csv").decode())))
    for branch in ("original","alternate"):
        for p in report[branch+"_opening_review_packets"]:
            owned = [r for r in rows if r["source_path"]==branch and r["source_packet_id"]==p["packet_id"]]
            assert [r["required_evidence"] for r in owned] == p["next_required_evidence"]
            assert all(r["first_remaining_gate"]==p["next_required_evidence"][0] for r in owned)
            assert [r["required_evidence_rank"] for r in owned] == [str(i+1) for i in range(len(owned))]
            assert all(r["source_sha256"] == p["selector"]["source_sha256"] for r in owned)
