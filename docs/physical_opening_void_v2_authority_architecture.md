# Physical Opening Void V2 — Authority Architecture

**Status:** validator-first contract foundation / TEST-ONLY lane

**Base:** `bb61a8dee24c71b12cffcbb19e8dd89965b6e4fe`

This contract defines one proposition only:

> **this authenticated physical opening creates this exact physical wall-local void.**

It does **not** prove that the void may be deducted commercially, that a finish or
assembly is affected, that a net-wall quantity is publishable, or that any FIRM /
commercial / JobHub capability is available.

## 1. Upstream prerequisites

A positive void requires all of the following to be independently positive and
scope-consistent:

1. authenticated physical-opening existence and exact physical-opening identity;
2. authenticated unique host binding for that exact opening;
3. producer-owned complete opening decision scope;
4. exact opening horizontal span / jamb position in the host-wall frame;
5. authenticated opening width;
6. authenticated opening height;
7. authenticated vertical placement sufficient to establish `z0` and `z1`
   (sill/head or an equivalent datum-bound proposition — height alone is not enough);
8. an authenticated wall-local coordinate frame;
9. an authenticated physical unit mapping for that exact page/frame, sufficient to
   express horizontal `u` in the same physical unit system as vertical `z`.

Item 7 is deliberately explicit. A height value proves only `z1-z0`; it cannot
lawfully invent the sill, head or centre. If no reviewed upstream authority can
establish the vertical datum, Physical Opening Void V2 must ABSTAIN.

Items 8–9 are also separate propositions. The host/opening geometry currently comes
from native PDF coordinates (points), while opening dimensions are physical values.
A direction/origin alone is not a physical unit mapping. The positive void therefore
must not silently mix PDF points with mm/m, derive a scale from caller inputs, or
promote an ordinary textual scale merely because it is spatially nearby. Current
`pb_page_scale_calibration_authority.measurement_authority_for_page_scale()` keeps
TITLE_BLOCK-only scale provisional; only an upstream scale proposition already
accepted as FIRM for the exact scope may establish the physical `u` mapping.

Independent evidence must also reconcile rather than compete. After conversion
through the authenticated unit map, the source-derived jamb span must be compatible
with the authenticated width. Likewise, `z1-z0` from authenticated vertical
placement must be compatible with authenticated height. A mismatch is a blocker;
production must not choose geometry over dimensions, dimensions over geometry, or
hide the conflict behind nearest/first/confidence/tolerance heuristics. Any numeric
tolerance used for compatibility must itself come from an already-reviewed
measurement/geometry contract appropriate to the evidence, not a new permissive
void-layer constant.

The wall-local frame and unit mapping must not be manufactured from caller
coordinates. Reversing a host baseline may change coordinate orientation, but must
not change the physical void proposition. Translation or rotation of an equivalent
source drawing must not change the represented physical void apart from the
corresponding deterministic frame transform.

## 2. Required positive record

A positive record is rectangular only when the authenticated evidence proves a
rectangular profile. It must carry, directly or through immutable referenced
records:

- exact lineage: document, revision, source SHA, snapshot, page, decision scope;
- exact authenticated physical-opening identity;
- exact authenticated host-binding identity / host-wall proposition;
- complete-opening-universe record identity;
- width and height authority record identities;
- wall-local frame identity;
- authenticated physical unit-mapping / scale record identity;
- vertical-placement authority identity;
- wall-local rectangular extent `[u0,u1] × [z0,z1]` in one declared physical unit
  system;
- deterministic record identity / serialization.

A derived void area may be carried diagnostically if computed from the authenticated
wall-local rectangle, but area is not a substitute for `u/z` geometry and is not
commercial deduction permission.

Candidate wall IDs are addresses only. They must not be promoted into a stronger
physical-wall identity than the upstream host/equivalence authority proves.

The void record must not carry or imply:

- `deductible=True` / commercial deduction permission;
- finish applicability;
- assembly applicability;
- net wall area;
- FIRM/commercial publication;
- JobHub publication.

## 3. Public caller firewall

Ordinary callers may address already-authenticated upstream propositions using
selectors. They must not be able to submit evidence-shaped truth values or raw
geometry to mint a void.

