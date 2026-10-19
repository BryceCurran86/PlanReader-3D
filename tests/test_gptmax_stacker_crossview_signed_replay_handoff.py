"""STACKER original p3/p5 label source is consumed by the SAME signed replay.

Test-only fakes exercise the composition wiring without inventing physical
opening, wall host, metric, count or customer issuance.
"""
from hashlib import sha256
from types import SimpleNamespace

import pytest

from tools import diag_gptmax_unmeasured_flank_capture_shadow as audit


def _source(sha, name):
    return SimpleNamespace(
        revision=SimpleNamespace(source_sha256=sha),
        snapshot=SimpleNamespace(snapshot_id="source-"+name),
    )


def _parity():
    return {
        "original_authority":{"quantities":{"original_exact":True}},
        "signed_customer_exact":{
            "customer_rows":True,"sealed_run":True,
            "customer_verification":True,
        },
        "all_original_issuer_receipts_exact":True,
    }


def test_signed_old_eight_and_native_crossview_are_one_opt_in_original_replay(monkeypatch):
    raw=b"synthetic bytes, never an authenticated original"
    digest=sha256(raw).hexdigest()
    called=[]
    comp=SimpleNamespace(opening_bindings=[])
    def fake_producer(data, sha, *, shadow, **options):
        called.append((data,sha,shadow,dict(options)))
        return (_source(sha,"shadow" if shadow else "original"),
                comp, {"signed":8})
    monkeypatch.setattr(audit,"_one_source_policy",fake_producer)
    monkeypatch.setattr(audit,"compare_original_g17_release_receipts",
                        lambda a,b:_parity())
    monkeypatch.setattr(audit,"_original_eight_firm_customer_retention",
                        lambda a,b,p:True)
    monkeypatch.setattr(audit,"source_verified_stacker_image_frame",
                        lambda data:{"single_native_image_frame_proven":True})
    def source_crossview(data):
        assert data is raw
        return {
            "source_sha256":digest,
            "native_marks":[{"page_number":3},{"page_number":5}],
            "exact_cross_page_physical_identity_proven":False,
            "unique_structural_host_proven":False,
            "quantity_promotion_granted":False,
        }
    monkeypatch.setattr(audit,"original_2127_crossview_receipt",source_crossview)
    report=audit.replay_opt_in(raw,expected_sha256=digest)
    assert len(called)==2 and [v[2] for v in called]==[False,True]
    assert report["original_8_signed_areas_proven_unchanged"] is True
    assert report["original_quantity_receipt_retention_proven"] is True
    native=report["stacker_2127_original_crossview_native_label_source"]
    assert native["source_sha256"]==report["source_sha256"]==digest
    assert [v["page_number"] for v in native["native_marks"]]==[3,5]
    assert native["exact_cross_page_physical_identity_proven"] is False
    assert native["unique_structural_host_proven"] is False
    assert native["quantity_promotion_granted"] is False
    assert report["new_metric_handoff_granted"] is False
    assert report["new_signed_area_granted"] is False
    assert report["new_benchmark_match_granted"] is False
    assert report["global_capture_default_changed"] is False


def test_native_crossview_gate_aborts_replay_on_false_original_label(monkeypatch):
    raw=b"not the original source"
    digest=sha256(raw).hexdigest()
    comp=SimpleNamespace(opening_bindings=[])
    monkeypatch.setattr(
        audit,"_one_source_policy",
        lambda data,sha,*,shadow,**kwargs: (_source(sha,"s"),comp,{"signed":8}),
    )
    monkeypatch.setattr(audit,"compare_original_g17_release_receipts",
                        lambda a,b:_parity())
    monkeypatch.setattr(audit,"_original_eight_firm_customer_retention",
                        lambda a,b,p:True)
    monkeypatch.setattr(audit,"source_verified_stacker_image_frame",
                        lambda data:{"single_native_image_frame_proven":True})
    def reject(data):
        raise ValueError("unique native 2127 STACKER mark is unproved")
    monkeypatch.setattr(audit,"original_2127_crossview_receipt",reject)
    with pytest.raises(ValueError,match="unique native 2127 STACKER"):
        audit.replay_opt_in(raw,expected_sha256=digest)
