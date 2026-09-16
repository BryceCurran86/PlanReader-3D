"""Frozen collection surface for Opening Vertical Placement Authority V1.

TEST ONLY / EXPECTED RED ON BASELINE / DO NOT MERGE.

This module intentionally re-exports the independently reviewed core validator and
its supplemental attacks so the replay harness can pin one immutable blob while
executing the complete validator bundle.
"""
from tests.test_opening_vertical_placement_authority_validator_v1 import *  # noqa: F403
from tests.test_opening_vertical_placement_authority_validator_v1_supplemental import *  # noqa: F403
