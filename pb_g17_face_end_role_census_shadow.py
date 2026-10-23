"""Census FACE/END roles on G17 support observations for unhosted openings."""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority


def census_g17_face_end_roles_shadow(
    *,
    composition: object,
    published: object,
    physical_opening_ids: Sequence[str],
) -> dict[str, Any]:
    revision = published.revision
    snapshot = published.snapshot
    opening_authority = composition.physical_opening_authority
    visibility = opening_authority.source_visibility_authority()
    if type(visibility) is not SourceVisibilityAuthority:
        raise TypeError("SourceVisibilityAuthority required")

    kind_counts: Counter[str] = Counter()
    openings: list[dict[str, Any]] = []
    for oid in sorted({str(x).strip() for x in physical_opening_ids if str(x).strip()}):
        trace = next(
            (r for r in composition.opening_bindings if r.opening_identity_id == oid),
            None,
        )
        if trace is None or trace.status is not EvidenceResolutionStatus.ABSTAINED:
            raise ValueError(f"unhosted abstained opening required: {oid}")
        existence = opening_authority.prove_existence(ObservationSelector(
            document_id=revision.document_id,
            revision_id=revision.revision_id,
            source_sha256=revision.source_sha256,
            snapshot_id=snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        ))
        opening = existence.existence_record
        if existence.status is not EvidenceResolutionStatus.CORROBORATED or opening is None:
            raise RuntimeError("existence lost")
        roles: Counter[str] = Counter()
        for observation_id in opening.source_observation_ids:
            res = visibility.resolve_raster_opening_primitive(ObservationSelector(
                document_id=opening.document_id,
                revision_id=opening.revision_id,
                source_sha256=opening.source_sha256,
                snapshot_id=opening.snapshot_id,
                observation_id=observation_id,
            ))
            if res.status is not EvidenceResolutionStatus.CORROBORATED or res.observation is None:
                raise RuntimeError("support observation unverified")
            kind = str(res.observation.observation_kind or "")
            roles[kind] += 1
            kind_counts[kind] += 1
        openings.append({
            "physical_opening_id": oid,
            "support_kind_counts": dict(sorted(roles.items())),
            "host_granted": False,
        })
    return {
        "status": "UNPUBLISHED_G17_FACE_END_ROLE_CENSUS",
        "opening_count": len(openings),
        "support_kind_counts": dict(sorted(kind_counts.items())),
        "openings": openings,
        "host_granted": False,
        "shadow_only": True,
    }
