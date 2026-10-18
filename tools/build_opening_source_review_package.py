"""Create a portable offline source review with per-opening evidence and assets.

No PDF/image bytes, authority imports, signed-row reissues or network scripts.
Serialized packets are explanations only. The actual source producer must be
replayed for any later authority decision.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import io
import json
import math
<<<<<<< HEAD
import os
=======
>>>>>>> 4c09f4dc (feat(gptmax): bind explicit nominal width approvals to source-owned opening reviews)
from pathlib import Path
import tempfile
import zipfile

from pb_canonical_building import CanonicalOpening, ReviewState
from pb_migration_contracts import canonical_contract_json
from pb_opening_source_review_shadow import nominal_opening_obj_shadow, _source_support_signature


def _validate_review_report(report):
    def safe_token(value):
        return (type(value) is str and bool(value) and (value[0].isalnum() or value[0] == "_")
                and all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-" for c in value))
    if not isinstance(report, dict):
        raise ValueError("source review report must be an object")
    for field in ("new_authority_promotion_granted", "customer_publication_granted",
                  "original_signed_rows_reissued", "official_benchmark_executed"):
        if report.get(field) is not False:
            raise ValueError("source review report cannot grant authority: " + field)
    sha = report.get("original_source_sha256")
    if type(sha) is not str or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("source review report requires its exact source SHA")
    issuer_scopes = set()
    for branch in ("original", "alternate"):
        packets = report.get(branch + "_opening_review_packets")
        receipt = report.get(branch + "_receipt")
        if (not isinstance(packets, (tuple, list)) or not isinstance(receipt, dict)
                or any(not isinstance(receipt.get(k), (tuple, list)) for k in ("hosts", "frames", "quantities"))):
            raise ValueError("complete source review packets and receipts required")
        physical_ids = set()
        for packet in packets:
            if not isinstance(packet, dict) or any(packet.get(k) is not False
                    for k in ("takeoff_eligible", "deduction_authority")):
                raise ValueError("source review packet cannot grant authority")
            selector = packet.get("selector")
            if (not isinstance(selector, dict) or selector.get("source_sha256") != sha
                    or any(type(selector.get(k)) is not str or not selector[k]
                           for k in ("document_id", "revision_id", "snapshot_id"))):
                raise ValueError("source review packet issuer mismatch")
            if not safe_token(selector["snapshot_id"]) or (
                    packet.get("opening_identity_id") is not None and not safe_token(packet["opening_identity_id"])):
                raise ValueError("safe source review identifiers required")
            if (type(packet.get("page_id")) is not str or not packet["page_id"].isascii()
                    or not packet["page_id"].isdigit() or str(int(packet["page_id"])) != packet["page_id"]
                    or int(packet["page_id"]) < 1):
                raise ValueError("canonical source page required")
            # A review export cannot rename or reissue a physical occurrence.
            # This structural check does not authenticate the imported packet.
            opening = packet.get("physical_opening")
            identity = packet.get("opening_identity_id")
            if opening is None:
                if identity is not None or packet.get("source_lineage") is not None:
                    raise ValueError("absent physical opening cannot claim identity or source ancestry")
            else:
                if (not isinstance(opening, dict) or not safe_token(identity)
                        or opening.get("record_id") != identity
                        or opening.get("page_id") != packet["page_id"]
                        or any(opening.get(k) != selector[k] for k in
                               ("document_id", "revision_id", "source_sha256", "snapshot_id"))):
                    raise ValueError("physical opening identity or original source scope disagrees")
                roots = opening.get("source_observation_ids")
                if (not isinstance(roots, (tuple, list)) or not roots
                        or any(type(v) is not str or not v or v != v.strip() for v in roots)
                        or len(roots) != len(set(roots))):
                    raise ValueError("physical opening source observations must be uniquely owned")
                if identity in physical_ids:
                    raise ValueError("duplicate physical opening identity in one source review branch")
                physical_ids.add(identity)
            blockers = packet.get("next_required_evidence")
            if not isinstance(blockers, (tuple, list)) or not blockers or any(type(v) is not str or not v
                    or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in v) for v in blockers):
                raise ValueError("typed source review evidence blockers required")
            lineage = packet.get("source_lineage")
            if lineage is not None and (not isinstance(lineage, dict)
                    or lineage.get("authority_import_allowed") is not False):
                raise ValueError("source lineage is explanation only")
            if lineage is not None and lineage.get("source_proof_closed") is True and _source_support_signature(packet)[0] is None:
                raise ValueError("source review packet contradicts its closed parent graph")
            issuer_scopes.add((selector["document_id"], selector["revision_id"]))
            local = packet.get("local_aperture_frame")
            if local is not None and not isinstance(local, dict):
                raise ValueError("local aperture review must be a typed review record")
            if local is not None and local.get("evidence") is not None:
                if not isinstance(local["evidence"], dict):
                    raise ValueError("local aperture source evidence must be a typed record")
                if (local.get("status") != "candidate"
                        or local["evidence"].get("whole_wall_frame_id") is not None
                        or local["evidence"].get("whole_wall_length_pt") is not None):
                    raise ValueError("local aperture review cannot claim whole-wall authority")
            canonical = packet.get("canonical_nominal_review")
            if canonical is not None and (not isinstance(canonical, dict) or any(
                    canonical.get(k) is not False for k in ("takeoff_eligible", "deduction_authority"))):
                raise ValueError("nominal asset cannot grant authority")
            if canonical is not None and (canonical.get("id") != packet.get("opening_identity_id")
                    or any(canonical.get(k) is not None for k in ("wall_id", "offset_along_wall_m", "sill_height_m"))):
                raise ValueError("nominal asset must retain its unplaced physical opening identity")
            if canonical is not None:
                metadata = canonical.get("metadata")
                if not isinstance(metadata, dict):
                    raise ValueError("nominal asset metadata must be a dictionary")
                if metadata.get("dimension_basis") == "user_approved_single_nominal_width":
                    value = canonical.get("width_m")
                    approval = metadata.get("nominal_width_approval") or {}
                    stated = approval.get("value_mm")
                    if (type(value) not in (int, float) or type(stated) not in (int, float)
                            or not math.isfinite(value) or not math.isfinite(stated)
                            or min(value, stated) <= 0 or not math.isclose(value, stated / 1000., abs_tol=1e-12, rel_tol=1e-12)
                            or canonical.get("height_m") is not None):
                        raise ValueError("single width nominal asset dimensions invalid")
                else:
                    axes = (packet.get("nominal_axes") or {}).get("evidence")
                    if (not isinstance(axes, dict)
                            or axes.get("opening_record_id") != packet["opening_identity_id"]
                            or any(metadata.get(k) != selector[k] for k in ("source_sha256", "revision_id", "snapshot_id"))):
                        raise ValueError("nominal asset source axes do not belong to this packet")
                    for metric, nominal in (("width_m","width_mm"),("height_m","height_mm")):
                        value, stated = canonical.get(metric), axes.get(nominal)
                        if (type(value) not in (int,float) or type(stated) not in (int,float)
                                or not math.isfinite(value) or not math.isfinite(stated)
                                or min(value,stated) <= 0 or not math.isclose(value,stated/1000.,abs_tol=1e-12,rel_tol=1e-12)):
                            raise ValueError("nominal asset dimensions disagree with its owned axes")
    if len(issuer_scopes) > 1:
        raise ValueError("source review cannot mix document/revision issuers")
    additions = report.get("quantity_addition_review")
    if additions is not None:
        if not isinstance(additions, dict) or not isinstance(additions.get("additional_area_reviews"), (tuple,list)):
            raise ValueError("additional quantity review must be an object")
        for record in (additions, *additions.get("additional_area_reviews", ())):
            if not isinstance(record, dict) or any(record.get(k) is not False for k in (
                    "original_signed_rows_reissued", "commercial_projection_allowed", "opening_count_granted")):
                raise ValueError("additional quantity review cannot publish")
            if "append_authority_granted" in record and record["append_authority_granted"] is not False:
                raise ValueError("additional quantity review cannot append signed output")


def build_opening_source_review_package(report,output):
    output=Path(output)
    if output.suffix.lower()!=".zip":
        raise ValueError("review package must be a ZIP file")
    if output.exists() or output.is_symlink():
        raise FileExistsError("source review package output must be new")
    _validate_review_report(report)
    if (report.get("status")!="original_issuer_preserved_additional_source_shadow"
            or report.get("original_issuer_body_unchanged_during_fork") is not True
            or report.get("new_authority_promotion_granted") is not False
            or report.get("customer_publication_granted") is not False):
        raise ValueError("nonpublishing original-preserving source report required")
    content={}
    content["recovery.json"]=(canonical_contract_json(report)+"\n").encode()
    # The full retained wall universe stays in recovery.json. The inspector
    # needs per-opening source geometry and counts, not duplicate full seals
    # or thousands of unrelated W4 records in an executable document.
    view={k:report[k] for k in ("original_opening_review_packets",
        "alternate_opening_review_packets","original_issuer_body_unchanged_during_fork")}
    for branch in ("original","alternate"):
        receipt=report[branch+"_receipt"]
        view[branch+"_receipt"]={"hosts":[{"host_wall_id":r["host_wall_id"]} for r in receipt["hosts"]],
            "frames":[{"record_id":r["record_id"]} for r in receipt["frames"]],
            "quantities":[r["quantity_id"] for r in receipt["quantities"]]}
    safe_json=json.dumps(view,sort_keys=True,allow_nan=False).replace("<","\\u003c").replace(
        "\u2028","\\u2028").replace("\u2029","\\u2029")
    template=Path(__file__).with_name("opening_source_review.html").read_text()
    content["review.html"]=template.replace("__OPENING_REVIEW_DATA__",safe_json).encode()
    queue=[]
    for branch in ("original","alternate"):
        seen_packet_ids=set()
        for packet in report[branch+"_opening_review_packets"]:
            identity=packet["packet_id"]
            if identity in seen_packet_ids:
                raise ValueError("duplicate source packet address in review export")
            seen_packet_ids.add(identity)
            if not isinstance(identity,str) or not identity.startswith("opening_source_review_shadow_") or any(
                    c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in identity):
                raise ValueError("unsafe source packet address")
            content[f"{branch}/evidence/{identity}.json"]=(canonical_contract_json(packet)+"\n").encode()
            canonical=packet.get("canonical_nominal_review")
            if canonical is not None:
                opening=CanonicalOpening.from_dict(canonical)
                if opening.metadata.get("dimension_basis")=="user_approved_single_nominal_width":
                    if (type(opening.width_m) not in (int,float)
                            or not math.isfinite(opening.width_m) or opening.width_m<=0
                            or opening.id!=packet["opening_identity_id"]
                            or opening.review_state is not ReviewState.REVIEW_REQUIRED
                            or opening.height_m is not None or opening.takeoff_eligible
                            or opening.deduction_authority or opening.wall_id is not None
                            or opening.sill_height_m is not None or opening.offset_along_wall_m is not None):
                        raise ValueError("partial nominal width review cannot carry height or placement authority")
                else:
                    obj=nominal_opening_obj_shadow(opening)
                    content[f"{branch}/nominal-review/{identity}.obj"]=obj.encode()
            blockers = packet["next_required_evidence"]
            lineage = packet.get("source_lineage") or {}
            for rank, capability in enumerate(blockers, 1):
                queue.append({"source_path":branch,"page_id":packet["page_id"],
                    "physical_opening_id":packet["opening_identity_id"],
                    "required_evidence":capability,"source_packet_id":identity,
                    "source_sha256":packet["selector"]["source_sha256"],
                    "snapshot_id":packet["selector"]["snapshot_id"],
                    "first_remaining_gate":blockers[0],
                    "required_evidence_rank":rank,
                    "source_parent_dag_closed":lineage.get("source_proof_closed") is True,
                    "unresolved_source_parent_count":len(lineage.get("unresolved_parent_ids", ()))})
    stream=io.StringIO(newline="")
    writer=csv.DictWriter(stream,fieldnames=("source_path","page_id","physical_opening_id",
        "required_evidence","source_packet_id","source_sha256","snapshot_id",
        "first_remaining_gate","required_evidence_rank","source_parent_dag_closed",
        "unresolved_source_parent_count"))
    writer.writeheader();writer.writerows(queue)
    content["source-evidence-work-queue.csv"]=stream.getvalue().encode()
    content["README.txt"]=("Open review.html locally. Every object remains a review candidate.\n"
        "nominal-review OBJ files are unplaced X/Z faces in metres with no depth.\n"
        "PDF geometry is in points and never supplies metric wall placement.\n"
        "recovery.json retains both original and independent source receipts.\n"
        "No original PDF or image bytes are included. No new commercial authority.\n").encode()
    manifest={"source_sha256":report["original_source_sha256"],
        "authority_import_allowed":False,"entries":[{"path":name,"size":len(payload),
        "sha256":sha256(payload).hexdigest()} for name,payload in sorted(content.items())]}
    content["manifest.json"]=(canonical_contract_json(manifest)+"\n").encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    # Fixed archive metadata makes equivalent reports byte-reproducible.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".opening-review-", delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary,"w",compression=zipfile.ZIP_DEFLATED) as archive:
            for name,payload in sorted(content.items()):
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o600<<16
                archive.writestr(info,payload)
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.report.resolve()==args.output.resolve():
        raise ValueError("source report cannot be overwritten")
    result=build_opening_source_review_package(json.loads(args.report.read_text()),args.output)
    print(json.dumps({"files":len(result["entries"])+1,"authority_import_allowed":False}))


if __name__=="__main__":
    main()
