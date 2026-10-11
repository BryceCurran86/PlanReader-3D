"""Fail-closed diagnostic of authentic native G17 opening/source receipts."""
from hashlib import sha256

import pytest

from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_native_dimension_witness import probe_original_native_opening
from test_g17_visible_opening_existence_v1 import _opening_pdf_bytes


@pytest.fixture(scope="module")
def evidence():
    pdf = _opening_pdf_bytes()
    source = SourceVisibilityProducer(
        producer_method="gptmax-diagnostic-test", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gptmax-diagnostic-test", source_bytes=pdf,
        source_locator="memory://gptmax-diagnostic-test.pdf", page_ids=("1",),
    )
    physical = source.physical_opening_authority()
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if result.existence_record is not None:
            return pdf, observation_id, result.existence_record.record_id
    pytest.fail("synthetic G17 fixture produced no original physical opening")


def _run(evidence, **overrides):
    pdf, oid, record = evidence
    args = dict(
        expected_source_sha=sha256(pdf).hexdigest(), page_id="1",
        representative_observation_id=oid, expected_opening_record_id=record,
    )
    args.update(overrides)
    return probe_original_native_opening(pdf, **args)


def test_reproves_native_support_without_minting_a_host_or_quantity(evidence):
    first = _run(evidence)
    assert first == _run(evidence)
    assert first["opening_currently_source_corroborated"] is True
    assert first["opening_source_observation_count"] >= 1
    assert first["physical_host_proven"] is False
    assert first["physical_nonexistence_proven"] is False
    assert first["opening_count_publication_allowed"] is False
    assert first["metric_quantity_publication_allowed"] is False
    assert first["benchmark_accuracy"] is None
    assert first["source_roles_preserved_without_mutation"] is True
    observations = first["opening_source_observations"]
    assert len({r["observation_id"] for r in observations}) == len(observations)
    assert all(len(r["geometry_pt"]) == 4 and r["source_primitive_ref"] for r in observations)
    assert all(atom["status"] == "candidate"
               for atom in first["native_dimension_cap_opposing_atoms"])


@pytest.mark.parametrize("field, bad", [
    ("expected_source_sha", "0" * 64),
    ("representative_observation_id", "source_observation_unknown"),
    ("expected_opening_record_id", "physical_opening_existence_unowned"),
    ("page_id", "4"),
    ("page_id", "not-a-page"),
])
def test_foreign_or_invalid_source_cannot_pass_as_g17_proof(evidence, field, bad):
    with pytest.raises((ValueError, RuntimeError)):
        _run(evidence, **{field: bad})


@pytest.mark.parametrize("invalid", [None, "", {}, bytearray(b"%PDF")])
def test_caller_cannot_substitute_unverified_pdf_descriptor(evidence, invalid):
    pdf, oid, record = evidence
    with pytest.raises((TypeError, ValueError)):
        probe_original_native_opening(
            invalid, expected_source_sha=sha256(pdf).hexdigest(), page_id="1",
            representative_observation_id=oid, expected_opening_record_id=record,
        )
