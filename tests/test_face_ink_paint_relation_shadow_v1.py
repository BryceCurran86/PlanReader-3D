"""S2b (owner directive 2026-11-02): how the ink on and across a wall face is painted, relative to the wall's own lines.

Real producer and authority, ink drawn in a controlled paint order, every relation checked against what PyMuPDF itself
reports. The shadow decides nothing: no role, no polarity, no veto released, every competing structure retained."""
from __future__ import annotations

import ast
import re
from dataclasses import replace
from pathlib import Path

import fitz
import pytest

import pb_face_ink_paint_relation_shadow as shadow
from pb_face_ink_paint_relation_shadow import (
    FACE_INK_ROLE_UNRESOLVED,
    INVENTORY_NOT_AVAILABLE,
    PAINT_FACT_INTEGRITY_FAILURE,
    PAINT_FACT_UNAVAILABLE,
    FaceInkPaintRelationAudit,
    relate_face_ink_to_paint,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from test_physical_opening_seeded_existence_review_v1 import POSES
from test_physical_opening_seeded_existence_v1 import LAYERED, PLAIN, _transform

REPO = Path(__file__).resolve().parent.parent
MODULE = "pb_face_ink_paint_relation_shadow"
SOURCE = REPO / f"{MODULE}.py"
CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED

WALL = dict(color=(0.0, 0.0, 0.0), width=0.48)
RED = dict(color=(1.0, 0.0, 0.0), width=0.24)
TRANSPARENT = dict(color=(0.0, 0.0, 0.0), width=0.48, stroke_opacity=0.0)

CLOSE_B = (((100.0, 110.0), (140.0, 110.0)), WALL)             # spans the gap on B's outer face, painted right after the wall
THROUGH_B = (((60.0, 110.0), (180.0, 110.0)), WALL)            # runs on past both jambs, painted much later
STUB_A = (((112.0, 100.0), (128.0, 100.0)), RED)               # an interior stub on A's outer face, thin red, painted last
MID = (((100.0, 105.0), (140.0, 105.0)), TRANSPARENT)          # spans the shared face, fully transparent
GLAZE = [(((104.0, 102.0), (136.0, 102.0)), WALL), (((104.0, 108.0), (136.0, 108.0)), WALL)]
FILL_RECT = ((104.0, 100.0), (136.0, 106.0))


def _wall(segments):
    return [(seg, WALL) for seg in segments]


SCENE = _wall(LAYERED) + [CLOSE_B] + GLAZE + [THROUGH_B, MID, STUB_A]


def _build(scene, *, fill_rect=None, **kw):
    kw = {"angle_deg": 0.0, "scale": 1.0, "offset": (0.0, 0.0), **kw}
    doc = fitz.open()
    page = doc.new_page(width=700, height=700)
    for (first, second), style in scene:
        a, b = _transform(first, **kw), _transform(second, **kw)
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=style["color"], width=style["width"],
                       stroke_opacity=style.get("stroke_opacity", 1.0))
    if fill_rect is not None:
        a, b = _transform(fill_rect[0], **kw), _transform(fill_rect[1], **kw)
        page.draw_rect(fitz.Rect(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])),
                       color=None, fill=(1, 1, 1))
    data = doc.tobytes()
    doc.close()
    producer = SourceVisibilityProducer(producer_method="face-ink-relation-test", producer_version="1.0")
    published = producer.ingest_native_pdf_bytes(
        document_id="face-ink-relation-doc", source_bytes=data, source_locator="memory://face-ink-relation.pdf")
    by_geometry = {}
    for observation_id, record in producer.authority().authenticated_visible_observations(published):
        g = record.geometry
        by_geometry[frozenset(((round(g[0], 2), round(g[1], 2)), (round(g[2], 2), round(g[3], 2))))] = observation_id

    def ids(segments):
        out = []
        for first, second in segments:
            a, b = _transform(first, **kw), _transform(second, **kw)
            out.append(by_geometry[frozenset(((round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2))))])
        return out

    def selector(observation_id):
        return ObservationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id)

    return producer, producer.physical_opening_authority(), data, ids, selector


def _audit(scene, *, strip=(), fill_rect=None, **kw):
    producer, physical, data, ids, selector = _build(scene, fill_rect=fill_rect, **kw)
    members = ids(LAYERED)
    result = FaceInkPaintRelationAudit(physical, producer, enabled=True).audit(
        selector(members[6]), members, strip_ink_ids=ids(strip) if strip else ())
    return producer, physical, data, ids, selector, members, result


def _by(result, observation_id):
    return [r for r in result.relations if r.observation_id == observation_id]


