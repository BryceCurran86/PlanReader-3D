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
from pathlib import Path
import zipfile

from pb_canonical_building import CanonicalOpening, ReviewState
from pb_migration_contracts import canonical_contract_json
from pb_opening_source_review_shadow import nominal_opening_obj_shadow


def build_opening_source_review_package(report,output):
    output=Path(output)
    if output.suffix.lower()!=".zip":
        raise ValueError("review package must be a ZIP file")
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
            for capability in packet["next_required_evidence"]:
                queue.append({"source_path":branch,"page_id":packet["page_id"],
                    "physical_opening_id":packet["opening_identity_id"],
                    "required_evidence":capability,"source_packet_id":identity,
                    "source_sha256":packet["selector"]["source_sha256"],
                    "snapshot_id":packet["selector"]["snapshot_id"]})
    stream=io.StringIO(newline="")
    writer=csv.DictWriter(stream,fieldnames=("source_path","page_id","physical_opening_id",
        "required_evidence","source_packet_id","source_sha256","snapshot_id"))
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
    with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for name,payload in sorted(content.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o600<<16
            archive.writestr(info,payload)
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
