"""The actual source-issued area preflight, never a shadow guess, is final."""
from dataclasses import MISSING, fields, replace

import pytest

from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject, LivePhysicalOpeningVoidComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt1_opening_area_actual_issuer_preflight_shadow import (
    reconcile_gpt1_area_review_with_issuer,
)
from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture, run


def _typed(canonical):
    """Model the actual immutable canonical dataclass, not producer authority."""
    rows=[]
    for item in canonical:
        vals={
            "semantic_class":"physical_opening",
            "structural_pattern":item.get("structural_pattern") or "",
            "source_lineage_root_ids":("source-own-1",),
            "source_geometries":(),
            "schedule_count_explicit":False,
            "schedule_row_observation_ids":(),
        }
        vals.update(item)
        for field in fields(LiveCanonicalOpeningObject):
            if field.name not in vals:
                if field.default is not MISSING:
                    vals[field.name]=field.default
                elif field.name.endswith("_ids"):
                    vals[field.name]=()
                elif field.name in ("geometry_complete","schedule_count_explicit"):
                    vals[field.name]=False
                else:
                    vals[field.name]=None
        vals["evidence_ids"]=tuple(vals["evidence_ids"])
        vals["source_observation_ids"]=tuple(vals["source_observation_ids"])
        rows.append(LiveCanonicalOpeningObject(**{
            f.name:vals[f.name] for f in fields(LiveCanonicalOpeningObject)
        }))
    return LivePhysicalOpeningVoidComposition(
        revision_id=canonical[0]["revision_id"],
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(),
        traces=(),
        physical_opening_void_authorities={},
        void_selectors={},
        canonical_openings=tuple(rows),
    )


def _original_case():
    rows,c=fixture()
    rows[2]["frame_record"]=None
    c[2]["host_frame_record_id"]=None
    return rows,c


def test_real_typed_opening_area_issuer_matches_only_source_review_ready():
    rows,c=_original_case()
    source=run(rows,c)
    real=_typed(c)
    q=_opening_quantity(real.canonical_openings[2])
    assert q is not None
    assert q.semantic_key=="window_area:physical-3"
    assert q.value==2.16 and q.unit=="m2"
    assert q.input_entity_ids==("physical-3",)
    assert q.metadata["area_basis"]=="figured_opening_label"
    pre=reconcile_gpt1_area_review_with_issuer(real,source)
    assert pre["source_review_issuer_compatible_ids"] == ["physical-3"]
    assert pre["measurement_published"] is False
    assert pre["customer_seal_granted"] is False
    assert pre["opening_count_granted"] is False
    assert pre["shadow_only"]


@pytest.mark.parametrize("tamper", [
    lambda o:replace(o,area_m2=None),
    lambda o:replace(o,area_m2=8.82),
    lambda o:replace(o,area_basis="resolved_opening_geometry"),
    lambda o:replace(o,representative_observation_id="foreign"),
    lambda o:replace(o,source_observation_ids=()),
    lambda o:replace(o,viewport_id=""),
    lambda o:replace(o,host_binding_record_id="unowned-host"),
    lambda o:replace(o,source_sha256="0"*64),
])
def test_forged_publisher_relevant_field_cannot_pass_shadow_parity(tamper):
    rows,c=_original_case()
    source=run(rows,c)
    real=_typed(c)
    changed=list(real.canonical_openings)
    changed[2]=tamper(changed[2])
    fake=replace(real,canonical_openings=tuple(changed))
    with pytest.raises((ValueError, RuntimeError)):
        reconcile_gpt1_area_review_with_issuer(fake,source)


def test_preexisting_original_signed_quantity_not_rediscovered():
    rows,c=_original_case()
    rows[2]["quantity_id"]="existing-source-sealed"
    source=run(rows,c)
    output=reconcile_gpt1_area_review_with_issuer(_typed(c),source)
    assert output["source_review_issuer_compatible_ids"] == []
    assert output["issuer_compatible_but_source_abstained_ids"] == []


def test_one_unknown_original_opening_cannot_be_silently_dropped():
    rows,c=_original_case()
    source=run(rows,c)
    physical=_typed(c)
    narrower=replace(physical,canonical_openings=physical.canonical_openings[:-1])
    with pytest.raises(ValueError,match="inventory mismatch"):
        reconcile_gpt1_area_review_with_issuer(narrower,source)


def test_review_only_no_extra_3d_count_or_customer_authority():
    rows,c=_original_case()
    source=run(rows,c)
    pre=reconcile_gpt1_area_review_with_issuer(_typed(c),source)
    assert pre["benchmark_score_granted"] is False
    assert pre["measurement_published"] is False
    assert pre["opening_count_granted"] is False
    assert pre["customer_seal_granted"] is False
