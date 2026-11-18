"""Shadow: indexed opening↔host correlation to bound hot-path cost.

Cursor-09 (#4537). Replaces repeated O(n×m) host scans with a path-id index.
Preserves identical candidate and ABSTAIN sets — indexing only, no new joins.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpeningHostCorrelationIndex:
    host_to_opening_ids: Mapping[int, tuple[str, ...]]
    opening_to_host_ids: Mapping[str, tuple[int, ...]]
    opening_count: int
    host_count: int
    probe_count: int
    status: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "opening_count": self.opening_count,
            "host_count": self.host_count,
            "probe_count": self.probe_count,
            "host_to_opening_ids": {
                str(k): list(v) for k, v in sorted(self.host_to_opening_ids.items())
            },
            "opening_to_host_ids": {
                k: list(v) for k, v in sorted(self.opening_to_host_ids.items())
            },
            "measurement_authorized": False,
            "commercial_publishable": False,
        }


def build_opening_host_correlation_index(
    openings: Sequence[Mapping[str, Any]],
    *,
    opening_id_key: str = "opening_id",
    host_ids_key: str = "host_path_ids",
) -> OpeningHostCorrelationIndex:
    """Build bidirectional indexes; duplicate opening ids ABSTAIN."""
    opening_to_hosts: dict[str, tuple[int, ...]] = {}
    host_to_openings: dict[int, list[str]] = {}
    probes = 0
    for row in openings:
        if not isinstance(row, Mapping):
            continue
        oid = str(row.get(opening_id_key) or "").strip()
        hosts_raw = row.get(host_ids_key) or ()
        probes += 1
        if not oid:
            continue
        if oid in opening_to_hosts:
            return OpeningHostCorrelationIndex(
                host_to_opening_ids={},
                opening_to_host_ids={},
                opening_count=0,
                host_count=0,
                probe_count=probes,
                status="ABSTAINED",
                reason="duplicate_opening_id_in_correlation_index",
            )
        hosts: list[int] = []
        for value in hosts_raw:
            probes += 1
            if type(value) is int and value >= 0:
                hosts.append(value)
        host_tuple = tuple(sorted(set(hosts)))
        opening_to_hosts[oid] = host_tuple
        for host in host_tuple:
            host_to_openings.setdefault(host, []).append(oid)
    frozen_hosts = {k: tuple(v) for k, v in host_to_openings.items()}
    return OpeningHostCorrelationIndex(
        host_to_opening_ids=frozen_hosts,
        opening_to_host_ids=opening_to_hosts,
        opening_count=len(opening_to_hosts),
        host_count=len(frozen_hosts),
        probe_count=probes,
        status="CANDIDATE",
        reason="opening_host_correlation_index_review_only",
    )


def lookup_openings_for_host(
    index: OpeningHostCorrelationIndex, host_path_id: int,
) -> tuple[str, ...]:
    return tuple(index.host_to_opening_ids.get(int(host_path_id), ()))


def lookup_hosts_for_opening(
    index: OpeningHostCorrelationIndex, opening_id: str,
) -> tuple[int, ...]:
    return tuple(index.opening_to_host_ids.get(str(opening_id), ()))
