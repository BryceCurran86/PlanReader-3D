"""Real-source shadow harness for Item 19B KSTVET page 54.

Diagnostic only. The input PDF must match the repository-pinned KSTVET SHA.
No benchmark quantity, expected BOQ value, live extractor, or commercial output
is read or changed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pb_wall_finish_face_binding_authority import WallFinishFaceBindingProducer
from pb_source_visibility_authority import SourceVisibilityProducer

EXPECTED_SHA256 = "6856bfa739aa136dd8e0bf17cb25fd43d0d31c9c3dfe3252525454f09d8fa4dc"
PAGE_ID = "54"


def run(pdf_path: Path) -> list[dict]:
    payload = pdf_path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_SHA256:
        raise SystemExit(
            f"KSTVET source SHA mismatch: expected {EXPECTED_SHA256}, got {actual}"
        )

    source = SourceVisibilityProducer(
        producer_method="item19b-kstvet-direct-finish-shadow",
        producer_version="1.0.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="kstvet-item19b-shadow",
        source_bytes=payload,
        source_locator=f"sha256://{EXPECTED_SHA256}",
        page_ids=(PAGE_ID,),
    )
    producer = WallFinishFaceBindingProducer.from_source_visibility_producer(
        source,
        page_ids=(PAGE_ID,),
    )

    rows: list[dict] = []
    for result in producer.published_results():
        for record in result.bindings:
            if record.page_id != PAGE_ID:
                continue
            rows.append(
                {
                    "annotation_observation_ids": list(record.annotation_observation_ids),
                    "leader_path_ids": list(record.leader_path_ids),
                    "terminator_primitive_ids": list(record.terminator_primitive_ids),
                    "physical_wall_id": record.physical_wall_id,
                    "wall_role_record_id": record.wall_role_record_id,
                    "wall_role": record.wall_role.value,
                    "semantic_face": record.physical_face_role.value,
                    "physical_face_id": record.physical_face_id,
                    "source_face_segment_ids": list(record.source_face_segment_ids),
                    "trade_scope_id": record.trade_scope_id,
                    "finish_material": record.finish_material,
                    "binding_status": record.status.value,
                    "scope_completeness": record.decision_scope_complete,
                    "reason_codes": list(record.reason_codes),
                }
            )
        for scope in result.scope_records:
            rows.append(
                {
                    "scope_record": True,
                    "scope_id": scope.scope_id,
                    "trade_scope_id": scope.trade_scope_id,
                    "finish_material": scope.finish_material,
                    "target_face_ids": list(scope.target_face_ids),
                    "covered_face_ids": list(scope.covered_face_ids),
                    "binding_ids": list(scope.binding_ids),
                    "scope_status": scope.scope_status.value,
                    "scope_completeness": scope.decision_scope_complete,
                    "reason_codes": list(scope.reason_codes),
                }
            )
    return rows


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: wall_finish_face_binding_kstvet_shadow.py <canonical-kstvet.pdf>")
    rows = run(Path(sys.argv[1]))
    print(json.dumps(rows, indent=2, sort_keys=True))
    direct = [row for row in rows if not row.get("scope_record")]
    if not direct:
        raise SystemExit("KSTVET page 54 produced no accepted direct finish callout bindings")


if __name__ == "__main__":
    main()
