"""Release gate: only immutable original Lot16 PDF can issue a source replay."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

import tools.diag_gpt3_lot16_max_area_owner_original_replay as original
from tools.diag_gpt3_max_area_review_source_issuer_bijection import (
    ORIGINAL_LOT16_ARCHIVED_EIGHT_FINGERPRINT,
    ORIGINAL_LOT16_SOURCE_SHA256,
)


ARCHIVE = Path("docs/engineering/lot16_original_signed_eight_row_20261015/production")
PRIVATE_ORIGINAL = Path(
    "documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf"
)


def _archive():
    return (
        json.loads((ARCHIVE / "source_sealed_run.json").read_text()),
        json.loads((ARCHIVE / "verified_customer_rows.json").read_text()),
    )


def test_real_original_eight_fingerprint_and_source_sha_are_exact():
    signed, customer = _archive()
    assert signed["fingerprint"] == ORIGINAL_LOT16_ARCHIVED_EIGHT_FINGERPRINT
    assert len(signed["quantities"]) == len(customer) == 8
    assert all(
        item["source_sha256"] == ORIGINAL_LOT16_SOURCE_SHA256
        for item in signed["quantities"]
    )
    assert signed["project_id"] == "au_qld_lot16_power"


@pytest.mark.parametrize("wrong_input", [
    b"%PDF-1.7\nprivate-looking synthetic bytes",
    b"",
    "not-original-pdf",
    None,
    bytearray(b"fake"),
])
def test_owner_source_bytes_must_be_exact_sha_before_any_source_producer(wrong_input,
                                                                      monkeypatch):
    signed, customer = _archive()

    def forbidden(*args, **kwargs):
        raise AssertionError("source producer called before immutable source SHA check")

    monkeypatch.setattr(original, "SourceVisibilityProducer", forbidden)
    with pytest.raises((ValueError, TypeError)):
        original.replay_owner_original_lot16_area_convergence(
            wrong_input, archived_signed_run=signed,
            archived_customer_rows=customer,
        )


@pytest.mark.parametrize("field", ["fingerprint", "project_id", "customer_array"])
def test_original_archive_must_match_predecessor_scope_before_ingestion(field,
                                                                         monkeypatch):
    signed, customer = _archive()
    # Test this archive branch with the synthetic source digest being declared
    # original *only within pytest*; no client PDF or real source grant exists.
    source_bytes = b"synthetic-not-a-client-plan"
    monkeypatch.setattr(original, "ORIGINAL_LOT16_SOURCE_SHA256",
                        sha256(source_bytes).hexdigest())

    def forbidden(*args, **kwargs):
        raise AssertionError("source producer called before immutable archive check")

    monkeypatch.setattr(original, "SourceVisibilityProducer", forbidden)
    if field == "fingerprint":
        signed["fingerprint"] = "0" * 64
    elif field == "project_id":
        signed["project_id"] = "not-Lot16"
    else:
        customer = {"forged": "customer"}
    with pytest.raises(ValueError, match="immutable original Lot16 eight"):
        original.replay_owner_original_lot16_area_convergence(
            source_bytes, archived_signed_run=signed,
            archived_customer_rows=customer,
        )


@pytest.mark.skipif(not PRIVATE_ORIGINAL.is_file(),
                    reason="private original client PDF not on public GitHub runner")
def test_exact_owner_original_page3_full_source_issuer_customer_replay():
    signed, customer = _archive()
    pdf = PRIVATE_ORIGINAL.read_bytes()
    assert sha256(pdf).hexdigest() == ORIGINAL_LOT16_SOURCE_SHA256
    report = original.replay_owner_original_lot16_area_convergence(
        pdf, archived_signed_run=signed, archived_customer_rows=customer,
    )
    assert report["real_original_source_replayed"] is True
    assert report["original_source_customer_retention_unchanged"] is True
    assert report["owner_original_source_sha256"] == ORIGINAL_LOT16_SOURCE_SHA256
    assert report["historical_full_signed_and_customer_bodies_verified"]
    assert report["original_max_source_opening_count"] >= 21
    assert report["original_max_host_binding_count"] >= 15
    assert report["original_max_complete_frame_count"] >= 9
    assert report["real_producer_issued_opening_area_count"] >= 8
    assert report["source_verified_new_quantity_count"] is not None
    assert not report["customer_release_authorized"]
    assert not report["benchmark_score_authorized"]
