"""Protected original 3Laurel p3 false-box source-role acceptance.

Owner's two false morphological spikes reach north into the dimension strip.
Their native source lines are Annotation_FloorPlan, not wall paint. Only
SHA-verified original source authorizes exact path fixture observations; this
test does not grant a new FIRM exterior footprint or measured customer area.
"""
from __future__ import annotations

import hashlib
import fitz

from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel


def test_original_north_dim_extension_lines_are_not_physical_exterior_walls():
    original = require_original_3laurel()
    raw = original.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=raw, filetype="pdf") as doc:
        assert len(doc) == 18
        drawings = doc[2].get_drawings()
    assert len(drawings) == 11_030
    # Two original dimension extension paths which triggered the owner's
    # unsupported morphological box excursions. These are NOT source walls.
    for path_id, expected_x in ((10847, 370.356), (10853, 219.213)):
        row = drawings[path_id]
        assert row.get("layer") == "Annotation_FloorPlan"
        assert row.get("fill") is None
        assert row.get("type") == "s"
        lines = [part for part in row.get("items", ()) if part and part[0] == "l"]
        assert len(lines) == 1
        a, b = lines[0][1:3]
        assert abs(float(a.x) - expected_x) < 0.01
        assert abs(float(a.x) - float(b.x)) < 0.001
        assert 132.9 < float(a.y) < 133.2
        assert 190.0 < float(b.y) < 193.0

    # Genuine native host and PARTY wall ink must not be suppressed along
    # with the annotations, even though both are black when rendered.
    for path_id in (1027, 1029, 1031, 1139, 1708, 1709):
        row = drawings[path_id]
        assert row.get("layer") == "Enclosure_WallExternal"
        assert row.get("type") == "f"
        assert row.get("fill") == (0.0, 0.0, 0.0)



def test_original_p3_entire_exterior_has_only_source_proven_outside_roles():
    """End-to-end original: two dwellings, no invented join or customer area."""
    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
    from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
    import hashlib

    original = require_original_3laurel()
    raw = original.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=raw, filetype="pdf") as doc:
        page = doc[2]
        paths = tuple(page.get_drawings())
        words = tuple(page.get_text("words"))
    attempt = attempt_source_native_outer_wall_first(
        paths, source_words=words, window_source_drawings=paths,
        source_page_index=2,
    )
    walk = attempt.source_outside_face_walk
    assert walk is not None
    assert walk.status == "CANDIDATE"
    assert walk.enclosed_dwelling_zone_count == 2
    assert walk.unclosed_dwelling_sides == ()
    assert walk.other_source_wall_band_count == 0
    assert walk.source_outside_role_audit_applied is True
    assert walk.source_outside_band_count_before_role_audit >= 11
    assert walk.source_proven_nonwall_band_count == (
        walk.source_outside_band_count_before_role_audit
    )
    assert walk.unresolved_outside_native_path_id_sample == ()
    assert attempt.status == "CANDIDATE"
    assert attempt.reason == "source_closed_painted_wall_ring_needs_exterior_role_authentication"
    assert len(attempt.polygon_pdf_pts) >= 4
    assert len(walk.outer_wall_native_path_ids) >= 4
    assert len(attempt.shared_dwelling_divider_candidates) == 1
    assert not walk.measurement_authorized
    assert not walk.building_footprint_authenticated
    assert not attempt.measurement_authorized
