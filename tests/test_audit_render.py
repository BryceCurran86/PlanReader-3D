"""Synthetic proofs for the clean/audit 3D render (pb_audit_render, pb_audit_coverage_record)."""
from __future__ import annotations

import copy
import json
import math
import random

import pytest

from pb_audit_coverage_record import (
    CoverageState,
    DefaultCoverageProvider,
    TakeoffLink,
)
from pb_audit_render import (
    CAMERA_PRESETS,
    DISPLAY_ONLY_UNRESOLVED_HEIGHT_M,
    build_audit_scene,
    callout_label,
    camera_for,
    render_audit_html,
)
from pb_canonical_building import (
    CanonicalColumn,
    CanonicalLevel,
    CanonicalOpening,
    CanonicalRoof,
    CanonicalSpace,
    CanonicalWall,
    ObjectType,
    Vector2D,
)


def wall(wid, a, b, *, h=2.4, t=0.2, ext=False, openings=(), meta=None):
    return CanonicalWall(
        id=wid, start_point=Vector2D(*a), end_point=Vector2D(*b), height_m=h, thickness_m=t,
        is_external=ext, openings=list(openings), metadata=dict(meta or {}),
    )


def level(walls=(), spaces=(), roofs=(), columns=(), elev=0.0):
    return CanonicalLevel(id="L1", elevation_m=elev, height_m=2.7, walls=list(walls), spaces=list(spaces),
                          roofs=list(roofs), columns=list(columns))


def square(x0=0.0, y0=0.0, s=4.0):
    return [Vector2D(x0, y0), Vector2D(x0 + s, y0), Vector2D(x0 + s, y0 + s), Vector2D(x0, y0 + s)]


def states(scene):
    return {o["id"]: o["audit"]["coverage_state"] for o in scene["objects"] + scene["not_drawn"]}


# ---- positives ---------------------------------------------------------------

def test_linked_wall_is_accounted_and_unlinked_is_unaccounted():
    lv = level([wall("w1", (0, 0), (4, 0)), wall("w2", (4, 0), (4, 4))])
    prov = DefaultCoverageProvider({"w1": [TakeoffLink("row-1")]})
    st = states(build_audit_scene([lv], prov))
    assert st == {"w1": "ACCOUNTED", "w2": "UNACCOUNTED"}


def test_partial_link_is_partial_and_row_ids_are_carried():
    lv = level([wall("w1", (0, 0), (4, 0))])
    scene = build_audit_scene([lv], DefaultCoverageProvider({"w1": [TakeoffLink("r1"), TakeoffLink("r2", complete=False)]}))
    rec = scene["objects"][0]["audit"]
    assert rec["coverage_state"] == "PARTIAL" and rec["takeoff_row_ids"] == ["r1", "r2"]


def test_refusing_topology_status_is_abstained_even_with_link():
    lv = level([wall("w1", (0, 0), (4, 0), meta={"topology_status": "ABSTAINED"})])
    scene = build_audit_scene([lv], DefaultCoverageProvider({"w1": [TakeoffLink("r1")]}))
    assert scene["objects"][0]["audit"]["coverage_state"] == "ABSTAINED"
    assert scene["objects"][0]["audit"]["reason_code"] == "topology_status:ABSTAINED"


def test_opening_room_roof_and_post_are_rendered_with_types():
    op = CanonicalOpening(id="o1", opening_type="WINDOW", wall_id="w1", offset_along_wall_m=1.0,
                          width_m=1.2, height_m=1.2, sill_height_m=0.9)
    lv = level([wall("w1", (0, 0), (6, 0), openings=[op])], [CanonicalSpace(id="s1", boundary_polygon=square())],
               [CanonicalRoof(id="r1", polygon=square())], [CanonicalColumn(id="c1", center=Vector2D(1, 1), width_m=0.2, depth_m=0.2, height_m=2.4)])
    scene = build_audit_scene([lv], DefaultCoverageProvider())
    types = {o["id"]: o["type"] for o in scene["objects"]}
    assert types == {"w1": "WALL", "o1": "WINDOW", "s1": "SPACE", "r1": "ROOF", "c1": "COLUMN"}
    assert callout_label("WINDOW", CoverageState.UNACCOUNTED) == "UNACCOUNTED OPENING"
    assert callout_label("SPACE", CoverageState.UNACCOUNTED) == "ROOM AREA NOT RECONCILED"
    assert callout_label("ROOF", CoverageState.UNACCOUNTED) == "ROOF PLANE NOT LINKED"
    assert callout_label("COLUMN", CoverageState.UNACCOUNTED) == "POST/PIER NOT COUNTED"
    assert callout_label("WALL", CoverageState.PARTIAL) == "PARTIAL WALL COVERAGE"
    assert callout_label("WALL", CoverageState.ABSTAINED) == "AUTHORITY ABSTAINED"
    assert callout_label("WALL", CoverageState.ACCOUNTED) is None


