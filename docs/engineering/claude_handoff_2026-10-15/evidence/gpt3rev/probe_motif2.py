import sys
sys.path.insert(0, ".")
from types import SimpleNamespace
from pb_physical_wall_candidate_authority import repeated_raster_drafting_motif_wall_ids as motif

def rw(i, x1, y1, x2, y2):
    return SimpleNamespace(wall_candidate_id=i, wall_candidate=SimpleNamespace(centerline_pts=((x1, y1), (x2, y2))),
                           physical_identity=SimpleNamespace(source_primitive_ids=(f"raster_segment:s:1:{i}",)))

def fam(n, length, pitch, y=10.0, x0=0.0):
    return [rw(f"w{k}", x0 + k * pitch, y, x0 + k * pitch + length, y) for k in range(n)]

print("4.5pt ticks, 8 collinear, by pitch -> motif count:", {p: len(motif(fam(8, 4.5, p))) for p in (15.0, 20.0, 20.7, 21.0, 25.0, 60.0)})
print("28pt genuine-length pieces, 8 collinear, by pitch -> motif count:", {p: len(motif(fam(8, 28.0, p))) for p in (60.0, 120.0, 130.0, 200.0)})
base = fam(8, 4.5, 25.0)
print("add unrelated long wall:", len(motif(base + [rw("long", 0, 5000, 2000, 5000)])))
print("add 8 MORE identical ticks far away (same signature, x+2000):", len(motif(base + fam(8, 4.5, 25.0, y=10.0, x0=2000.0))))
print("add 8 identical ticks, other row y+300 same x (cross-axis only):", len(motif(base + fam(8, 4.5, 25.0, y=310.0))))
for k in (0.5, 2.0, 10.0):
    sc = [rw(w.wall_candidate_id, *(c * k for c in (*w.wall_candidate.centerline_pts[0], *w.wall_candidate.centerline_pts[1]))) for w in base]
    print("scale", k, len(motif(sc)))
# vertical ticks stacked side-by-side (perpendicular to the dimension line): same x-range, different x
vt = [rw(f"v{k}", k * 25.0, 0.0, k * 25.0, 4.5) for k in range(8)]
print("8 parallel 4.5pt vertical ticks side by side (typical perpendicular dimension ticks):", len(motif(vt)))
