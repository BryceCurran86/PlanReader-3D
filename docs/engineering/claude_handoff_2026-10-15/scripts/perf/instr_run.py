"""Measurement-only wrapper: run the real source-closed handoff unchanged, counting a few hot-path calls.

usage: python instr_run.py <code_tree> <stats.json> -- <handoff args...>
Patches only by wrapping (same arguments, same return value); it never alters a result.
"""
import atexit, hashlib, json, os, runpy, sys, time
from collections import Counter, defaultdict

tree, stats_path = sys.argv[1], sys.argv[2]
args = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, tree)
os.chdir(tree)

stats = defaultdict(float)
renders = Counter()
render_png = {}
render_time = defaultdict(float)

import pb_source_observation_authority as soa  # noqa: E402
import pb_wall_room_topology_primitive_lineage as lin  # noqa: E402

# --- renders -----------------------------------------------------------------------------------------------------
_orig_render = soa.SourceObservationProducer.render_native_page_png


def render(self, **kw):
    t = time.perf_counter()
    out = _orig_render(self, **kw)
    dt = time.perf_counter() - t
    clip = kw.get("clip_pt")
    key = (kw.get("revision_id"), str(kw.get("page_id")), float(kw.get("dpi", 300.0)),
           tuple(clip) if clip is not None else None, bool(kw.get("images_only", False)))
    full = key + (kw.get("snapshot_id"), bool(kw.get("include_native_frame", False)))
    renders[full] += 1
    render_time[key] += dt
    png = out[0]
    digest = hashlib.sha1(png).hexdigest()
    render_png.setdefault(key, set()).add(digest)
    stats["render_calls"] += 1
    stats["render_seconds"] += dt
    stats["render_png_bytes"] += len(png)
    return out


soa.SourceObservationProducer.render_native_page_png = render

# --- lineage ------------------------------------------------------------------------------------------------------
_orig_attach = lin.attach_lineage_to_split_fragments
_orig_sources = lin.sources_for_fragment
_cur = {"all": None}


def sources_for_fragment(fragment, source_segments):
    full = source_segments is _cur["all"]
    t = time.perf_counter()
    res = _orig_sources(fragment, source_segments)
    dt = time.perf_counter() - t
    if full:
        stats["lineage_fallback_calls"] += 1
        stats["lineage_fallback_scanned"] += len(source_segments)
        stats["lineage_fallback_seconds"] += dt
        stats["lineage_fallback_found"] += 1 if res else 0
    else:
        stats["lineage_bucket_calls"] += 1
        stats["lineage_bucket_scanned"] += len(source_segments)
        stats["lineage_bucket_seconds"] += dt
        stats["lineage_bucket_empty"] += 0 if res else 1
    return res


def attach(split_pairs, source_segments, **kw):
    _cur["all"] = source_segments
    t = time.perf_counter()
    out = _orig_attach(split_pairs, source_segments, **kw)
    dt = time.perf_counter() - t
    _cur["all"] = None
    stats["attach_calls"] += 1
    stats["attach_seconds"] += dt
    stats["attach_fragments"] += len(split_pairs)
    stats["attach_sources"] += len(source_segments)
    stats["attach_max_sources"] = max(stats["attach_max_sources"], len(source_segments))
    stats["attach_max_fragments"] = max(stats["attach_max_fragments"], len(split_pairs))
    return out


lin.sources_for_fragment = sources_for_fragment
lin.attach_lineage_to_split_fragments = attach
# modules that imported the name directly
for modname, mod in list(sys.modules.items()):
    if modname.startswith("pb_") and getattr(mod, "attach_lineage_to_split_fragments", None) is _orig_attach:
        mod.attach_lineage_to_split_fragments = attach

# --- commits ------------------------------------------------------------------------------------------------------
if hasattr(soa.SourceObservationProducer, "_commit"):
    _orig_commit = soa.SourceObservationProducer._commit

    def commit(self, *a, **kw):
        before = len(self._store.observations)
        t = time.perf_counter()
        try:
            return _orig_commit(self, *a, **kw)
        finally:
            stats["commit_calls"] += 1
            stats["commit_seconds"] += time.perf_counter() - t
            stats["commit_added_records"] += len(self._store.observations) - before
            stats["commit_store_records_max"] = max(stats["commit_store_records_max"], len(self._store.observations))

    soa.SourceObservationProducer._commit = commit

START = time.perf_counter()


def dump():
    dup = {k: n for k, n in renders.items() if n > 1}
    same_args_diff_snapshot = Counter()
    for (rev, page, dpi, clip, imgs, snap, nf), n in renders.items():
        same_args_diff_snapshot[(rev, page, dpi, clip, imgs)] += n
    out = {
        "elapsed_s": time.perf_counter() - START,
        "stats": dict(stats),
        "render_distinct_requests_incl_snapshot": len(renders),
        "render_requests_repeated_exactly": sum(n - 1 for n in renders.values() if n > 1),
        "render_distinct_requests_ignoring_snapshot": len(same_args_diff_snapshot),
        "render_repeats_ignoring_snapshot": sum(n - 1 for n in same_args_diff_snapshot.values() if n > 1),
        "render_seconds_by_key_top": sorted(
            [(list(map(str, k)), round(v, 3), same_args_diff_snapshot[k]) for k, v in render_time.items()],
            key=lambda r: -r[1])[:12],
        "render_png_identical_across_snapshots": all(len(v) == 1 for v in render_png.values()),
        "render_png_variants_max": max((len(v) for v in render_png.values()), default=0),
    }
    json.dump(out, open(stats_path, "w"), indent=1, default=str)


atexit.register(dump)
sys.argv = ["run_source_closed_project_handoff.py"] + args
runpy.run_path(os.path.join(tree, "tools", "run_source_closed_project_handoff.py"), run_name="__main__")
