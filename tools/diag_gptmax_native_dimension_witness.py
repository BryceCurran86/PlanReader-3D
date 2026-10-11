"""Original-PDF read-only G17 native-opening support/annotation receipt diagnostic.

The report is evidence for engineering triage, never a host, opening-count,
measurement, quantity, or benchmark publication route. No source role is guessed
from appearance, surrounding text or proximity.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def source_complete_dimension_opposition(atom_rows: list[dict], support_ids: tuple[str, ...]) -> bool:
    """An individual original-source opponent must cover EVERY G17 support.

    A union of individually partial native annotation components is not
    evidence of one complete dimension. This is read-only classification of
    candidate atoms, not a source-role or physical-nonexistence decision.
    """
    required = frozenset(support_ids)
    if not required or len(required) != len(support_ids):
        return False
    for atom in atom_rows:
        if (atom.get("kind") != "dimension_annotation"
                or atom.get("status") != "candidate"
                or atom.get("reason_codes") != ["native_dimension_cap_tick_text_topology"]
                or atom.get("all_opening_support_covered") is not True):
            continue
        owned = atom.get("source_observation_ids")
        claimed = atom.get("opening_support_observation_ids")
        if (not isinstance(owned, list) or not isinstance(claimed, list)
                or len(owned) != len(set(owned))
                or len(claimed) != len(set(claimed))):
            continue
        if set(claimed) == required and required <= set(owned):
            return True
    return False


def probe_original_native_opening(
    original_pdf_bytes: bytes, *, expected_source_sha: str,
    page_id: str, representative_observation_id: str,
    expected_opening_record_id: str,
) -> dict:
    """Reprove one opening and its complete existing native support on source.

    Any missing or mismatched original receipt raises; the caller must not treat
    absent dimension-cap proof as proof that a physical opening does not exist.
    """
    if not isinstance(original_pdf_bytes, bytes):
        raise TypeError("source PDF must be original immutable bytes")
    actual_sha = sha256(original_pdf_bytes).hexdigest()
    if actual_sha != expected_source_sha or len(actual_sha) != 64:
        raise ValueError("original PDF source SHA mismatch")
    if not isinstance(page_id, str) or not page_id.isdigit() or int(page_id) < 1:
        raise ValueError("invalid original page id")
    for name, value in (
        ("representative observation", representative_observation_id),
        ("expected opening record", expected_opening_record_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"invalid {name}")

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{actual_sha[:32]}",
        source_bytes=original_pdf_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=(page_id,),
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=(page_id,),
    )
    visible_rows = dict(source.authority().authenticated_visible_observations(published))
    if representative_observation_id not in visible_rows:
        raise ValueError("representative is not an authenticated native visible observation")

    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=actual_sha,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=representative_observation_id,
    )
    physical = source.physical_opening_authority()
    result = physical.prove_existence(selector)
    opening = result.existence_record
    if opening is None or opening.record_id != expected_opening_record_id:
        raise ValueError("opening identity not proved by exact original source")
    if opening.page_id != page_id:
        raise ValueError("opening page scope changed")
    support_ids = tuple(opening.source_observation_ids)
    if (not support_ids or len(support_ids) != len(set(support_ids))
            or representative_observation_id not in support_ids
            or not set(support_ids) <= visible_rows.keys()):
        raise ValueError("complete native opening source support unavailable")
    support = []
    for observation_id in sorted(support_ids):
        record = visible_rows[observation_id]
        if record.page_id != page_id or len(record.geometry) != 4:
            raise ValueError("source support geometry or page is unavailable")
        support.append({
            "observation_id": observation_id,
            "geometry_pt": list(record.geometry),
            "observation_kind": record.observation_kind,
            "source_primitive_ref": record.source_primitive_ref,
        })
    # Reuse the producer-owned authority. An empty tuple is genuinely
    # UNPROVED dimension opposition, not an assertion of physical opening.
    atoms = source.native_dimension_cap_evidence(
        selector, opening_support_ids=support_ids,
    )
    # Candidate atoms have opposing polarity only; never decide the G17
    # candidate's physical truth or mutate its source/host identities here.
    atom_rows = [{
        "evidence_id": a.evidence_id,
        "kind": a.kind,
        "status": a.status.value,
        "reason_codes": list(a.reason_codes),
        "source_observation_ids": list(
            a.metadata.get("source_observation_ids", ())
        ),
        "opening_support_observation_ids": list(
            a.metadata.get("opening_support_observation_ids", ())
        ),
        "all_opening_support_covered": a.metadata.get(
            "all_opening_support_covered", False,
        ),
    } for a in atoms]
    return {
        "schema_version": "1.0.0",
        "source_sha256": actual_sha,
        "page_id": page_id,
        "opening_record_id": opening.record_id,
        "opening_currently_source_corroborated": True,
        "opening_source_observation_count": len(support),
        "opening_source_observations": support,
        "native_dimension_cap_opposing_atoms": atom_rows,
        "native_dimension_cap_opposition_proven": source_complete_dimension_opposition(
            atom_rows, support_ids,
        ),
        "physical_host_proven": False,
        "opening_count_publication_allowed": False,
        "metric_quantity_publication_allowed": False,
        "physical_nonexistence_proven": False,
        "benchmark_accuracy": None,
        "source_roles_preserved_without_mutation": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--representative-observation-id", required=True)
    parser.add_argument("--expected-opening-record-id", required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = probe_original_native_opening(
        args.pdf.read_bytes(), page_id=args.page_id,
        representative_observation_id=args.representative_observation_id,
        expected_opening_record_id=args.expected_opening_record_id,
        expected_source_sha=args.expected_source_sha,
    )
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
    )
    print(json.dumps({
        "opening_record_id": result["opening_record_id"],
        "native_support_count": result["opening_source_observation_count"],
        "dimension_opposing_atoms": len(result["native_dimension_cap_opposing_atoms"]),
        "host_publication_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
