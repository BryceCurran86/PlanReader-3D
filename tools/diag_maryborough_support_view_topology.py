from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TARGETS = (
    "FOOD PREP",
    "COLD ROOM",
    "FREEZER",
    "DRY STORE",
    "SALES",
    "WASH UP",
    "FOOD SERVICE",
    "POS COUNTER",
    "M-AMB",
    "F-AMB",
    "TRUCK DRIVER LOUNGE",
    "PWD",
    "AIRLOCK",
    "LAUNDRY",
    "OFFICE",
)

# Zero-based page indices, selected from already-classified support views.
SCOPES = {
    "A120_RCP": 8,
    "A140_FLOOR_FINISHES_PARTITIONS": 10,
}


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _summarize_claim(claim) -> dict:
    labels = sorted(
        {
            _norm(room.room_label)
            for room in claim.canonical_rooms
            if _norm(room.room_label)
        }
    )
    labelled_rooms = [
        {
            "room_entity_id": room.room_entity_id,
            "physical_room_id": room.physical_room_id,
            "room_label": _norm(room.room_label),
            "source_room_face_record_id": room.source_room_face_record_id,
            "source_page_id": room.source_page_id,
            "decision_scope_id": room.decision_scope_id,
            "geometry_complete": room.geometry_complete,
            "polygon_vertex_count": len(room.polygon or ()),
        }
        for room in claim.canonical_rooms
        if _norm(room.room_label)
    ]
    targets = {
        target: {
            "label_present": target in labels,
            "room_count": sum(
                1
                for room in labelled_rooms
                if room["room_label"] == target
            ),
            "rooms": [
                room for room in labelled_rooms
                if room["room_label"] == target
            ],
        }
        for target in TARGETS
    }
    return {
        "status": getattr(claim.status, "value", str(claim.status)),
        "reason_codes": list(claim.reason_codes),
        "canonical_room_count": len(claim.canonical_rooms),
        "canonical_floor_count": len(claim.canonical_floors),
        "label_count": len(labels),
        "labels": labels,
        "targets": targets,
    }


def main() -> int:
    payload = SOURCE.read_bytes()
    source_sha256 = hashlib.sha256(payload).hexdigest()
    results = {}

    for name, page_index in SCOPES.items():
        started = time.perf_counter()
        claim = collect_live_physical_net_wall_claim(
            SOURCE,
            pages=(page_index,),
            topology_pages=(page_index,),
            room_area_support_pages=(page_index,),
        )
        results[name] = {
            "page_index_zero_based": page_index,
            "page_number_one_based": page_index + 1,
            "elapsed_seconds": time.perf_counter() - started,
            **_summarize_claim(claim),
        }

    print(
        json.dumps(
            {
                "source_sha256": source_sha256,
                "mode": "DIAGNOSTIC_ONLY_SUPPORT_VIEW_TOPOLOGY",
                "results": results,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
