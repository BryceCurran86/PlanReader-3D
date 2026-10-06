from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import fitz

from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TOPOLOGY_PAGE_INDEX = 6
TARGETS = ("AIRLOCK", "LAUNDRY", "PWD", "OFFICE")


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _exact_line_hits(page: fitz.Page) -> set[str]:
    words = page.get_text("words") or []
    grouped: dict[tuple[int, int], list[tuple[int, str]]] = defaultdict(list)
    for row in words:
        if len(row) < 8:
            continue
        block_no = int(row[5])
        line_no = int(row[6])
        word_no = int(row[7])
        text = str(row[4] or "")
        grouped[(block_no, line_no)].append((word_no, text))
    hits=set()
    for items in grouped.values():
        line=_norm(" ".join(text for _,text in sorted(items)))
        if line in TARGETS:
            hits.add(line)
    return hits


def main() -> int:
    started=time.perf_counter()
    payload=SOURCE.read_bytes()
    source_sha=hashlib.sha256(payload).hexdigest()

    doc=fitz.open(stream=payload,filetype="pdf")
    try:
        selected=tuple(range(doc.page_count))
        scope=source_floor_plan_topology_scope(SOURCE, selected)
        if scope is None:
            raise RuntimeError("source floor-plan scope unavailable")
        support_indices=tuple(scope.room_area_support_page_indices)
        decisions={int(d.page_index):d for d in scope.decisions}
        hits_by_page={}
        for index in support_indices:
            hits=sorted(_exact_line_hits(doc.load_page(index)))
            if hits:
                decision=decisions.get(index)
                hits_by_page[index]={
                    "page_index_zero_based":index,
                    "page_number_one_based":index+1,
                    "title":None if decision is None else decision.title,
                    "view_types":[] if decision is None else list(decision.view_types),
                    "target_labels":hits,
                }
    finally:
        doc.close()

    candidate_support=tuple(sorted(hits_by_page))
    if not candidate_support:
        raise RuntimeError("no source-classified support pages contain target labels")

    pages=tuple(sorted({TOPOLOGY_PAGE_INDEX,*candidate_support}))
    claim=collect_live_physical_net_wall_claim(
        SOURCE,
        pages=pages,
        topology_pages=(TOPOLOGY_PAGE_INDEX,),
        room_area_support_pages=candidate_support,
    )

    labels=sorted({
        _norm(room.room_label)
        for room in claim.canonical_rooms
        if _norm(room.room_label)
    })
    firm=[]
    for q in claim.room_area_quantity_evidence:
        if q.abstained:
            continue
        metadata=dict(q.metadata or {})
        label=_norm(metadata.get("room_label"))
        if label not in TARGETS:
            continue
        firm.append({
            "room_label":label,
            "value":q.value,
            "unit":q.unit,
            "authority":q.authority,
            "status":q.status,
            "quantity_id":q.quantity_id,
            "evidence_ids":list(q.evidence_ids or ()),
            "input_entity_ids":list(q.input_entity_ids or ()),
            "metadata":metadata,
        })

    floors=[]
    room_label_by_id={
        room.canonical_room_id:_norm(room.room_label)
        for room in claim.canonical_rooms
        if _norm(room.room_label) in TARGETS
    }
    for floor in claim.canonical_floors:
        label=room_label_by_id.get(floor.room_entity_id)
        if label is None:
            continue
        floors.append({
            "room_label":label,
            "canonical_floor_id":floor.canonical_floor_id,
            "room_entity_id":floor.room_entity_id,
            "metric_area_m2":floor.metric_area_m2,
            "metric_area_quantity_id":floor.metric_area_quantity_id,
            "metric_area_authority":floor.metric_area_authority,
        })

    targets={}
    for target in TARGETS:
        targets[target]={
            "label_present":target in labels,
            "firm_areas":[row for row in firm if row["room_label"]==target],
            "floors":[row for row in floors if row["room_label"]==target],
            "support_pages":[
                row for row in hits_by_page.values()
                if target in row["target_labels"]
            ],
        }

    print(json.dumps({
        "source_sha256":source_sha,
        "mode":"DIAGNOSTIC_ONLY_SOURCE_CLASSIFIED_ROOM_AREA_SUPPORT",
        "topology_page_index_zero_based":TOPOLOGY_PAGE_INDEX,
        "candidate_support_page_indices":list(candidate_support),
        "candidate_support_pages":[hits_by_page[i] for i in candidate_support],
        "claim_status":getattr(claim.status,"value",str(claim.status)),
        "claim_reason_codes":list(claim.reason_codes),
        "canonical_room_count":len(claim.canonical_rooms),
        "canonical_floor_count":len(claim.canonical_floors),
        "firm_target_area_count":len(firm),
        "targets":targets,
        "elapsed_seconds":time.perf_counter()-started,
    },indent=2,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