def test_relations_are_exact_paint_measures_checked_against_the_pdf_itself():
    producer, physical, data, ids, selector, members, result = _audit(SCENE, strip=[g[0] for g in GLAZE])
    assert result.status is CAND and result.reason_codes == (FACE_INK_ROLE_UNRESOLVED,)
    with fitz.open(stream=data, filetype="pdf") as pdf:
        seq = {i: d["seqno"] for i, d in enumerate(pdf[0].get_drawings())}
    # SCENE draws in this order: 10 wall lines, CLOSE_B, two glazing lines, THROUGH_B, MID, STUB_A
    close, through, mid, stub = (ids([s[0]])[0] for s in (CLOSE_B, THROUGH_B, MID, STUB_A))
    glaze = ids([g[0] for g in GLAZE])
    order = [m for m in ids(LAYERED)] + [close] + glaze + [through, mid, stub]
    facts = {f.observation_id: f for f in producer.native_paint_facts(selector(members[6]), observation_ids=order)}
    assert [facts[o].sequence_number for o in order] == [seq[i] for i in range(len(order))]

    (closing,) = [r for r in _by(result, close) if r.structure_status == "survivor"]
    assert (closing.kind, closing.extent_class, closing.locality) == ("face_ink", "at_at", "opening_local")
    assert closing.same_style_as_face_member_ids and closing.paint_order_among_face_members == "after_all"
    face_pieces = [m for m in members if m in closing.same_style_as_face_member_ids]
    assert closing.nearest_face_member_sequence_distance == facts[close].sequence_number - max(
        facts[m].sequence_number for m in ids(LAYERED)[:6])
    assert not closing.unstroked_fill_boundary and closing.stroke_opacity == 1.0 and face_pieces

    (run_on,) = _by(result, through)
    assert (run_on.extent_class, run_on.locality) == ("beyond_beyond", "extends_past_both_jambs")
    assert run_on.same_style_as_face_member_ids and run_on.nearest_face_member_sequence_distance > closing.nearest_face_member_sequence_distance

    (red,) = _by(result, stub)
    assert (red.extent_class, red.structure_status, red.stroke_color) == ("within_within", "set_aside", (1.0, 0.0, 0.0))
    assert red.same_style_as_face_member_ids == () and red.paint_order_among_face_members == "after_all"

    both = _by(result, mid)
    assert len(both) == 2 and {r.structure_status for r in both} == {"set_aside", "survivor"}     # kept for each structure
    assert all(r.stroke_is_transparent and not r.stroke_is_partially_transparent and r.stroke_opacity == 0.0 for r in both)


def test_strip_ink_is_located_in_the_paint_order_without_a_threshold():
    producer, physical, data, ids, selector, members, result = _audit(SCENE, strip=[g[0] for g in GLAZE])
    glaze = ids([g[0] for g in GLAZE])
    for observation_id in glaze:
        rows = _by(result, observation_id)
        assert rows and all(r.in_strip_ink and r.nearest_strip_ink_sequence_distance in (0, 1) for r in rows)
        assert all(r.kind == "interior_ink" and r.extent_class is None and r.locality is None for r in rows)
    close = ids([CLOSE_B[0]])[0]
    assert all(r.nearest_strip_ink_sequence_distance == 1 and not r.in_strip_ink for r in _by(result, close))
    (without,) = [_audit(SCENE)[-1]]
    assert all(r.nearest_strip_ink_sequence_distance is None for r in without.relations)


def test_every_competing_structure_and_the_shared_support_are_retained():
    producer, physical, data, ids, selector, members, result = _audit(SCENE)
    assert len(result.structure_ids) == 2
    assert {r.structure_id for r in result.relations} == set(result.structure_ids)
    assert {r.structure_status for r in result.relations} == {"set_aside", "survivor"}
    face_pieces_105 = ids(LAYERED)[2:4]
    assert set(result.shared_support_ids) == set(face_pieces_105)


def test_an_unstroked_fill_boundary_is_reported_as_such():
    producer, physical, data, ids, selector = _build(_wall(PLAIN), fill_rect=FILL_RECT)
    members = ids(PLAIN)
    result = FaceInkPaintRelationAudit(physical, producer, enabled=True).audit(selector(members[4]), members)
    assert result.relations and all(r.paint_fact_available for r in result.relations)
    edges = [r for r in result.relations if r.unstroked_fill_boundary]
    assert len(edges) == len(result.relations) == 4 and {r.stroke_color for r in edges} == {None}
    assert {r.kind for r in edges} == {"face_ink", "interior_ink"}
    assert not any(r.stroke_is_transparent or r.stroke_is_partially_transparent for r in edges)


