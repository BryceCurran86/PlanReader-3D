# Opening → Host Wall Binding — architecture report (test-first)

Base: merged G17 main `62a161519e617cdf9ce23069820dbf7c68aaf521`

Lane: architecture / adversarial tests only. **Production host-binding
implementation is out of scope.** Opening-dimensions PR #332 stays frozen
(DRAFT, test-only). Opening-identity production remains ChatGPT #331.

Axes stay separate:

`existence ≠ identity ≠ width ≠ height ≠ type ≠ host`

Compliance (this report)

- Files read: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`,
  `docs/wall_topology_observability_architecture.md` (W7),
  `pb_wall_room_topology_opening_host_binding.py`,
  `pb_hosted_opening_wall_binding.py`, `pb_hosted_opening_geometry.py`,
  `pb_hosted_opening_instance_adapter.py`,
  `pb_wall_room_topology_wall_identity_v2.py`,
  `pb_wall_room_topology_wall_assembly.py` (`_canonical_wall_candidate_id`),
  `pb_physical_wall_identity.py`,
  `pb_wall_room_topology_room_wall_relationships.py` (interior/exterior role),
  `pb_opening_deduction_readiness.py`,
  `pb_physical_opening_authority.py` (`capabilities`),
  `pb_wall_room_topology_contracts.py` (`OpeningHostCandidate`),
  `pb_wall_topology_diagnostics.py` (W7 call site).
- Functions traced: `detect_opening_host_candidates`,
  `bind_hosted_opening_to_walls`, `canonical_path_fingerprint`,
  `canonical_wall_candidate_id_v2`, `resolve_physical_wall_identity`,
  `_host_blockers` / `build_opening_deduction_quantity`,
  `PhysicalOpeningAuthority.capabilities`,
  `hosted_span_to_opening_instance`.
- Authority boundaries: detection/nomination ≠ unique host; local candidate
  list ≠ authenticated host universe; #323 path fingerprint ≠ caller-minted
  fingerprint; host bind ≠ dimensions / voids / deductions / FIRM / JobHub.
- Untouched: all production modules, gold/benchmark files, #331 identity,
  #332 dimension production (none), commercial / JobHub publishers.

---

## OBSERVED (repository behavior)

### W7 dangling-gap detector (adopted observability)

`pb_wall_room_topology_opening_host_binding.detect_opening_host_candidates`

- Input: viewport `WallCandidate`s with `JunctionType.ENDPOINT` dangling ends.
- Clusters collinear anti-parallel dangling ends above Stage-A snap tolerance.
- **Every** returned `OpeningHostCandidate` has `host_status="ambiguous_host"`.
  `hosted` is unreachable from this detector alone (module docstring +
  AGENTS.md).
- Unpaired dangling end is discarded (not an opening).
- `wall_candidate_id` is set to the sorted first considered wall id for
  record shape only; both/all flanking walls remain in
  `candidate_wall_ids_considered`.
- Optional `gap_width_m` scales min gap pt by average of bounding walls'
  `length_m / length_pt` when those lengths exist; otherwise `None`.
  Geometric gap width is **not** firm opening width (AGENTS).
- Wired only into `pb_wall_topology_diagnostics.collect_topology_from_segments`
  (observability). W10 adapter does not emit `CanonicalOpening` from W7.

### Hosted-opening geometric binder (unwired diagnostic)

`pb_hosted_opening_wall_binding.bind_hosted_opening_to_walls`

- Pure geometry: collinear axis, cross-axis proximity, containment **or**
  two-sided jamb adjacency.
- Statuses: `bound` (exactly one containment, no adjacency rivals),
  `ambiguous` (two flanking chains or ≥2 plausibles), `unbound`.
- Explicitly refuses nearest-wall / one-sided adjacency promotion.
- Not on the live extraction / commercial path (AGENTS: diagnostic only).

### Hosted span → F.9 instance adapter

`pb_hosted_opening_instance_adapter.hosted_span_to_opening_instance`

- `bound_wall_id` is `None` unless the **caller** supplies an independently
  evidenced wall id. Never defaults to perimeter / nearest wall.
- Height always `None`. Anonymous span id — not a schedule mark.

### #323 / P2 wall path fingerprint (reuse — do not fork)

`pb_wall_room_topology_wall_identity_v2.canonical_path_fingerprint`

- Quantize → collinear-collapse → direction-canonical min(forward, reverse).
- W4 assembly `_canonical_wall_candidate_id` hashes
  `(viewport_id, path_fingerprint)` — geometry-only.
- Hybrid `canonical_wall_candidate_id_v2` adds sorted U1 provenance for the
  physical-wall identity sidecar only.
- `pb_physical_wall_identity.resolve_physical_wall_identity` recomputes the
  fingerprint from producer-owned edge geometry; abstains when edges /
  coordinates / walkability are unavailable.

### Wall role (interior/exterior)

`pb_wall_room_topology_room_wall_relationships` may set
`interior_exterior` to interior/exterior/unresolved from room-usage counts.
This is topology role, **not** opening-host authority.

### Deduction readiness firewall (already fail-closed)

`pb_opening_deduction_readiness._host_blockers`

- Requires `host_status=="hosted"` and cardinality exactly one.
- Blocks nomination reasons: `nearest_wall_only`, `bbox_overlap_only`,
  `regional_clip_only`, `centerline_distance_only`.
- Even a caller-constructed `hosted` record still gets
  `opening_host_universe_completeness_not_authenticated` — a local candidate
  set cannot certify its own completeness.

### G17 capability lock

`PhysicalOpeningAuthority.capabilities()`:

```
host_identity: False
host_binding: False
opening_dimensions: False
opening_universe_complete: False
physical_void: False
net_wall_area: False
```

---

## INFERENCE (wiring / tests, not a single production orchestrator)

- Live commercial opening quantities do not consume W7 or
  `bind_hosted_opening_to_walls` as firm host authority today.
- A future unique host bind still needs an **independently authenticated
  host-universe producer** (viewport-complete wall enumeration under the
  same document/revision/source/viewport ownership). Without it, uniqueness
  among a caller-cropped wall list is meaningless.
- Opening existence (G17) and opening identity (#331) are prerequisites for
  binding a *named* physical opening to a host; geometric gap detection alone
  is not physical-opening existence.
- Binding a host must not unlock dimensions, completeness, voids, deductions,
  FIRM commercial rows, or JobHub publication.

---

## PROPOSED (not implemented in this PR)

Introduce a later, separately reviewed **OpeningHostBindingAuthority** that:

1. Reuses `#323` `canonical_path_fingerprint` / producer-owned
   `resolve_physical_wall_identity` — **never** a second fingerprint algorithm
   and never a caller-supplied fingerprint blob as authority.
