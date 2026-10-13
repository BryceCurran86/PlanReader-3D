"""Verify additive source-snapshot host/frame retention without blessing rekeyed receipts.

This checker is intentionally narrower than production authority. It compares two
original-source stage reports and accepts snapshot-scoped receipt rekeys only when
all physical/source propositions behind every prior host and frame are unchanged.
It never creates a wall/opening/host/frame/quantity or changes scoring.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from pb_opening_host_source_candidate_witness import (
    source_candidate_membership_witness_id,
)


def _rows(value: object, name: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise ValueError(f"{name} must be an array of objects")
    return list(value)


def _index(rows: list[Mapping[str, Any]], key: str, name: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        identity = row.get(key)
        if type(identity) is not str or not identity or identity != identity.strip():
            raise ValueError(f"{name} has malformed {key}")
        if identity in result:
            raise ValueError(f"{name} has duplicate {key}")
        result[identity] = row
    return result


def _wall_records(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for scope in _rows(report.get("source_owned_wall_scopes"), "source_owned_wall_scopes"):
        records = _rows(scope.get("records"), "wall scope records")
        for record in records:
            wall_id = record.get("wall_candidate_id")
            if type(wall_id) is not str or not wall_id or wall_id != wall_id.strip():
                raise ValueError("wall record has malformed identity")
            previous = result.get(wall_id)
            if previous is not None and previous != record:
                raise ValueError("same wall candidate has contradictory source records")
            result[wall_id] = record
    return result


def _canonical(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return _index(
        _rows(report.get("canonical_openings"), "canonical_openings"),
        "physical_opening_id",
        "canonical_openings",
    )


def _candidate_identity(record: Mapping[str, Any]) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    physical = record.get("physical_identity")
    if not isinstance(physical, Mapping):
        raise ValueError("wall candidate lacks physical identity")
    candidate = physical.get("candidate_identity_id")
    sources = physical.get("source_primitive_ids")
    edges = physical.get("edge_ids")
    if (
        type(candidate) is not str
        or not candidate
        or candidate != candidate.strip()
        or not isinstance(sources, (list, tuple))
        or not sources
        or any(type(value) is not str or not value for value in sources)
        or len(set(sources)) != len(sources)
        or not isinstance(edges, (list, tuple))
        or any(type(value) is not str or not value for value in edges)
        or len(set(edges)) != len(edges)
    ):
        raise ValueError("wall candidate physical ancestry is incomplete")
    return candidate, tuple(sorted(sources)), tuple(sorted(edges))


def _host_signature(
    report: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> dict[str, Any]:
    opening_id = binding["opening_identity_id"]
    canonical = _canonical(report).get(opening_id)
    if canonical is None:
        raise ValueError("hosted opening is absent from canonical source inventory")
    document_id = canonical.get("document_id")
    page_id = canonical.get("page_id")
    source_sha = report.get("source_sha256")
    member_ids = binding.get("member_wall_candidate_ids")
    if (
        type(document_id) is not str
        or not document_id
        or type(page_id) is not str
        or not page_id
        or type(source_sha) is not str
        or len(source_sha) != 64
        or not isinstance(member_ids, (list, tuple))
        or not member_ids
        or any(type(value) is not str or not value for value in member_ids)
        or len(set(member_ids)) != len(member_ids)
    ):
        raise ValueError("host binding lacks immutable source ownership")
    walls = _wall_records(report)
    member_rows = []
    candidate_ids = []
    for wall_id in member_ids:
        wall = walls.get(wall_id)
        if wall is None:
            raise ValueError("host member is absent from source-owned wall scope")
        candidate, source_primitives, edge_ids = _candidate_identity(wall)
        candidate_ids.append(candidate)
        member_rows.append(
            {
                "wall_candidate_id": wall_id,
                "candidate_identity_id": candidate,
                "source_primitive_ids": source_primitives,
                "edge_ids": edge_ids,
            }
        )
    witness = source_candidate_membership_witness_id(
        document_id=document_id,
        source_sha256=source_sha,
        page_id=page_id,
        opening_identity_id=opening_id,
        member_candidate_identity_ids=tuple(candidate_ids),
    )
    if not witness:
        raise ValueError("snapshot-independent host membership witness unavailable")
    return {
        "opening_identity_id": opening_id,
        "status": binding.get("status"),
        "reason_codes": tuple(binding.get("reason_codes") or ()),
        "member_wall_candidate_ids": tuple(member_ids),
        "candidate_membership_witness_id": witness,
        "member_source_signatures": tuple(
            sorted(member_rows, key=lambda row: row["wall_candidate_id"])
        ),
    }


def _frame_evidence(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return _index(
        _rows(report.get("resolved_host_frame_evidence"), "resolved_host_frame_evidence"),
        "opening_identity_id",
        "resolved_host_frame_evidence",
    )


def _frame_signature(evidence: Mapping[str, Any]) -> dict[str, Any]:
    # These fields describe the physical/source proposition. Snapshot-scoped
    # selector/receipt IDs are deliberately excluded and may rekey.
    fields = (
        "opening_identity_id",
        "whole_wall_candidate_ids",
        "source_observation_ids",
        "origin_pt",
        "axis_unit",
        "normal_unit",
        "u0_pt",
        "u1_pt",
        "wall_thickness_pt",
        "whole_wall_length_pt",
        "coordinate_unit",
    )
    result = {field: evidence.get(field) for field in fields}
    for field in ("whole_wall_candidate_ids", "source_observation_ids"):
        values = result[field]
        if (
            not isinstance(values, (list, tuple))
            or not values
            or any(type(value) is not str or not value for value in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError(f"frame {field} is incomplete")
        result[field] = tuple(values)
    for field in ("origin_pt", "axis_unit", "normal_unit"):
        values = result[field]
        if not isinstance(values, (list, tuple)) or len(values) != 2:
            raise ValueError(f"frame {field} is malformed")
        result[field] = tuple(values)
    return result


def compare_additive_snapshot_retention(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    expected_new_host_ids: tuple[str, ...],
) -> dict[str, Any]:
    for key in ("source_sha256", "revision_id", "selected_geometry_page_ids", "primitive_safety_cap"):
        if baseline.get(key) != candidate.get(key):
            raise ValueError(f"source envelope changed: {key}")
    if baseline.get("primitive_safety_cap") != 20_000:
        raise ValueError("source primitive safety cap changed")

    old_bindings = _index(
        _rows(baseline.get("opening_bindings"), "baseline opening_bindings"),
        "opening_identity_id",
        "baseline opening_bindings",
    )
    new_bindings = _index(
        _rows(candidate.get("opening_bindings"), "candidate opening_bindings"),
        "opening_identity_id",
        "candidate opening_bindings",
    )
    if set(old_bindings) != set(new_bindings):
        raise ValueError("physical opening identity universe changed")

    expected = set(expected_new_host_ids)
    if not expected or len(expected) != len(expected_new_host_ids):
        raise ValueError("expected new host identities must be unique and non-empty")
    if not expected <= set(old_bindings):
        raise ValueError("expected new host is not an existing physical opening")

    old_hosted = {key for key, row in old_bindings.items() if row.get("host_wall_id")}
    new_hosted = {key for key, row in new_bindings.items() if row.get("host_wall_id")}
    if new_hosted - old_hosted != expected or old_hosted - new_hosted:
        raise ValueError("host population changed outside the expected additive set")

    retained = []
    for opening_id in sorted(old_hosted):
        old_sig = _host_signature(baseline, old_bindings[opening_id])
        new_sig = _host_signature(candidate, new_bindings[opening_id])
        if old_sig != new_sig:
            raise ValueError(f"physical host/source proposition changed: {opening_id}")
        retained.append(opening_id)

    # Non-target unhosted openings must not silently change their authority state.
    for opening_id in sorted(set(old_bindings) - old_hosted - expected):
        old = old_bindings[opening_id]
        new = new_bindings[opening_id]
        for field in (
            "status",
            "reason_codes",
            "representative_observation_id",
            "page_id",
            "member_wall_candidate_ids",
        ):
            if old.get(field) != new.get(field):
                raise ValueError(f"unrelated opening authority changed: {opening_id}:{field}")

    old_frames = _frame_evidence(baseline)
    new_frames = _frame_evidence(candidate)
    if set(old_frames) - set(new_frames):
        raise ValueError("previously resolved host frame was lost")
    new_frame_ids = set(new_frames) - set(old_frames)
    if not new_frame_ids <= expected:
        raise ValueError("frame population changed outside the expected additive host set")
    for opening_id in sorted(old_frames):
        if _frame_signature(old_frames[opening_id]) != _frame_signature(new_frames[opening_id]):
            raise ValueError(f"physical frame/source geometry changed: {opening_id}")

    for opening_id in sorted(expected):
        binding = new_bindings[opening_id]
        if binding.get("status") != "corroborated" or not binding.get("host_wall_id"):
            raise ValueError(f"expected new host is not corroborated: {opening_id}")
        reasons = tuple(binding.get("reason_codes") or ())
        if "opening_local_supplemental_source_band_host_resolved" not in reasons:
            raise ValueError(
                f"expected new host is not opening-local supplemental: {opening_id}"
            )
        member_ids = binding.get("member_wall_candidate_ids")
        if (
            not isinstance(member_ids, (list, tuple))
            or len(member_ids) != 2
            or any(type(value) is not str or not value for value in member_ids)
            or len(set(member_ids)) != len(member_ids)
        ):
            raise ValueError(
                f"expected new supplemental host members are malformed: {opening_id}"
            )
        # Supplemental W4 candidates are intentionally absent from the
        # canonical page-wide wall scope. Their positive source proposition is
        # re-proved by OpeningHostBindingProducer itself; this checker only
        # verifies that no pre-existing global host/frame proposition changed.
        evidence = new_frames.get(opening_id)
        if evidence is not None:
            _frame_signature(evidence)

    return {
        "source_sha256": candidate.get("source_sha256"),
        "physical_opening_count": len(new_bindings),
        "baseline_host_count": len(old_hosted),
        "candidate_host_count": len(new_hosted),
        "baseline_frame_count": len(old_frames),
        "candidate_frame_count": len(new_frames),
        "retained_host_ids": retained,
        "new_host_ids": sorted(expected),
        "new_frame_ids": sorted(new_frame_ids),
        "additive_snapshot_rekey_only": True,
        "host_publication_granted_by_checker": False,
        "quantity_publication_granted_by_checker": False,
        "benchmark_score_granted_by_checker": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expected-new-host-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_additive_snapshot_retention(
        json.loads(args.baseline.read_text(encoding="utf-8")),
        json.loads(args.candidate.read_text(encoding="utf-8")),
        expected_new_host_ids=tuple(args.expected_new_host_id),
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
