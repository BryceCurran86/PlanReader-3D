from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from random import Random

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_roof_eave_shadow import (
    RoofMaterialAnnotation,
    RoofPath,
    RoofSourceScope,
    collect_gable_outer_roof_edge,
    collect_longitudinal_roof_edge,
    extract_document_roof_surface_geometry_shadow,
    is_valid_roof_material_text,
    reconcile_roof_eave_geometry,
)


def _scope(viewport: str, page: int = 1, revision: str = "rev-1", doc: str = "doc-1", entity: str = "roof-1", sha: str | None = None) -> RoofSourceScope:
    return RoofSourceScope(doc, revision, sha or "0" * 64, page, viewport, entity)


def _long_paths(dx: float = 0, dy: float = 0, scale: float = 1, height: float = 35):
    def p(id, a, b, **kw):
        return RoofPath(id, tuple(scale * v + t for v, t in zip(a, (dx, dy))), tuple(scale * v + t for v, t in zip(b, (dx, dy))), **kw)
    return [
        p("roof-top", (20, 20), (180, 20)),
        p("roof-bottom", (20, 20 + height), (180, 20 + height)),
        p("roof-left", (20, 20), (20, 20 + height)),
        p("roof-right", (180, 20), (180, 20 + height)),
        p("dimension", (25, 95), (175, 95)),
        p("border-top", (1, 1), (199, 1), width_pt=0),
        p("border-bottom", (1, 110), (199, 110), width_pt=0),
        p("border-left", (1, 1), (1, 110), width_pt=0),
        p("border-right", (199, 1), (199, 110), width_pt=0),
    ]


def _long(paths=None, *, viewport="front", dy=0, scale=1, material=("corrugated roofing",), height=35):
    if paths is None:
        paths = [RoofPath(f"{viewport}:{p.path_id}", p.start, p.end, p.stroke, p.width_pt, p.dashes)
                 for p in _long_paths(dy=dy, scale=scale, height=height)]
    return collect_longitudinal_roof_edge(
        paths,
        scope=_scope(viewport),
        viewport_bbox=(0, 0 + dy, 200 * scale, 120 * scale + dy),
        page_width_pt=200 * scale,
        roof_material_annotations=tuple(RoofMaterialAnnotation(
            f"callout:{i}", text, _scope(viewport),
            (40 * scale, 10 * scale + dy, 90 * scale, 18 * scale + dy))
            for i, text in enumerate(material)),
    )


def _gable(paths=None, *, dx=0, dy=0, scale=1, material=("sheet roofing",), apex=None, left_y=65, right_y=65):
    def pt(x, y):
        return (x * scale + dx, y * scale + dy)
    paths = paths if paths is not None else [
        RoofPath("left-outer", pt(15, left_y), pt(100, 30)),
        RoofPath("right-outer", pt(100, 30), pt(185, right_y)),
        RoofPath("left-inner", pt(40, 55), pt(100, 30)),
        RoofPath("right-inner", pt(100, 30), pt(160, 55)),
        RoofPath("frame", pt(1, 110), pt(199, 110), width_pt=0),
    ]
    # atan(35/85) is about 22.38 degrees; inner segments also share it.
    return collect_gable_outer_roof_edge(
        paths, scope=_scope("gable"),
        viewport_bbox=(dx, dy, 200 * scale + dx, 120 * scale + dy),
        apex_xy=apex if apex is not None else pt(100, 30), pitch_deg=22.38,
        structural_left_x=40 * scale + dx, structural_right_x=160 * scale + dx,
        roof_material_annotations=tuple(RoofMaterialAnnotation(
            f"gable-callout:{i}", text, _scope("gable"),
            (40 * scale + dx, 5 * scale + dy, 90 * scale + dx, 18 * scale + dy))
            for i, text in enumerate(material)),
    )


def test_two_owned_long_elevations_and_gable_keep_native_geometry_only():
    front = _long(viewport="front", height=55.68)
    rear = _long(viewport="rear", dy=150, height=37.80)
    gable = replace(_gable(), left_drop_pt=55.56, right_drop_pt=38.16)
    assert (front.status, rear.status, gable.status) == (Status.CANDIDATE,) * 3
    assert front.span_pt == rear.span_pt == 160
    assert gable.span_pt == 170
    assert gable.left_drop_pt == 55.56
    assert gable.right_drop_pt == 38.16
    result = reconcile_roof_eave_geometry([front, rear], gable, pitch_deg=22.38)
    assert result.status is Status.CANDIDATE
    assert result.longitudinal_span_pt == 160
    assert result.transverse_span_pt == 170
    assert result.quantity_m2 is None
    assert len(result.path_ids) == 10
    assert result.physical_distinctness == "distinct_front_rear_eaves"


