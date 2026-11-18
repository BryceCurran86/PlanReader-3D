"""GPT2-25: exact original opening candidate suppression parity.

All candidates carry synthetic source observation IDs. This tests the active
source-to-opening producer's combinatorial path without private plan data,
modified benchmark truth, or inferred opening/quantity authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import random

import pytest

from pb_physical_opening_authority import PhysicalOpeningAuthority


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    support_ids: tuple[str, ...]
    accesses: list[int] | None = None

    @property
    def source_observation_ids(self) -> tuple[str, ...]:
        if self.accesses is not None:
            self.accesses[0] += 1
        return self.support_ids


def _run(monkeypatch, strong, generic):
    monkeypatch.setattr(
        PhysicalOpeningAuthority,
        "_visible_structural_candidates",
        staticmethod(lambda _seed, _records: tuple(strong)),
    )
    monkeypatch.setattr(
        PhysicalOpeningAuthority,
        "_visible_generic_correlated_candidates",
        staticmethod(lambda _seed, _records: tuple(generic)),
    )
    # The production method only requests seed/records from the two verified
    # candidate producers; this avoids forged source authority in the test.
    return PhysicalOpeningAuthority._visible_all_structural_candidates(None, ())


def _reference(strong, generic):
    supports = [set(item.source_observation_ids) for item in strong]
    retained = [
        item for item in generic
        if not any(set(item.source_observation_ids) <= support for support in supports)
    ]
    by_id = {item.candidate_id: item for item in (*strong, *retained)}
    return tuple(by_id[key] for key in sorted(by_id))


@pytest.mark.parametrize(
    "strong,generic",
    [
        ((), (_Candidate("no-strong", ()),)),
        ((_Candidate("empty-strong", ()),), (_Candidate("empty-generic", ()),)),
        ((_Candidate("strong", ("a", "b", "c")),), (
            _Candidate("covered", ("b", "a")),
            _Candidate("not-covered", ("b", "d")),
            _Candidate("empty", ()),
        )),
        ((_Candidate("strong-a", ("a",)), _Candidate("strong-b", ("b",))), (
            _Candidate("union-not-covered", ("a", "b")),
            _Candidate("missing", ("no-evidence",)),
        )),
        ((_Candidate("shared", ("a", "b")),), (
            _Candidate("shared", ("b", "a")),
            _Candidate("duplicate-members", ("a", "a")),
            _Candidate("competing", ("x",)),
        )),
    ],
)
def test_support_containment_preserves_existing_candidate_semantics(
    monkeypatch, strong, generic
):
    assert _run(monkeypatch, strong, generic) == _reference(strong, generic)


@pytest.mark.parametrize("seed", [1, 2, 3, 17, 83, 20261119])
def test_index_parity_with_disjoint_ambiguous_and_overlapping_supports(monkeypatch, seed):
    rng = random.Random(seed)
    universe = tuple(f"source-{i}" for i in range(90))

    def rows(prefix, count):
        return tuple(
            _Candidate(
                f"{prefix}-{index % 37}",  # intentional candidate-ID collisions
                tuple(rng.choices(universe, k=rng.randrange(0, 7))),
            )
            for index in range(count)
        )

    strong = rows("strong", 80)
    generic = rows("generic", 160) + (
        _Candidate("strong-0", ("unmatched",)),
    )
    assert _run(monkeypatch, strong, generic) == _reference(strong, generic)


def test_large_disjoint_source_universe_avoids_quadratic_support_reads(monkeypatch):
    source_reads = [0]
    strong = tuple(
        _Candidate(f"strong-{i}", (f"strong-source-{i}",), source_reads)
        for i in range(600)
    )
    generic = tuple(
        _Candidate(f"generic-{i}", (f"generic-source-{i}",), source_reads)
        for i in range(600)
    )
    result = _run(monkeypatch, strong, generic)

    assert len(result) == 1200
    assert {item.candidate_id for item in result} == {
        *(item.candidate_id for item in strong),
        *(item.candidate_id for item in generic),
    }
    # A full cross-product repeats generic support extraction ~360k times.
    # The indexed live path reads each producer's support only once.
    assert source_reads[0] <= len(strong) + len(generic) + 2



def test_indexed_combination_matches_reference_from_an_ingested_pdf_snapshot():
    """Real native-PDF ingest, no private source or FIRM customer promotion."""
    import fitz

    from pb_source_observation_authority import ObservationSelector
    from pb_source_visibility_authority import SourceVisibilityProducer

    doc = fitz.open()
    page = doc.new_page(width=680, height=430)
    for start, end in (
        ((50, 100), (180, 100)),
        ((240, 100), (400, 100)),
        ((50, 124), (180, 124)),
        ((240, 124), (400, 124)),
        ((180, 100), (180, 124)),
        ((240, 100), (240, 124)),
        ((50, 230), (190, 230)),
        ((50, 250), (190, 250)),
    ):
        page.draw_line(fitz.Point(*start), fitz.Point(*end), width=1.0)
    original_pdf = doc.tobytes()
    doc.close()

    source = SourceVisibilityProducer(
        producer_method="gpt2-support-index-source-parity",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gpt2-support-index-test-document",
        source_bytes=original_pdf,
        source_locator="memory://gpt2-support-index-source.pdf",
    )
    authority = PhysicalOpeningAuthority(source.authority())
    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=published.visible_observation_ids[0],
    )
    observed = source.authority().resolve_visible(selector)
    assert observed.observation is not None
    records, failures = authority._visible_snapshot_records(observed)
    assert not failures
    strong = authority._visible_structural_candidates(observed.observation, records)
    generic = authority._visible_generic_correlated_candidates(
        observed.observation, records
    )
    actual = authority._visible_all_structural_candidates(
        observed.observation, records
    )
    assert actual == _reference(strong, generic)
    # Source IDs and candidate source provenance are not rewritten by indexing.
    assert all(
        item.source_sha256 == published.revision.source_sha256
        for item in actual
    )
