"""Synthetic proof for the corner-terminated two-face reveal-stub host SHADOW.

Source-neutral: every scene is built from plain tuples in an opening frame and
then moved rigidly (rotate / mirror / translate / scale >= 1). No private
drawing, filename, project name or expected quantity is read. The one test that
reads a private original is skipped when the PDF is absent.
"""
from __future__ import annotations

import copy
import hashlib
import math
import os
import random
from pathlib import Path

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_corner_terminated_host_shadow as shadow
from pb_opening_corner_terminated_host_shadow import (
    CornerFrame,
    DrawnPrimitive,
    FaceStub,
    OwnerRef,
    assess_corner_terminated_host_shadow,
    resolve_corner_terminated_stub_host_shadow,
)

T = 2.55          # host wall thickness
L = 42.8          # opening gap length
STUB_L = 2.7      # left (collinear-flank side) stub length
CORNER_OUT = 4.7  # right outer stub length (outer face)
S_A = L + CORNER_OUT          # outer corner point along the axis
S_B = S_A - T                 # inner corner point along the axis
H = T / 2.0
CANDIDATE = EvidenceResolutionStatus.CANDIDATE
ABSTAINED = EvidenceResolutionStatus.ABSTAINED
CONFLICT = EvidenceResolutionStatus.CONFLICT


class Scene:
    """Opening-frame scene plus a rigid page transform."""

    def __init__(self, *, flip_frame=False, theta=0.0, mirror=False, shift=(0.0, 0.0), scale=1.0):
        self.flip_frame = flip_frame
        self.theta, self.mirror, self.shift, self.scale = theta, mirror, shift, scale
        self.faces: list[FaceStub] = []
        self.drawn: list[DrawnPrimitive] = []
        self.owners: dict[str, OwnerRef] = {}

    # -- transform -----------------------------------------------------------
    def pt(self, s, n):
        if self.mirror:
            n = -n
        c, sn = math.cos(self.theta), math.sin(self.theta)
        x, y = s * c - n * sn, s * sn + n * c
        return (self.scale * x + self.shift[0], self.scale * y + self.shift[1])

    def line(self, s0, n0, s1, n1):
        a, b = self.pt(s0, n0), self.pt(s1, n1)
        return (a[0], a[1], b[0], b[1])

    def frame(self) -> CornerFrame:
        """Opening frame. ``flip_frame`` starts at the other jamb with the axis reversed
        (real openings can have either axis sign), which swaps left and right."""
        o = self.pt(0.0, 0.0)
        e = self.pt(1.0, 0.0)
        ax = ((e[0] - o[0]) / self.scale, (e[1] - o[1]) / self.scale)
        if self.flip_frame:
            o = self.pt(L, 0.0)
            ax = (-ax[0], -ax[1])
        nv = (-ax[1], ax[0])
        return CornerFrame(origin=o, axis=ax, normal=nv, length=self.scale * L, thickness=self.scale * T)

    # -- population ----------------------------------------------------------
    def owner(self, name, group=None, *, clean=True, near=None):
        pts = (self.pt(*near), self.pt(near[0] - 1.0, near[1])) if near is not None else (
            self.pt(500.0, 500.0), self.pt(501.0, 500.0))
        self.owners[name] = OwnerRef(name, tuple(group or (name,)), clean, pts)
        return self.owners[name]

    def prim(self, pid, s0, n0, s1, n1, *owner_names):
        self.drawn.append(DrawnPrimitive(pid, self.line(s0, n0, s1, n1), tuple(self.owners[n] for n in owner_names)))

    def stub(self, pid, s0, n0, s1, n1):
        self.faces.append(FaceStub(pid, self.line(s0, n0, s1, n1)))


def base_scene(**kw) -> Scene:
    sc = Scene(**kw)
    # opening support: 4 face stubs (jamb lines are not needed by the core)
    sc.stub("sL-", 0.0, -H, -STUB_L, -H)
    sc.stub("sL+", 0.0, H, -STUB_L, H)
    sc.stub("sR-", L, -H, S_A, -H)
    sc.stub("sR+", L, H, S_B, H)
    # collinear flank (left) owners
    sc.owner("flankN", near=(-STUB_L, -H))
    sc.owner("flankS", near=(-STUB_L, H))
    sc.owner("flankS_far")  # same raw line, a piece far away: must not count
    sc.prim("fN", -STUB_L, -H, -30.0, -H, "flankN")
    sc.prim("fS", S_B, H, -400.0, H, "flankS", "flankS_far")  # through line containing the stub end
    # corner terminator: mitre + two perpendicular faces (+ a duplicate overlapping one)
    sc.owner("mitreW")
    sc.owner("perpA")
    sc.owner("perpB")
    sc.owner("perpB2")
    sc.prim("mit", S_A, -H, S_B, H, "mitreW")
    sc.prim("pA", S_A, -H, S_A, 12.0, "perpA")
    sc.prim("pB", S_B, H, S_B, 12.0, "perpB")
    sc.prim("pB2", S_B, H, S_B, 47.0, "perpB2")
    return sc