@pytest.mark.parametrize("kw", POSES)
def test_the_relations_survive_translation_scale_rotation_and_reflection(kw):
    def signature(result):
        return sorted((r.kind, r.extent_class, r.locality, r.structure_status, len(r.same_style_as_face_member_ids),
                       r.paint_order_among_face_members, r.nearest_face_member_sequence_distance,
                       r.nearest_strip_ink_sequence_distance, r.in_strip_ink, r.stroke_color, r.stroke_opacity,
                       r.stroke_is_transparent) for r in result.relations)

    base = _audit(SCENE, strip=[g[0] for g in GLAZE])[-1]
    other = _audit(SCENE, strip=[g[0] for g in GLAZE], **kw)[-1]
    assert signature(other) == signature(base)
    assert len(other.shared_support_ids) == len(base.shared_support_ids) == 2


def test_order_repetition_replay_and_no_role_polarity_or_grant():
    producer, physical, data, ids, selector = _build(SCENE)[:1] + _build(SCENE)[1:]
    members = ids(LAYERED)
    audit = FaceInkPaintRelationAudit(physical, producer, enabled=True)
    first = audit.audit(selector(members[6]), members)
    assert audit.audit(selector(members[6]), list(reversed(members))) == first
    assert audit.audit(selector(members[6]), tuple(members) + tuple(members)) == first
    assert audit.audit(selector(members[6]), members) == first
    assert not (first.decides_existence or first.decides_role or first.releases_veto or first.grants_quantity
                or first.grants_firm_authority or first.publishes_atoms_to_live_path)
    with pytest.raises(ValueError):
        replace(first, releases_veto=True)
    atoms = first.to_atoms()
    assert len(atoms) == len(first.relations) and len({a.evidence_id for a in atoms}) == len(atoms)
    assert all(a.status is CAND and a.kind == "unknown" and a.metadata["polarity"] == "unknown"
               and a.reason_codes == (FACE_INK_ROLE_UNRESOLVED,) for a in atoms)
    assert atoms == first.to_atoms()


def test_a_missing_paint_fact_is_reported_not_guessed():
    producer, physical, data, ids, selector = _build(SCENE)
    members = ids(LAYERED)
    inventory = physical.seeded_face_ink_inventory(selector(members[6]), members)
    needed = set(members)
    for structure in inventory.structures:
        needed |= {i.observation_id for i in structure.face_ink} | set(structure.interior_ink_ids)
    facts = producer.native_paint_facts(selector(members[6]), observation_ids=tuple(sorted(needed)))
    victim = ids([CLOSE_B[0]])[0]
    partial = relate_face_ink_to_paint(inventory, [f for f in facts if f.observation_id != victim])
    assert partial.status is ABST and partial.unresolved_observation_ids == (victim,)
    assert PAINT_FACT_UNAVAILABLE in partial.reason_codes
    (row,) = _by(partial, victim)
    assert not row.paint_fact_available and row.sequence_number is None and row.same_style_as_face_member_ids == ()
    assert row.reason_codes == (PAINT_FACT_UNAVAILABLE,)
    assert all(r.paint_fact_available for r in partial.relations if r.observation_id != victim)


def test_failures_and_the_default_are_closed():
    producer, physical, data, ids, selector = _build(SCENE)
    members = ids(LAYERED)
    off = FaceInkPaintRelationAudit(physical, producer).audit(selector(members[6]), members)
    assert off.status is ABST and off.relations == () and off.reason_codes == ("face_ink_paint_relation_shadow_disabled",)

    class Damaged:
        def native_paint_facts(self, *_a, **_k):
            raise RuntimeError("producer integrity failure")

    damaged = FaceInkPaintRelationAudit(physical, Damaged(), enabled=True).audit(selector(members[6]), members)
    assert damaged.status is ABST and damaged.reason_codes == (PAINT_FACT_INTEGRITY_FAILURE,) and damaged.relations == ()

    nothing = FaceInkPaintRelationAudit(physical, producer, enabled=True).audit(selector(members[6]), members[:3])
    assert nothing.status is ABST and nothing.reason_codes == (INVENTORY_NOT_AVAILABLE,) and nothing.relations == ()


def test_nothing_in_production_imports_the_shadow_and_it_imports_no_authority_issuer_or_binder():
    importers = []
    for root in ("", "tools", "scripts"):
        for path in sorted((REPO / root).glob("*.py")):
            if path != SOURCE and re.search(rf"^\s*(?:from|import)\s+{MODULE}\b",
                                           path.read_text(encoding="utf-8", errors="replace"), re.M):
                importers.append(path.relative_to(REPO).as_posix())
    assert importers == []
    imports = set()
    for node in ast.walk(ast.parse(SOURCE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imports |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert imports <= {"__future__", "math", "dataclasses", "typing", "pb_migration_contracts",
                       "pb_wall_room_topology_typed_negative_evidence"}
    assert shadow.STANDING_LIMITS and "relations_are_exact_paint_measures_not_roles" in shadow.STANDING_LIMITS
