"""Ceiling customer figured-axis authority cannot normalize original receipts.

Source-neutral adversarial tests. No inferred area, finish, or new FIRM authority.
"""
from dataclasses import replace

import pytest

from pb_live_ceiling_customer_projection import (
    _figured_authority,
    project_live_ceiling_customer_rows,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from test_live_ceiling_lining_source_closed_export import _claim, _quantity


class StrSubclass(str):
    """A text-like imported object is not a native source-owned ID."""


@pytest.mark.parametrize(
    "raw",
    (
        ["dim-h", "dim-v", "dim-h"],
        ("dim-h", "dim-h"),
        ("dim-h",),
        ("dim-h", "dim-v", "dim-x"),
        ("dim-h", " dim-v"),
        ("dim-h", "dim-v "),
        ("dim-h", ""),
        ("dim-h", " "),
        ("dim-h", True),
        ("dim-h", 7),
        ("dim-h", None),
        ("dim-h", StrSubclass("dim-v")),
        ("dim-h", ["dim-v"]),
        "dim-h,dim-v",
        b"dim-h,dim-v",
        None,
        {},
        False,
    ),
)
def test_final_customer_axis_authority_never_repairs_original_pair(raw):
    original = _quantity()
    tampered = replace(
        original,
        metadata={**dict(original.metadata), "figured_dimension_ids": raw},
    )
    before = dict(tampered.metadata)
    assert _figured_authority(tampered) is None
    assert dict(tampered.metadata) == before


@pytest.mark.parametrize("bad_authority", ("pdf_scaled", " documented_dimension", True))
def test_final_customer_axis_authority_requires_original_documented_source(bad_authority):
    original = _quantity()
    tampered = replace(original, authority=bad_authority)
    assert _figured_authority(tampered) is None



def test_original_quantity_constructor_rejects_missing_authority_first():
    original = _quantity()
    with pytest.raises(ValueError, match="authority must be a non-empty string"):
        replace(original, authority=None)

def test_exact_native_two_axis_pair_preserves_original_customer_receipt():
    original = _quantity()
    authority = _figured_authority(original)
    assert authority is not None
    assert authority.method == "figured_dimension"
    assert authority.figured_dimension_ids == ("dim-h", "dim-v")
    reordered = replace(
        original,
        metadata={
            **dict(original.metadata),
            "figured_dimension_ids": ("dim-v", "dim-h"),
        },
    )
    assert _figured_authority(reordered).figured_dimension_ids == (
        "dim-h", "dim-v",
    )

    rows = project_live_ceiling_customer_rows(
        _claim(original), workspace_id=1, project_id="project-1",
    )
    assert len(rows) == 1
    assert rows[0]["quantity_id"] == original.quantity_id
    assert rows[0]["measurement_method"] == "figured_dimension"


@pytest.mark.parametrize("raw", (
    ("dim-h", "dim-v", "dim-h"),
    ("dim-h", " dim-v"),
    ("dim-h", "dim-h"),
))
def test_real_source_to_customer_projection_vetoes_forged_axes_before_seal(raw):
    original = _quantity()
    tampered = replace(
        original,
        metadata={**dict(original.metadata), "figured_dimension_ids": raw},
    )
    before = dict(tampered.metadata)
    with pytest.raises(
        SourceClosedRunConflictError, match="exact figured dimension pair",
    ):
        project_live_ceiling_customer_rows(
            _claim(tampered), workspace_id=1, project_id="project-1",
        )
    assert dict(tampered.metadata) == before


def test_original_abstained_ceiling_still_emits_no_customer_row():
    original = _quantity()
    abstained = replace(
        original, status="blocked", abstained=True, value=None,
        blocking_reasons=("original_source_unresolved",),
    )
    assert project_live_ceiling_customer_rows(
        _claim(abstained), workspace_id=1, project_id="project-1",
    ) == ()