def run(sc: Scene, are_ambiguous=lambda a, b: False):
    return resolve_corner_terminated_stub_host_shadow(sc.frame(), sc.faces, sc.drawn, are_ambiguous)


def summary(r):
    return (r.status, r.reason_codes, r.host_member_ids, r.terminator_witness_ids, r.mitre_primitive_ids,
            r.terminator_primitive_ids)


def assert_positive(r):
    assert r.status is CANDIDATE, r.reason_codes
    assert r.reason_codes == (shadow.CORNER_HOST_CANDIDATE,)
    assert set(r.host_member_ids) == {"flankN", "flankS"}
    assert set(r.terminator_witness_ids) == {"mitreW", "perpA", "perpB", "perpB2"}
    assert not set(r.host_member_ids) & set(r.terminator_witness_ids)
    assert r.mitre_primitive_ids == ("mit",)


# ------------------------------------------------------------------ positives

def test_synthetic_corner_terminated_stub_host_is_a_shadow_candidate():
    r = run(base_scene())
    assert_positive(r)
    assert r.collinear_side == "left"
    assert r.perpendicular_thickness_pt == pytest.approx(T, abs=1e-6)
    assert r.status is not EvidenceResolutionStatus.CORROBORATED


@pytest.mark.parametrize("theta_deg", [0, 90, 180, 270, 37.0])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("flip_frame", [False, True])
def test_rotation_mirror_and_flank_side_metamorphic(theta_deg, mirror, flip_frame):
    r = run(base_scene(theta=math.radians(theta_deg), mirror=mirror, flip_frame=flip_frame))
    assert_positive(r)
    assert r.collinear_side == ("right" if flip_frame else "left")


@pytest.mark.parametrize("shift", [(0.0, 0.0), (123.4, -77.7), (5000.0, 9000.0)])
@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
def test_translation_and_scale_metamorphic(shift, scale):
    r = run(base_scene(shift=shift, scale=scale, theta=math.radians(23.0)))
    assert_positive(r)
    assert r.perpendicular_thickness_pt == pytest.approx(T * scale, abs=1e-4)


def test_input_order_invariance_and_stable_ids():
    sc = base_scene(theta=math.radians(11.0))
    reference = run(sc)
    for seed in range(8):
        rng = random.Random(seed)
        faces, drawn = list(sc.faces), list(sc.drawn)
        rng.shuffle(faces)
        rng.shuffle(drawn)
        other = resolve_corner_terminated_stub_host_shadow(sc.frame(), faces, drawn)
        assert other == reference
        assert other.result_id == reference.result_id


def test_segment_splitting_invariance():
    sc = base_scene(theta=math.radians(7.0))
    reference = run(sc)

    def split(prim, frac):
        x0, y0, x1, y1 = prim.line
        mx, my = x0 + frac * (x1 - x0), y0 + frac * (y1 - y0)
        return [DrawnPrimitive(prim.primitive_id + "a", (x0, y0, mx, my), prim.owners),
                DrawnPrimitive(prim.primitive_id + "b", (mx, my, x1, y1), prim.owners)]

    drawn = []
    for p in sc.drawn:
        drawn.extend(split(p, 0.5) if p.primitive_id in {"pA", "pB", "pB2", "fN"} else [p])
    other = resolve_corner_terminated_stub_host_shadow(sc.frame(), sc.faces, drawn)
    assert other.status is CANDIDATE
    assert other.host_member_ids == reference.host_member_ids
    assert other.terminator_witness_ids == reference.terminator_witness_ids


def test_unrelated_content_and_viewport_expansion_invariance():
    sc = base_scene(theta=math.radians(3.0))
    reference = run(sc)
    extra = []
    rng = random.Random(5)
    far = Scene(theta=sc.theta)  # reuse transform only
    other_owner = OwnerRef("elsewhere", ("elsewhere",), True, ((9000.0, 9000.0), (9001.0, 9000.0)))
    for i in range(300):
        x, y = rng.uniform(2000, 9000), rng.uniform(2000, 9000)
        extra.append(DrawnPrimitive(f"far{i}", (x, y, x + rng.uniform(1, 40), y + rng.uniform(-3, 3)), (other_owner,)))
    # a far collinear line on the very same support line: not touching, must not matter
    extra.append(DrawnPrimitive("farcollinear", sc.line(-900.0, H, -700.0, H), (other_owner,)))
    del far
    other = resolve_corner_terminated_stub_host_shadow(sc.frame(), sc.faces, list(sc.drawn) + extra)
    assert other == reference