Forbidden public inputs include, at minimum:

- raw `host_wall_id`, wall candidate lists or host confidence;
- raw `width`, `height`, `area`;
- raw `u0`, `u1`, `z0`, `z1`;
- raw `(x,y)` position, centre, jambs or polygon;
- raw `scale`, `scale_ratio`, `px_per_m`, `points_per_m` or unit-conversion factors;
- `sill`, `head`, `sill_height`, `head_height`;
- `default_height`, `typical_height`, `default_sill`, `default_head`;
- `claimed_complete` / completeness booleans, counts, hashes or fingerprints;
- nearest / first / radius / confidence tie-breakers;
- caller-authored profile type used as authority.

Selectors are addresses only. Every positive proposition must be recomputed or
resolved from producer-owned upstream authorities.

## 4. Fail-closed attack matrix

Before this validator may be frozen, executable coverage must prove each attack
below fails closed against the real production module.

| Attack | Required result |
| --- | --- |
| no authenticated height | ABSTAIN |
| no authenticated host | ABSTAIN |
| ambiguous host | CONFLICT / ABSTAIN, never positive |
| wrong host / cross-wired host selector | ABSTAIN / CONFLICT |
| width only | ABSTAIN |
| height only | ABSTAIN |
| authenticated width conflicts with source-derived physical jamb span | ABSTAIN / CONFLICT |
| authenticated height conflicts with authenticated `z1-z0` | ABSTAIN / CONFLICT |
| caller position / raw `u` | structurally unavailable |
| guessed centre | structurally unavailable / ABSTAIN |
| guessed sill | structurally unavailable / ABSTAIN |
| guessed head | structurally unavailable / ABSTAIN |
| height without vertical datum | ABSTAIN |
| no authenticated physical unit mapping / scale | ABSTAIN |
| provisional/title-block-only scale | ABSTAIN for physical void geometry |
| caller scale or conversion factor | structurally unavailable |
| wrong-page / stale scale | ABSTAIN |
| wrong page | ABSTAIN |
| wrong source SHA | ABSTAIN |
| wrong revision | ABSTAIN |
| stale snapshot | ABSTAIN |
| duplicate observation of same physical opening | one physical void only |
| unsupported arch / non-rectangular profile | ABSTAIN unless separately authenticated profile geometry exists |
| reversed wall baseline | same physical void proposition under deterministic frame transform |
| translated drawing | invariant under deterministic frame transform |
| rotated drawing | invariant under deterministic frame transform |
| incomplete opening universe | ABSTAIN |
| caller completeness flag | structurally unavailable |
| candidate identity masquerading as physical-wall identity | ABSTAIN / CONFLICT |
| unresolved physical-wall equivalence relevant to host | ABSTAIN / CONFLICT |

## 5. Current external dependencies

At this validator base:

- Item 4B physical-wall equivalence is merged.
- Host-binding V3 production #381 is independently accepted and merged on main.
- `OpeningDimensionAuthority.resolve_height(...)` remains fail-closed / unavailable
  for authoritative positive height on current main.
- No reviewed wall-local vertical-placement authority is available on current main.
- Page/viewport scale machinery exists, but ordinary textual TITLE_BLOCK scale is
  intentionally PROVISIONAL rather than FIRM; the void lane must consume only an
  exact-scope physical unit mapping already authorized for measurement.

Therefore a real positive Physical Opening Void V2 is intentionally unavailable.
The validator foundation is expected-red until the remaining prerequisites exist.
Do not fake them with monkeypatched height, default sill/head, schedule-only values,
caller geometry, caller scale, or an uncorroborated textual scale.

## 6. Freeze rule

This validator may be called **FROZEN** only after independent review verifies:

1. every attack in Section 4 is executable against the real upstream chain;
2. the positive fixture uses only authenticated upstream propositions;
3. no validator helper manufactures host, height, vertical placement, scale/unit
   mapping, completeness, or wall-local geometry as authority;
4. ordinary and `--runxfail` behavior is recorded at an exact validator blob;
5. benchmark/gold/holdout files are untouched.

Until then this lane remains **DRAFT / TEST-ONLY / EXPECTED-RED / DO NOT MERGE**.
