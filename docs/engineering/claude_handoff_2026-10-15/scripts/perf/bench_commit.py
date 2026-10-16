"""Micro-benchmark of the per-record loops in SourceObservationProducer._commit on synthetic records (real result dataclass)."""
import gc, sys, time
from types import SimpleNamespace

sys.path.insert(0, "C:/claude-work/stack")
import pb_source_observation_authority as soa  # noqa: E402

N = 500_000
Result = soa.SourceObservationAuthorityResult
status = soa.EvidenceResolutionStatus.CORROBORATED
rev, snap = SimpleNamespace(), SimpleNamespace()
records = [SimpleNamespace(observation_id=f"obs_{i:08d}", observation_payload_sha256=f"{i:064x}") for i in range(N)]
gc.collect()
gc.disable()


def timed(label, fn):
    t = time.perf_counter()
    out = fn()
    print(f"{label:46s} {time.perf_counter() - t:7.3f}s  {1e6 * (time.perf_counter() - t) / N:6.2f} us/record")
    return out


sid = "source_snapshot_abc"
staged = {}


def stage():
    for r in records:
        key = (sid, r.observation_id)
        prior = staged.get(key)
        staged[key] = r


timed("1 staging loop (key tuple + get + set)", stage)
observations, fps = {}, {}


def store():
    for key, r in staged.items():
        observations[key] = r
        fps[key] = r.observation_payload_sha256


timed("2 observations + fingerprints dict inserts", store)
cache = {}


def seed_current():
    for key, r in staged.items():
        result = Result(status=status, proposition="x", physical_opening_existence="y", reason_codes=("a",),
                        source_revision=rev, snapshot=snap, observation=r,
                        semantic_enumeration_complete=None, decision_scope_complete=None)
        cache[key] = (rev, snap, r, r.observation_payload_sha256, result)


timed("3a verified cache: result + 5-tuple per record", seed_current)
cache2 = {}
template = Result(status=status, proposition="x", physical_opening_existence="y", reason_codes=("a",),
                  source_revision=rev, snapshot=snap, observation=None,
                  semantic_enumeration_complete=None, decision_scope_complete=None)


def seed_template():
    for key, r in staged.items():
        cache2[key] = (rev, snap, r, r.observation_payload_sha256, template)


timed("3b verified cache: shared template + 5-tuple", seed_template)
big = dict(cache)  # emulate an existing large cache from earlier snapshots
for i in range(400_000):
    big[(f"old_{i % 4}", f"o{i}")] = None
keep = {sid, "p"}


def evict_scan():
    for k in tuple(big):
        if k[0] not in keep:
            big.pop(k, None)


timed("4 eviction scan (tuple copy + pops) over 900k", evict_scan)
