# Faster validation without weaker release gates

Owner request 25 November 2026. Baseline #4713: Python 3.13 18m45s, 3.14 14m29s; both already run concurrently.

- Required CI / test (3.13) and CI / test (3.14) still run the entire tests/ tree on every main PR/push. No changed-path waiver. Retain all source/truth/security checks and post-test smoke. Release CI defaults to serial. Parallel xdist workers are manual experiments only until database and disk isolation is proven. Both matrix versions continue even if one fails. Report the 30 slowest durations.
- Manual full dispatch can select 0 (serial), 2 or 4 workers for a like-for-like timing/count comparison. Never ignore collection mismatch or race failures. If parallel suite fails, investigate shared state before promotion; serial baseline is diagnostic, not an automatic green fallback.
- Nightly full CI (02:17 AEST) and full PR/main checks remain. No original PDF provisioning or public original-source validation claim.
- VR development branch pushes get TypeScript/browser feedback and, if a strict merge-base diff consists exclusively of browser source/test code, both Python versions run scoped editable-3D integration tests. Mixed, package, workflow, native/installer, Python and unknown edits require the full gate. Development feedback never authorises a merge.
- Cache dependency downloads using both Python requirements and the npm lockfile; consolidate three unchanged fastpath test targets into one process.
- Next evaluation: exact-head pass/skip/xfail counts against a serial full run, job wall time, slowest 30 tests, repeated determinism, peak memory. Only then consider four workers or balanced independent runner shards. No speedup is claimed until measured.
