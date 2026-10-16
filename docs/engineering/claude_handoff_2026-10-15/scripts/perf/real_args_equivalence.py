"""Old vs new attach_lineage_to_split_fragments on REAL captured call arguments: exact equality + wall time.

usage: python real_args_equivalence.py <attach_args.pkl> <reference_module.py> <new_tree>
"""
import importlib.util, pickle, sys, time

pkl, ref_path, new_tree = sys.argv[1:4]
calls = pickle.load(open(pkl, "rb"))
print("captured calls:", len(calls), [(len(p), len(s), sorted(k)) for p, s, k in calls])


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ref = load(ref_path, "lineage_ref")
sys.path.insert(0, new_tree)
import pb_wall_room_topology_primitive_lineage as new  # noqa: E402

assert new.__file__.replace("\\", "/").startswith(new_tree.replace("\\", "/")), new.__file__
for i, (pairs, sources, kw) in enumerate(calls):
    t = time.perf_counter(); a = ref.attach_lineage_to_split_fragments(pairs, sources, **kw); ta = time.perf_counter() - t
    t = time.perf_counter(); b = new.attach_lineage_to_split_fragments(pairs, sources, **kw); tb = time.perf_counter() - t
    same = (a == b) and ([list(x) for x in a] == [list(x) for x in b])
    plural = sum(1 for f in b if len(f["primitive_lineage"]["source_primitive_ids"]) > 1)
    empty = sum(1 for f in b if not f["primitive_lineage"]["source_primitive_ids"])
    print(f"call {i}: fragments={len(pairs)} sources={len(sources)} identical={same} "
          f"(multi-parent fragments {plural}, parentless {empty}); reference {ta:.2f}s new {tb:.2f}s speedup {ta / max(tb, 1e-9):.1f}x")
    assert same, "OUTPUT DIFFERS"
