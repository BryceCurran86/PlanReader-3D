"""Attach host-identity shadows to unhosted G17 flank ancestry rows.

Candidate wall IDs come only from exact source-primitive W4 ancestry already
emitted by ``audit_g17_unhosted_flank_original_ancestry``. Never elects nearest
or grants a host.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_opening_host_identity_shadow import build_opening_host_identity_shadow


def _candidate_wall_ids_from_ancestry(row: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for obs in row.get("source_g17_observations") or ():
        buckets = list(obs.get("exact_source_ref_w4_candidates") or ())
        for parent in obs.get("authenticated_source_parents") or ():
            buckets.extend(parent.get("exact_source_ref_w4_candidates") or ())
        for cand in buckets:
            wid = str(cand.get("wall_candidate_id") or "").strip()
            if wid and wid not in seen:
                seen.add(wid)
                ids.append(wid)
    return ids


def attach_host_identity_to_unhosted_ancestry(
    ancestry_rows: Sequence[Mapping[str, Any]],
    *,
    pair_classifications: Sequence[Sequence[str]] | Sequence[tuple[str, str, str]] = (),
) -> dict[str, Any]:
    attached: list[dict[str, Any]] = []
    dispositions: dict[str, int] = {}
    for row in ancestry_rows:
        oid = str(row.get("physical_opening_id") or "").strip()
        if not oid:
            raise ValueError("physical opening identity required")
        if row.get("host_granted") is not False:
            raise RuntimeError("ancestry row must deny host_granted")
        candidates = _candidate_wall_ids_from_ancestry(row)
        identity = build_opening_host_identity_shadow(
            physical_opening_id=oid,
            candidate_wall_ids=candidates,
            pair_classifications=pair_classifications,
        )
        dispositions[identity["disposition"]] = (
            dispositions.get(identity["disposition"], 0) + 1
        )
        attached.append({
            "physical_opening_id": oid,
            "host_reason_codes": list(row.get("host_reason_codes") or ()),
            "exact_source_w4_candidate_count": len(candidates),
            "host_identity_shadow": identity,
            "host_granted": False,
            "nearest_or_first_used": False,
            "measurement_published": False,
        })
    return {
        "status": "UNPUBLISHED_UNHOSTED_HOST_IDENTITY_ORIGINAL_ATTACH",
        "unhosted_opening_count": len(attached),
        "disposition_counts": dict(sorted(dispositions.items())),
        "openings": attached,
        "host_granted": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
