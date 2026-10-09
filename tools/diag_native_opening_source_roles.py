"""Read-only native source-role proof; no benchmark, measurement or quantity inputs."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def source_role_report(source_bytes: bytes, *, page_ids: tuple[str, ...]) -> dict:
    sha = hashlib.sha256(source_bytes).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=source_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf", page_ids=page_ids,
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=page_ids,
    )
    physical = source.physical_opening_authority()
    positive, opposed, page_selectors = {}, {}, {}
    native_ids = frozenset(published.visible_observation_ids)
    for observation_id in (
        *published.visible_observation_ids,
        *published.raster_opening_primitive_observation_ids,
    ):
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=sha, snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if result.existence_record is not None:
            positive[result.existence_record.record_id] = asdict(result.existence_record)
        if result.candidate is not None and result.opposing_evidence_atoms:
            opposed[result.candidate.candidate_id] = {
                "status": result.status.value,
                "reason_codes": result.reason_codes,
                "candidate": asdict(result.candidate),
                "opposing_evidence_atoms": [asdict(atom) for atom in result.opposing_evidence_atoms],
            }
        if observation_id in native_ids:
            observation = result.source_observation.observation
            if observation is None:
                raise RuntimeError("native source ownership unavailable")
            page_selectors.setdefault(str(observation.page_id), selector)
    return {
        "source_sha256": sha,
        "revision_id": published.revision.revision_id,
        "snapshot_id": published.snapshot.snapshot_id,
        "source_decode_coverage": asdict(published.coverage),
        "selected_geometry_page_ids": page_ids,
        "positive_existence_records": [positive[key] for key in sorted(positive)],
        "retained_opposed_candidates": [opposed[key] for key in sorted(opposed)],
        "native_candidate_closures": [
            asdict(physical.assess_visible_candidate_closure(page_selectors[key]))
            for key in sorted(page_selectors, key=int)
        ],
        "summary": {
            "positive_existence_claims": len(positive),
            "retained_opposed_hypotheses": len(opposed),
            "opposition_reason_counts": dict(Counter(
                reason for row in opposed.values() for reason in row["reason_codes"]
            )),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = source_role_report(
        args.pdf.read_bytes(), page_ids=tuple(sorted(set(args.page_id), key=int)),
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True,
                                      default=lambda value: value.value) + "\n")
    print(json.dumps({"source_sha256": result["source_sha256"], **result["summary"]}))


if __name__ == "__main__":
    main()
