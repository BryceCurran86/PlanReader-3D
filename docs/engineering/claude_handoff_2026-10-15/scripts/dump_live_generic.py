"""Read-only: run the existing live pipeline on original Maryborough page 7 and dump walls/rooms/floors with geometry.

Uses exactly the call the Maryborough floor score-input runner uses (pages=(6,), topology_pages=(6,),
room_area_support_pages=(10,); 0-based). OCR is blocked to mirror CI.
"""
import dataclasses
import json
import sys
import time

sys.modules["rapidocr"] = None
sys.modules["onnxruntime"] = None
repo = sys.argv[1]
out = sys.argv[2]
sys.path.insert(0, repo)

from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim  # noqa: E402

PDF = f"{repo}/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf"
t0 = time.time()
pg=tuple(int(v) for v in sys.argv[3].split(","))
support=tuple(int(v) for v in sys.argv[4].split(",")) if len(sys.argv)>4 and sys.argv[4] else None
claim = collect_live_physical_net_wall_claim(PDF, pages=pg, topology_pages=pg, room_area_support_pages=support)
print("claim done", round(time.time() - t0, 1), "s", claim.status, claim.canonical_wall_status.value if claim.canonical_wall_status else None)


def plain(obj):
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:  # noqa: BLE001
            pass
    if dataclasses.is_dataclass(obj):
        return {f.name: plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [plain(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): plain(v) for k, v in obj.items()}
    if hasattr(obj, "value") and not isinstance(obj, (str, int, float)):
        return obj.value
    return obj


payload = {
    "status": plain(claim.status),
    "reason_codes": list(claim.reason_codes),
    "canonical_wall_status": plain(claim.canonical_wall_status),
    "walls": [plain(w) for w in claim.canonical_walls],
    "unresolved_wall_candidate_ids": list(claim.unresolved_wall_candidate_ids),
    "rooms": [plain(r) for r in claim.canonical_rooms],
    "floors": [plain(f) for f in claim.canonical_floors],
    "floor_status": plain(claim.canonical_floor_status),
    "room_status": plain(claim.canonical_room_status),
    "room_area_quantity_evidence": [plain(q) for q in claim.room_area_quantity_evidence],
}
json.dump(payload, open(out, "w"), indent=1, default=str)
print("walls", len(payload["walls"]), "unresolved", len(payload["unresolved_wall_candidate_ids"]), "rooms", len(payload["rooms"]), "floors", len(payload["floors"]))
