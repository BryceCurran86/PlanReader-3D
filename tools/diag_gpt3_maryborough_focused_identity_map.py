from __future__ import annotations

import json
from pathlib import Path

PROJECT = "au_qld_maryborough_service_station"
PROJECT_DIR = Path("benchmarks/frozen_holdout/full_plan_v2/projects") / PROJECT
ROOT = Path("artifacts/gpt3-maryborough-focused-surfaces")


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain an object")
    return value


def main() -> None:
    sealed_path = ROOT / f"{PROJECT}.json"
    audit_path = ROOT / "audit.json"
    if not sealed_path.is_file():
        raise SystemExit("focused Maryborough sealed run missing")
    if not audit_path.is_file():
        raise SystemExit("focused Maryborough audit missing")

    sealed = _load(sealed_path)
    audit = _load(audit_path)
    universe = _load(PROJECT_DIR / "object_universe.json")
    takeoff = _load(PROJECT_DIR / "reference_takeoff.json")

    source_sha256s = tuple(str(x) for x in sealed.get("source_sha256s") or ())
    if source_sha256s != (
        "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007",
    ):
        raise SystemExit(f"unexpected Maryborough source envelope: {source_sha256s}")

    item_by_object_ref: dict[str, str] = {}
    for item in takeoff.get("items", ()):
        if not item.get("denominator_eligible", False):
            continue
        for ref in item.get("expected_object_refs", ()):
            ref = str(ref)
            if ref in item_by_object_ref:
                raise SystemExit(f"duplicate benchmark object ref: {ref}")
            item_by_object_ref[ref] = str(item["item_id"])

    # Benchmark-side identity anchors. The anchor is an independently frozen
    # physical entry-door tag attached to the exact surface object. No room
    # label, expected quantity, finish text, or numeric similarity is used.
    floor_ref_by_tag: dict[str, str] = {}
    for row in universe.get("verified_floor_surfaces", ()):
        tag = str(row.get("entry_door_tag") or "").strip().upper()
        ref = str(row.get("object_ref") or "").strip()
        if not tag or not ref or ref not in item_by_object_ref:
            continue
        if tag in floor_ref_by_tag:
            raise SystemExit(f"ambiguous frozen floor entry-door anchor: {tag}")
        floor_ref_by_tag[tag] = ref

    ceiling_ref_by_tag: dict[str, str] = {}
    for row in universe.get("verified_ceiling_surfaces", ()):
        tag = str(row.get("entry_door_tag") or "").strip().upper()
        ref = str(row.get("object_ref") or "").strip()
        if not tag or not ref or ref not in item_by_object_ref:
            continue
        if tag in ceiling_ref_by_tag:
            raise SystemExit(f"ambiguous frozen ceiling entry-door anchor: {tag}")
        ceiling_ref_by_tag[tag] = ref

    room_tags: dict[str, tuple[str, ...]] = {}
    for room in audit.get("rooms", ()):
        room_id = str(room.get("canonical_room_id") or "").strip()
        tags = tuple(sorted({
            str(tag).strip().upper()
            for tag in (room.get("anchor_tags") or ())
            if str(tag).strip()
        }))
        if room_id:
            room_tags[room_id] = tags

    floor_room_by_ref: dict[tuple[str, str], str] = {}
    for floor in audit.get("floors", ()):
        room_id = str(floor.get("room_entity_id") or "").strip()
        canonical_id = str(floor.get("canonical_floor_id") or "").strip()
        physical_id = str(floor.get("physical_floor_surface_id") or "").strip()
        if canonical_id and room_id:
            floor_room_by_ref[("floor_finish_area", canonical_id)] = room_id
        if physical_id and room_id:
            floor_room_by_ref[("floor_area", physical_id)] = room_id

    ceiling_room_by_ref: dict[str, str] = {}
    for ceiling in audit.get("ceilings", ()):
        canonical_id = str(ceiling.get("canonical_ceiling_id") or "").strip()
        room_id = str(ceiling.get("room_entity_id") or "").strip()
        if canonical_id and room_id:
            ceiling_room_by_ref[canonical_id] = room_id

    bindings = []
    audit_rows = []
    used_items: set[str] = set()

    for row in sealed.get("quantities", ()):
        qid = str(row.get("quantity_id") or "")
        family = str(row.get("family") or "")
        refs = tuple(str(x) for x in (row.get("object_identity_refs") or ()) if str(x))
        status = "UNMAPPED"
        anchor_tags: tuple[str, ...] = ()
        benchmark_item_id = None

        # Floor benchmark objects are finish surfaces. Bind only authenticated
        # floor-finish production rows; generic floor_area rows remain extras.
        if family == "floor_finish_area" and len(refs) == 1:
            room_id = floor_room_by_ref.get((family, refs[0]))
            if room_id:
                anchor_tags = room_tags.get(room_id, ())
                if len(anchor_tags) == 1:
                    object_ref = floor_ref_by_tag.get(anchor_tags[0])
                    if object_ref:
                        benchmark_item_id = item_by_object_ref[object_ref]

        # Ceiling benchmark objects are lining/finish surfaces. Bind only where
        # the frozen ceiling object itself carries the independent door anchor.
        elif family == "ceiling_lining" and len(refs) == 1:
            room_id = ceiling_room_by_ref.get(refs[0])
            if room_id:
                anchor_tags = room_tags.get(room_id, ())
                if len(anchor_tags) == 1:
                    object_ref = ceiling_ref_by_tag.get(anchor_tags[0])
                    if object_ref:
                        benchmark_item_id = item_by_object_ref[object_ref]

        if benchmark_item_id is not None:
            if benchmark_item_id in used_items:
                raise SystemExit(
                    f"multiple production rows map to benchmark item {benchmark_item_id}"
                )
            used_items.add(benchmark_item_id)
            bindings.append({
                "benchmark_item_id": benchmark_item_id,
                "production_object_identity_refs": list(refs),
                "production_family": family,
            })
            status = "BOUND"

        audit_rows.append({
            "quantity_id": qid,
            "family": family,
            "object_identity_refs": list(refs),
            "anchor_tags": list(anchor_tags),
            "benchmark_item_id": benchmark_item_id,
            "status": status,
        })

    identity_map = {
        "schema_version": "1.0.0",
        "project_id": PROJECT,
        "source_sha256s": list(source_sha256s),
        "bindings": bindings,
    }
    (ROOT / "maryborough.identity-map.json").write_text(
        json.dumps(identity_map, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (ROOT / "maryborough.identity-audit.json").write_text(
        json.dumps({
            "binding_count": len(bindings),
            "floor_anchor_tags": sorted(floor_ref_by_tag),
            "ceiling_anchor_tags": sorted(ceiling_ref_by_tag),
            "rows": audit_rows,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "sealed_quantity_count": len(sealed.get("quantities", ())),
        "binding_count": len(bindings),
        "bindings": bindings,
        "rows": audit_rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
