# SCRATCH experiment (no repo edit): bind compact callouts to proven G17 openings through #1242's label authority with an injected grammar.
import sys, os, json, time, hashlib, collections, re
WT = r'C:\Users\bryce\Documents\PB-PlanReader-3D\.claude\worktrees\lot16-publication'
sys.path.insert(0, WT); os.chdir(WT)
from pathlib import Path
import pb_opening_label_dimension_authority as lda
import pb_source_plan_opening_callout as co
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_observation_authority import ObservationSelector
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationProducer
from pb_migration_contracts import EvidenceResolutionStatus
import pb_physical_opening_viewport_scope_authority as vsa
from pb_title_block_viewport_shadow import propose_title_block_floor_plan_viewport
from pb_viewport_segmentation import segment_page_viewports

def compact_parse(text):
    tokens = tuple(t for t in str(text).split() if t)
    codes = [i for i,t in enumerate(tokens) if re.fullmatch(r'\d{4}', t)]
    if len(codes) != 1: return None
    code = tokens[codes[0]]; desc = tuple(t for i,t in enumerate(tokens) if i != codes[0])
    kind = co._classify_descriptor(desc)
    if kind is None: return None
    dims = co._compact_dimensions_mm(code, kind)
    if dims is None: return None
    w,h = dims
    return lda.ParsedOpeningLabel(raw_text=' '.join(tokens), dimension_values_mm=(h,w), semantic_kind=kind, compact_hundreds_used=True)
mode = sys.argv[1]
lda.parse_opening_label_dimensions = compact_parse
if mode == 'vp':
    def patched(page, *, page_number):
        f07 = segment_page_viewports(page, page_number=page_number)
        prop = propose_title_block_floor_plan_viewport(page, page_number=page_number, f07_viewports=f07)
        sv = prop.to_segmented_viewport()
        return (tuple(f07)+(sv,), (sv,)) if sv else vsa.__dict__['_orig'](page, page_number=page_number)
    vsa._orig = vsa._authenticated_viewports
    vsa._authenticated_viewports = patched
pdf = Path(r'C:\Users\bryce\Downloads\1. Construction Plans - Lot 16 Power (REV E).pdf')
payload = pdf.read_bytes(); sha = hashlib.sha256(payload).hexdigest()
src = SourceVisibilityProducer(producer_method="labelbind", producer_version="1")
pub = src.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload, source_locator="memory://x.pdf", page_ids=("3",))
rev = pub.revision.revision_id
sem = SemanticOpeningEnumerationProducer.from_source_visibility_producer(src)
res = sem.publish_page_scope(revision_id=rev, decision_scope_id="scratch-scope", page_ids=("3",))
snap = src.published_snapshot_for_revision(rev)
physical = src.physical_opening_authority()
labelp = lda.OpeningLabelDimensionProducer.from_source_visibility_producer(src)

from pb_opening_label_dimension_authority import _trusted_text_lines, _gap_span, _label_matches_gap, _dot
import math
openings=[]
for obs in res.record.representative_observation_ids:
    sel = ObservationSelector(document_id=snap.revision.document_id, revision_id=rev, source_sha256=snap.revision.source_sha256, snapshot_id=snap.snapshot.snapshot_id, observation_id=obs)
    ex = physical.prove_existence(sel); rec = ex.existence_record
    if rec is None: continue
    openings.append((sel, rec))
print('proven', len(openings))
lines = _trusted_text_lines(src, openings[0][1])
print('trusted lines', len(lines))
hits = [(l, compact_parse(l.text)) for l in lines]
hits = [(l,pz) for l,pz in hits if pz]
print('compact callout lines in trusted text:', len(hits), [l.text for l,_ in hits])
vis = src.authority()
for l,pz in hits:
    cx=(l.bbox[0]+l.bbox[2])/2; cy=(l.bbox[1]+l.bbox[3])/2
    best=[]
    for sel,rec in openings:
        recs=[]
        for oid in rec.source_observation_ids:
            r=vis.resolve_visible(ObservationSelector(document_id=rec.document_id, revision_id=rec.revision_id, source_sha256=rec.source_sha256, snapshot_id=rec.snapshot_id, observation_id=oid))
            if r.observation is not None: recs.append(r.observation)
        gap=_gap_span(recs)
        if gap is None: continue
        along=_dot((cx,cy),gap.axis); cross=_dot((cx,cy),gap.normal)
        inside = gap.along_min<=along<=gap.along_max
        best.append((abs(cross-gap.cross_center), inside, round(along-gap.along_min,1), round(gap.along_max-gap.along_min,1), _label_matches_gap(l,gap), [round(v) for v in (recs[0].geometry if recs else ())]))
    best.sort(key=lambda t:(not t[1],t[0]))
    print(l.text, [round(v) for v in l.bbox], 'glyph_h', round(min(abs(l.bbox[2]-l.bbox[0]),abs(l.bbox[3]-l.bbox[1])),1))
    for b in best[:3]: print('     cross', round(b[0],1), 'inside_along', b[1], 'gapwidth', b[3], 'match', b[4])