# ---- look-alike negatives / fail-closed --------------------------------------

def test_unresolved_height_or_display_geometry_can_never_be_accounted():
    w = wall("w1", (0, 0), (4, 0), h=None)
    lv = level([w])
    scene = build_audit_scene([lv], DefaultCoverageProvider({"w1": [TakeoffLink("r1")]}))
    o = scene["objects"][0]
    assert o["height_basis"] == "display_only_unresolved" and o["height_m"] == DISPLAY_ONLY_UNRESOLVED_HEIGHT_M
    assert o["audit"]["coverage_state"] == "PARTIAL" and "unresolved:height" in o["audit"]["reason_code"]

    nogeo = CanonicalWall(id="w2", height_m=2.4, thickness_m=0.2)
    scene = build_audit_scene([level([nogeo])], DefaultCoverageProvider({"w2": [TakeoffLink("r1")]}),
                              {"w2": {"pts": [[0, 0], [3, 0]], "basis": "display_only_title_block"}})
    o = scene["objects"][0]
    assert o["geometry"]["basis"] == "display_only_title_block"
    assert o["audit"]["coverage_state"] == "PARTIAL"


def test_unresolved_level_elevation_prevents_accounted():
    lv = CanonicalLevel(id="L1", elevation_m=None, walls=[wall("w1", (0, 0), (4, 0))])
    scene = build_audit_scene([lv], DefaultCoverageProvider({"w1": [TakeoffLink("r1")]}))
    assert scene["objects"][0]["audit"]["coverage_state"] == "PARTIAL"


def test_objects_without_any_geometry_are_listed_not_dropped_and_never_accounted():
    lv = level([CanonicalWall(id="w1", height_m=2.4, thickness_m=0.2)])
    scene = build_audit_scene([lv], DefaultCoverageProvider({"w1": [TakeoffLink("r1")]}))
    assert scene["objects"] == [] and [o["id"] for o in scene["not_drawn"]] == ["w1"]
    assert scene["not_drawn"][0]["audit"]["coverage_state"] != "ACCOUNTED"
    assert scene["summary"]["WALL"]["ACCOUNTED"] == 0
    import base64
    import re
    b64 = re.search(r'atob\("([^"]+)"\)', render_audit_html(scene, mode="audit")).group(1)
    assert json.loads(base64.b64decode(b64))["not_drawn"][0]["id"] == "w1"


def test_link_to_other_object_does_not_account_a_lookalike():
    lv = level([wall("w1", (0, 0), (4, 0)), wall("w1b", (0, 1), (4, 1))])
    st = states(build_audit_scene([lv], DefaultCoverageProvider({"w1": [TakeoffLink("r1")]})))
    assert st["w1b"] == "UNACCOUNTED"


def test_refused_opening_physical_state_is_abstained():
    op = CanonicalOpening(id="o1", object_type=ObjectType.DOOR, wall_id="w1", offset_along_wall_m=1, width_m=.9,
                          height_m=2.1, metadata={"physical_state": "evidence_only"})
    scene = build_audit_scene([level([wall("w1", (0, 0), (4, 0), openings=[op])])], DefaultCoverageProvider())
    assert states(scene)["o1"] == "ABSTAINED"


# ---- invariances --------------------------------------------------------------

def _mk(walls):
    return build_audit_scene([level(walls)], DefaultCoverageProvider({"w1": [TakeoffLink("r")]}))


def test_input_order_invariance_of_states_and_summary():
    ws = [wall(f"w{i}", (i, 0), (i, 3)) for i in range(1, 8)]
    a = _mk(ws)
    shuffled = ws[:]
    random.Random(4).shuffle(shuffled)
    b = _mk(shuffled)
    assert states(a) == states(b) and a["summary"] == b["summary"]


def _transform(walls, fn):
    out = []
    for w in walls:
        out.append(wall(w.id, fn(w.start_point.x, w.start_point.y), fn(w.end_point.x, w.end_point.y)))
    return out


