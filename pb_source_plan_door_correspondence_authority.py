"""Source-owned architectural plan door-tag to schedule-row correspondence.

This read-only bridge uses the existing SourceVisibilityProducer and A600
source schedule publisher, on the SAME original PDF revision/snapshot. A Dxx
tag on a floor plan and a same-code schedule row corroborate a printed code
only, NEVER a unique physical door symbol, structural host, installation
count, opening area, customer scope or frozen benchmark item.

No nearest label, inferred missing code, default count of one, or source
document re-interpretation is permitted.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import re

from pb_source_door_schedule_authority import (
    SourceDoorScheduleResult,
    SourceDoorScheduleWord,
    _producer_owned_native_words,
    inspect_published_door_schedule,
)
from pb_source_visibility_authority import SourceVisibilityProducer

_DOOR_CODE = re.compile(r"^D(?:0[1-9]|[1-9][0-9]*)$")


@dataclass(frozen=True)
class SourcePlanDoorCodePair:
    code: str
    plan_page_id: str
    schedule_page_id: str
    plan_word_observation_ids: tuple[str, ...]
    schedule_word_observation_ids: tuple[str, ...]
    plan_native_word_addresses: tuple[tuple[int, int, int], ...]
    schedule_source_row_status: str | None
    source_code_correspondence_proven: bool
    first_unclosed_gate: str
    physical_door_symbol_bound: bool = False
    structural_host_bound: bool = False
    opening_count: int | None = None
    installed_opening_area_m2: float | None = None
    customer_quantity_authorized: bool = False


@dataclass(frozen=True)
class SourcePlanDoorCorrespondence:
    source_sha256: str
    revision_id: str
    snapshot_id: str
    plan_page_id: str
    schedule_page_id: str
    source_plan_observation_universe_complete: bool
    source_schedule_observation_universe_complete: bool
    pairs: tuple[SourcePlanDoorCodePair, ...]
    unresolved_codes: tuple[str, ...]
    eligible_printed_code_pair_count: int
    new_opening_counts: int = 0
    new_opening_area_quantities: int = 0
    frozen_benchmark_accuracy: float | None = None


def pair_trusted_original_door_codes(
    *, plan_words: tuple[SourceDoorScheduleWord, ...],
    schedule: SourceDoorScheduleResult,
    plan_page_id: str,
) -> SourcePlanDoorCorrespondence:
    """Retain missing, repeated and untrusted source labels as explicit rivals."""
    if (
        type(plan_words) is not tuple
        or type(schedule) is not SourceDoorScheduleResult
        or type(plan_page_id) is not str or not plan_page_id.isdecimal()
        or plan_page_id != str(int(plan_page_id)) or int(plan_page_id) < 1
        or plan_page_id == schedule.page_id
    ):
        raise ValueError("source-owned distinct plan/schedule page required")
    plan_by_code: dict[str, list[SourceDoorScheduleWord]] = defaultdict(list)
    exact_addresses: set[tuple[int, int, int]] = set()
    seen_observation_ids: set[str] = set()
    for word in plan_words:
        if type(word) is not SourceDoorScheduleWord or word.page_id != plan_page_id:
            raise ValueError("source plan word from foreign page or issuer")
        if word.partition_id != "page:" + plan_page_id:
            raise ValueError("source plan word partition conflict")
        if (
            not word.observation_id or word.observation_id in seen_observation_ids
            or type(word.block_no) is not int or type(word.line_no) is not int
            or type(word.word_no) is not int
            or any(v < 0 for v in (word.block_no, word.line_no, word.word_no))
        ):
            raise ValueError("duplicate or invalid source plan text observation")
        seen_observation_ids.add(word.observation_id)
        address = (word.block_no, word.line_no, word.word_no)
        if address in exact_addresses:
            raise ValueError("duplicate native text address in source plan")
        exact_addresses.add(address)
        if _DOOR_CODE.fullmatch(word.literal):
            plan_by_code[word.literal].append(word)

    schedule_by_code: dict[str, list] = defaultdict(list)
    for row in schedule.rows:
        if row.source_page_id != schedule.page_id or not _DOOR_CODE.fullmatch(row.code):
            raise ValueError("foreign or malformed source schedule row")
        schedule_by_code[row.code].append(row)

    # An accepted schedule row must not erase a competing source-visible
    # occurrence which the schedule publisher could not parse. Nor may two
    # independently named door rows share one source word receipt.
    unparsed_codes = set(schedule.unparsed_original_door_codes)
    original_census_codes = set(schedule.all_original_source_codes)
    shared_schedule_observation_codes: set[str] = set()
    observation_owners: dict[str, set[str]] = defaultdict(set)
    for code, schedule_rows in schedule_by_code.items():
        for source_row in schedule_rows:
            for observation_id in source_row.observation_ids:
                if type(observation_id) is str and observation_id:
                    observation_owners[observation_id].add(code)
                else:
                    shared_schedule_observation_codes.add(code)
            if len(set(source_row.observation_ids)) != len(source_row.observation_ids):
                shared_schedule_observation_codes.add(code)
    for owners in observation_owners.values():
        if len(owners) > 1:
            shared_schedule_observation_codes.update(owners)

    universe = sorted(
        set(plan_by_code) | original_census_codes | set(schedule_by_code)
        | unparsed_codes
    )
    rows: list[SourcePlanDoorCodePair] = []
    unresolved: list[str] = []
    for code in universe:
        tags = plan_by_code[code]
        schedule_rows = schedule_by_code[code]
        status = schedule_rows[0].status if len(schedule_rows) == 1 else None
        valid_schedule = (
            len(schedule_rows) == 1
            and schedule.title_source_trusted
            and schedule.complete_source_word_universe
            and status == "source_schedule_row_text_authenticated"
            and all(
                type(x) is str and bool(x) for x in schedule_rows[0].observation_ids
            )
        )
        if not tags:
            failure = "original_plan_door_tag_missing"
        elif len(tags) != 1:
            failure = "original_plan_door_tag_ambiguous_or_repeated"
        elif not tags[0].trusted:
            failure = "original_plan_text_integrity_unverified"
        elif code in unparsed_codes:
            failure = "original_schedule_competing_unparsed_code"
        elif code in shared_schedule_observation_codes:
            failure = "original_schedule_shared_word_observation_conflict"
        elif code not in original_census_codes:
            failure = "original_schedule_code_absent_from_complete_census"
        elif len(schedule_rows) != 1:
            failure = "original_schedule_row_missing_or_competing"
        elif not valid_schedule:
            failure = "original_schedule_row_or_universe_unverified"
        else:
            failure = "physical_door_symbol_host_and_customer_scope_unproven"
        positive = failure == "physical_door_symbol_host_and_customer_scope_unproven"
        if not positive:
            unresolved.append(code)
        rows.append(SourcePlanDoorCodePair(
            code=code,
            plan_page_id=plan_page_id,
            schedule_page_id=schedule.page_id,
            plan_word_observation_ids=tuple(w.observation_id for w in tags),
            schedule_word_observation_ids=(
                schedule_rows[0].observation_ids if len(schedule_rows) == 1 else ()
            ),
            plan_native_word_addresses=tuple(
                (w.block_no, w.line_no, w.word_no) for w in tags
            ),
            schedule_source_row_status=status,
            source_code_correspondence_proven=positive,
            first_unclosed_gate=failure,
        ))
    return SourcePlanDoorCorrespondence(
        source_sha256=schedule.source_sha256,
        revision_id=schedule.revision_id,
        snapshot_id=schedule.snapshot_id,
        plan_page_id=plan_page_id,
        schedule_page_id=schedule.page_id,
        source_plan_observation_universe_complete=False,
        source_schedule_observation_universe_complete=(
            schedule.complete_source_word_universe and schedule.title_source_trusted
        ),
        pairs=tuple(rows),
        unresolved_codes=tuple(unresolved),
        eligible_printed_code_pair_count=sum(x.source_code_correspondence_proven for x in rows),
    )


def inspect_published_plan_and_schedule_door_codes(
    producer: SourceVisibilityProducer, *,
    revision_id: str, plan_page_id: str, schedule_page_id: str,
) -> SourcePlanDoorCorrespondence:
    """Read both page inventories from one producer-issued immutable snapshot."""
    if type(producer) is not SourceVisibilityProducer:
        raise TypeError("source visibility issuer required")
    published = producer.published_snapshot_for_revision(revision_id)
    if published is None:
        raise ValueError("source revision missing from active producer")
    for page_id in (plan_page_id, schedule_page_id):
        if (
            type(page_id) is not str or not page_id.isdecimal()
            or page_id != str(int(page_id)) or int(page_id) < 1
            or int(page_id) not in {int(x) for x in published.coverage.decoded_pages}
        ):
            raise ValueError("source plan or schedule page not in published coverage")
    if plan_page_id == schedule_page_id:
        raise ValueError("plan and schedule pages must be independently source-addressed")
    schedule = inspect_published_door_schedule(
        producer, revision_id=revision_id, page_id=schedule_page_id,
    )
    if (
        schedule.revision_id != published.revision.revision_id
        or schedule.snapshot_id != published.snapshot.snapshot_id
        or schedule.source_sha256 != published.revision.source_sha256
    ):
        raise ValueError("cross-document source snapshot or revision conflict")
    plan_words = _producer_owned_native_words(producer, published, plan_page_id)
    # A caller-curated subset may prove an individual printed correspondence,
    # but ONLY the issuer's complete published word universe may claim a
    # complete source census. Do not expose a caller-controlled completeness
    # boolean to downstream count/quantity producers.
    return replace(
        pair_trusted_original_door_codes(
            plan_words=plan_words, schedule=schedule, plan_page_id=plan_page_id,
        ),
        source_plan_observation_universe_complete=True,
    )


__all__ = [
    "SourcePlanDoorCodePair",
    "SourcePlanDoorCorrespondence",
    "pair_trusted_original_door_codes",
    "inspect_published_plan_and_schedule_door_codes",
]