def test_deterministic_replay_and_no_mutation():
    sc = base_scene(theta=math.radians(19.0), shift=(10.0, 20.0))
    faces0, drawn0, frame0 = copy.deepcopy(sc.faces), copy.deepcopy(sc.drawn), copy.deepcopy(sc.frame())
    first = resolve_corner_terminated_stub_host_shadow(sc.frame(), sc.faces, sc.drawn)
    second = resolve_corner_terminated_stub_host_shadow(sc.frame(), sc.faces, sc.drawn)
    assert first == second and first.result_id == second.result_id
    assert sc.faces == faces0 and sc.drawn == drawn0 and sc.frame() == frame0
    assert isinstance(first.result_id, str) and len(first.result_id) > 16
    # the id depends on the evidence it summarises
    sc2 = base_scene(theta=math.radians(19.0), shift=(10.0, 20.0))
    sc2.owners["perpB"] = OwnerRef("perpB_other", ("perpB_other",), True, sc2.owners["perpB"].centerline_pts)
    sc2.drawn = [DrawnPrimitive(p.primitive_id, p.line,
                                tuple(sc2.owners["perpB"] if o.wall_candidate_id == "perpB" else o for o in p.owners))
                 for p in sc2.drawn]
    assert resolve_corner_terminated_stub_host_shadow(sc2.frame(), sc2.faces, sc2.drawn).result_id != first.result_id


# ------------------------------------------------------------ look-alike negatives

def _drop(sc: Scene, *ids):
    sc.drawn = [p for p in sc.drawn if p.primitive_id not in ids]
    return sc


def test_missing_mitre_abstains():
    r = run(_drop(base_scene(), "mit"))
    assert r.status is ABSTAINED and r.reason_codes == (shadow.MITRE_NOT_DRAWN,)


def test_unowned_furniture_dimension_or_joinery_look_alike_is_not_wall_evidence():
    # The perpendicular faces exist as ink, but no W4 candidate owns them
    # (furniture / dimension tick / joinery): they are absent from the wall-owned population.
    r = run(_drop(base_scene(), "pA", "pB", "pB2"))
    assert r.status is ABSTAINED and r.reason_codes == (shadow.PERPENDICULAR_NOT_DRAWN,)


def test_detached_pier_never_connects():
    sc = base_scene()
    sc.drawn = [p for p in sc.drawn if p.primitive_id not in {"pA", "pB", "pB2"}]
    sc.owner("detA"), sc.owner("detB")
    sc.prim("pA", S_A, -H + 0.5, S_A, 12.0, "detA")   # starts 0.5 pt short of the drawn corner
    sc.prim("pB", S_B, H + 0.5, S_B, 12.0, "detB")
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.PERPENDICULAR_NOT_DRAWN,)


def test_wrong_thickness_perpendicular_wall_abstains():
    sc = Scene()
    wide = 1.6 * T
    sc.stub("sL-", 0.0, -H, -STUB_L, -H)
    sc.stub("sL+", 0.0, H, -STUB_L, H)
    sc.stub("sR-", L, -H, S_A, -H)
    sc.stub("sR+", L, H, S_A - wide, H)
    for n in ("flankN", "flankS", "mitreW", "perpA", "perpB"):
        sc.owner(n, near=(-STUB_L, -H if n == "flankN" else H) if n.startswith("flank") else None)
    sc.prim("fN", -STUB_L, -H, -30.0, -H, "flankN")
    sc.prim("fS", -STUB_L, H, -30.0, H, "flankS")
    sc.prim("mit", S_A, -H, S_A - wide, H, "mitreW")
    sc.prim("pA", S_A, -H, S_A, 12.0, "perpA")
    sc.prim("pB", S_A - wide, H, S_A - wide, 12.0, "perpB")
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.THICKNESS_MISMATCH,)


def test_collinear_continuation_at_the_corner_abstains():
    sc = base_scene()
    sc.owner("cont")
    sc.prim("cont", S_A, -H, S_A + 20.0, -H, "cont")
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.COLLINEAR_CONTINUATION,)


def test_perpendicular_wall_that_passes_through_is_not_a_corner():
    sc = base_scene()
    sc.owner("tee")
    sc.drawn = [p for p in sc.drawn if p.primitive_id != "pA"]
    sc.prim("pA", S_A, -12.0, S_A, 12.0, "tee")   # passes through the stub end
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.PERPENDICULAR_THROUGH,)


