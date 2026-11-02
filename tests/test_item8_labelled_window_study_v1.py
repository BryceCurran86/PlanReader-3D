"""Study B (owner-labelled framed windows): synthetic proofs for the pure helpers and the viewer template.

Pre-registration: docs/engineering/claude_item8_labelled_window_study_20261103.md (Part A). These tests use only synthetic rows
and extents. No original drawing, label or expected quantity is read. The study instrument changes no production module."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from tools.item8_b import b_core
from tools.item8_b.b_core import (
    OUTCOME_NO_CONTAINING_STRUCTURE,
    OUTCOME_NO_OUTLINE_FITS,
    OUTCOME_PICKED,
    SCHEMA,
    bbox_of_lines,
    build_viewer_html,
    containing_structures,
    decide,
    judge,
    label_counts,
    picked_ids,
    structures_digest,
    summarise_rows,
    validate_labels,
)

REPO = Path(__file__).resolve().parents[1]


def S(sid, box):
    return {"id": sid, "bbox": box}


def face(d_i, d_m, same=True, available=True):
    return dict(order="before_all", d_M=d_m, d_I=d_i, same_style=same, fill_edge=False, transparent=False,
                available=available, locality="opening_local", extent_class="x")


def interior(order="before_all", available=True):
    return dict(order=order, d_M=1, d_I=1, same_style=True, fill_edge=False, transparent=False, available=available)


def row(interiors, faces):
    return dict(members=6, status="x", shared_support=0, face_ink=list(faces), interior=list(interiors), shadow_status="ok")


# ---------------------------------------------------------------- geometry helpers
def test_bbox_is_order_and_splitting_invariant_and_translates():
    lines = [(0.0, 0.0, 10.0, 0.0), (10.0, 0.0, 10.0, 4.0), (0.0, 4.0, 10.0, 4.0)]
    box = bbox_of_lines(lines)
    assert box == (0.0, 0.0, 10.0, 4.0)
    assert bbox_of_lines(reversed(lines)) == box
    split = [(0.0, 0.0, 4.0, 0.0), (4.0, 0.0, 10.0, 0.0)] + lines[1:]
    assert bbox_of_lines(split) == box
    shifted = [(x0 + 7.5, y0 - 3.0, x1 + 7.5, y1 - 3.0) for x0, y0, x1, y1 in lines]
    assert bbox_of_lines(shifted) == (7.5, -3.0, 17.5, 1.0)
    assert bbox_of_lines([]) is None


def test_containing_returns_every_structure_in_id_order_never_a_single_choice():
    structures = [S("c", (0, 0, 100, 100)), S("a", (40, 40, 60, 60)), S("b", (45, 45, 55, 55)), S("far", (200, 200, 210, 210))]
    # a point inside three nested extents returns all three: no nearest, first or smallest choice
    assert containing_structures(structures, 50, 50) == ["a", "b", "c"]
    assert containing_structures(list(reversed(structures)), 50, 50) == ["a", "b", "c"]
    assert containing_structures(structures, 50, 50) == containing_structures(structures, 50, 50)
    assert containing_structures(structures, 150, 150) == []
    # boundary is inclusive and deterministic
    assert containing_structures(structures, 100, 100) == ["c"]


def test_containing_is_translation_invariant_and_ignores_unrelated_structures():
    base = [S("a", (0, 0, 10, 10)), S("b", (5, 5, 20, 20))]
    moved = [S(s["id"], tuple(v + 1000.0 for v in s["bbox"])) for s in base]
    assert containing_structures(base, 7, 7) == containing_structures(moved, 1007.0, 1007.0) == ["a", "b"]
    noise = base + [S("n%d" % i, (500 + i, 500 + i, 501 + i, 501 + i)) for i in range(50)]
    assert containing_structures(noise, 7, 7) == ["a", "b"]


def test_digest_depends_on_ids_only_and_not_on_order_or_geometry():
    a = [S("x", (0, 0, 1, 1)), S("y", (2, 2, 3, 3))]
    b = [S("y", (9, 9, 10, 10)), S("x", (5, 5, 6, 6))]
    assert structures_digest(a) == structures_digest(b)
    assert structures_digest(a) != structures_digest(a + [S("z", (0, 0, 1, 1))])


# ---------------------------------------------------------------- labels
def good_labels(sha="abc", marks=None):
    return {"schema": SCHEMA, "document": "d", "page": 1, "structures_sha256": sha,
            "marks": marks if marks is not None else [
                {"outcome": OUTCOME_PICKED, "picked": "s1", "containing_count": 2},
                {"outcome": OUTCOME_NO_OUTLINE_FITS, "picked": None, "containing_count": 3},
                {"outcome": OUTCOME_NO_CONTAINING_STRUCTURE, "picked": None, "containing_count": 0},
                {"outcome": OUTCOME_PICKED, "picked": "s1", "containing_count": 1}]}


def test_valid_labels_have_no_problems_and_the_a5_counts_match():
    labels = good_labels()
    assert validate_labels(labels, {"s1", "s2"}, "abc") == []
    counts = label_counts(labels)
    assert counts == dict(marks=4, picked_marks=2, picked_unique=1, picked_duplicates=1, no_outline_fits=1,
                          no_containing_structure=1, more_than_one_containing=2)


def test_invalid_labels_are_reported_and_never_repaired():
    assert "structures_enumeration_changed" in validate_labels(good_labels(sha="zzz"), {"s1"}, "abc")
    assert "schema_mismatch" in validate_labels(dict(good_labels(), schema="other"), {"s1"}, "abc")
    unknown = good_labels(marks=[{"outcome": OUTCOME_PICKED, "picked": "ghost", "containing_count": 1}])
    assert validate_labels(unknown, {"s1"}, "abc") == ["mark_0_picked_id_not_in_enumeration"]
    carrying = good_labels(marks=[{"outcome": OUTCOME_NO_OUTLINE_FITS, "picked": "s1", "containing_count": 1}])
    assert validate_labels(carrying, {"s1"}, "abc") == ["mark_0_unpicked_outcome_carries_an_id"]
    odd = good_labels(marks=[{"outcome": "maybe", "picked": None, "containing_count": 0}])
    assert validate_labels(odd, {"s1"}, "abc") == ["mark_0_unknown_outcome"]
    assert validate_labels({"schema": SCHEMA, "structures_sha256": "abc"}, {"s1"}, "abc") == ["marks_missing"]


def test_picked_ids_are_unique_and_independent_of_click_order():
    one = good_labels(marks=[{"outcome": OUTCOME_PICKED, "picked": p, "containing_count": 1} for p in ("s3", "s1", "s2", "s1")])
    two = good_labels(marks=[{"outcome": OUTCOME_PICKED, "picked": p, "containing_count": 1} for p in ("s1", "s2", "s3")])
    assert picked_ids(one) == picked_ids(two) == ("s1", "s2", "s3")


def test_label_helpers_do_not_mutate_their_input():
    labels = good_labels()
    before = copy.deepcopy(labels)
    validate_labels(labels, {"s1"}, "abc")
    label_counts(labels)
    picked_ids(labels)
    assert labels == before


# ---------------------------------------------------------------- relations
def synthetic_rows():
    r1 = row([interior("before_all")],
             [face(0, 5, True), face(5, 0, True), face(3, 3, False), face(10, 1, True), face(9, 1, False), face(None, 3, True),
              face(2, 2, True, available=False)])
    r2 = row([interior("after_all")], [])
    r3 = row([interior("inside")], [])
    r4 = row([], [face(1, 1, True)])
    return [r1, r2, r3, r4, dict(anomaly="structure_not_reproduced_from_its_own_members")]


def test_relation_counts_follow_s3_definitions_exactly():
    s = summarise_rows(synthetic_rows())
    assert s["structures"] == 4 and s["anomalies"] == 1
    assert (s["with_interior"], s["r_a_true"]) == (3, 2)
    # R-B: (0,5) interior decisive, (5,0) wall decisive, (3,3) tie, (10,1) exactly the ratio so decisive, (9,1) undecided;
    # the line with no interior distance and the unavailable line are excluded
    assert (s["b_items"], s["b_decisive"], s["b_nearer_interior"], s["b_nearer_wall"], s["b_tie"]) == (5, 3, 1, 2, 1)
    assert s["b_structures"] == 1  # only the first row has interior ink and valid distances
    # R-C: available face lines 6 in the first row plus 1 in the last; same style among them 4 + 1
    assert (s["c_items"], s["c_same"]) == (7, 5)
    assert s["c_structures"] == 2  # the first and the last row each carry available face ink


def test_relation_counts_are_order_invariant_replayable_and_non_mutating():
    rows = synthetic_rows()
    before = copy.deepcopy(rows)
    first = summarise_rows(rows)
    assert summarise_rows(list(reversed(rows))) == first
    assert summarise_rows(rows) == first
    assert rows == before


def test_unavailable_interior_ink_removes_the_structure_from_r_a_not_from_r_c():
    r = row([interior("before_all", available=False)], [face(0, 9, True)])
    s = summarise_rows([r])
    assert s["with_interior"] == 0 and s["r_a_true"] == 0
    assert s["c_items"] == 1


# ---------------------------------------------------------------- decision rules (pre-registered A4)
def per_doc(*triples):
    """Each entry is (items, share, direction[, contributing structures]); structures default to ten."""
    return {"doc%d" % i: (t if len(t) == 4 else t + (10,)) for i, t in enumerate(triples)}


def test_fewer_than_two_qualifying_documents_is_inconclusive_never_a_separator():
    assert judge(per_doc((50, 1.0, "outside")))["verdict"] == "INCONCLUSIVE"
    assert judge(per_doc((50, 1.0, "outside"), (19, 1.0, "outside")))["verdict"] == "INCONCLUSIVE"
    assert judge({})["verdict"] == "INCONCLUSIVE"


def test_many_lines_from_a_few_structures_do_not_qualify_a_document():
    # 200 items but only four distinct structures: lines of one window are not a population
    few = per_doc((200, 1.0, "outside", 4), (200, 1.0, "outside", 4))
    assert judge(few)["verdict"] == "INCONCLUSIVE" and judge(few)["qualifying"] == []
    five = per_doc((200, 1.0, "outside", 5), (200, 1.0, "outside", 5))
    assert judge(five)["verdict"] == "CLEAN_SEPARATOR"


def test_two_documents_at_or_above_ninety_percent_in_one_direction_are_a_clean_separator():
    v = judge(per_doc((30, 0.95, "outside"), (20, 0.92, "outside")))
    assert v["verdict"] == "CLEAN_SEPARATOR" and v["qualifying"] == ["doc0", "doc1"]
    assert judge(per_doc((30, 0.90, "outside"), (20, 0.90, "outside")))["verdict"] == "CLEAN_SEPARATOR"


@pytest.mark.parametrize("triples", [
    ((30, 0.95, "nearer_interior"), (20, 0.95, "nearer_wall")),   # direction differs between qualifying documents
    ((30, 0.89, "outside"), (20, 0.95, "outside")),               # one document just below ninety percent
    ((30, 0.80, "outside"), (20, 0.99, "outside")),               # one document well below, wide spread
])
def test_look_alike_negatives_are_not_clean(triples):
    assert judge(per_doc(*triples))["verdict"] == "NOT_CLEAN"


def test_a_non_qualifying_document_is_ignored_not_averaged_in():
    # the third document has 19 items and a poor share: it does not qualify, so it neither blocks nor helps
    v = judge(per_doc((30, 0.95, "outside"), (20, 0.92, "outside"), (19, 0.10, "outside")))
    assert v["verdict"] == "CLEAN_SEPARATOR" and v["qualifying"] == ["doc0", "doc1"]
    # the 15 point spread rule is implied by the 90 percent rule for every share the relations can produce (0.9 to 1.0)


def test_decision_is_independent_of_document_order_and_replays():
    stats = {
        "a": dict(with_interior=40, r_a_true=38, b_items=100, b_structures=30, b_decisive=95, b_nearer_interior=60, b_nearer_wall=35, b_tie=0,
                  c_items=60, c_structures=30, c_same=57),
        "b": dict(with_interior=25, r_a_true=24, b_items=80, b_structures=20, b_decisive=75, b_nearer_interior=50, b_nearer_wall=25, b_tie=0,
                  c_items=50, c_structures=20, c_same=48),
    }
    forward = decide(stats)
    assert forward == decide(dict(reversed(list(stats.items())))) == decide(stats)
    assert forward["R-A"]["verdict"] == "CLEAN_SEPARATOR"
    assert forward["R-B"]["verdict"] == "CLEAN_SEPARATOR"
    assert forward["R-C"]["verdict"] == "CLEAN_SEPARATOR"


def test_decision_does_not_mutate_its_input():
    stats = {"a": dict(with_interior=1, r_a_true=1, b_items=0, b_structures=0, b_decisive=0, b_nearer_interior=0,
                       b_nearer_wall=0, b_tie=0, c_items=0, c_structures=0, c_same=0)}
    before = copy.deepcopy(stats)
    decide(stats)
    assert stats == before


# ---------------------------------------------------------------- viewer and privacy separation
def viewer(structures=None):
    return build_viewer_html(title="t <x> & y", image_data_url="data:image/png;base64,AAAA", image_size=(100, 50),
                             structures_px=structures or [S("s1", (1, 2, 3, 4))], document="doc", page=7,
                             structures_sha256="d1", render_sha256="r1")


def test_viewer_is_self_contained_with_no_network_or_external_resource():
    html = viewer()
    for forbidden in ("http://", "https://", "fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource", "importScripts",
                      "<link", "<iframe", "document.cookie", "<script src"):
        assert forbidden not in html, forbidden
    assert 'src="' not in html  # the only image is set by script from the embedded data URL
    assert "data:image/png;base64,AAAA" in html


def test_viewer_embeds_the_payload_and_escapes_the_title_and_script_breakouts():
    html = viewer([S("x</script><b>", (0, 0, 1, 1))])
    assert "</script><b>" not in html
    assert "t &lt;x&gt; &amp; y" in html
    payload = re.search(r"const P = (\{.*?\});\nconst COLORS", html, re.S).group(1).replace("<\\/", "</")
    data = json.loads(payload)
    assert data["document"] == "doc" and data["page"] == 7 and data["structures_sha256"] == "d1"
    assert data["structures"][0]["id"] == "x</script><b>"


def test_the_label_file_the_viewer_writes_carries_no_coordinates():
    html = viewer()
    out = re.search(r'const out = \{(.*?)\};', html, re.S).group(1)
    assert "cx" not in out and "cy" not in out and "bbox" not in out
    assert "outcome: m.outcome, picked: m.picked, containing_count: m.containing_count" in out


def test_the_tool_is_not_imported_by_any_production_module_and_the_core_imports_only_the_standard_library():
    import ast

    offenders = [p.name for p in REPO.glob("pb_*.py") if "item8_b" in p.read_text(encoding="utf-8", errors="ignore")]
    assert offenders == []
    tree = ast.parse((REPO / "tools" / "item8_b" / "b_core.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "json", "hashlib", "typing"}, imported


def test_enumerate_tool_protects_its_output_folder_before_writing_anything():
    source = (REPO / "tools" / "item8_b" / "b_enumerate.py").read_text(encoding="utf-8")
    assert source.index('".gitignore"') < source.index("enumerate_page(")
    assert '"*\\n"' in source
