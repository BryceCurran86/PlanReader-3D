"""Tests for Source-Authenticated Whole-Opening Aperture Structural Authority."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    NATIVE_PDF_VISIBLE_SEGMENT,
    CandidateSemanticOpening,
    SourceObservationRecord,
)
from pb_structural_whole_opening_aperture_authority import (
    AMBIGUOUS_MULTI_LAYER_OFFSET,
    APERTURE_EXTENT_INCOMPLETE,
    HOST_WALL_CONTINUITY_PROVEN,
    INTERNAL_GLAZING_SUBDIVISION_GAP,
    STRUCTURAL_JAMB_COMPOSITE,
    STRUCTURAL_JAMB_HEAVY,
    STRUCTURAL_TERMINAL_JAMB_PROVEN,
    TERMINAL_ROLE_UNPROVEN,
    WALL_CONTINUITY_MISSING,
    WHOLE_OPENING_APERTURE_CORROBORATED,
    ApertureSourceStroke,
    GlazingSubdivisionDiscriminationRecord,
    StructuralWholeOpeningApertureAuthority,
    StructuralWholeOpeningApertureProducer,
    WholeOpeningApertureRecord,
)


def _make_seed(
    doc: str = "doc_test",
    rev: str = "rev_test",
    sha: str = "a" * 64,
    snap: str = "snap_test",
    page: str = "7",
) -> SourceObservationRecord:
    return SourceObservationRecord(
        observation_id="seed_obs",
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_id=page,
        source_partition_id=f"page:{page}",
        observation_kind=NATIVE_PDF_VISIBLE_SEGMENT,
        source_primitive_ref="prim:seed",
        origin_kind="native_pdf",
        derivation_parent_ids=("parent_seed",),
        raw_text="",
        geometry=(0.0, 0.0, 10.0, 0.0),
        viewport_id="viewport_test",
        producer_method="test",
        producer_version="1",
        producer_generation=1,
        observation_payload_sha256="0" * 64,
    )


def _make_obs(
    obs_id: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    width: float = 0.48,
    doc: str = "doc_test",
    rev: str = "rev_test",
    sha: str = "a" * 64,
    snap: str = "snap_test",
    page: str = "7",
    opaque: bool = True,
    has_fill_mask: bool = False,
    clipped: bool = False,
) -> ApertureSourceStroke:
    return ApertureSourceStroke(
        observation_id=obs_id,
        geometry=(x0, y0, x1, y1),
        stroke_width=width,
        stroke_rgb=(0.0, 0.0, 0.0),
        stroke_opacity=1.0 if opaque else 0.5,
        dashes="[] 0",
        is_fill_mask=has_fill_mask,
        is_clipped=clipped,
    )


# -----------------------------------------------------------------------------
# 1. Sealed Boundary & Immutability Tests
# -----------------------------------------------------------------------------


def test_sealing_raises_permission_error():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        StructuralWholeOpeningApertureProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        StructuralWholeOpeningApertureAuthority({}, {}, _seal=object())

    with pytest.raises(ValueError, match="shadow mode"):
        GlazingSubdivisionDiscriminationRecord(
            record_id="rec_sub",
            document_id="doc",
            revision_id="rev",
            source_sha256="sha",
            snapshot_id="snap",
            page_id="1",
            viewport_id=None,
            axis="H",
            is_internal_subdivision=True,
            subdivision_span_along=(10.0, 12.0),
            subdivision_depth_across=0.72,
            member_observation_ids=("obs1",),
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(),
            commercial_projection_allowed=True,
        )

    with pytest.raises(ValueError, match="shadow mode"):
        WholeOpeningApertureRecord(
            record_id="rec_ap",
            document_id="doc",
            revision_id="rev",
            source_sha256="sha",
            snapshot_id="snap",
            page_id="1",
            viewport_id=None,
            axis="H",
            aperture_span_along=(10.0, 50.0),
            wall_band_across=(100.0, 110.0),
            terminal_jamb_lo_ids=(),
            terminal_jamb_hi_ids=(),
            host_face_ids=(),
            glazing_strip_ids=(),
            discriminated_subdivision_ids=(),
            status=EvidenceResolutionStatus.CANDIDATE,
            structural_role="role",
            reason_codes=(),
            takeoff_eligible=True,
        )


# -----------------------------------------------------------------------------
# 2. Synthetic Multi-Panel Ribbon Window Positive Test
# -----------------------------------------------------------------------------


def test_synthetic_three_panel_window_with_internal_posts():
    """3-panel window along X: [100.0, 304.0] with 2 internal posts of span 2.0 pt."""
    # Glass line 1: y = 200.0, Glass line 2: y = 200.72 (depth = 0.72 pt)
    # Panel 1: [100.0, 160.0]
    # Post 1:  [160.0, 162.0]
    # Panel 2: [162.0, 230.0]
    # Post 2:  [230.0, 232.0]
    # Panel 3: [232.0, 304.0]

    obs = [
        # Panel 1 glass lines and end ticks
        _make_obs("g1_p1_lo", 100.0, 200.0, 160.0, 200.0),
        _make_obs("g2_p1_hi", 100.0, 200.72, 160.0, 200.72),
        _make_obs("t_p1_start", 100.0, 200.0, 100.0, 200.72),
        _make_obs("t_p1_end", 160.0, 200.0, 160.0, 200.72),
        # Panel 2 glass lines and end ticks
        _make_obs("g1_p2_lo", 162.0, 200.0, 230.0, 200.0),
        _make_obs("g2_p2_hi", 162.0, 200.72, 230.0, 200.72),
        _make_obs("t_p2_start", 162.0, 200.0, 162.0, 200.72),
        _make_obs("t_p2_end", 230.0, 200.0, 230.0, 200.72),
        # Panel 3 glass lines and end ticks
        _make_obs("g1_p3_lo", 232.0, 200.0, 304.0, 200.0),
        _make_obs("g2_p3_hi", 232.0, 200.72, 304.0, 200.72),
        _make_obs("t_p3_start", 232.0, 200.0, 232.0, 200.72),
        _make_obs("t_p3_end", 304.0, 200.0, 304.0, 200.72),
        # Terminal jambs across wall band y in [195.0, 205.0]
        # Low jamb at x = 100.0 (heavy 0.96 pt stroke)
        _make_obs("jamb_lo", 100.0, 195.0, 100.0, 205.0, width=0.96),
        # High jamb at x = 304.0 (heavy 0.96 pt stroke)
        _make_obs("jamb_hi", 304.0, 195.0, 304.0, 205.0, width=0.96),
        # Continuing wall faces on either side
        _make_obs("wall_left_lo", 20.0, 195.0, 100.0, 195.0),
        _make_obs("wall_left_hi", 20.0, 205.0, 100.0, 205.0),
        _make_obs("wall_right_lo", 304.0, 195.0, 380.0, 195.0),
        _make_obs("wall_right_hi", 304.0, 205.0, 380.0, 205.0),
    ]

    producer = StructuralWholeOpeningApertureProducer.create()
    seed = _make_seed()
    apertures = producer.analyze_page(seed, obs)

    assert len(apertures) == 1
    ap = apertures[0]
    assert ap.axis == "H"
    assert ap.aperture_span_along == (100.0, 304.0)
    assert ap.status is EvidenceResolutionStatus.CANDIDATE
    assert WHOLE_OPENING_APERTURE_CORROBORATED in ap.reason_codes
    assert STRUCTURAL_TERMINAL_JAMB_PROVEN in ap.reason_codes
    assert HOST_WALL_CONTINUITY_PROVEN in ap.reason_codes
    assert ap.structural_role == STRUCTURAL_JAMB_HEAVY
    assert "jamb_lo" in ap.terminal_jamb_lo_ids
    assert "jamb_hi" in ap.terminal_jamb_hi_ids

    # Verify that the two intermediate post gaps were discriminated
    auth = producer.authority()
    subs = auth.all_discriminated_subdivisions()
    assert len(subs) == 2
    assert subs[0].subdivision_span_along == (160.0, 162.0)
    assert subs[1].subdivision_span_along == (230.0, 232.0)
    assert all(s.is_internal_subdivision for s in subs)
    assert all(INTERNAL_GLAZING_SUBDIVISION_GAP in s.reason_codes for s in subs)

    # Verify filter_opening_candidates
    cand_post1 = CandidateSemanticOpening(
        candidate_id="cand_post1",
        source_observation_ids=(
            "g1_p1_lo",
            "g2_p1_hi",
            "g1_p2_lo",
            "g2_p2_hi",
            "t_p1_end",
            "t_p2_start",
        ),
        source_lineage_root_ids=("root1",),
        document_id="doc_test",
        revision_id="rev_test",
        source_sha256="a" * 64,
        snapshot_id="snap_test",
        page_id="7",
        viewport_id=None,
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(),
    )
    cand_whole = CandidateSemanticOpening(
        candidate_id="cand_whole",
        source_observation_ids=(
            "wall_left_lo",
            "wall_right_lo",
            "wall_left_hi",
            "wall_right_hi",
            "jamb_lo",
            "jamb_hi",
        ),
        source_lineage_root_ids=("root2",),
        document_id="doc_test",
        revision_id="rev_test",
        source_sha256="a" * 64,
        snapshot_id="snap_test",
        page_id="7",
        viewport_id=None,
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(),
    )

    retained = producer.filter_opening_candidates([cand_post1, cand_whole])
    assert len(retained) == 1
    assert retained[0].candidate_id == "cand_whole"


# -----------------------------------------------------------------------------
# 3. Adversarial Negatives and Graphic-State Uncertainty Tests
# -----------------------------------------------------------------------------


def test_missing_terminal_jamb_yields_incomplete_aperture():
    """Window missing terminal jamb at high end fails closed."""
    obs = [
        _make_obs("g1", 100.0, 200.0, 200.0, 200.0),
        _make_obs("g2", 100.0, 200.72, 200.0, 200.72),
        _make_obs("t_start", 100.0, 200.0, 100.0, 200.72),
        _make_obs("t_end", 200.0, 200.0, 200.0, 200.72),
        # Only low jamb present
        _make_obs("jamb_lo", 100.0, 195.0, 100.0, 205.0),
        # Continuing wall faces
        _make_obs("wall_left", 20.0, 195.0, 100.0, 195.0),
        _make_obs("wall_right", 200.0, 195.0, 280.0, 195.0),
    ]
    producer = StructuralWholeOpeningApertureProducer.create()
    seed = _make_seed()
    apertures = producer.analyze_page(seed, obs)
    assert len(apertures) == 1
    ap = apertures[0]
    assert ap.status is EvidenceResolutionStatus.ABSTAINED
    assert APERTURE_EXTENT_INCOMPLETE in ap.reason_codes


def test_missing_wall_continuity_yields_ambiguous():
    """Window without continuing wall faces yields WALL_CONTINUITY_MISSING."""
    obs = [
        _make_obs("g1", 100.0, 200.0, 200.0, 200.0),
        _make_obs("g2", 100.0, 200.72, 200.0, 200.72),
        _make_obs("t_start", 100.0, 200.0, 100.0, 200.72),
        _make_obs("t_end", 200.0, 200.0, 200.0, 200.72),
        _make_obs("jamb_lo", 100.0, 195.0, 100.0, 205.0),
        _make_obs("jamb_hi", 200.0, 195.0, 200.0, 205.0),
        # Wall continuity missing!
    ]
    producer = StructuralWholeOpeningApertureProducer.create()
    seed = _make_seed()
    apertures = producer.analyze_page(seed, obs)
    assert len(apertures) == 1
    assert apertures[0].status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_CONTINUITY_MISSING in apertures[0].reason_codes


def test_white_mask_fill_boundary_abstains():
    """Jamb stroke obscured by white fill mask fails closed on graphic-state uncertainty."""
    obs = [
        _make_obs("g1", 100.0, 200.0, 200.0, 200.0),
        _make_obs("g2", 100.0, 200.72, 200.0, 200.72),
        _make_obs("t_start", 100.0, 200.0, 100.0, 200.72),
        _make_obs("t_end", 200.0, 200.0, 200.0, 200.72),
        _make_obs("jamb_lo", 100.0, 195.0, 100.0, 205.0, has_fill_mask=True),
        _make_obs("jamb_hi", 200.0, 195.0, 200.0, 205.0),
        _make_obs("wall_left", 20.0, 195.0, 100.0, 195.0),
        _make_obs("wall_right", 200.0, 195.0, 280.0, 195.0),
    ]
    producer = StructuralWholeOpeningApertureProducer.create()
    seed = _make_seed()
    apertures = producer.analyze_page(seed, obs)
    assert len(apertures) == 1
    assert apertures[0].status is EvidenceResolutionStatus.ABSTAINED
    assert TERMINAL_ROLE_UNPROVEN in apertures[0].reason_codes


# -----------------------------------------------------------------------------
# 4. Stepped Pier Multi-Layer Offset Test (Maryborough W03 style)
# -----------------------------------------------------------------------------


def test_stepped_pier_multi_layer_offset():
    """Stepped pier with 0.72 pt offset between outer pier return and core cap."""
    obs = [
        # Window V axis: y in [1343.12, 1550.00]
        _make_obs("g1", 1119.84, 1343.12, 1119.84, 1550.00),
        _make_obs("g2", 1120.56, 1343.12, 1120.56, 1550.00),
        _make_obs("t_lo", 1119.84, 1343.12, 1120.56, 1343.12),
        _make_obs("t_hi", 1119.84, 1550.00, 1120.56, 1550.00),
        # Low jamb cap at y = 1343.12
        _make_obs("jamb_lo", 1110.72, 1343.12, 1124.16, 1343.12),
        # High jamb returns: outer return at 1550.00, core cap at 1550.72 (offset = 0.72 pt)
        _make_obs("jamb_hi_outer", 1121.76, 1550.00, 1124.16, 1550.00),
        _make_obs("jamb_hi_core", 1113.12, 1550.72, 1121.52, 1550.72),
        # Continuing walls beyond jambs
        _make_obs("wall_lo", 1110.72, 1280.00, 1110.72, 1343.12),
        _make_obs("wall_hi", 1110.72, 1550.72, 1110.72, 1600.00),
    ]
    producer = StructuralWholeOpeningApertureProducer.create()
    seed = _make_seed()
    apertures = producer.analyze_page(seed, obs)

    assert len(apertures) == 1
    ap = apertures[0]
    assert ap.axis == "V"
    assert ap.aperture_span_along == (1343.12, 1550.00)
    assert ap.status is EvidenceResolutionStatus.CANDIDATE
    assert ap.structural_role == STRUCTURAL_JAMB_COMPOSITE
    assert AMBIGUOUS_MULTI_LAYER_OFFSET in ap.reason_codes
    assert STRUCTURAL_TERMINAL_JAMB_PROVEN in ap.reason_codes
    assert HOST_WALL_CONTINUITY_PROVEN in ap.reason_codes


# -----------------------------------------------------------------------------
# 5. Metamorphic Invariance Tests
# -----------------------------------------------------------------------------


def test_invariance_under_rotation_and_translation():
    """Verify that rotating 90 degrees or translating preserves aperture length and properties."""
    base_obs = [
        _make_obs("g1", 100.0, 200.0, 200.0, 200.0),
        _make_obs("g2", 100.0, 200.72, 200.0, 200.72),
        _make_obs("t_lo", 100.0, 200.0, 100.0, 200.72),
        _make_obs("t_hi", 200.0, 200.0, 200.0, 200.72),
        _make_obs("jamb_lo", 100.0, 195.0, 100.0, 205.0),
        _make_obs("jamb_hi", 200.0, 195.0, 200.0, 205.0),
        _make_obs("wall_lo", 20.0, 195.0, 100.0, 195.0),
        _make_obs("wall_hi", 200.0, 195.0, 280.0, 195.0),
    ]

    p_base = StructuralWholeOpeningApertureProducer.create()
    seed = _make_seed()
    ap_base = p_base.analyze_page(seed, base_obs)[0]
    base_span_len = ap_base.aperture_span_along[1] - ap_base.aperture_span_along[0]

    # Rotate 90 degrees: (x, y) -> (-y, x) + (500, 500)
    rot_obs = []
    for s in base_obs:
        x0, y0, x1, y1 = s.geometry
        rx0, ry0 = -y0 + 500.0, x0 + 500.0
        rx1, ry1 = -y1 + 500.0, x1 + 500.0
        rot_obs.append(
            _make_obs(
                f"rot_{s.observation_id}",
                rx0,
                ry0,
                rx1,
                ry1,
                width=getattr(s, "stroke_width", 0.48),
            )
        )

    p_rot = StructuralWholeOpeningApertureProducer.create()
    ap_rot = p_rot.analyze_page(seed, rot_obs)[0]
    rot_span_len = ap_rot.aperture_span_along[1] - ap_rot.aperture_span_along[0]

    assert ap_rot.axis == "V"
    assert round(rot_span_len, 4) == round(base_span_len, 4)
    assert ap_rot.status == ap_base.status
    assert ap_rot.reason_codes == ap_base.reason_codes


def test_input_stroke_ordering_invariance():
    """Shuffling stroke input sequence produces identical aperture records."""
    obs = [
        _make_obs("g1", 100.0, 200.0, 200.0, 200.0),
        _make_obs("g2", 100.0, 200.72, 200.0, 200.72),
        _make_obs("t_lo", 100.0, 200.0, 100.0, 200.72),
        _make_obs("t_hi", 200.0, 200.0, 200.0, 200.72),
        _make_obs("jamb_lo", 100.0, 195.0, 100.0, 205.0),
        _make_obs("jamb_hi", 200.0, 195.0, 200.0, 205.0),
        _make_obs("wall_lo", 20.0, 195.0, 100.0, 195.0),
        _make_obs("wall_hi", 200.0, 195.0, 280.0, 195.0),
    ]
    seed = _make_seed()
    p1 = StructuralWholeOpeningApertureProducer.create()
    ap1 = p1.analyze_page(seed, obs)[0]

    shuffled = list(obs)
    random.seed(42)
    random.shuffle(shuffled)

    p2 = StructuralWholeOpeningApertureProducer.create()
    ap2 = p2.analyze_page(seed, shuffled)[0]

    assert ap1.record_id == ap2.record_id
    assert ap1.aperture_span_along == ap2.aperture_span_along
    assert ap1.terminal_jamb_lo_ids == ap2.terminal_jamb_lo_ids
    assert ap1.terminal_jamb_hi_ids == ap2.terminal_jamb_hi_ids


# -----------------------------------------------------------------------------
# 6. Original Source Regression Tests (Maryborough Page 7: W01, W02, W03, W05)
# -----------------------------------------------------------------------------


def test_original_source_maryborough_page7_windows():
    """Verify whole openings and post discrimination on Maryborough page 7 if local PDF available."""
    pdf_path = Path(
        r"C:\claude-work\main-ref\documents\sources\Arch_Combined_Maryborough_Service_Station.pdf"
    )
    if not pdf_path.exists():
        pytest.skip("Original Maryborough PDF not available in current test runtime")

    import fitz

    from pb_vector_geometry_v130 import extract_native_page

    data = pdf_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    doc = fitz.open(stream=data, filetype="pdf")
    page = doc[6]  # page 7
    raw_segs = extract_native_page(page)["segments"]

    obs_records = []
    for idx, primitive in enumerate(raw_segs):
        if not primitive.get("stroke_present") or not primitive.get("width_present"):
            continue
        w = primitive.get("width")
        if w is None:
            continue
        x0, y0, x1, y1 = (
            float(primitive["x1"]),
            float(primitive["y1"]),
            float(primitive["x2"]),
            float(primitive["y2"]),
        )
        rec = _make_obs(
            f"obs_{idx}",
            x0,
            y0,
            x1,
            y1,
            width=float(w),
            sha=sha,
            page="7",
        )
        obs_records.append(rec)

    seed = _make_seed(sha=sha, page="7")
    producer = StructuralWholeOpeningApertureProducer.create()
    apertures = producer.analyze_page(seed, obs_records)

    # We expect authenticated apertures for the major windows on page 7
    # Check that apertures were found and that post gaps were discriminated
    auth = producer.authority()
    subs = auth.all_discriminated_subdivisions()

    # Verify W03/W01 along V in [1343.12, 1550.00]
    w03 = [
        ap
        for ap in apertures
        if ap.axis == "V"
        and abs(ap.aperture_span_along[0] - 1343.12) <= 2.5
        and abs(ap.aperture_span_along[1] - 1550.00) <= 2.5
    ]
    assert len(w03) >= 1
    assert w03[0].status is EvidenceResolutionStatus.CANDIDATE
    assert STRUCTURAL_TERMINAL_JAMB_PROVEN in w03[0].reason_codes
    assert AMBIGUOUS_MULTI_LAYER_OFFSET in w03[0].reason_codes

    # Verify W03 intermediate posts [1410.56, 1413.44] and [1479.68, 1482.32] are discriminated
    w03_subs = [
        s
        for s in subs
        if abs(s.subdivision_span_along[0] - 1410.56) <= 2.5
        or abs(s.subdivision_span_along[0] - 1479.68) <= 2.5
    ]
    assert len(w03_subs) >= 1
    assert all(s.is_internal_subdivision for s in w03_subs)

    # Verify W05 ribbon window along V in [646.40, 1076.48]
    w05 = [
        ap
        for ap in apertures
        if ap.axis == "V"
        and abs(ap.aperture_span_along[0] - 646.40) <= 2.5
        and abs(ap.aperture_span_along[1] - 1076.48) <= 2.5
    ]
    assert len(w05) >= 1
    assert w05[0].status is EvidenceResolutionStatus.CANDIDATE

    # Verify W02 along V in [1557.44, 1789.76]
    w02 = [
        ap
        for ap in apertures
        if ap.axis == "V"
        and abs(ap.aperture_span_along[0] - 1557.44) <= 2.5
        and abs(ap.aperture_span_along[1] - 1789.76) <= 2.5
    ]
    assert len(w02) >= 1
    assert w02[0].status is EvidenceResolutionStatus.CANDIDATE
