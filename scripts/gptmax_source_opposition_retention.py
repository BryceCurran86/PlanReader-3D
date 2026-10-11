"""Audit native opening opposition with fresh source proof and exact old receipts.

The default source-face comparator remains strict. This separate diagnostic
may explain removal of an unhosted, unframed opening claim only by rerunning
the existing native source-role authority on its exact source observation.
It never authorizes deletion of a hypothesis, wall binding or publication.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import re

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_figured_dimension_evidence import classify_dimension_token
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import _physical_opening_geometry_identity
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.gptmax_compare_source_face_retention import compare_source_face_reports


def _index(rows, name):
    if not isinstance(rows, list):
        raise ValueError(name + " must be a list")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(name + " contains a non-object")
        identity = row.get("opening_identity_id")
        if not isinstance(identity, str) or not identity.strip() or identity in result:
            raise ValueError(name + " has missing or repeated physical identities")
        result[identity] = row
    return result


def _source_ids(value):
    if (not isinstance(value,(tuple,list)) or not value
            or any(not isinstance(x,str) or not x.strip() for x in value)
            or len(value)!=len(set(value))):
        raise ValueError("incomplete original opposing source inventory")
    return set(value)


def _validate_opposition(source,selector,candidate,result):
    """Reauthenticate complete typed native support; never trust count changes."""
    fill=result.reason_codes==("native_unstroked_fill_boundary_opposes_opening",)
    dimension=result.reason_codes==("native_dimension_annotation_opposes_opening",)
    if not (fill or dimension):
        raise ValueError("missing claim lacks complete original native fill opposition or dimension opposition")
    support=_source_ids(candidate.source_observation_ids)
    covered=set()
    for atom in result.opposing_evidence_atoms:
        metadata=atom.metadata
        if (atom.status is not EvidenceResolutionStatus.CANDIDATE
                or atom.document_id!=candidate.document_id or atom.page_id!=candidate.page_id
                or metadata.get("polarity")!="opposing"
                or metadata.get("source_sha256")!=selector.source_sha256
                or metadata.get("revision_id")!=selector.revision_id
                or metadata.get("snapshot_id")!=selector.snapshot_id):
            raise ValueError("foreign original native opposing receipt")
        ids=_source_ids(metadata.get("source_observation_ids"))
        if fill:
            if (atom.kind!="annotation_border"
                    or metadata.get("all_source_primitives_covered") is not True
                    or ids!=support):
                raise ValueError("incomplete original native paint-role receipt")
        else:
            if (atom.kind!="dimension_annotation"
                    or atom.reason_codes!=("native_dimension_cap_tick_text_topology",)
                    or metadata.get("all_opening_support_covered") is not True
                    or _source_ids(metadata.get("opening_support_observation_ids"))!=support
                    or not _source_ids(metadata.get("dimension_line_observation_ids"))<=ids):
                raise ValueError("incomplete original native dimension-role receipt")
            word_id=metadata.get("text_observation_id")
            if not isinstance(word_id,str) or not word_id.strip():
                raise ValueError("original dimension text ownership unavailable")
            text=source.text_integrity_authority().resolve_text(replace(selector,observation_id=word_id))
            if (text.status is not EvidenceResolutionStatus.CORROBORATED
                    or text.receipt is None or text.receipt.page_id!=candidate.page_id
                    or not classify_dimension_token(str(text.trusted_text)).is_linear_dimension):
                raise ValueError("original dimension text receipt unavailable")
        for observation_id in ids:
            owned=source.authority().resolve_visible(replace(selector,observation_id=observation_id))
            if (owned.status is not EvidenceResolutionStatus.CORROBORATED
                    or owned.observation is None
                    or owned.observation.page_id!=candidate.page_id):
                raise ValueError("opposing component lacks original visible source ownership")
        covered.update(ids)
    if not support<=covered:
        raise ValueError("opposing component union misses original opening support")


def _fresh_opposition(source_bytes, pages, missing):
    """Use original producers; never accept caller-supplied opposing atoms."""
    digest = sha256(source_bytes).hexdigest()
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published = source.ingest_native_pdf_bytes(document_id=f"live-source:{digest[:32]}",
        source_bytes=source_bytes, source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=tuple(pages))
    # Missing native hypotheses require only original PDF lines. Do not use
    # a caller JSON role report or create raster observations to explain them.
    physical = source.physical_opening_authority()
    proofs = []
    for identity, previous in sorted(missing.items()):
        representative = previous.get("representative_observation_id")
        if not isinstance(representative, str) or not representative.strip():
            raise ValueError("missing native source observation for opposition")
        selector = ObservationSelector(published.revision.document_id,
            published.revision.revision_id, digest, published.snapshot.snapshot_id,
            representative)
        result = physical.prove_existence(selector)
        candidate = result.candidate
        if (result.status is not EvidenceResolutionStatus.ABSTAINED
                or result.existence_record is not None or candidate is None
                or not result.opposing_evidence_atoms
                or candidate.page_id != previous.get("page_id")):
            raise ValueError("missing claim lacks complete original native fill opposition or dimension opposition")
        support = candidate.source_observation_ids
        if (not support or len(support) != len(set(support))
                or representative not in support):
            raise ValueError("ambiguous native candidate support ownership")
        records = []
        for observation_id in support:
            owned = source.authority().resolve_visible(replace(selector,
                observation_id=observation_id))
            if (owned.status is not EvidenceResolutionStatus.CORROBORATED
                    or owned.observation is None
                    or owned.observation.page_id != candidate.page_id):
                raise ValueError("opposed support lacks original visible source ownership")
            records.append(owned.observation)
        geometry = _physical_opening_geometry_identity(candidate, records)
        if not geometry:
            raise ValueError("opposed original source geometry unavailable")
        original_identity = stable_contract_id("physical_opening_existence", {
            "document_id": candidate.document_id, "revision_id": candidate.revision_id,
            "source_sha256": digest, "page_id": candidate.page_id,
            "semantic_class": "opening", "source_geometry": geometry,
        }, digest_chars=32)
        if original_identity != identity:
            raise ValueError("opposing source belongs to a different physical geometry")
        atoms = result.opposing_evidence_atoms
        _validate_opposition(source,selector,candidate,result)
        proofs.append({"opening_identity_id": identity,
            "representative_observation_id": representative,
            "candidate": asdict(candidate),
            "opposing_evidence_atoms": [asdict(atom) for atom in atoms],
            "original_source_reauthenticated": True,
            "physical_nonexistence_proven": False,
            "host_publication_allowed": False})
    return proofs


def compare_opposed_source_reports(before, after, *, source_bytes: bytes):
    """Preserve exact shared bindings/firm frames; explain only unproven loss."""
    if not isinstance(source_bytes, bytes):
        raise TypeError("original PDF must be immutable bytes")
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("source reports must be objects")
    digest = sha256(source_bytes).hexdigest()
    pages = before.get("selected_geometry_page_ids")
    if (not isinstance(pages, list) or not pages
            or any(not isinstance(p, str) or re.fullmatch(r"[1-9][0-9]*", p) is None for p in pages)
            or len(pages) != len(set(pages))):
        raise ValueError("invalid original source page universe")
    for report in (before, after):
        if (report.get("source_sha256") != digest
                or report.get("selected_geometry_page_ids") != pages
                or type(report.get("primitive_safety_cap")) is not int
                or report["primitive_safety_cap"] != 20000):
            raise ValueError("source bytes, page scope or primitive cap mismatch")
    old = _index(before.get("opening_bindings"), "old bindings")
    new = _index(after.get("opening_bindings"), "new bindings")
    old_frames = _index(before.get("host_frames"), "old frames")
    new_frames = _index(after.get("host_frames"), "new frames")
    if set(old_frames) != set(old) or set(new_frames) != set(new):
        raise ValueError("source frame universe differs from physical claims")
    if set(new) - set(old):
        raise ValueError("opposition audit cannot approve additional physical claims")
    missing = {key: old[key] for key in set(old) - set(new)}
    for key, row in missing.items():
        if (row.get("record_id") is not None or row.get("host_wall_id") is not None
                or row.get("status") != EvidenceResolutionStatus.ABSTAINED.value
                or old_frames[key].get("record_id") is not None):
            raise ValueError("source opposition cannot remove any existing host or frame proof")
    for key, row in new.items():
        if old[key] != row:
            raise ValueError("original shared opening binding changed")
        if old_frames[key].get("record_id") is not None and old_frames[key] != new_frames[key]:
            raise ValueError("original authenticated frame changed")
    proofs = _fresh_opposition(source_bytes, pages, missing) if missing else []
    # Filter only independently explained *unproven* rows for this secondary
    # audit. The original report and the strict default comparator are intact.
    retained_before = dict(before,
        opening_bindings=[row for row in before["opening_bindings"] if row["opening_identity_id"] in new],
        host_frames=[row for row in before["host_frames"] if row["opening_identity_id"] in new])
    result = compare_source_face_reports(retained_before, after)
    result.update(original_baseline_physical_claim_count=len(old),
        source_opposed_missing_claims=proofs,
        source_opposition_freshly_reauthenticated=bool(proofs),
        hypotheses_deletion_allowed=False, host_publication_allowed=False,
        opening_count_publication_allowed=False, metric_quantity_publication_allowed=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_opposed_source_reports(json.loads(args.baseline.read_bytes()),
        json.loads(args.candidate.read_bytes()), source_bytes=args.pdf.read_bytes())
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"retention_pass": result["retention_pass"],
        "freshly_source_opposed_claims": len(result["source_opposed_missing_claims"]),
        **result["count_summary"]}))
    raise SystemExit(0 if result["retention_pass"] else 1)


if __name__ == "__main__":
    main()
