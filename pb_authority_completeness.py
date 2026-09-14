"""Deterministic completeness and authenticity contracts for authority universes.

The central invariant is deliberately stronger than "no conflict was supplied":
a FIRM decision must be bound to the exact scoped universe that was enumerated.
All hashes use canonical JSON plus SHA-256.  Python object identity, ``hash()``,
memory addresses, and unordered set serialization are never authority inputs.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

AUTHORITY_COMPLETENESS_SCHEMA_VERSION = "1.0.0"
BOUND_RESOLUTION_SCHEMA_VERSION = "1.0.0"

DOMAIN_WALL_LENGTH_SCALE = "wall_length.scale"
DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES = "wall_length.physical_candidates"


class AuthorityBindingStatus(str, Enum):
    AUTHENTIC = "AUTHENTIC"
    STALE = "STALE"
    UNBOUND = "UNBOUND"
    MISMATCH = "MISMATCH"


@dataclass(frozen=True)
class AuthorityVerification:
    status: AuthorityBindingStatus
    reasons: tuple[str, ...] = ()

    @property
    def authentic(self) -> bool:
        return self.status == AuthorityBindingStatus.AUTHENTIC and not self.reasons


@dataclass(frozen=True)
class AuthorityScope:
    domain: str
    document_id: str
    source_sha256: str
    revision_id: str
    evidence_snapshot_id: str
    graph_snapshot_id: str
    page_id: str
    viewport_id: str
    schema_version: str = AUTHORITY_COMPLETENESS_SCHEMA_VERSION

    def payload(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            "domain": self.domain,
            "document_id": self.document_id,
            "source_sha256": self.source_sha256,
            "revision_id": self.revision_id,
            "evidence_snapshot_id": self.evidence_snapshot_id,
            "graph_snapshot_id": self.graph_snapshot_id,
            "page_id": self.page_id,
            "viewport_id": self.viewport_id,
        }

    def fingerprint(self) -> str:
        return canonical_sha256(self.payload())


@dataclass(frozen=True)
class AuthorityUniverseMember:
    candidate_id: str
    provenance_fingerprint: str


@dataclass(frozen=True)
class AuthorityUniverseFingerprint:
    scope: AuthorityScope
    members: tuple[AuthorityUniverseMember, ...]
    fingerprint: str
    schema_version: str = AUTHORITY_COMPLETENESS_SCHEMA_VERSION


@dataclass(frozen=True)
class ExplicitExclusion:
    candidate_id: str
    reason_code: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class CompletenessManifest:
    scope: AuthorityScope
    discovered_candidate_ids: tuple[str, ...]
    admitted_candidate_ids: tuple[str, ...]
    unresolved_candidate_ids: tuple[str, ...]
    explicit_exclusions: tuple[ExplicitExclusion, ...]
    member_fingerprints: tuple[tuple[str, str], ...]
    authority_universe_fingerprint: str
    manifest_fingerprint: str
    schema_version: str = AUTHORITY_COMPLETENESS_SCHEMA_VERSION


@dataclass(frozen=True)
class BoundResolutionFingerprint:
    scope: AuthorityScope
    candidate_universe_fingerprint: str
    physical_wall_graph_fingerprint: str
    resolver_rule_version: str
    representative_wall_ids: tuple[str, ...]
    member_ids: tuple[str, ...]
    decision_evidence_ids: tuple[str, ...]
    resolution_fingerprint: str
    fingerprint: str
    schema_version: str = BOUND_RESOLUTION_SCHEMA_VERSION


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return _canonicalize(value.value)
    if is_dataclass(value):
        return {
            item.name: _canonicalize(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        raise TypeError("unordered sets are forbidden in authority fingerprints")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite floats are forbidden in authority fingerprints")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported authority fingerprint value: {type(value).__name__}")


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        _canonicalize(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _member_payload(member: AuthorityUniverseMember) -> dict[str, str]:
    return {
        "candidate_id": member.candidate_id,
        "provenance_fingerprint": member.provenance_fingerprint,
    }


def build_authority_universe(
    scope: AuthorityScope,
    members: Sequence[AuthorityUniverseMember],
) -> AuthorityUniverseFingerprint:
    ordered = tuple(sorted(members, key=lambda item: (item.candidate_id, item.provenance_fingerprint)))
    ids = [item.candidate_id for item in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_authority_universe_candidate_id")
    if any(not item.candidate_id or not item.provenance_fingerprint for item in ordered):
        raise ValueError("invalid_authority_universe_member")
    payload = {
        "schema_version": AUTHORITY_COMPLETENESS_SCHEMA_VERSION,
        "scope": scope.payload(),
        "members": [_member_payload(item) for item in ordered],
    }
    return AuthorityUniverseFingerprint(
        scope=scope,
        members=ordered,
        fingerprint=canonical_sha256(payload),
    )


def _exclusion_payload(exclusion: ExplicitExclusion) -> dict[str, Any]:
    return {
        "candidate_id": exclusion.candidate_id,
        "reason_code": exclusion.reason_code,
        "evidence_ids": sorted(exclusion.evidence_ids),
    }


def _manifest_payload(
    *,
    scope: AuthorityScope,
    discovered: Sequence[str],
    admitted: Sequence[str],
    unresolved: Sequence[str],
    exclusions: Sequence[ExplicitExclusion],
    member_fingerprints: Sequence[tuple[str, str]],
    universe_fingerprint: str,
) -> dict[str, Any]:
    return {
        "schema_version": AUTHORITY_COMPLETENESS_SCHEMA_VERSION,
        "scope": scope.payload(),
        "discovered_candidate_ids": sorted(discovered),
        "admitted_candidate_ids": sorted(admitted),
        "unresolved_candidate_ids": sorted(unresolved),
        "explicit_exclusions": [
            _exclusion_payload(item)
            for item in sorted(exclusions, key=lambda item: item.candidate_id)
        ],
        "member_fingerprints": [list(item) for item in sorted(member_fingerprints)],
        "authority_universe_fingerprint": universe_fingerprint,
    }


def build_completeness_manifest(
    universe: AuthorityUniverseFingerprint,
    *,
    admitted_candidate_ids: Sequence[str],
    unresolved_candidate_ids: Sequence[str] = (),
    explicit_exclusions: Sequence[ExplicitExclusion] = (),
) -> CompletenessManifest:
    discovered = tuple(item.candidate_id for item in universe.members)
    admitted = tuple(sorted(str(item) for item in admitted_candidate_ids))
    unresolved = tuple(sorted(str(item) for item in unresolved_candidate_ids))
    exclusions = tuple(sorted(explicit_exclusions, key=lambda item: item.candidate_id))
    excluded = tuple(item.candidate_id for item in exclusions)

    for label, values in (
        ("admitted", admitted),
        ("unresolved", unresolved),
        ("excluded", excluded),
    ):
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate_{label}_candidate_id")

    admitted_set = set(admitted)
    unresolved_set = set(unresolved)
    excluded_set = set(excluded)
    discovered_set = set(discovered)
    if admitted_set & unresolved_set or admitted_set & excluded_set or unresolved_set & excluded_set:
        raise ValueError("authority_universe_partition_overlap")
    if admitted_set | unresolved_set | excluded_set != discovered_set:
        raise ValueError("authority_universe_partition_incomplete")
    if any(not item.reason_code or not item.evidence_ids for item in exclusions):
        raise ValueError("explicit_exclusion_requires_reason_and_evidence")

    member_fingerprints = tuple(
        sorted((item.candidate_id, item.provenance_fingerprint) for item in universe.members)
    )
    payload = _manifest_payload(
        scope=universe.scope,
        discovered=discovered,
        admitted=admitted,
        unresolved=unresolved,
        exclusions=exclusions,
        member_fingerprints=member_fingerprints,
        universe_fingerprint=universe.fingerprint,
    )
    return CompletenessManifest(
        scope=universe.scope,
        discovered_candidate_ids=tuple(sorted(discovered)),
        admitted_candidate_ids=admitted,
        unresolved_candidate_ids=unresolved,
        explicit_exclusions=exclusions,
        member_fingerprints=member_fingerprints,
        authority_universe_fingerprint=universe.fingerprint,
        manifest_fingerprint=canonical_sha256(payload),
    )


def _scope_verification(actual: AuthorityScope, expected: AuthorityScope) -> AuthorityVerification:
    if actual == expected:
        return AuthorityVerification(AuthorityBindingStatus.AUTHENTIC)
    stale_fields = {
        "source_sha256",
        "revision_id",
        "evidence_snapshot_id",
        "graph_snapshot_id",
    }
    actual_payload = actual.payload()
    expected_payload = expected.payload()
    differing = {
        key for key in actual_payload
        if key != "schema_version" and actual_payload[key] != expected_payload[key]
    }
    status = (
        AuthorityBindingStatus.STALE
        if differing and differing.issubset(stale_fields)
        else AuthorityBindingStatus.MISMATCH
    )
    return AuthorityVerification(
        status,
        tuple(sorted(f"authority_scope_{key}_mismatch" for key in differing)),
    )


def verify_completeness_manifest(
    manifest: Optional[CompletenessManifest],
    *,
    current_universe: Optional[AuthorityUniverseFingerprint],
    expected_scope: AuthorityScope,
    supplied_admitted_ids: Sequence[str],
    require_resolved: bool = True,
) -> AuthorityVerification:
    if manifest is None or current_universe is None:
        return AuthorityVerification(
            AuthorityBindingStatus.UNBOUND,
            ("authority_universe_manifest_unbound",),
        )

    scope_check = _scope_verification(manifest.scope, expected_scope)
    if not scope_check.authentic:
        return scope_check
    current_scope_check = _scope_verification(current_universe.scope, expected_scope)
    if not current_scope_check.authentic:
        return current_scope_check

    try:
        rebuilt_universe = build_authority_universe(current_universe.scope, current_universe.members)
    except (TypeError, ValueError) as exc:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            (f"authority_universe_invalid:{exc}",),
        )
    if rebuilt_universe.fingerprint != current_universe.fingerprint:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("authority_universe_fingerprint_mismatch",),
        )
    if manifest.authority_universe_fingerprint != current_universe.fingerprint:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("authority_universe_changed_after_manifest",),
        )

    discovered = tuple(item.candidate_id for item in current_universe.members)
    current_member_fingerprints = tuple(
        sorted((item.candidate_id, item.provenance_fingerprint) for item in current_universe.members)
    )
    if tuple(sorted(manifest.discovered_candidate_ids)) != tuple(sorted(discovered)):
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("authority_universe_discovered_ids_mismatch",),
        )
    if tuple(sorted(manifest.member_fingerprints)) != current_member_fingerprints:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("authority_universe_member_provenance_mismatch",),
        )

    excluded_ids = tuple(item.candidate_id for item in manifest.explicit_exclusions)
    try:
        rebuilt_manifest = build_completeness_manifest(
            current_universe,
            admitted_candidate_ids=manifest.admitted_candidate_ids,
            unresolved_candidate_ids=manifest.unresolved_candidate_ids,
            explicit_exclusions=manifest.explicit_exclusions,
        )
    except (TypeError, ValueError) as exc:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            (f"authority_universe_partition_invalid:{exc}",),
        )
    if rebuilt_manifest.manifest_fingerprint != manifest.manifest_fingerprint:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("completeness_manifest_fingerprint_mismatch",),
        )
    if require_resolved and manifest.unresolved_candidate_ids:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("authority_universe_unresolved_candidates",),
        )
    supplied = tuple(sorted(str(item) for item in supplied_admitted_ids))
    if supplied != tuple(sorted(manifest.admitted_candidate_ids)):
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("authority_universe_admitted_set_mismatch",),
        )
    if len(excluded_ids) != len(set(excluded_ids)):
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("authority_universe_duplicate_exclusion",),
        )
    return AuthorityVerification(AuthorityBindingStatus.AUTHENTIC)


def scale_binding_member(binding: Any) -> AuthorityUniverseMember:
    candidate_id = str(getattr(binding, "scale_fingerprint", "") or "")
    calibration = getattr(binding, "calibration", None)
    payload = {
        "candidate_id": candidate_id,
        "viewport_id": str(getattr(binding, "viewport_id", "") or ""),
        "page_no": int(getattr(binding, "page_no", 0) or 0),
        "source_sha256": str(getattr(binding, "source_sha256", "") or ""),
        "revision_id": str(getattr(binding, "revision_id", "") or ""),
        "scale_fingerprint": candidate_id,
        "measurement_authority": str(getattr(binding, "measurement_authority", "") or ""),
        "blocking_reasons": sorted(tuple(getattr(binding, "blocking_reasons", ()) or ())),
        "calibration": _canonicalize(calibration) if calibration is not None else None,
    }
    return AuthorityUniverseMember(candidate_id, canonical_sha256(payload))


def physical_wall_identity_member(identity: Any) -> AuthorityUniverseMember:
    candidate_id = str(getattr(identity, "wall_candidate_id", "") or "")
    payload = {
        "wall_candidate_id": candidate_id,
        "viewport_id": str(getattr(identity, "viewport_id", "") or ""),
        "candidate_identity_id": getattr(identity, "candidate_identity_id", None),
        "path_fingerprint": getattr(identity, "path_fingerprint", None),
        "source_primitive_ids": sorted(tuple(getattr(identity, "source_primitive_ids", ()) or ())),
        "edge_ids": sorted(tuple(getattr(identity, "edge_ids", ()) or ())),
        "status": getattr(getattr(identity, "status", None), "value", getattr(identity, "status", None)),
        "blocking_reasons": sorted(tuple(getattr(identity, "blocking_reasons", ()) or ())),
        "comparison_mode": str(getattr(identity, "comparison_mode", "") or ""),
        "level_id": getattr(identity, "level_id", None),
        "schema_version": str(getattr(identity, "schema_version", "") or ""),
    }
    return AuthorityUniverseMember(candidate_id, canonical_sha256(payload))


def physical_wall_graph_fingerprint(identities: Sequence[Any]) -> str:
    members = tuple(sorted(
        (physical_wall_identity_member(item) for item in identities),
        key=lambda item: (item.candidate_id, item.provenance_fingerprint),
    ))
    ids = [item.candidate_id for item in members]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_physical_wall_identity_id")
    return canonical_sha256({
        "schema_version": BOUND_RESOLUTION_SCHEMA_VERSION,
        "physical_wall_members": [_member_payload(item) for item in members],
    })


def _resolution_payload(resolution: Any) -> dict[str, Any]:
    groups = [tuple(sorted(str(item) for item in group)) for group in getattr(resolution, "equivalence_groups", ())]
    pairs = [
        (str(left), str(right), str(classification))
        for left, right, classification in getattr(resolution, "pair_classifications", ())
    ]
    blockers = getattr(resolution, "blocking_reasons_by_wall_id", {}) or {}
    return {
        "scope_viewport_id": str(getattr(resolution, "scope_viewport_id", "") or ""),
        "representative_wall_ids": sorted(tuple(getattr(resolution, "representative_wall_ids", ()) or ())),
        "abstained_wall_ids": sorted(tuple(getattr(resolution, "abstained_wall_ids", ()) or ())),
        "equivalence_groups": sorted(groups),
        "ambiguous_wall_ids": sorted(tuple(getattr(resolution, "ambiguous_wall_ids", ()) or ())),
        "same_wall_ids": sorted(tuple(getattr(resolution, "same_wall_ids", ()) or ())),
        "pair_classifications": sorted(pairs),
        "blocking_reasons_by_wall_id": {
            str(key): sorted(tuple(value or ()))
            for key, value in sorted(blockers.items(), key=lambda item: str(item[0]))
        },
        "schema_version": str(getattr(resolution, "schema_version", "") or ""),
    }


def bind_resolution_fingerprint(
    resolution: Any,
    *,
    scope: AuthorityScope,
    candidate_universe: AuthorityUniverseFingerprint,
    identities: Sequence[Any],
    resolver_rule_version: str,
) -> BoundResolutionFingerprint:
    graph_fingerprint = physical_wall_graph_fingerprint(identities)
    member_ids = tuple(sorted(str(getattr(item, "wall_candidate_id", "") or "") for item in identities))
    if len(member_ids) != len(set(member_ids)) or any(not item for item in member_ids):
        raise ValueError("invalid_bound_resolution_member_ids")
    decision_evidence_ids = tuple(sorted({
        str(evidence_id)
        for identity in identities
        for evidence_id in (getattr(identity, "source_primitive_ids", ()) or ())
    }))
    representative_ids = tuple(sorted(tuple(getattr(resolution, "representative_wall_ids", ()) or ())))
    resolution_fingerprint = canonical_sha256(_resolution_payload(resolution))
    payload = {
        "schema_version": BOUND_RESOLUTION_SCHEMA_VERSION,
        "scope": scope.payload(),
        "candidate_universe_fingerprint": candidate_universe.fingerprint,
        "physical_wall_graph_fingerprint": graph_fingerprint,
        "resolver_rule_version": resolver_rule_version,
        "representative_wall_ids": list(representative_ids),
        "member_ids": list(member_ids),
        "decision_evidence_ids": list(decision_evidence_ids),
        "resolution_fingerprint": resolution_fingerprint,
    }
    return BoundResolutionFingerprint(
        scope=scope,
        candidate_universe_fingerprint=candidate_universe.fingerprint,
        physical_wall_graph_fingerprint=graph_fingerprint,
        resolver_rule_version=resolver_rule_version,
        representative_wall_ids=representative_ids,
        member_ids=member_ids,
        decision_evidence_ids=decision_evidence_ids,
        resolution_fingerprint=resolution_fingerprint,
        fingerprint=canonical_sha256(payload),
    )


def verify_bound_resolution_fingerprint(
    resolution: Any,
    bound: Optional[BoundResolutionFingerprint],
    *,
    expected_resolution: Any,
    expected_scope: AuthorityScope,
    candidate_universe: AuthorityUniverseFingerprint,
    identities: Sequence[Any],
    resolver_rule_version: str,
) -> AuthorityVerification:
    if bound is None:
        return AuthorityVerification(
            AuthorityBindingStatus.UNBOUND,
            ("physical_equivalence_authenticity_unproven",),
        )
    scope_check = _scope_verification(bound.scope, expected_scope)
    if not scope_check.authentic:
        return scope_check
    try:
        expected_bound = bind_resolution_fingerprint(
            expected_resolution,
            scope=expected_scope,
            candidate_universe=candidate_universe,
            identities=identities,
            resolver_rule_version=resolver_rule_version,
        )
        supplied_bound = bind_resolution_fingerprint(
            resolution,
            scope=expected_scope,
            candidate_universe=candidate_universe,
            identities=identities,
            resolver_rule_version=resolver_rule_version,
        )
    except (TypeError, ValueError) as exc:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            (f"physical_equivalence_binding_invalid:{exc}",),
        )
    if bound != expected_bound:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("physical_equivalence_bound_fingerprint_mismatch",),
        )
    if supplied_bound.resolution_fingerprint != expected_bound.resolution_fingerprint:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("physical_equivalence_resolution_mismatch",),
        )
    return AuthorityVerification(AuthorityBindingStatus.AUTHENTIC)
