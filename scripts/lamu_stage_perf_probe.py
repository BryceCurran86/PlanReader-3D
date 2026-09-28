#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, time
from pathlib import Path
import fitz

from pb_source_visibility_authority import SourceVisibilityProducer
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_gross_wall_geometry_composition import compose_live_gross_wall_geometry
from pb_live_whole_wall_role_composition import compose_live_whole_wall_roles
from pb_live_external_physical_net_wall_publication import compose_live_external_physical_net_wall_publication
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor

p=argparse.ArgumentParser()
p.add_argument("--pdf",required=True)
p.add_argument("--stage",required=True,choices=["ingest","wall","downstream","commercial"])
a=p.parse_args()
pdf=Path(a.pdf)
payload=pdf.read_bytes()
pages=("41","42","43","44","45")
page_indices=[40,41,42,43,44]

def source():
    s=SourceVisibilityProducer(producer_method="lamu-stage-probe",producer_version="1")
    t=time.perf_counter()
    pub=s.ingest_native_pdf_bytes(
        document_id="lamu-stage:"+hashlib.sha256(payload).hexdigest()[:24],
        source_bytes=payload,source_locator="memory://lamu.pdf",page_ids=pages)
    return s,pub,time.perf_counter()-t

if a.stage=="ingest":
    _,pub,elapsed=source()
    print(f"STAGE ingest seconds={elapsed:.6f} visible={len(pub.visible_observation_ids)} text={len(pub.text_observation_ids)}")
elif a.stage=="wall":
    s,pub,ingest=source()
    t=time.perf_counter()
    wall=compose_live_wall_opening_authority(
        source_visibility_producer=s,revision_id=pub.revision.revision_id,page_ids=pages)
    elapsed=time.perf_counter()-t
    print(f"STAGE wall ingest_seconds={ingest:.6f} wall_seconds={elapsed:.6f} status={wall.status.value} scopes={len(wall.wall_scopes)} openings={len(wall.opening_bindings)}")
elif a.stage=="downstream":
    s,pub,ingest=source()
    t=time.perf_counter()
    wall=compose_live_wall_opening_authority(
        source_visibility_producer=s,revision_id=pub.revision.revision_id,page_ids=pages)
    wall_s=time.perf_counter()-t
    t=time.perf_counter()
    voids=compose_live_physical_opening_voids(source_visibility_producer=s,wall_opening_composition=wall)
    gross=compose_live_gross_wall_geometry(source_visibility_producer=s,wall_opening_composition=wall,physical_void_composition=voids)
    roles=compose_live_whole_wall_roles(gross_wall_composition=gross)
    pubn=compose_live_external_physical_net_wall_publication(
        wall_opening_composition=wall,physical_void_composition=voids,
        gross_wall_composition=gross,whole_wall_role_composition=roles)
    downstream=time.perf_counter()-t
    print(f"STAGE downstream ingest_seconds={ingest:.6f} wall_seconds={wall_s:.6f} downstream_seconds={downstream:.6f} void={voids.status.value} gross={gross.status.value} roles={roles.status.value} net={pubn.status.value}")
else:
    t=time.perf_counter()
    ex=GenericPlanReaderExtractor()
    preds=ex.extract_from_pdf(pdf,pages=page_indices,collect_item35_shadow=False)
    elapsed=time.perf_counter()-t
    print(f"STAGE commercial seconds={elapsed:.6f} predictions={len(preds)} net={ex.physical_net_wall_live.get('status')}")