def test_provenance_ownership_validation():
    """Missing or malformed document, revision, SHA, entity, or target pages fails closed."""
    # RoofSourceScope validations
    with pytest.raises(ValueError, match="document, revision, viewport and entity ownership"):
        RoofSourceScope("", "rev-1", "0" * 64, 1, "vp-1", "entity-1")
    with pytest.raises(ValueError, match="document, revision, viewport and entity ownership"):
        RoofSourceScope("doc-1", "", "0" * 64, 1, "vp-1", "entity-1")
    with pytest.raises(ValueError, match="document, revision, viewport and entity ownership"):
        RoofSourceScope("doc-1", "rev-1", "0" * 64, 1, "vp-1", "")
    with pytest.raises(ValueError, match="64-char lower-case SHA-256"):
        RoofSourceScope("doc-1", "rev-1", "short-hash", 1, "vp-1", "entity-1")

    # Document-level wrapper validations
    dummy_doc = []
    res_no_doc = extract_document_roof_surface_geometry_shadow(
        dummy_doc, document_id="", revision_id="rev-1", source_sha256="0" * 64, entity_id="entity-1", target_pages=[0],
    )
    assert res_no_doc.status is Status.ABSTAINED
    assert "missing_document_id" in res_no_doc.reason_codes

    res_no_rev = extract_document_roof_surface_geometry_shadow(
        dummy_doc, document_id="doc-1", revision_id="", source_sha256="0" * 64, entity_id="entity-1", target_pages=[0],
    )
    assert res_no_rev.status is Status.ABSTAINED
    assert "missing_revision_id" in res_no_rev.reason_codes

    res_no_ent = extract_document_roof_surface_geometry_shadow(
        dummy_doc, document_id="doc-1", revision_id="rev-1", source_sha256="0" * 64, entity_id="", target_pages=[0],
    )
    assert res_no_ent.status is Status.ABSTAINED
    assert "missing_entity_id" in res_no_ent.reason_codes

    res_bad_sha = extract_document_roof_surface_geometry_shadow(
        dummy_doc, document_id="doc-1", revision_id="rev-1", source_sha256="invalid", entity_id="entity-1", target_pages=[0],
    )
    assert res_bad_sha.status is Status.ABSTAINED
    assert "invalid_source_sha256" in res_bad_sha.reason_codes

    res_no_pages = extract_document_roof_surface_geometry_shadow(
        dummy_doc, document_id="doc-1", revision_id="rev-1", source_sha256="0" * 64, entity_id="entity-1", target_pages=[],
    )
    assert res_no_pages.status is Status.ABSTAINED
    assert "missing_target_pages" in res_no_pages.reason_codes


def test_roof_material_negatives_rejected():
    """Negative non-roof annotations (damp proof, waterproof, proofing) must never authenticate roofing."""
    # Negative cases
    negatives = [
        "proof",
        "proofing",
        "damp proof",
        "damp proof course",
        "damp-proof membrane",
        "waterproof membrane",
        "fireproof",
        "sound-proof panel",
        "dpc",
    ]
    for neg in negatives:
        assert not is_valid_roof_material_text(neg), f"Expected '{neg}' to be rejected as roof material"
        res = _long(material=(neg,))
        assert res.status is Status.ABSTAINED

    # Positive cases
    positives = [
        "roof",
        "roofing",
        "corrugated roofing",
        "sheet roofing",
        "G.C.I roof covering not exceeding 30 degrees",
        "galvanized corrugated sheet",
        "metal deck roofing",
        "tiles",
    ]
    for pos in positives:
        assert is_valid_roof_material_text(pos), f"Expected '{pos}' to be accepted as roof material"
        res = _long(material=(pos,))
        assert res.status is Status.CANDIDATE


def test_missing_material_border_dimension_and_dashes_do_not_mint_roof():
    assert _long(material=()).status is Status.ABSTAINED
    only_nonroof = [p for p in _long_paths() if p.path_id in {"dimension", "border-top", "border-bottom", "border-left", "border-right"}]
    assert _long(only_nonroof).status is Status.ABSTAINED
    dashed = [RoofPath(p.path_id, p.start, p.end, dashes="[3 2] 0") for p in _long_paths()]
    assert _long(dashed).status is Status.ABSTAINED
    assert _gable(material=()).status is Status.ABSTAINED


def test_material_callout_must_share_viewport_source_and_entity():
    for wrong in (
        RoofMaterialAnnotation("x", "roofing", _scope("rear"), (40, 10, 90, 18)),
        RoofMaterialAnnotation("x", "roofing", replace(_scope("front"), entity_id="other"), (40, 10, 90, 18)),
        RoofMaterialAnnotation("x", "roofing", replace(_scope("front"), source_sha256="1" * 64), (40, 10, 90, 18)),
        RoofMaterialAnnotation("x", "roofing", _scope("front"), (40, 121, 90, 130)),
        RoofMaterialAnnotation("x", "window", _scope("front"), (40, 10, 90, 18)),
    ):
        result = collect_longitudinal_roof_edge(
            _long_paths(), scope=_scope("front"), viewport_bbox=(0, 0, 200, 120),
            page_width_pt=200, roof_material_annotations=(wrong,),
        )
        assert result.status is Status.ABSTAINED


