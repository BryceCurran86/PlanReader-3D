"""Read-only: run the unchanged live claim for original page 7 (+support page 11) and capture the cross-view / same-view room-area
producer results (dimension box, label bboxes, ids) by wrapping the producers' publish() in THIS process only. No repo edit.
"""
import json
import sys
import time

sys.modules["rapidocr"] = None
sys.modules["onnxruntime"] = None
repo, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)

import pb_cross_view_room_area_authority as cv  # noqa: E402
import pb_same_view_room_area_authority as sv  # noqa: E402
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim  # noqa: E402

STASH = {"cross": [], "same": []}
_orig_cv = cv.CrossViewRoomAreaProducer.publish
_orig_sv = sv.SameViewRoomAreaProducer.publish


def _wrap_cv(self):
    res = _orig_cv(self)
    STASH["cross"].append(res)
    return res


def _wrap_sv(self):
    res = _orig_sv(self)
    STASH["same"].append(res)
    return res


cv.CrossViewRoomAreaProducer.publish = _wrap_cv
sv.SameViewRoomAreaProducer.publish = _wrap_sv

PDF = f"{repo}/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf"
t0 = time.time()
claim = collect_live_physical_net_wall_claim(PDF, pages=(6,), topology_pages=(6,), room_area_support_pages=(10,))
print("claim done", round(time.time() - t0, 1), "s", flush=True)


def jsonable(v):
    if hasattr(v, "value") and not isinstance(v, (str, int, float)):
        return v.value
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return v


def dump(res):
    rows = []
    for r in res.records:
        ev = r.area_evidence
        rows.append({
            "physical_room_id": r.physical_room_id, "source_room_face_record_id": r.source_room_face_record_id,
            "room_label": r.room_label, "source_dimension_page_id": getattr(r, "source_dimension_page_id", None),
            "horizontal_dimension_id": getattr(r, "horizontal_dimension_id", None), "vertical_dimension_id": getattr(r, "vertical_dimension_id", None),
            "evidence_id": ev.evidence_id, "value": ev.normalized_value, "unit": ev.unit, "method": ev.method, "kind": ev.kind,
            "metadata": jsonable(dict(ev.metadata or {})),
        })
    return {"status": jsonable(res.status), "reason_codes": list(res.reason_codes), "records": rows,
            "unresolved_physical_room_ids": list(getattr(res, "unresolved_physical_room_ids", ())),
            "unresolved_first_failure_codes": [list(x) for x in getattr(res, "unresolved_first_failure_codes", ())]}


payload = {"cross": [dump(r) for r in STASH["cross"]], "same": [dump(r) for r in STASH["same"]],
           "rooms": [{"label": r.room_label, "physical_room_id": r.physical_room_id, "source_room_face_record_id": r.source_room_face_record_id,
                      "polygon": [list(p) for p in r.polygon_pdf_pts]} for r in claim.canonical_rooms if r.room_label]}
json.dump(payload, open(out, "w"), indent=1, default=str)
print("saved", out, "cross records", sum(len(x["records"]) for x in payload["cross"]), "same records", sum(len(x["records"]) for x in payload["same"]), flush=True)