@pytest.mark.parametrize("fn", [
    lambda x, y: (x + 100.5, y - 33.25),
    lambda x, y: (x * math.cos(0.7) - y * math.sin(0.7), x * math.sin(0.7) + y * math.cos(0.7)),
    lambda x, y: (x * 2.0, y * 2.0),
])
def test_translation_rotation_scale_do_not_change_states(fn):
    ws = [wall("w1", (0, 0), (4, 0)), wall("w2", (4, 0), (4, 3)), wall("w3", (4, 3), (0, 3))]
    assert states(_mk(ws)) == states(_mk(_transform(ws, fn)))


def test_segment_splitting_never_upgrades_an_unlinked_span():
    split = _mk([wall("w1", (0, 0), (4, 0)), wall("w1b", (4, 0), (8, 0))])
    st = states(split)
    assert st["w1"] == "ACCOUNTED" and st["w1b"] == "UNACCOUNTED"
    assert split["summary"]["WALL"]["UNACCOUNTED"] == 1


def test_unrelated_content_does_not_change_existing_states():
    base = states(_mk([wall("w1", (0, 0), (4, 0)), wall("w2", (4, 0), (4, 3))]))
    more = states(_mk([wall("w1", (0, 0), (4, 0)), wall("w2", (4, 0), (4, 3)), wall("far", (500, 500), (520, 500))]))
    assert all(more[k] == v for k, v in base.items())


# ---- determinism, no mutation, cameras ---------------------------------------

def test_deterministic_replay_and_json_stable():
    lv = level([wall("w1", (0, 0), (4, 0)), wall("w2", (4, 0), (4, 3))])
    a = json.dumps(build_audit_scene([lv], DefaultCoverageProvider()), sort_keys=True)
    b = json.dumps(build_audit_scene([lv], DefaultCoverageProvider()), sort_keys=True)
    assert a == b
    assert render_audit_html(json.loads(a), mode="audit") == render_audit_html(json.loads(b), mode="audit")


def test_inputs_are_not_mutated_and_authority_flags_untouched():
    lv = level([wall("w1", (0, 0), (4, 0), h=None)], [CanonicalSpace(id="s1", boundary_polygon=square())])
    before = copy.deepcopy(lv.to_dict()) if hasattr(lv, "to_dict") else None
    disp = {"w1": {"pts": [[0, 0], [1, 0]], "basis": "display_only_x"}}
    disp_before = copy.deepcopy(disp)
    build_audit_scene([lv], DefaultCoverageProvider({"w1": [TakeoffLink("r")]}), disp)
    assert disp == disp_before
    if before is not None:
        assert lv.to_dict() == before
    assert lv.walls[0].takeoff_eligible is False and lv.walls[0].deduction_authority is False
    assert lv.walls[0].height_m is None


@pytest.mark.parametrize("preset", CAMERA_PRESETS)
def test_clean_and_audit_cameras_match(preset):
    scene = build_audit_scene([level([wall("w1", (0, 0), (10, 0)), wall("w2", (10, 0), (10, 6))])], DefaultCoverageProvider())
    clean = render_audit_html(scene, mode="clean", camera_preset=preset)
    audit = render_audit_html(scene, mode="audit", camera_preset=preset)
    cam = json.dumps(camera_for(scene["bounds"], preset))
    assert f"const CAMERA = {cam};" in clean and f"const CAMERA = {cam};" in audit


def test_viewport_expansion_only_moves_camera_not_states():
    a = build_audit_scene([level([wall("w1", (0, 0), (4, 0))])], DefaultCoverageProvider())
    b = build_audit_scene([level([wall("w1", (0, 0), (4, 0)), wall("z", (200, 0), (210, 0))])], DefaultCoverageProvider())
    assert states(a)["w1"] == states(b)["w1"]
    assert camera_for(a["bounds"], "front_left") != camera_for(b["bounds"], "front_left")


def test_summary_counts_every_record():
    lv = level([wall("w1", (0, 0), (4, 0)), CanonicalWall(id="w2")])
    scene = build_audit_scene([lv], DefaultCoverageProvider())
    total = sum(sum(v.values()) for v in scene["summary"].values())
    assert total == len(scene["objects"]) + len(scene["not_drawn"]) == 2


def test_html_escapes_title_and_embeds_no_raw_script_breakout():
    scene = build_audit_scene([level([wall("w1", (0, 0), (4, 0))])], DefaultCoverageProvider(), title="</title><script>x</script>")
    html = render_audit_html(scene, mode="audit")
    assert "<script>x</script>" not in html
