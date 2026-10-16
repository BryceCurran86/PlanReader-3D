"""Replay original PDF scopes for source-side host/frame lineage review.

Accepts original bytes and explicit page selectors only. No supplied seal,
area, diagnostic JSON or receipt-pattern match can issue source evidence.
Snapshots remain distinct; this report cannot approve a receipt migration.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_live_opening_source_closed_export import seal_live_opening_area_run
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import (
    MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS, PhysicalWallCandidateProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_opening_scope_receipts import _observe, _pages
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.gptmax_source_host_rekey_parity_ledger import compare_source_host_rekeys


def _json(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def _fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _indexed(rows, key):
    result = {}
    for row in rows:
        identity = row.get(key)
        if not isinstance(identity, str) or not identity or identity in result:
            raise RuntimeError("missing or duplicated original " + key)
        result[identity] = row
    return result


def _scope_rows(rows, scopes, supplemental_scopes, sealed, root):
    quantities = _indexed(sealed["quantities"], "quantity_id")
    scope_index = {}
    for scope in scopes:
        if any(scope.get(k) != v for k, v in root.items()):
            raise RuntimeError("foreign original W4 scope root")
        address = (scope["page_id"], scope["decision_scope_id"])
        if address in scope_index:
            raise RuntimeError("duplicated original W4 decision scope")
        scope_index[address] = scope
    supplemental_index = {}
    for scope in supplemental_scopes:
        if any(scope.get(k) != v for k, v in root.items()):
            raise RuntimeError("foreign original supplemental W4 scope root")
        address = (scope["page_id"], scope["decision_scope_id"])
        if address in supplemental_index or scope["scope_complete"] is not False:
            raise RuntimeError("supplemental scope duplicated or falsely complete")
        supplemental_index[address] = scope
    physical = _indexed(rows, "physical_opening_id")
    seen_quantities = set()
    result = {}
    for identity, row in sorted(physical.items()):
        existence = row["physical_existence_record"]
        selector = row["attempted_host_selector"]
        if (any(row.get(k) != v or existence.get(k) != v or selector.get(k) != v
                for k, v in root.items())
                or existence.get("record_id") != identity
                or selector.get("opening_identity_id") != identity
                or selector.get("page_id") != row["page_id"]):
            raise RuntimeError("physical source identity/root disagreement")
        scope = scope_index.get((row["page_id"], selector["decision_scope_id"]))
        if scope is None:
            raise RuntimeError("original competing W4 source scope missing")
        host, frame = row["host_record"], row["frame_record"]
        candidates = _indexed(scope["records"], "wall_candidate_id")
        supplement = supplemental_index.get((row["page_id"], selector["decision_scope_id"]))
        supplemental_candidates = (_indexed(supplement["records"], "wall_candidate_id")
                                   if supplement is not None else {})
        if candidates.keys() & supplemental_candidates.keys():
            raise RuntimeError("ordinary/supplemental wall identity collision")
        member_owners = {}
        members = []
        if host is not None:
            if (any(host.get(k) != v for k, v in selector.items())
                    or host["decision_scope_id"] != row["decision_scope_id"]
                    or scope["status"] != "corroborated" or not scope["scope_complete"]
                    or not scope["equivalence"]):
                raise RuntimeError("host lacks complete source-owned wall scope")
            for wid in host["member_wall_candidate_ids"]:
                if wid in candidates:
                    members.append(candidates[wid])
                    member_owners[wid] = "ordinary"
                elif (wid in supplemental_candidates
                        and supplement["status"] == "corroborated"
                        and supplement["equivalence"]
                        and "opening_local_supplemental_source_band_host_resolved" in row["host_reason_codes"]):
                    members.append(supplemental_candidates[wid])
                    member_owners[wid] = "opening_local_supplemental"
                else:
                    raise RuntimeError("original host member absent from W4 competitors")
            if not members:
                raise RuntimeError("original host membership empty")
        elif row["decision_scope_id"] is not None:
            raise RuntimeError("hostless source row asserts positive host scope")
        if frame is not None and (host is None
                or frame["selector"] != selector
                or frame["opening_identity_id"] != identity
                or frame["host_binding_record_id"] != host["record_id"]
                or frame["host_wall_id"] != host["host_wall_id"]):
            raise RuntimeError("frame host/source selector disagreement")
        quantity = None
        qid = row["quantity_id"]
        if qid is not None:
            if qid not in quantities or qid in seen_quantities:
                raise RuntimeError("original quantity source owner missing or duplicated")
            seen_quantities.add(qid)
            quantity = quantities[qid]
            required = {identity, row["quantity_measurement_record_id"]}
            if host is None:
                raise RuntimeError("sealed quantity lacks original host record")
            required.add(host["record_id"])
            if frame is not None:
                required.add(frame["record_id"])
            forbidden_frame = [e for e in quantity["evidence_ids"]
                               if e.startswith("opening_host_frame_")]
            if (quantity["object_identity_refs"] != [identity]
                    or any(quantity.get(k) != root[k] for k in (
                        "document_id", "revision_id", "source_sha256"))
                    or quantity["source_page"] != row["page_id"]
                    or not required <= set(quantity["evidence_ids"])
                    or not required <= set(quantity["trace_evidence_ids"])
                    or (frame is None and forbidden_frame)):
                raise RuntimeError("sealed quantity disagrees with original host/frame source")
        result[identity] = {
            "snapshot_id": root["snapshot_id"], "page_id": row["page_id"],
            "decision_scope_id": row["decision_scope_id"],
            "attempted_host_selector": selector,
            "physical_existence_record": existence,
            "host_record": host, "frame_record": frame,
            "host_candidate_source_records": members,
            "host_candidate_source_owner_types": member_owners,
            # The full competitor scope and all typed negatives live once in
            # wall_source_scopes, addressed by both scope and content digest.
            "source_competitors": {
                "decision_scope_id": scope["decision_scope_id"],
                "scope_evidence_fingerprint": _fingerprint(scope),
                "scope_complete": scope["scope_complete"],
                "candidate_count": len(candidates),
                "supplemental_scope_evidence_fingerprint": (_fingerprint(supplement)
                    if supplement is not None else None),
                "supplemental_scope_complete": (supplement["scope_complete"]
                    if supplement is not None else None),
                "supplemental_candidate_count": len(supplemental_candidates),
            },
            "host_reason_codes": row["host_reason_codes"],
            "frame_reason_codes": row["frame_reason_codes"],
            "sealed_quantity": quantity,
            "first_failing_physical_geometry_stage": row["first_failing_physical_geometry_stage"],
        }
    if seen_quantities != set(quantities):
        raise RuntimeError("sealed quantity missing original physical scope")
    return result


def _replay(original_pdf, *, selected, decoded, evidence_pages, project_id):
    digest = sha256(original_pdf).hexdigest()
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}", source_bytes=original_pdf,
        source_locator="memory://original-scope-lineage.pdf",
        page_ids=tuple(map(int, decoded)))
    if tuple(map(str, initial.coverage.decoded_pages)) != decoded:
        raise ValueError("requested original decoding scope not fully available")
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=initial.revision.revision_id, page_ids=selected,
        evidence_page_ids=evidence_pages)
    voids = compose_live_physical_opening_voids(source_visibility_producer=source,
        wall_opening_composition=composition)
    published = source.published_snapshot_for_revision(initial.revision.revision_id)
    before = _retention(composition, voids, verify_customer_rows=True)
    supplemental_authority = PhysicalWallCandidateProducer.from_opening_local_supplemental_source_visibility_producer(
        source, page_ids=_pages((*selected, *evidence_pages))).authority()
    supplemental_scopes = _json([asdict(s) for s in supplemental_authority._scopes.values()])
    rows = _observe(source, published, composition, voids)
    sealed = seal_live_opening_area_run(voids, workspace_id=1, project_id=project_id).to_dict()
    root = {k: getattr(published.revision, k) for k in (
        "document_id", "revision_id", "source_sha256")}
    root["snapshot_id"] = published.snapshot.snapshot_id
    scopes = _json(before["walls"])
    bound = _scope_rows(_json(rows), scopes, supplemental_scopes, sealed, root)
    if (source.published_snapshot_for_revision(initial.revision.revision_id) != published
            or source._producer.current_revision_id(root["document_id"]) != root["revision_id"]
            or sha256(source._producer._store.source_bytes_by_revision[root["revision_id"]]).hexdigest() != digest
            or _retention(composition, voids, verify_customer_rows=True) != before
            or _observe(source, published, composition, voids) != rows
            or seal_live_opening_area_run(voids, workspace_id=1, project_id=project_id).to_dict() != sealed):
        raise RuntimeError("original source/competitors/sealed evidence changed during lineage read")
    parity_input = _json({
        **root,
        "selected_geometry_page_ids": selected,
        "primitive_safety_cap": MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        "opening_bindings": before["hosts"], "host_frames": before["frames"],
        "source_owned_wall_scope_results": [s for s in scopes if s["page_id"] in selected],
        "supplemental_source_owned_wall_scope_results": [s for s in supplemental_scopes
            if s["page_id"] in selected and s["status"] == "corroborated" and s["records"]],
        "resolved_host_frame_evidence": [r["frame_record"] for r in rows if r["frame_record"]],
    })
    return {
        **root, "decoded_page_ids": decoded, "topology_page_ids": selected,
        "evidence_page_ids": evidence_pages,
        "source_closed_run": sealed, "wall_source_scopes": scopes,
        "supplemental_wall_source_scopes": supplemental_scopes,
        "original_customer_verification": _json(before["customer_verification"]),
        "opening_scope_evidence": bound,
        "opening_universe_results": _json({k: asdict(v)
            for k, v in composition.opening_universe_results.items()}),
        "source_and_signed_receipts_unchanged": True,
    }, parity_input


def original_scope_lineage_report(original_pdf: bytes, *, page_ids,
        baseline_decoded_page_ids, candidate_decoded_page_ids, project_id: str,
        baseline_evidence_page_ids=(), candidate_evidence_page_ids=()):
    """Read both explicitly requested original scopes; never alias their roots.

    project_id labels the post-producer seal only. It does not enter any source,
    geometry, identity, host or measurement decision.
    """
    if type(original_pdf) is not bytes or not original_pdf:
        raise TypeError("original PDF bytes required")
    selected = _pages(page_ids)
    old_decoded = _pages(baseline_decoded_page_ids)
    new_decoded = _pages(candidate_decoded_page_ids)
    if not set(selected) <= set(old_decoded) & set(new_decoded):
        raise ValueError("topology pages must be decoded in both original scopes")
    def evidence_pages(values, decoded):
        if type(values) not in (list, tuple):
            raise ValueError("explicit evidence page sequence required")
        pages = _pages(values) if values else ()
        if set(pages) & set(selected) or not set(pages) <= set(decoded):
            raise ValueError("evidence pages must be decoded and separate from topology")
        return pages
    old_evidence = evidence_pages(baseline_evidence_page_ids, old_decoded)
    new_evidence = evidence_pages(candidate_evidence_page_ids, new_decoded)
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("post-producer seal label required")
    old, old_input = _replay(original_pdf, selected=selected, decoded=old_decoded,
        evidence_pages=old_evidence, project_id=project_id)
    new, new_input = _replay(original_pdf, selected=selected, decoded=new_decoded,
        evidence_pages=new_evidence, project_id=project_id)
    parity = compare_source_host_rekeys(old_input, new_input, supplemental_source_evidence=True)
    old_rows, new_rows = old["opening_scope_evidence"], new["opening_scope_evidence"]
    def all_scopes(replay):
        return {(kind, s["page_id"], s["decision_scope_id"]): s
            for kind, key in (("ordinary", "wall_source_scopes"),
                              ("opening_local_supplemental", "supplemental_wall_source_scopes"))
            for s in replay[key]}
    old_scopes, new_scopes = all_scopes(old), all_scopes(new)
    competitors = []
    for address in sorted(set(old_scopes) | set(new_scopes)):
        a, b = old_scopes.get(address), new_scopes.get(address)
        competitors.append({
            "scope_kind": address[0], "page_id": address[1], "decision_scope_id": address[2],
            "baseline_scope_evidence_fingerprint": _fingerprint(a) if a is not None else None,
            "candidate_scope_evidence_fingerprint": _fingerprint(b) if b is not None else None,
            # Exact whole-scope comparisons; no geometry/tie filtering or
            # inferred SAME/DISTINCT relation is introduced by this reader.
            "complete_candidate_records_equal": bool(a is not None and b is not None
                and a["records"] == b["records"]),
            "complete_equivalence_evidence_equal": bool(a is not None and b is not None
                and a["equivalence"] == b["equivalence"]),
            "complete_typed_negative_atoms_equal": bool(a is not None and b is not None
                and a["typed_semantic_evidence_atoms"] == b["typed_semantic_evidence_atoms"]),
            "source_observation_ids_equal": bool(a is not None and b is not None
                and a["source_observation_ids"] == b["source_observation_ids"]),
        })
    rows = [{"physical_opening_id": identity,
             "baseline": old_rows.get(identity), "candidate": new_rows.get(identity)}
            for identity in sorted(set(old_rows) | set(new_rows))]
    # No signed V2 scope, rekey acceptance, new quantity or customer permission.
    return _json({
        "schema_version": "1.0.0", "status": "ORIGINAL_SOURCE_LINEAGE_REPLAY_UNPUBLISHED",
        "baseline": old, "candidate": new, "opening_lineage_rows": rows,
        "complete_source_competitor_comparisons": competitors,
        "source_host_rekey_comparison": parity,
        "cross_snapshot_identity_granted": False, "customer_approval_granted": False,
        "new_firm_quantity_granted": False, "opening_count_granted": False,
        "benchmark_score_granted": False,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--page-id", action="append", required=True)
    parser.add_argument("--baseline-decoded-page-id", action="append", required=True)
    parser.add_argument("--candidate-decoded-page-id", action="append", required=True)
    parser.add_argument("--baseline-evidence-page-id", action="append", default=[])
    parser.add_argument("--candidate-evidence-page-id", action="append", default=[])
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original = args.pdf.read_bytes()
    if sha256(original).hexdigest() != args.sha256:
        raise ValueError("immutable original PDF SHA mismatch")
    result = original_scope_lineage_report(original, page_ids=args.page_id,
        baseline_decoded_page_ids=args.baseline_decoded_page_id,
        candidate_decoded_page_ids=args.candidate_decoded_page_id,
        baseline_evidence_page_ids=args.baseline_evidence_page_id,
        candidate_evidence_page_ids=args.candidate_evidence_page_id,
        project_id=args.project_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"baseline_snapshot": result["baseline"]["snapshot_id"],
        "candidate_snapshot": result["candidate"]["snapshot_id"],
        "physical_openings": len(result["opening_lineage_rows"]),
        "rekey_comparison": result["source_host_rekey_comparison"]["rekey_classification_counts"],
        "cross_snapshot_identity_granted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
