"""Legacy ceiling commercial labels must retain exact producer-owned source text.

Source-neutral negatives are integrity checks, not original-positive FIRM proof.
"""
from dataclasses import replace

import pytest

from pb_live_ceiling_area_customer_projection import (
    project_live_ceiling_area_customer_rows,
)
from pb_live_ceiling_area_quantity_publication import (
    publish_live_ceiling_area_quantities,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_area_quantity_publication import (
    _ceiling, _result, _shadow_quantity,
)


class ImportedString(str):
    """Imported string-like data must not become an original source receipt."""


@pytest.mark.parametrize(
    ("field", "forged"),
    (
        ("room_entity_id", ImportedString("room-1")),
        ("finish_descriptor", " plasterboard"),
        ("finish_descriptor", "plasterboard "),
        ("finish_descriptor", ImportedString("plasterboard")),
        ("finish_descriptor", ""),
    ),
)
def test_firm_legacy_ceiling_customer_rejects_repaired_original_label(field, forged):
    ceiling = replace(_ceiling(), **{field: forged})
    result = _result(ceiling=ceiling)
    # Prove this is the actual final customer gate, not an upstream
    # provisional filter. The numeric FIRM issuer has a source quantity.
    quantities = publish_live_ceiling_area_quantities(result)
    assert len(quantities) == 1
    assert quantities[0].value == 13.270425
    original = (ceiling, result.quantity_evidence, result.canonical_ceilings)
    with pytest.raises(
        SourceClosedRunConflictError,
        match="legacy ceiling customer cannot repair original",
    ):
        project_live_ceiling_area_customer_rows(
            result, workspace_id=7, project_id="source-project",
        )
    assert (ceiling, result.quantity_evidence, result.canonical_ceilings) == original


def test_valid_legacy_ceiling_source_labels_keep_exact_sealed_customer_row():
    result = _result()
    first = project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="source-project",
    )
    second = project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="source-project",
    )
    assert first == second
    assert len(first) == 1
    assert first[0]["location"] == "room-1"
    assert first[0]["finish_system"] == "plasterboard"
    assert first[0]["quantity"] == 13.270425


def test_genuine_abstained_original_ceiling_remains_noncommercial():
    original = _shadow_quantity()
    blocked = replace(
        original, abstained=True, value=None,
        blocking_reasons=("source_unresolved",),
    )
    result = _result(shadow=blocked)
    assert project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="source-project",
    ) == ()