def test_competing_long_roof_rectangles_conflict_rather_than_choose_longest():
    paths = _long_paths() + [
        RoofPath("other-top", (30, 40), (170, 40)),
        RoofPath("other-bottom", (30, 50), (170, 50)),
        RoofPath("other-left", (30, 40), (30, 55)),
        RoofPath("other-right", (170, 40), (170, 55)),
    ]
    result = _long(paths)
    assert result.status is Status.CONFLICT
    assert result.span_pt is None
    assert {a.end_pt - a.start_pt for a in result.alternatives} == {140, 160}
    assert all(a.candidate_id for a in result.alternatives)


def test_three_longitudinal_candidates_conflict_fail_closed():
    """Three valid longitudinal candidates must produce a CONFLICT rather than arbitrarily selecting two."""
    c1 = _long(viewport="front")
    c2 = _long(viewport="rear", dy=150)
    c3 = _long(viewport="side_extra", dy=300)
    gable = _gable()
    reconciled = reconcile_roof_eave_geometry([c1, c2, c3], gable, pitch_deg=22.38)
    assert reconciled.status is Status.CONFLICT
    assert "competing_longitudinal_elevations" in reconciled.reason_codes
    assert "extra_longitudinal_candidates_unresolved" in reconciled.blockers


def test_competing_longitudinal_faces_conflict():
    """Two longitudinal candidates both matching the same gable side must produce a conflict."""
    # Asymmetric gable: left drop 55, right drop 38
    gable = replace(_gable(), left_drop_pt=55.0, right_drop_pt=38.0)
    # Both candidates have height 55 (both match left side, neither matches right)
    c1 = replace(_long(viewport="view_a"), height_pt=55.0)
    c2 = replace(_long(viewport="view_b", dy=150), height_pt=55.0)
    reconciled = reconcile_roof_eave_geometry([c1, c2], gable, pitch_deg=22.38)
    assert reconciled.status is Status.CONFLICT
    assert "duplicate_or_competing_longitudinal_faces" in reconciled.reason_codes


def test_ambiguous_gable_side_match():
    """A candidate whose drop can match both sides ambiguously must abstain."""
    gable = replace(_gable(), left_drop_pt=40.0, right_drop_pt=41.0)
    # Candidate drop 40.5 is within 1.5 pt tolerance of both 40.0 and 41.0
    c1 = replace(_long(viewport="view_a"), height_pt=40.5)
    c2 = replace(_long(viewport="view_b", dy=150), height_pt=40.5)
    reconciled = reconcile_roof_eave_geometry([c1, c2], gable, pitch_deg=22.38)
    assert reconciled.status is Status.ABSTAINED
    assert "ambiguous_gable_side_match" in reconciled.reason_codes


def test_longitudinal_gable_drop_mismatch_abstains():
    """Longitudinal elevations whose drops do not match the gable drops must abstain."""
    gable = replace(_gable(), left_drop_pt=55.0, right_drop_pt=38.0)
    c1 = replace(_long(viewport="view_a"), height_pt=20.0)
    c2 = replace(_long(viewport="view_b", dy=150), height_pt=20.0)
    reconciled = reconcile_roof_eave_geometry([c1, c2], gable, pitch_deg=22.38)
    assert reconciled.status is Status.ABSTAINED
    assert "longitudinal_gable_drop_mismatch" in reconciled.reason_codes


def test_symmetric_roof_abstains_without_facade_role():
    """For a symmetric roof where both drops are equal, equal drop alone cannot prove distinct faces."""
    gable = replace(_gable(), left_drop_pt=35.0, right_drop_pt=35.0)
    # Arbitrary viewport names with no facade role
    c1 = replace(_long(viewport="vp_1"), height_pt=35.0, orientation=None)
    c2 = replace(_long(viewport="vp_2", dy=150), height_pt=35.0, orientation=None)
    reconciled = reconcile_roof_eave_geometry([c1, c2], gable, pitch_deg=22.38)
    assert reconciled.status is Status.ABSTAINED
    assert "symmetric_roof_facade_identity_unproven" in reconciled.reason_codes


def test_symmetric_roof_viewport_name_and_number_negatives_must_abstain():
    """Negative test: Viewport names, numbers, or directional labels must never infer facade role on symmetric roof.

    Candidates named ELEVATION 01 / ELEVATION 03, front / rear, etc. without producer-owned facade_role MUST ABSTAIN.
    """
    gable = replace(_gable(), left_drop_pt=35.0, right_drop_pt=35.0)
    name_pairs = [
        ("ELEVATION 01", "ELEVATION 03"),
        ("elevation 01", "elevation 03"),
        ("elev1", "elev3"),
        ("ELEV_1", "ELEV_3"),
        ("front", "rear"),
        ("front_elevation", "rear_elevation"),
        ("south_facade", "north_facade"),
        ("back", "front"),
        ("vp_front_elevation_01", "vp_rear_elevation_03"),
    ]
    for vp1, vp2 in name_pairs:
        c1 = replace(_long(viewport=vp1), height_pt=35.0, orientation=None)
        c2 = replace(_long(viewport=vp2, dy=150), height_pt=35.0, orientation=None)
        reconciled = reconcile_roof_eave_geometry([c1, c2], gable, pitch_deg=22.38)
        assert reconciled.status is Status.ABSTAINED, f"Expected {vp1}/{vp2} without facade_role to abstain"
        assert "symmetric_roof_facade_identity_unproven" in reconciled.reason_codes
        assert "symmetric_roof_facade_identity_unproven" in reconciled.blockers


