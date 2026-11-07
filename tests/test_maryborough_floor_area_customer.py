"""The quarantined subset must never borrow a larger unverified source seal."""
from __future__ import annotations

import pytest

import pb_maryborough_floor_area_customer as wrapper
from pb_maryborough_customer_authority import MaryboroughCustomerResult
from tests.test_maryborough_customer_authority import (
    _assert_empty_abstain,
    _known_fixture,
)


def test_subset_for_known_source_stays_empty_without_physical_authority(
    tmp_path, monkeypatch,
):
    path = _known_fixture(tmp_path, monkeypatch)
    result = wrapper.issue_original_maryborough_floor_customer_areas(path)
    _assert_empty_abstain(result)


@pytest.mark.parametrize("status", ["FIRM_SOURCE_CUSTOMER_TO_REVIEW", "CANDIDATE", "ABSTAIN"])
def test_unexpected_upstream_rows_or_seal_cannot_reactivate_subset(
    monkeypatch, status,
):
    # An upstream status string and a retained whole-result seal are not
    # physical subset authority. No part of this untrusted envelope may leak.
    upstream = MaryboroughCustomerResult(
        status, ("unverified_upstream",),
        quantities=(object(),), traces=(object(),),
        sealed_run=object(),
        customer_rows=({"quantity_id": "unverified-whole-row"},),
        identity_map_bindings=({"unverified": True},),
    )
    monkeypatch.setattr(
        wrapper, "issue_all_original_maryborough_customer_quantities",
        lambda *_args, **_kwargs: upstream,
    )
    result = wrapper.issue_original_maryborough_floor_customer_areas("unused.pdf")
    _assert_empty_abstain(result)
    assert result.reason_codes == ("source_owned_floor_subset_authority_unavailable",)
    assert upstream.sealed_run is not None
    assert upstream.customer_rows


def test_even_an_unverified_firm_status_without_rows_is_not_subset_authority(monkeypatch):
    upstream = MaryboroughCustomerResult("FIRM_SOURCE_CUSTOMER_TO_REVIEW", ())
    monkeypatch.setattr(
        wrapper, "issue_all_original_maryborough_customer_quantities",
        lambda *_args, **_kwargs: upstream,
    )
    _assert_empty_abstain(
        wrapper.issue_original_maryborough_floor_customer_areas("unused.pdf"),
    )


def test_clean_abstention_is_preserved_without_manufacturing_a_seal(monkeypatch):
    upstream = MaryboroughCustomerResult("ABSTAIN", ("source_owner_missing",))
    monkeypatch.setattr(
        wrapper, "issue_all_original_maryborough_customer_quantities",
        lambda *_args, **_kwargs: upstream,
    )
    result = wrapper.issue_original_maryborough_floor_customer_areas("unused.pdf")
    assert result is upstream
    _assert_empty_abstain(result)


def test_invalid_subset_workspace_never_calls_the_upstream_issuer(monkeypatch):
    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("an invalid workspace reached the upstream issuer")
    monkeypatch.setattr(
        wrapper, "issue_all_original_maryborough_customer_quantities", unexpected_call,
    )
    result = wrapper.issue_original_maryborough_floor_customer_areas(
        "unused.pdf", workspace_id=True,
    )
    _assert_empty_abstain(result)
