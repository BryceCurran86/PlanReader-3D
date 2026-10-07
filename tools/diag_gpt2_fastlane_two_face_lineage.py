import json
from collections import Counter
from pathlib import Path

import pb_opening_host_binding_authority as host
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
source=SourceVisibilityProducer(
    producer_method="diag-gpt2-two-face-lineage-owner-census",
    producer_version="1",
)
published=source.ingest_native_pdf_bytes(
    document_id="diag-gpt2-two-face-lineage-owner-census",
    source_bytes=SOURCE.read_bytes(),
    source_locator="memory://maryborough.pdf",
    page_ids=("7",),
)
comp=compose_live_wall_opening_authority(
    source_visibility_producer=source,
    revision_id=published.revision.revision_id,
    page_ids=("7",),
)
visibility=comp.physical_opening_authority.source_visibility_authority()

# The page-7 W4 scope is the producer-owned source of truth for this
# diagnostic. Inspect all records even when the scope is incomplete;
# do not promote or filter them.
selector0=next(iter(comp.binding_selectors.values()),None)
if selector0 is None:
    raise AssertionError("no binding selectors")
wall_scope=comp.physical_wall_candidate_authority.resolve_scope(
    PhysicalWallCandidateSelector(
        document_id=selector0.document_id,
        revision_id=selector0.revision_id,
        source_sha256=selector0.source_sha256,
        snapshot_id=selector0.snapshot_id,
        page_id="7",
        decision_scope_id=selector0.decision_scope_id,
    )
)
all_walls=tuple(wall_scope.records)

lineage_index={}
suffix_index={}
for wall in all_walls:
    ident=wall.physical_identity
    for sid in ident.source_primitive_ids:
        sid=str(sid)
        lineage_index.setdefault(sid,[]).append(wall)
        suffix_index.setdefault(sid.split(":")[-1],[]).append((sid,wall))

rows=[]
state_counts=Counter()
namespace_counts=Counter()
role_count=0
target_openings=0
for trace in comp.opening_bindings:
    if "no_authenticated_host_wall_band" not in trace.reason_codes:
        continue
    bsel=comp.binding_selectors.get(trace.opening_identity_id)
    if bsel is None:
        continue
    existence=comp.physical_opening_authority.prove_existence(
        ObservationSelector(
            document_id=bsel.document_id,
            revision_id=bsel.revision_id,
            source_sha256=bsel.source_sha256,
            snapshot_id=bsel.snapshot_id,
            observation_id=trace.representative_observation_id,
        )
    )
    opening=existence.existence_record
    if opening is None or opening.structural_pattern != host.JAMB_BOUNDED_TWO_FACE_INTERRUPTION:
        continue
    source_records=[]
    for obs_id in opening.source_observation_ids:
        result=visibility.resolve_visible(ObservationSelector(
            document_id=opening.document_id,
            revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id,
            observation_id=obs_id,
        ))
        if result.status is EvidenceResolutionStatus.CORROBORATED and result.observation is not None:
            source_records.append(result.observation)
    pairs=host._positive_gap_source_pairs(source_records)
    if len(pairs)!=2:
        continue
    face_records=(pairs[0][0],pairs[0][1],pairs[1][0],pairs[1][1])
    target_openings+=1
    role_rows=[]
    for rec in face_records:
        role_count+=1
        raw=host._raw_source_primitive_id(rec)
        exact=tuple(lineage_index.get(str(raw),())) if raw is not None else ()
        usable=tuple(w for w in exact if w.physical_identity.usable)
        suffix=tuple(suffix_index.get(str(raw).split(":")[-1],())) if raw is not None else ()
        if usable:
            state="usable_exact_owner"
        elif exact:
            state="exact_owner_unusable"
        elif suffix:
            state="namespace_mismatch_owner"
        else:
            state="no_w4_lineage_owner"
        state_counts[state]+=1
        namespace_counts[str(getattr(rec,"source_primitive_ref","") or "").split(":")[0]]+=1
        role_rows.append({
            "observation_id":rec.observation_id,
            "source_primitive_ref":str(getattr(rec,"source_primitive_ref","") or ""),
            "raw_id":raw,
            "state":state,
            "exact_owner_ids":[w.wall_candidate_id for w in exact],
            "exact_owner_usable":[w.physical_identity.usable for w in exact],
            "exact_owner_blocking_reasons":[list(w.physical_identity.blocking_reasons) for w in exact],
            "suffix_matches":[
                {"stored_source_id":sid,"wall_id":w.wall_candidate_id,"usable":w.physical_identity.usable}
                for sid,w in suffix[:12]
            ],
        })
    rows.append({
        "opening_identity_id":trace.opening_identity_id,
        "roles":role_rows,
    })

print(json.dumps({
    "wall_scope_status":getattr(wall_scope.status,"value",str(wall_scope.status)),
    "wall_scope_complete":wall_scope.scope_complete,
    "wall_record_count":len(all_walls),
    "no_band_opening_count":sum("no_authenticated_host_wall_band" in t.reason_codes for t in comp.opening_bindings),
    "two_face_openings_censused":target_openings,
    "role_count":role_count,
    "role_state_counts":dict(sorted(state_counts.items())),
    "source_ref_prefix_counts":dict(sorted(namespace_counts.items())),
    "sample_rows":rows[:40],
},indent=2,sort_keys=True))