def test_two_terminators_conflict():
    sc = base_scene()
    sc.owner("second")
    sc.prim("pA_up", S_A, -H, S_A, -12.0, "second")   # a wall-owned face going the other way from the same end
    r = run(sc)
    assert r.status is CONFLICT and r.reason_codes == (shadow.TERMINATOR_AMBIGUOUS,)


def test_unexplained_wall_owned_contact_abstains():
    sc = base_scene()
    sc.owner("diag")
    sc.prim("odd", S_A, -H, S_A + 6.0, -H + 3.0, "diag")  # neither mitre, perpendicular nor collinear
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.UNEXPLAINED_CONTACT,)


def test_inverted_stagger_abstains():
    # Perpendicular wall goes toward +normal but the LONGER stub is on the + face.
    sc = Scene()
    sc.stub("sL-", 0.0, -H, -STUB_L, -H)
    sc.stub("sL+", 0.0, H, -STUB_L, H)
    sc.stub("sR-", L, -H, S_B, -H)
    sc.stub("sR+", L, H, S_A, H)
    for n in ("flankN", "flankS", "mitreW", "perpA", "perpB"):
        sc.owner(n, near=(-STUB_L, -H if n == "flankN" else H) if n.startswith("flank") else None)
    sc.prim("fN", -STUB_L, -H, -30.0, -H, "flankN")
    sc.prim("fS", -STUB_L, H, -30.0, H, "flankS")
    sc.prim("mit", S_B, -H, S_A, H, "mitreW")
    sc.prim("pA", S_B, -H, S_B, 12.0, "perpA")
    sc.prim("pB", S_A, H, S_A, 12.0, "perpB")
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.STAGGER_INCONSISTENT,)


def test_symmetric_opening_without_a_corner_is_not_this_pattern():
    sc = Scene()
    for pid, args in (("a", (0.0, -H, -STUB_L, -H)), ("b", (0.0, H, -STUB_L, H)),
                      ("c", (L, -H, L + STUB_L, -H)), ("d", (L, H, L + STUB_L, H))):
        sc.stub(pid, *args)
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.STUBS_NOT_STAGGERED,)


def test_faces_that_are_not_two_clean_pairs_are_unsupported():
    sc = base_scene()
    sc.faces = sc.faces[:3]
    assert run(sc).reason_codes == (shadow.FACES_UNSUPPORTED,)


# --------------------------------------------- stale / foreign / ambiguous evidence

def _replace_owner(sc: Scene, name, **changes):
    old = sc.owners[name]
    new = OwnerRef(old.wall_candidate_id, changes.get("group", old.equivalence_group),
                   changes.get("clean", old.clean), changes.get("pts", old.centerline_pts))
    sc.owners[name] = new
    sc.drawn = [DrawnPrimitive(p.primitive_id, p.line, tuple(new if o.wall_candidate_id == name else o for o in p.owners))
                for p in sc.drawn]


def test_unclean_terminator_evidence_abstains():
    sc = base_scene()
    _replace_owner(sc, "perpA", clean=False)
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.TERMINATOR_NOT_CLEAN,)


def test_unclean_collinear_flank_evidence_abstains():
    sc = base_scene()
    _replace_owner(sc, "flankN", clean=False)
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.FLANK_NOT_CLEAN,)


def test_flank_owned_only_by_a_far_piece_is_unmapped():
    sc = base_scene()
    far = sc.owners["flankN"]
    _replace_owner(sc, "flankN", pts=((900.0, 900.0), (901.0, 900.0)))
    assert far.centerline_pts != sc.owners["flankN"].centerline_pts
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.FLANK_UNMAPPED,)


def test_local_owner_reach_uses_the_existing_gap_snap_unchanged():
    # 2.4 pt away is within the existing 2.5 pt W4 gap snap, 2.6 pt is not.
    for gap, expected in ((2.4, CANDIDATE), (2.6, ABSTAINED)):
        sc = base_scene()
        _replace_owner(sc, "flankN", pts=(sc.pt(-STUB_L - gap, -H - 0.0), sc.pt(-STUB_L - gap - 1.0, -H - 0.0)))
        # owner polyline lies on the flank line, `gap` pt beyond the stub end
        assert run(sc).status is expected