2. Requires authenticated host-universe completeness proof as a first-class
   evidence object (not inferred from `len(candidates)`).
3. Emits unique host only when exactly one producer-owned wall identity
   survives after completeness; otherwise `CONFLICT` / `BLOCKED` /
   `ambiguous_host`.
4. Keeps width, height, type, void, deduction, FIRM, and JobHub closed.
5. Remains shadow until a dedicated authority-promotion review.

Do **not** promote:

- W7 `ambiguous_host` → `hosted` by picking first / nearest / smallest.
- `gap_width_m` → firm opening width.
- Local containment uniqueness without universe completeness.
- Caller-minted wall ids or fingerprints.

---

## BENCHMARK (must not drive algorithms)

Holdout / tender scores are observation only. This lane does not change
prediction code or gold. Expected snapshot remains **31/61 = 50.82%**,
holdout exposure **NONE**.

---

## Attack surface (test suite map)

| # | Case | Expected eventual / current |
|---|---|---|
| 1 | One unambiguous host + complete universe | RED until authority |
| 2 | Corner door | RED |
| 3 | T-junction | RED |
| 4 | Two parallel competing walls | BLOCKED / ambiguous |
| 5 | Multi-wythe / cavity | BLOCKED unless wythe identity proven |
| 6 | Curved / segmented wall | RED; reuse #323 collapse |
| 7 | Angled wall | RED |
| 8 | Nearby-but-not-host | unbound / blocked |
| 9 | Footprint intersects two candidates | ambiguous |
| 10 | Same geometry, different wall IDs | fingerprint equivalence via #323 |
| 11 | Identical fingerprint only if producer-owned | reject caller mint |
| 12 | Caller-supplied fingerprint | rejected |
| 13 | Nearest-wall fallback | rejected (GREEN documented) |
| 14 | First / smallest candidate | rejected |
| 15 | Incomplete / truncated universe | BLOCKED (GREEN today via readiness) |
| 16 | Page / revision / source mismatch | BLOCKED |
| 17 | Viewport laundering | BLOCKED |
| 18 | Input-order determinism | same result |
| 19 | Line-direction reversal | same #323 / bind behavior |
| 20 | Segment split / collinear collapse | #323 compatible |
| 21 | Translation / rotation (owned source) | structural bind preserved |
| 22 | Downstream firewall after bind | dims/void/deduction/FIRM/JobHub closed |

Green tests lock current fail-closed behavior and document unsafe nomination
patterns without implementing production binding.