def test_symmetric_roof_raw_caller_facade_role_rejected_fails_closed():
    """Raw caller input such as facade_role='front' must not establish physical identity for symmetric roof."""
    gable = replace(_gable(), left_drop_pt=35.0, right_drop_pt=35.0)
    c1 = replace(_long(viewport="ELEVATION 01"), height_pt=35.0, facade_role="front")
    c2 = replace(_long(viewport="ELEVATION 03", dy=150), height_pt=35.0, facade_role="rear")
    reconciled = reconcile_roof_eave_geometry([c1, c2], gable, pitch_deg=22.38)
    assert reconciled.status is Status.ABSTAINED
    assert "symmetric_roof_facade_identity_unproven" in reconciled.reason_codes
    assert "symmetric_roof_facade_identity_unproven" in reconciled.blockers


def test_no_caller_accessible_tolerance_override():
    """Verify reconcile_roof_eave_geometry rejects caller-supplied tolerance override."""
    c1 = _long(viewport="front")
    c2 = _long(viewport="rear", dy=150)
    gable = _gable()
    with pytest.raises(TypeError, match="unexpected keyword argument 'tol'"):
        reconcile_roof_eave_geometry([c1, c2], gable, pitch_deg=22.38, tol=10.0)  # type: ignore[call-arg]


def test_asymmetric_roof_resolves_purely_geometrically():
    """An asymmetric roof resolves purely geometrically without any facade names or elevation numbers."""
    gable = replace(_gable(), left_drop_pt=55.56, right_drop_pt=38.16)
    # Viewport names are arbitrary identifiers
    c1 = replace(_long(viewport="vp_alpha"), height_pt=55.68, orientation=None)
    c2 = replace(_long(viewport="vp_beta", dy=150), height_pt=37.80, orientation=None)
    reconciled = reconcile_roof_eave_geometry([c1, c2], gable, pitch_deg=22.38)
    assert reconciled.status is Status.CANDIDATE
    assert reconciled.physical_distinctness == "distinct_front_rear_eaves"
    assert len(reconciled.longitudinal_matches) == 2
    # Verify exact matches
    match_dict = {m[0]: m[1] for m in reconciled.longitudinal_matches}
    assert match_dict["vp_alpha"] == "left"
    assert match_dict["vp_beta"] == "right"


def test_elevation_ordering_and_numbering_invariance():
    """Reversing candidate order or using arbitrary elevation numbers produces identical geometric results."""
    gable = replace(_gable(), left_drop_pt=55.56, right_drop_pt=38.16)
    cA = replace(_long(viewport="elevation_42"), height_pt=55.68)
    cB = replace(_long(viewport="elevation_99", dy=150), height_pt=37.80)

    res_forward = reconcile_roof_eave_geometry([cA, cB], gable, pitch_deg=22.38)
    res_reverse = reconcile_roof_eave_geometry([cB, cA], gable, pitch_deg=22.38)

    assert res_forward.status is Status.CANDIDATE
    assert res_reverse.status is Status.CANDIDATE
    assert res_forward.geometry_id == res_reverse.geometry_id
    assert res_forward.longitudinal_span_pt == res_reverse.longitudinal_span_pt
    assert res_forward.transverse_span_pt == res_reverse.transverse_span_pt


