"""Unbound floor-area total claims cannot borrow another source receipt."""
from dataclasses import replace
from pb_explicit_floor_area_evidence import (
    ExplicitFloorAreaEvidence, resolve_explicit_floor_area_evidence,
)


def _claim(*, page=1, sha="a"*64, revision="source-revision", area=12.5):
    return ExplicitFloorAreaEvidence(
        area_m2=area, source_pages=(page,),
        raw_evidence=("FLOOR AREA: 12.5m2",),
        source_sha256=sha, revision_id=revision,
    )


def test_two_exact_original_total_repetitions_are_unbound_and_reconciled():
    result=resolve_explicit_floor_area_evidence([_claim(),_claim(page=2)])
    assert result is not None
    assert result.source_pages == (1,2)
    assert result.binding == "unbound"


def test_unscoped_legacy_totals_may_reconcile_without_inventing_ownership():
    result=resolve_explicit_floor_area_evidence([
        _claim(sha=None,revision=None),
        _claim(page=2,sha=None,revision=None),
    ])
    assert result is not None and result.source_sha256 is None
    assert result.revision_id is None


def test_missing_original_source_digest_cannot_borrow_other_pdf():
    assert resolve_explicit_floor_area_evidence([
        _claim(),_claim(page=2,sha=None)
    ]) is None


def test_missing_revision_cannot_be_imputed_by_identical_number():
    assert resolve_explicit_floor_area_evidence([
        _claim(),_claim(page=2,revision=None)
    ]) is None


def test_competing_source_revisions_and_pdf_digests_stay_disputed():
    assert resolve_explicit_floor_area_evidence([
        _claim(),_claim(page=2,sha="b"*64)
    ]) is None
    assert resolve_explicit_floor_area_evidence([
        _claim(),_claim(page=2,revision="other")
    ]) is None


def test_invalid_value_bool_nonfinite_and_missing_page_are_not_reconciled():
    for bad in [True, float("nan"), float("inf"), -1.0, 0.0, "12.5"]:
        assert resolve_explicit_floor_area_evidence([_claim(area=bad)]) is None
    assert resolve_explicit_floor_area_evidence([
        replace(_claim(), source_pages=(True,))
    ]) is None
    assert resolve_explicit_floor_area_evidence([
        replace(_claim(), source_pages=())
    ]) is None


def test_rewritten_nonreconciliation_claims_cannot_enter_area_total_ledger():
    for altered in [
        replace(_claim(), authority="FIRM"),
        replace(_claim(), binding="physical_floor_owned"),
    ]:
        assert resolve_explicit_floor_area_evidence([altered]) is None


def test_malformed_original_source_sha_or_revision_cannot_reconcile_even_if_values_agree():
    for sha in ("", "A"*64, "g"*64, "0123", True):
        assert resolve_explicit_floor_area_evidence([
            _claim(sha=sha), _claim(page=2,sha=sha)
        ]) is None
    for rev in ("", " padded ", True, 45):
        assert resolve_explicit_floor_area_evidence([
            _claim(revision=rev),_claim(page=2,revision=rev)
        ]) is None
