"""Observe source-positive W4 pair blockers without granting frame authority.

The actual frame producer still decides every result. The wrapper records
only equivalence lookups made while the original _shared_host_frame executes;
it never inserts an equivalence, changes W4 membership or changes a result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pb_opening_host_frame_authority as frame_authority
from tools.diag_opening_wall_face_preservation import source_face_report


BLOCKED = "opening_host_frame_aligned_fragment_distinctness_unproven"


class _PairReads(dict):
    """Dict-compatible observational wrapper; preserving ordinary get()."""

    def __init__(self, pairs, record):
        super().__init__(pairs)
        self._record = record

    def get(self, key, default=None):
        value = super().get(key, default)
        if isinstance(key, tuple) and len(key) == 2:
            members = tuple(str(member) for member in key)
            if all(members):
                self._record.append({
                    "candidate_pair": sorted(members),
                    "physical_equivalence_class": (
                        str(value.value) if value is not None else "NO_PROVEN_RELATION"
                    ),
                })
        return value


def _certify_observation_association(source_report, captured, sha, page_ids):
    if (source_report.get("source_sha256") != sha
            or tuple(source_report.get("selected_geometry_page_ids", ())) != page_ids
            or source_report.get("primitive_safety_cap") != 20_000):
        raise RuntimeError("observed source identity or safety bound differs")
    bindings = {b["opening_identity_id"]: b for b in source_report.get("opening_bindings", ())}
    frames = {f["opening_identity_id"]: f for f in source_report.get("host_frames", ())}
    if (not bindings or set(frames) != set(bindings)
            or len(bindings) != len(source_report["opening_bindings"])
            or len(frames) != len(source_report["host_frames"])):
        raise RuntimeError("incomplete or repeated physical source opening owner")
    scope_candidates = {}
    for scope in source_report.get("source_owned_wall_scope_results", ()):
        if (scope.get("source_sha256") != sha
                or scope.get("status") != "corroborated"
                or scope.get("scope_complete") is not True):
            raise RuntimeError("unproven source wall scope")
        page = str(scope.get("page_id"))
        bucket = scope_candidates.setdefault(page, set())
        for row in scope.get("records", ()):
            wall_id = row.get("wall_candidate_id")
            if not isinstance(wall_id, str) or not wall_id or wall_id in bucket:
                raise RuntimeError("repeated/invalid W4 wall candidate in source scope")
            bucket.add(wall_id)
    result=[]
    seen=set()
    for item in captured:
        oid=item["opening_identity_id"]
        if oid not in bindings or oid not in frames or oid in seen:
            raise RuntimeError("foreign or duplicate observed frame opening")
        seen.add(oid)
        opening=bindings[oid]
        frame=frames[oid]
        if (opening.get("page_id") != item["page_id"]
                or item["page_id"] not in page_ids
                or BLOCKED not in frame.get("reason_codes", ())
                or frame.get("record_id") is not None):
            raise RuntimeError("frame blocker reason/identity does not match producer")
        pairs=[]
        for row in item["candidate_pair_reads"]:
            ids=row["candidate_pair"]
            if (len(ids)!=2 or ids[0]==ids[1]
                    or any(wall not in scope_candidates.get(item["page_id"], ())
                           for wall in ids)):
                raise RuntimeError("unowned W4 candidate in observational pair read")
            pairs.append(row)
        if not pairs:
            raise RuntimeError("aligned fragment blocker without observed candidate pair")
        result.append({
            "opening_identity_id":oid,
            "source_page_id":item["page_id"],
            "frame_failure_reason":BLOCKED,
            "observed_equivalence_pair_reads":sorted(
                {json.dumps(row,sort_keys=True) for row in pairs}),
            "pair_read_is_distinctness_proof":False,
            "host_frame_publication_allowed":False,
        })
    return sorted(result,key=lambda row:row["opening_identity_id"])


def source_aligned_frame_blocker_report(source_bytes: bytes, *, page_ids: tuple[str,...]):
    sha=hashlib.sha256(source_bytes).hexdigest()
    original_pair_lookup=frame_authority._pair_lookup
    original_frame=frame_authority.OpeningHostFrameProducer._shared_host_frame
    active=[]
    observed=[]

    def tracking_lookup(equivalence):
        lookup=original_pair_lookup(equivalence)
        if not active:
            return lookup
        return _PairReads(lookup, active[-1]["candidate_pair_reads"])

    def tracking_frame(self, *, binding, geometry, opening=None, failure_reasons=None):
        entry={
            "opening_identity_id":getattr(opening,"record_id",None),
            "page_id":str(binding.page_id),
            "candidate_pair_reads":[],
        }
        before_count=len(failure_reasons) if isinstance(failure_reasons,list) else 0
        active.append(entry)
        try:
            value=original_frame(
                self,binding=binding,geometry=geometry,opening=opening,
                failure_reasons=failure_reasons)
        finally:
            active.pop()
        reasons=(
            tuple(failure_reasons[before_count:])
            if isinstance(failure_reasons,list) else ()
        )
        if BLOCKED in reasons:
            if not isinstance(entry["opening_identity_id"],str):
                raise RuntimeError("aligned frame cannot identify its physical opening")
            observed.append(entry)
        return value

    with patch.object(frame_authority,"_pair_lookup",tracking_lookup), patch.object(
        frame_authority.OpeningHostFrameProducer,
        "_shared_host_frame",tracking_frame,
    ):
        published=source_face_report(source_bytes,page_ids=page_ids)
    rows=_certify_observation_association(published,observed,sha,page_ids)
    return {
        "source_sha256":sha,
        "source_report":published,
        "aligned_frame_blocker_source_pair_reads":rows,
        "w4_member_exclusion_permission":False,
        "new_host_frame_or_quantity_permission":False,
        "benchmark_accuracy":None,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--page-id",action="append",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=source_aligned_frame_blocker_report(
        args.pdf.read_bytes(),page_ids=tuple(sorted(set(args.page_id),key=int)))
    args.output.write_text(
        json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",
        encoding="utf-8")
    print(json.dumps({
        "source_sha256":result["source_sha256"],
        "aligned_frame_blocker_count":len(
            result["aligned_frame_blocker_source_pair_reads"]),
        "source_report_summary":result["source_report"]["summary"],
        "commercial_publication_allowed":False,
    }))


if __name__=="__main__":
    main()