def test_metamorphic_coordinate_scaling_preserves_reconciliation_and_rejection():
    """Metamorphic test: Constructing the same generic roof geometry at 1x and 2x coordinate scales.

    Reconciled classification and bijection must remain identical,
    scaling differences and tolerance proportionally.
    A true mismatch that exceeds tolerance must remain rejected at both scales.
    """
    # 1. Base 1x asymmetric roof geometry
    gable_1x = replace(_gable(scale=1.0), left_drop_pt=55.56, right_drop_pt=38.16)
    c1_1x = replace(_long(viewport="vp_front", scale=1.0, dy=0), height_pt=55.68)
    c2_1x = replace(_long(viewport="vp_rear", scale=1.0, dy=150), height_pt=37.80)

    res_1x = reconcile_roof_eave_geometry([c1_1x, c2_1x], gable_1x, pitch_deg=22.38)
    assert res_1x.status is Status.CANDIDATE
    assert res_1x.physical_distinctness == "distinct_front_rear_eaves"
    matches_1x = {m[0]: m[1] for m in res_1x.longitudinal_matches}
    assert matches_1x["vp_front"] == "left"
    assert matches_1x["vp_rear"] == "right"

    tol_1x = res_1x.reconciliation_tol_pt
    assert tol_1x is not None and tol_1x > 0
    diff_left_1x = abs(c1_1x.height_pt - gable_1x.left_drop_pt)
    diff_right_1x = abs(c2_1x.height_pt - gable_1x.right_drop_pt)
    assert diff_left_1x <= tol_1x
    assert diff_right_1x <= tol_1x

    # 2. Scaled 2x asymmetric roof geometry (all coordinates / dimensions doubled)
    gable_2x = replace(_gable(scale=2.0), left_drop_pt=111.12, right_drop_pt=76.32)
    c1_2x = replace(_long(viewport="vp_front", scale=2.0, dy=0), height_pt=111.36)
    c2_2x = replace(_long(viewport="vp_rear", scale=2.0, dy=300), height_pt=75.60)

    res_2x = reconcile_roof_eave_geometry([c1_2x, c2_2x], gable_2x, pitch_deg=22.38)
    assert res_2x.status is Status.CANDIDATE
    assert res_2x.physical_distinctness == "distinct_front_rear_eaves"
    matches_2x = {m[0]: m[1] for m in res_2x.longitudinal_matches}
    assert matches_2x["vp_front"] == "left"
    assert matches_2x["vp_rear"] == "right"

    tol_2x = res_2x.reconciliation_tol_pt
    assert tol_2x is not None and tol_2x > 0
    diff_left_2x = abs(c1_2x.height_pt - gable_2x.left_drop_pt)
    diff_right_2x = abs(c2_2x.height_pt - gable_2x.right_drop_pt)
    assert diff_left_2x <= tol_2x
    assert diff_right_2x <= tol_2x

    # Invariants under uniform 2x scaling:
    # A. Tolerance scales proportionally by 2x
    assert tol_2x == pytest.approx(2.0 * tol_1x, rel=1e-4)
    # B. Differences scale proportionally by 2x
    assert diff_left_2x == pytest.approx(2.0 * diff_left_1x, rel=1e-4)
    assert diff_right_2x == pytest.approx(2.0 * diff_right_1x, rel=1e-4)
    # C. Relative margin (diff / tol) remains identical at both scales
    assert (diff_left_2x / tol_2x) == pytest.approx(diff_left_1x / tol_1x, rel=1e-4)
    assert (diff_right_2x / tol_2x) == pytest.approx(diff_right_1x / tol_1x, rel=1e-4)

    # 3. True mismatch that exceeds tolerance must be rejected at both 1x and 2x
    c1_mismatch_1x = replace(c1_1x, height_pt=round(gable_1x.left_drop_pt + 1.5 * tol_1x, 4))
    res_mismatch_1x = reconcile_roof_eave_geometry([c1_mismatch_1x, c2_1x], gable_1x, pitch_deg=22.38)
    assert res_mismatch_1x.status is Status.ABSTAINED
    assert "longitudinal_gable_drop_mismatch" in res_mismatch_1x.reason_codes

    c1_mismatch_2x = replace(c1_2x, height_pt=round(gable_2x.left_drop_pt + 1.5 * tol_2x, 4))
    res_mismatch_2x = reconcile_roof_eave_geometry([c1_mismatch_2x, c2_2x], gable_2x, pitch_deg=22.38)
    assert res_mismatch_2x.status is Status.ABSTAINED
    assert "longitudinal_gable_drop_mismatch" in res_mismatch_2x.reason_codes


def test_order_translation_and_scale_preserve_spans_without_mutating_inputs():
    original = _long_paths()
    before = deepcopy(original)
    reordered = original[:]
    Random(7).shuffle(reordered)
    assert _long(original) == _long(reordered)
    assert original == before
    shifted = _long(_long_paths(dx=11.75, dy=32.5), dy=32.5)
    assert shifted.span_pt == _long(original).span_pt
    doubled = _long(scale=2)
    assert doubled.span_pt == 2 * _long(original).span_pt
    gable = _gable()
    assert _gable(dx=11.75, dy=32.5).span_pt == gable.span_pt
    assert _gable(scale=2).span_pt == 2 * gable.span_pt


def test_split_paths_preserve_geometry_and_contract_id():
    original = _long()
    whole = _long_paths()
    split = []
    for p in whole:
        if p.path_id in {"roof-top", "roof-bottom"}:
            middle = ((p.start[0] + p.end[0]) / 2, p.start[1])
            split.extend([replace(p, path_id=p.path_id + ":a", end=middle),
                          replace(p, path_id=p.path_id + ":b", start=middle)])
        else:
            split.append(p)
    result = _long(split)
    assert result.status is Status.CANDIDATE
    assert result.span_pt == original.span_pt
    assert result.candidate_id == original.candidate_id
    assert len(result.path_ids) == len(original.path_ids) + 2

    gable = _gable()

    def bisect(p):
        middle = tuple((x + y) / 2 for x, y in zip(p.start, p.end))
        return [replace(p, path_id=p.path_id + ":a", end=middle),
                replace(p, path_id=p.path_id + ":b", start=middle)]
    split_gable = [*bisect(RoofPath("left-outer", (15, 65), (100, 30))),
                   *bisect(RoofPath("right-outer", (100, 30), (185, 65)))]
    gable_result = _gable(split_gable)
    assert gable_result.status is Status.CANDIDATE
    assert gable_result.span_pt == gable.span_pt
    assert gable_result.candidate_id == gable.candidate_id


