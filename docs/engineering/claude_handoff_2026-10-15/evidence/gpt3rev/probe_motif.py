import sys
sys.path.insert(0, ".")
from types import SimpleNamespace
from pb_physical_wall_candidate_authority import repeated_raster_drafting_motif_wall_ids as motif

def rw(i, x1, y1, x2, y2):
    return SimpleNamespace(wall_candidate_id=i, wall_candidate=SimpleNamespace(centerline_pts=((x1, y1), (x2, y2))),
                           physical_identity=SimpleNamespace(source_primitive_ids=(f"raster_segment:s:1:{i}",)))

def fam(n, length, pitch, y=10.0, x0=0.0):
    return [rw(f"w{k}", x0 + k * pitch, y, x0 + k * pitch + length, y) for k in range(n)]

# 1. viewport expansion: same 8 ticks, page span 100 -> 1000 -> 5000 (an unrelated sheet region added)
ticks = fam(8, 4.5, 20.0)
print("viewport span -> motif count:", {s: len(motif(ticks, page_span=s)) for s in (100.0, 150.0, 151.0, 1000.0, 5000.0)})
# 2. uniform scale of geometry AND span: invariant?
for k in (0.5, 2.0, 10.0):
    sc = [rw(w.wall_candidate_id, *(c * k for c in (w.wall_candidate.centerline_pts[0] + w.wall_candidate.centerline_pts[1]))) for w in ticks]
    print("scale", k, len(motif(sc, page_span=1000.0 * k)))
# 3. 8 identical collinear genuine wall pieces (e.g. a corridor wall split by openings), 3% of a 1000 pt page = 30 pt
pieces = fam(8, 28.0, 60.0)
print("8 identical collinear 28pt wall pieces classified as motif:", len(motif(pieces, page_span=1000.0)))
# 4. one longer piece breaks the signature -> not motif
pieces2 = fam(7, 28.0, 60.0) + [rw("odd", 420.0, 10.0, 455.0, 10.0)]
print("7 identical + 1 different:", len(motif(pieces2, page_span=1000.0)))
# 5. rounding boundary: lengths differing by 0.004 pt still the same signature (round(length,2))
near = [rw(f"n{k}", k * 20.0, 10.0, k * 20.0 + 4.5 + (0.004 if k % 2 else 0.0), 10.0) for k in range(8)]
print("lengths jittered 0.004pt:", len(motif(near, page_span=1000.0)))