def test_two_local_flank_owners_in_different_groups_conflict():
    sc = base_scene()
    sc.owner("flankN2", group=("other_group",), near=(-STUB_L, -H))
    sc.drawn = [DrawnPrimitive(p.primitive_id, p.line, p.owners + ((sc.owners["flankN2"],) if p.primitive_id == "fN" else ()))
                for p in sc.drawn]
    r = run(sc)
    assert r.status is CONFLICT and r.reason_codes == (shadow.FLANK_AMBIGUOUS,)


def test_pairwise_ambiguous_flank_owners_conflict():
    sc = base_scene()
    sc.owner("flankN2", group=("flankN",), near=(-STUB_L, -H))
    sc.drawn = [DrawnPrimitive(p.primitive_id, p.line, p.owners + ((sc.owners["flankN2"],) if p.primitive_id == "fN" else ()))
                for p in sc.drawn]
    r = run(sc, are_ambiguous=lambda a, b: {a, b} == {"flankN", "flankN2"})
    assert r.status is CONFLICT and r.reason_codes == (shadow.FLANK_AMBIGUOUS,)


def test_terminator_may_not_overlap_the_host_lineage():
    sc = base_scene()
    sc.drawn = [DrawnPrimitive(p.primitive_id, p.line, p.owners + ((sc.owners["flankN"],) if p.primitive_id == "pA" else ()))
                for p in sc.drawn]
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.TERMINATOR_OVERLAPS_HOST,)


def test_no_collinear_flank_on_either_side_abstains():
    sc = base_scene()
    _drop(sc, "fN", "fS")
    r = run(sc)
    assert r.status is ABSTAINED and r.reason_codes == (shadow.FLANK_UNMAPPED,)


# ------------------------------------------------------------ default-off / isolation

def test_adapter_is_default_off_and_strictly_boolean():
    sentinel = object()  # would raise AttributeError if touched
    assert assess_corner_terminated_host_shadow(sentinel) == ()
    assert assess_corner_terminated_host_shadow(sentinel, enabled=False) == ()
    for bad in (1, "yes", None, 0):
        with pytest.raises(TypeError):
            assess_corner_terminated_host_shadow(sentinel, enabled=bad)


def test_no_production_module_imports_the_shadow():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.glob("*.py"):
        if path.name == "pb_opening_corner_terminated_host_shadow.py":
            continue
        if "pb_opening_corner_terminated_host_shadow" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(path.name)
    assert offenders == []


def test_module_carries_no_project_or_id_special_cases():
    text = Path(shadow.__file__).read_text(encoding="utf-8").lower()
    for token in ("3laurel", "lot16", "maryborough", "b5091e15", "reference_takeoff", "boq"):
        assert token not in text, token


# ------------------------------------------------------------------ original source

ORIGINAL_SHA256 = "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e"


def _original_pdf() -> Path | None:
    env = os.environ.get("PLANREADER_3LAUREL_ORIGINAL_PDF")
    candidates = [Path(env)] if env else []
    candidates.append(Path("documents/sources/3LAUREL - Construction Plan Set Rev3 08.05.26.pdf"))
    for path in candidates:
        if path.exists():
            return path
    return None


def test_original_source_shadow_is_read_only_and_finds_the_corner_slider():
    path = _original_pdf()
    if path is None:
        pytest.skip("private original PDF not available")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != ORIGINAL_SHA256:
        pytest.skip("original PDF hash differs")
    from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
        raster_paired_outer_faces_shadow=True,
    )
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{ORIGINAL_SHA256[:32]}", source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf", page_ids=(3,),
    )
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=initial.revision.revision_id, page_ids=("3",),
        include_unmeasured_ink_closed_flanks_shadow=True, source_fragment_roles_shadow=True,
    )

    def snap():
        return [(b.opening_identity_id, b.status.value, tuple(b.reason_codes), b.host_wall_id, b.record_id)
                for b in comp.opening_bindings]

    before = snap()
    assert assess_corner_terminated_host_shadow(comp) == ()
    assert snap() == before
    records = assess_corner_terminated_host_shadow(comp, enabled=True)
    assert snap() == before                       # nothing written back
    assert records == assess_corner_terminated_host_shadow(comp, enabled=True)   # deterministic
    assert len(records) > 50
    assert all(r.binding_status != "corroborated" for r in records)   # only non-hosted openings are assessed
    candidates = [r for r in records if r.result.is_candidate]
    assert [r.opening_identity_id[-8:] for r in candidates] == ["b5091e15"]
    only = candidates[0].result
    assert only.status is not EvidenceResolutionStatus.CORROBORATED
    assert only.host_member_ids and only.terminator_witness_ids
    assert not set(only.host_member_ids) & set(only.terminator_witness_ids)
    assert candidates[0].first_remaining_gate == shadow.PROMOTION_GATE
