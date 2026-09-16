# Opening Deduction Authority V1 — Validator Architecture

**Status:** TEST-ONLY / EXPECTED-RED foundation / DO NOT MERGE

**Base:** `5b5d92583ef8a8695da90209bf05f84b7385a77a`

This contract keeps two propositions separate:

> an authenticated physical opening creates an authenticated physical wall-local void

is **not the same proposition as**

> that void is authorized to participate in the deduction for this exact wall / trade / finish / assembly scope.

A physical void may exist while deduction permission remains unknown or inapplicable.
No scalar arithmetic, legacy host guess, caller boolean, schedule value, or provisional
quantity may upgrade that distinction.

## 1. Positive prerequisites

A positive deduction record requires all of the following:

1. authenticated physical-opening identity;
2. authenticated unique host binding for that exact opening;
3. authenticated physical-opening void for the same opening and host;
4. producer-owned complete opening decision scope;
5. exact target wall identity / binding scope;
6. exact trade / finish / assembly applicability when the deduction is scoped to one;
7. no unresolved relevant void in the target decision scope.

The authority should publish a per-physical-opening authorization record referencing
its authenticated void. It must not aggregate multiple voids by scalar area. Boolean
union belongs to the later Net-wall Boolean Union layer.

## 2. Identity and deduplication

Deduplication is by authenticated physical-opening identity only.

The following do **not** prove two openings are the same:

- equal width / height;
- equal void area;
- same type mark;
- same schedule row;
- same candidate ID text;
- overlapping geometry;
- nearest / first ordering.

Duplicate observations proven to represent one physical opening authorize at most one
physical deduction record. Two distinct physical openings with identical dimensions
remain two distinct authorized voids.

## 3. Unknown is not zero

If a relevant opening, host, void, universe member, wall applicability, trade scope,
finish scope, or assembly applicability is unresolved, the deduction result is
unknown / blocked. It is never authoritative zero.

Existing diagnostic arithmetic may retain a provisional numeric estimate in a
clearly non-authoritative field, but it cannot populate the authoritative value or
mint a positive proposition.

## 4. Public caller firewall

Ordinary callers may address authenticated upstream records using selectors. They
must not submit any of the following as authority:

- raw `area` / `area_m2`;
- raw `width * height` or width / height values;
- `deductible=True` / `deduction_allowed=True`;
- raw `host_wall_id` / caller wall id;
- raw void coordinates or polygon;
- caller opening lists, counts, completeness booleans or fingerprints;
- caller finish scope / assembly applicability as a truth claim;
- nearest / first / radius / confidence tie-breakers.

## 5. Required attack matrix before freeze

| Attack | Required result |
| --- | --- |
| caller raw area | structurally unavailable |
| caller deductible boolean | structurally unavailable |
| raw width × height | structurally unavailable |
| caller host ID | structurally unavailable |
| duplicate observations of one physical opening | one deduction record only |
| same physical opening supplied twice | one deduction record only |
| two same-size distinct openings | remain distinct |
| overlapping distinct openings | remain distinct here; later union prevents double-counted net subtraction |
| incomplete opening universe | ABSTAIN / BLOCKED |
| unresolved relevant void | ABSTAIN / BLOCKED |
| wrong wall | ABSTAIN / CONFLICT |
| wrong finish scope | ABSTAIN / CONFLICT |
| wrong assembly | ABSTAIN / CONFLICT |
| wrong trade scope | ABSTAIN / CONFLICT |
| stale revision / source / snapshot / page | ABSTAIN |
| candidate identity masquerading as physical identity | ABSTAIN / CONFLICT |
| legacy bbox / nearest host | unavailable / ABSTAIN |
| provisional arithmetic only | cannot mint positive authority |
| zero vs unknown confusion | unknown remains `None`, never `0` |

## 6. Relationship to net-wall geometry

Opening Deduction Authority authorizes physical void participation. It does not sum
void areas. The later Net-wall Boolean Union layer must operate on the authorized
wall-local void polygons/rectangles and use geometric union for overlapping voids.

Gross wall area must remain available diagnostically even when net wall area is
blocked by an unresolved relevant opening.

## 7. Current dependency state

At this base:

- host-binding V3 is in PR #381 and independently unmerged;
- Physical Opening Void V2 production does not exist;
- authenticated positive height / vertical placement are external dependencies.

Therefore production deduction authority is intentionally unavailable. This
validator foundation may be developed now, but it may not be called FROZEN until
its real-source behavioral attacks execute against the real upstream chain and an
independent reviewer accepts the exact validator blob.