def test_unrelated_content_and_viewport_expansion_preserve_candidate():
    original = _long()
    expanded = collect_longitudinal_roof_edge(
        _long_paths() + [RoofPath("furniture", (205, 60), (220, 70)),
                         RoofPath("grid", (10, 90), (190, 90), dashes="[2 2] 0")],
        scope=_scope("front"), viewport_bbox=(-10, -10, 230, 140),
        page_width_pt=230, roof_material_annotations=(RoofMaterialAnnotation(
            "callout:0", "corrugated roofing", _scope("front"), (40, 10, 90, 18)),),
    )
    assert expanded.status is Status.CANDIDATE
    assert expanded.span_pt == original.span_pt
    assert expanded.candidate_id == original.candidate_id


def test_rotation_180_preserves_long_span_and_gable_span():
    original = _long()

    def turn(p):
        return replace(p, start=(200 - p.start[0], 120 - p.start[1]),
                       end=(200 - p.end[0], 120 - p.end[1]))
    turned = collect_longitudinal_roof_edge(
        [turn(p) for p in _long_paths()], scope=_scope("front"),
        viewport_bbox=(0, 0, 200, 120), page_width_pt=200,
        roof_material_annotations=(RoofMaterialAnnotation(
            "callout:0", "corrugated roofing", _scope("front"), (40, 10, 90, 18)),),
    )
    assert turned.status is Status.CANDIDATE
    assert turned.span_pt == original.span_pt
    paths = [RoofPath("left-outer", (15, 65), (100, 30)),
             RoofPath("right-outer", (100, 30), (185, 65))]
    turned_gable = _gable([turn(p) for p in paths], apex=(100, 90))
    assert turned_gable.status is Status.CANDIDATE
    assert turned_gable.span_pt == _gable().span_pt


