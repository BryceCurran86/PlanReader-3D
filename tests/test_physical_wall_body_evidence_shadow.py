"""
tests/test_physical_wall_body_evidence_shadow.py

Test suite for SHADOW-ONLY physical wall-body evidence authority.

This suite MUST NOT:
    - assert any opening existence
    - assert any host binding
    - assert any wall equivalence
    - assert any net-wall or gross-wall geometry
    - assert any commercial predictions
    - assert benchmark outputs

It MUST:
    - assert correct EvidenceResolutionStatus
    - assert correct reason_codes
    - assert correct negative-evidence rejection
    - assert correct topology gating
    - assert correct thickness-family behaviour
    - assert correct segmentation-support behaviour
    - assert correct fail-closed behaviour

---------------------------------------------------------------------------
Test Groups
---------------------------------------------------------------------------
"""

import pytest


pytestmark = pytest.mark.skip(
    reason="SHADOW scaffold only; assertions are intentionally not implemented yet"
)


def test_double_face_wall_band_positive():
    """Parallel faces + bounded separation + overlap + topology → CORROBORATED."""


def test_single_face_ghazi_style_wall_positive():
    """Continuous raster band + segmentation support + topology → CORROBORATED."""


def test_fixture_double_lines_rejected():
    """Short double lines with no topology → ABSTAINED + NEGATIVE_LOCAL_FIXTURE_PATTERN_DETECTED."""


def test_table_grid_rejected():
    """Regular grid → ABSTAINED + NEGATIVE_TABLE_GRID_PATTERN_DETECTED."""


def test_paving_pattern_rejected():
    """Dense paving hatch → ABSTAINED + NEGATIVE_PAVING_PATTERN_DETECTED."""


def test_dimension_lines_rejected():
    """Thin arrowed dimension lines → ABSTAINED + NEGATIVE_DIMENSION_LINE_PATTERN_DETECTED."""


def test_structural_grid_rejected():
    """Grid lines with bubbles → ABSTAINED + NEGATIVE_STRUCTURAL_GRID_PATTERN_DETECTED."""


def test_thickness_family_match():
    """Consistent separations → CORROBORATED + THICKNESS_FAMILY_MATCH_CONFIRMED."""


def test_thickness_family_ambiguous():
    """Mixed separations → ABSTAINED + THICKNESS_FAMILY_AMBIGUOUS."""


def test_room_enclosure_cycle_positive():
    """Closed room-scale cycle → CORROBORATED + ROOM_ENCLOSURE_CYCLE_CONFIRMED."""


def test_cropped_plan_local_corrob_no_completeness():
    """
    Local bands CORROBORATED.
    No global completeness implied.
    reason_codes include NETWORK_INCOMPLETE_FOR_SCOPE.
    """


def test_segmentation_support_positive():
    """Wall mask supports band → CORROBORATED + SEGMENTATION_SUPPORT_CONFIRMED."""


def test_segmentation_support_insufficient():
    """Fragmented mask → ABSTAINED + SEGMENTATION_SUPPORT_INSUFFICIENT."""


def test_opening_local_topology_present_but_no_opening_authority():
    """
    Jamb + gap + glazing pattern inside proven band.
    CORROBORATED + OPENING_LOCAL_TOPOLOGY_PRESENT.
    MUST NOT modify opening existence or host binding.
    """


def test_ambiguous_double_line_pattern():
    """Double lines with no positive evidence → ABSTAINED + NEGATIVE_AMBIGUOUS_DOUBLE_LINE_PATTERN_DETECTED."""