def test_lamu_page41_source_roof_surface_geometry_shadow():
    """End-to-end fixture test on real Lamu Page 41 drawings."""
    from pathlib import Path
    fitz = pytest.importorskip("fitz")
    lamu_pdf = Path("benchmarks/sources/lamu-ishakani-ecd-classrooms-boq.pdf")
    if not lamu_pdf.exists():
        pytest.skip("Lamu benchmark source PDF not cached locally")

    from pb_source_roof_covering_authority import get_elevation_viewport_search_bbox
    from pb_viewport_segmentation import segment_page_viewports

    doc = fitz.open(str(lamu_pdf))
    try:
        page = doc[40]
        vps = segment_page_viewports(page, page_number=41)
        drawings = page.get_drawings()

        paths = []
        for idx, d in enumerate(drawings):
            items = d.get("items", [])
            stroke = d.get("color", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
            width = d.get("width", 1.0)
            dashes = str(d.get("dashes", "[] 0"))
            for it_idx, it in enumerate(items):
                if it[0] == "l":
                    p1, p2 = it[1], it[2]
                    paths.append(RoofPath(f"{idx}:{it_idx}", (p1.x, p1.y), (p2.x, p2.y), stroke=stroke, width_pt=width, dashes=dashes))

        vp_front = next(vp for vp in vps if vp.view_id == "view_p41_2")
        vp_rear = next(vp for vp in vps if vp.view_id == "view_p41_3")
        vp_gable = next(vp for vp in vps if vp.view_id == "view_p41_4")

        sbox_front = get_elevation_viewport_search_bbox(vp_front, vps, page.rect)
        sbox_rear = get_elevation_viewport_search_bbox(vp_rear, vps, page.rect)
        sbox_gable = get_elevation_viewport_search_bbox(vp_gable, vps, page.rect)

        annotations = []
        for b_idx, block in enumerate(page.get_text("blocks")):
            text = block[4].strip()
            if is_valid_roof_material_text(text):
                bbox = (block[0], block[1], block[2], block[3])
                for v_name, vp, sbox in [("front", vp_front, sbox_front), ("rear", vp_rear, sbox_rear), ("gable", vp_gable, sbox_gable)]:
                    if sbox[0] <= bbox[0] < bbox[2] <= sbox[2] and sbox[1] <= bbox[1] < bbox[3] <= sbox[3]:
                        scope = RoofSourceScope("doc-lamu", "rev-1", "fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2", 41, vp.view_id, "roof_classroom")
                        annotations.append(RoofMaterialAnnotation(f"anno_{b_idx}_{v_name}", text, scope, bbox))

        scope_front = RoofSourceScope("doc-lamu", "rev-1", "fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2", 41, vp_front.view_id, "roof_classroom")
        scope_rear = RoofSourceScope("doc-lamu", "rev-1", "fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2", 41, vp_rear.view_id, "roof_classroom")
        scope_gable = RoofSourceScope("doc-lamu", "rev-1", "fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2", 41, vp_gable.view_id, "roof_classroom")

        res_front = collect_longitudinal_roof_edge(paths, scope=scope_front, viewport_bbox=sbox_front, page_width_pt=page.rect.width, roof_material_annotations=annotations)
        assert res_front.status is Status.CANDIDATE
        assert res_front.span_pt == pytest.approx(487.68, abs=0.01)
        assert res_front.start_pt == pytest.approx(184.28, abs=0.01)
        assert res_front.end_pt == pytest.approx(671.96, abs=0.01)
        assert res_front.height_pt == pytest.approx(55.68, abs=0.05)
        assert set(res_front.path_ids) == {"1790:0", "1792:0", "1924:0", "1925:0", "2047:0"}

        res_rear = collect_longitudinal_roof_edge(paths, scope=scope_rear, viewport_bbox=sbox_rear, page_width_pt=page.rect.width, roof_material_annotations=annotations)
        assert res_rear.status is Status.CANDIDATE
        assert res_rear.span_pt == pytest.approx(487.68, abs=0.01)
        assert res_rear.start_pt == pytest.approx(184.28, abs=0.01)
        assert res_rear.end_pt == pytest.approx(671.96, abs=0.01)
        assert res_rear.height_pt == pytest.approx(37.80, abs=0.05)
        assert set(res_rear.path_ids) == {"1148:0", "1150:0", "1282:0", "1283:0", "1284:0"}

        res_gable = collect_gable_outer_roof_edge(
            paths, scope=scope_gable, viewport_bbox=sbox_gable,
            apex_xy=(469.04, 932.28), pitch_deg=18.019,
            structural_left_x=328.64, structural_right_x=561.20,
            roof_material_annotations=annotations,
        )
        assert res_gable.status is Status.CANDIDATE
        assert res_gable.span_pt == pytest.approx(260.76, abs=0.01)
        assert res_gable.start_pt == pytest.approx(311.72, abs=0.01)
        assert res_gable.end_pt == pytest.approx(572.48, abs=0.01)
        assert res_gable.left_drop_pt == pytest.approx(55.56, abs=0.1)
        assert res_gable.right_drop_pt == pytest.approx(38.16, abs=0.1)
        assert set(res_gable.path_ids) == {"578:0", "578:2", "580:0", "581:0"}

        reconciled = reconcile_roof_eave_geometry([res_front, res_rear], res_gable, pitch_deg=18.019)
        assert reconciled.status is Status.CANDIDATE
        assert reconciled.longitudinal_span_pt == pytest.approx(487.68, abs=0.01)
        assert reconciled.transverse_span_pt == pytest.approx(260.76, abs=0.01)
        assert reconciled.pitch_deg == pytest.approx(18.019, abs=0.01)
        assert reconciled.physical_distinctness == "distinct_front_rear_eaves"
        assert reconciled.geometry_completeness == "complete_closed_prism"
        assert reconciled.quantity_m2 is None
        assert reconciled.roof_plane_count == 2
        assert reconciled.geometry_id is not None
        assert len(reconciled.longitudinal_matches) == 2
        assert reconciled.reconciliation_tol_pt is not None and reconciled.reconciliation_tol_pt > 0
        assert abs(res_front.height_pt - res_gable.left_drop_pt) <= reconciled.reconciliation_tol_pt
        assert abs(res_rear.height_pt - res_gable.right_drop_pt) <= reconciled.reconciliation_tol_pt
        # Proves resolution is purely via asymmetric gable-drop bijection with derived tolerance:
        assert res_front.facade_role is None
        assert res_rear.facade_role is None
        match_dict = {m[0]: m[1] for m in reconciled.longitudinal_matches}
        assert match_dict[vp_front.view_id] == "left"
        assert match_dict[vp_rear.view_id] == "right"
    finally:
        doc.close()


def test_extract_document_roof_surface_geometry_shadow_lamu():
    """Verify document-level generic extractor function on Lamu PDF without elevation assumptions."""
    from pathlib import Path
    fitz = pytest.importorskip("fitz")
    lamu_pdf = Path("benchmarks/sources/lamu-ishakani-ecd-classrooms-boq.pdf")
    if not lamu_pdf.exists():
        pytest.skip("Lamu benchmark source PDF not cached locally")

    doc = fitz.open(str(lamu_pdf))
    try:
        res = extract_document_roof_surface_geometry_shadow(
            doc,
            document_id="lamu_ecd_doc",
            revision_id="rev-current",
            source_sha256="fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2",
            entity_id="roof_covering",
            target_pages=[40],
        )
        assert res.status is Status.CANDIDATE
        assert res.longitudinal_span_pt == pytest.approx(487.68, abs=0.01)
        assert res.transverse_span_pt == pytest.approx(260.76, abs=0.01)
        assert res.pitch_deg == pytest.approx(18.019, abs=0.01)
        assert res.physical_distinctness == "distinct_front_rear_eaves"
        assert res.geometry_completeness == "complete_closed_prism"
        assert res.quantity_m2 is None
        assert res.roof_plane_count == 2
        assert res.geometry_id is not None
        assert set(res.ridge_candidate_ids) == {"1282:0", "1924:0"}
        assert set(res.longitudinal_outer_edge_ids) == {"1284:0", "1925:0"}
        assert set(res.gable_outer_edge_ids) == {"578:0", "578:2", "580:0", "581:0"}
        assert len(res.longitudinal_matches) == 2
        assert res.reconciliation_tol_pt is not None and res.reconciliation_tol_pt > 0
        match_dict = {m[0]: m[1] for m in res.longitudinal_matches}
        assert match_dict["view_p41_2"] == "left"
        assert match_dict["view_p41_3"] == "right"
    finally:
        doc.close()


def test_duplicate_side_strokes_are_retained_without_first_match_selection():
    paths = _long_paths() + [RoofPath("roof-left-second", (20, 20), (20, 55))]
    result = _long(paths)
    assert result.status is Status.CANDIDATE
    assert {"roof-left", "roof-left-second"} <= set(result.path_ids)


def test_gable_needs_opposing_roof_slopes_enclosing_structural_supports():
    p = [RoofPath("one-side", (15, 65), (100, 30))]
    assert _gable(p).status is Status.ABSTAINED
    p.append(RoofPath("inside-only", (100, 30), (130, 42.35)))
    assert _gable(p).status is Status.CONFLICT


def test_incomplete_or_cross_page_view_universe_abstains():
    front = _long(viewport="front")
    gable = _gable()
    assert reconcile_roof_eave_geometry([front], gable, pitch_deg=22.38).status is Status.ABSTAINED
    rear = _long(viewport="rear", dy=150)
    swapped = replace(rear, scope=_scope("rear", page=2))
    assert reconcile_roof_eave_geometry([front, swapped], gable, pitch_deg=22.38).status is Status.CONFLICT


def test_cross_revision_and_source_hash_cannot_reconcile():
    front = _long(viewport="front")
    rear = _long(viewport="rear", dy=150)
    gable = _gable()
    other_revision = replace(rear, scope=_scope("rear", revision="rev-2"))
    assert reconcile_roof_eave_geometry([front, other_revision], gable, pitch_deg=22.38).status is Status.CONFLICT
    changed_hash = replace(rear, scope=replace(rear.scope, source_sha256="1" * 64))
    assert reconcile_roof_eave_geometry([front, changed_hash], gable, pitch_deg=22.38).status is Status.CONFLICT


def test_competing_gable_endpoints_and_entity_or_pitch_conflicts_abstain():
    ambiguous = [RoofPath("left-a", (15, 65), (100, 30)),
                 RoofPath("left-b", (25, 60.88), (100, 30)),
                 RoofPath("right", (100, 30), (185, 65))]
    gable_conflict = _gable(ambiguous)
    assert gable_conflict.status is Status.CONFLICT
    assert len(gable_conflict.alternatives) == 2
    assert {a.start_pt for a in gable_conflict.alternatives} == {15, 25}
    front = _long(viewport="front")
    rear = _long(viewport="rear", dy=150)
    gable = _gable()
    other_entity = replace(rear, scope=replace(rear.scope, entity_id="roof-2"))
    assert reconcile_roof_eave_geometry([front, other_entity], gable, pitch_deg=22.38).status is Status.CONFLICT
    assert reconcile_roof_eave_geometry([front, rear], gable, pitch_deg=30).status is Status.CONFLICT


def test_replay_is_deterministic_and_inputs_are_unchanged():
    paths = _long_paths()
    original = deepcopy(paths)
    results = [_long(paths) for _ in range(4)]
    assert all(r == results[0] for r in results)
    assert results[0].candidate_id
    assert paths == original


def test_real_roof_outline_with_separate_fascia_line():
    paths = _long_paths() + [
        RoofPath("fascia-bottom", (20, 58), (180, 58)),
        RoofPath("roof-left-ext", (20, 55), (20, 58)),
        RoofPath("roof-right-ext", (180, 55), (180, 58)),
    ]
    result = _long(paths)
    assert result.status is Status.CANDIDATE
    assert result.span_pt == 160
    assert "fascia-bottom" in result.path_ids
    assert result.height_pt == 38


def test_roof_plus_gutter_does_not_distort_roof_outline():
    paths = _long_paths() + [
        RoofPath("gutter-open", (15, 60), (185, 60)),
    ]
    result = _long(paths)
    assert result.status is Status.CANDIDATE
    assert result.span_pt == 160
    assert "gutter-open" not in result.path_ids


def test_page_border_long_line_is_rejected():
    border_paths = [
        RoofPath("border-full", (5, 50), (195, 50)),
        RoofPath("zero-width-long", (10, 60), (190, 60), width_pt=0.0),
    ]
    result = _long(border_paths)
    assert result.status is Status.ABSTAINED
    assert result.span_pt is None

