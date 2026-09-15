# G17 Upstream Authority Producer Architecture

**Status:** architecture contract only; no production implementation or new FIRM route is authorized by this document.

**Governing baseline:** `main` at `43a1597067d296ad0cd485eafbd38db0b5961625`.

**Protected prior work:** PR #304 remains frozen at `aedff4a152d8fae01613f6373380499d55e068d2` and is not modified by G17.

## 1. Decision

The current repository does **not** contain a sufficiently independent, inspectable, non-caller-mintable upstream authority producer for the source facts required to unlock new FIRM routes for opening identity, opening-universe completeness, host binding, wall-to-datum binding, physical voids, or net wall area.

The missing boundary is not another caller-constructible proof object. It is a producer-owned source-observation system that:

1. ingests immutable source material through a trusted ingestion path;
2. creates and owns observations and relationship records before quantity consumers query them;
3. publishes immutable producer snapshots over an independently bounded source domain;
4. exposes typed read/query interfaces that accept selectors, not caller-authored authority records;
5. preserves unresolved and contradictory evidence rather than silently filtering it away;
6. makes every positive authority result inspectable back to source observations and lineage; and
7. is deployed with a write/replace boundary strong enough for the threat model being claimed.

Until such a producer exists, existing fail-closed routes remain fail closed. This document does not authorize consumers to infer authority from hashes, snapshot identifiers, private/module-owned objects, candidate lists, `complete=True`, `CORROBORATED`, confidence, tags, dimensions, bboxes, proximity, caller lineage, self-hashes, internally consistent JSON, JCS, or Merkle roots.

A source hash may bind a **producer-owned** observation to immutable source bytes. It cannot convert a caller assertion into source authority.

## 2. Architectural question

G17 answers:

> Where do authoritative source observations come from, who owns them, how are they ingested, how are they queried, and why can an ordinary consumer not manufacture them?

The answer is a general source-authority store with typed authority services layered over producer-owned records. Opening authority, host authority, and wall-datum authority share the same source provenance substrate but remain separate semantic contracts.

## 3. Terminology

### 3.1 Producer

The **producer** is the trusted ingestion and authority subsystem that writes source observations, source-domain coverage records, lineage records, relationship records, and published snapshots.

“Producer” is a trust role, not a class name and not a string field such as `producer_id`.

### 3.2 Consumer

A **consumer** is quantity logic, application logic, an API handler, a measurement resolver, or another downstream component asking the authority subsystem a bounded question.

A consumer may submit selectors. It may not submit the record body that is supposed to prove its own claim.

### 3.3 Observation

A **source observation** is a producer-owned record traceable to an inspectable location or primitive in immutable source material. It may represent native vector/text content, raster/OCR evidence, or another decoded source primitive.

### 3.4 Normalized observation

A **normalized observation** is a producer-owned transformation of a raw observation into a canonical coordinate, text, or geometry form. Normalization retains lineage to the raw observation and cannot strengthen authority beyond that raw support.

### 3.5 Derived reconstruction

A **derived reconstruction** is geometry, grouping, topology, inferred identity, or another reconstruction produced from one or more observations. It is not automatically a source fact.

### 3.6 Semantic relationship

A **semantic relationship** states a typed relationship such as “this dimension applies to this physical opening,” “this opening is physically hosted by this wall,” or “this datum governs this exact wall segment.” It requires independent inspectable support appropriate to that relationship.

### 3.7 Producer snapshot

A **producer snapshot** is an immutable published view of producer-owned records plus source-domain coverage state for an exact source revision and producer generation. Consumers query a published snapshot; they do not assemble one from candidate objects.

### 3.8 FIRM

“FIRM” remains the downstream authority level used by quantity contracts. G17 does not itself create a FIRM quantity route. It defines the upstream evidence boundary that later implementation must satisfy before such routes can be reviewed.

## 4. Trust model

G17 distinguishes five actors/threat classes.

### 4.1 Ordinary application consumers

Ordinary consumers are **not trusted to create authority**. They may provide only bounded selectors such as:

- source/document identifier;
- revision;
- evidence snapshot identifier;
- graph snapshot identifier;
- page;
- viewport;
- lookup target ID; and
- bounded scope selector.

The authority layer re-fetches producer-owned state using those selectors. A consumer-supplied observation, universe, provenance object, record body, hash, boolean, or relationship claim is not accepted as the authoritative record.

### 4.2 Trusted producer ingestion code

Producer ingestion code is authorized to write the source-authority store. It must ingest source bytes and decoder/extractor output through a controlled writer path and create source observations, coverage records, lineage, relationships, and snapshots under producer rules.

The producer is responsible for refusing publication when ingestion cannot establish required coverage or integrity.

### 4.3 Trusted same-process code

If producer and consumer run in one Python interpreter with equal privileges, trusted same-process code can generally mutate module globals, monkey-patch providers, replace functions, reach nominally private state, or bypass ordinary API conventions.

Therefore Python names such as `_CURRENT_CANONICAL_PRODUCER`, leading underscores, frozen dataclasses, and module ownership are **conventional/structural software boundaries, not a security boundary against equally privileged same-process code**.

The current #304 `_CURRENT_CANONICAL_PRODUCER` is a valid fail-closed placeholder because its implementation returns unavailable authority. It is not sufficient as the future security boundary merely because the variable is module-owned or private by naming convention.

### 4.4 Potentially compromised or malicious consumer code

G17 intends to prevent a malicious consumer from manufacturing authority **when that consumer does not possess producer write credentials, cannot replace the producer service/process, and cannot directly mutate the producer backing store**.

A security-sensitive deployment therefore requires a privilege boundary such as:

- a separate producer process/service with a read-only consumer API;
- a database/schema/role whose write credential is unavailable to consumers; or
- an equivalent OS/process/credential boundary.

An in-process adapter may implement the same interfaces for development, but it must not be described as resistant to same-process provider replacement.

### 4.5 Persistent source/store tampering

Baseline G17 requires integrity checks sufficient to detect stale revisions, duplicate IDs, conflicting producer records, invalid snapshot relationships, and source-content mismatches when compared with the trusted source revision known to the producer.

G17 does **not** claim protection against a malicious actor that has both privileged producer-store write access and the ability to replace the producer's trusted source-of-truth metadata. Such privileged persistent compromise is outside the baseline threat model unless a later deployment adds an external trust root, append-only audit service, hardware-backed identity, or another specifically reviewed boundary.

JCS, Merkle trees, or content hashes alone do not solve privileged writer compromise and are not requirements here.

## 5. Security properties and non-properties

### 5.1 Properties G17 requires

A conforming deployment must ensure that:

- consumers cannot create authoritative records through the query API;
- authority services resolve consumer selectors against producer-owned immutable records;
- producer write capability is separated from ordinary consumer capability;
- a returned record may be copied or mutated by a consumer without changing producer state;
- exact source revision and published producer snapshot are bound to every positive result;
- all supporting and competing records remain inspectable;
- ambiguity and conflict fail closed;
- completeness is producer-domain completeness, not completeness of a consumer candidate list;
- relationship authority is distinct from proximity or candidate nomination; and
- derived evidence cannot increase authority beyond its upstream support.

### 5.2 Properties G17 does not claim by architecture alone

G17 does not claim that:

- a Python underscore prevents malicious same-process replacement;
- a SHA-256 hash proves who produced an object;
- a self-consistent JSON object proves its source;
- a snapshot ID proves a snapshot is genuine;
- `CORROBORATED` proves independent source authority;
- a confidence score proves identity, completeness, or binding;
- a candidate list is complete because it is internally consistent;
- JCS or a Merkle root authenticates an untrusted producer;
- spatial proximity proves physical/semantic attachment; or
- producer-store security survives compromise of the producer's own privileged credentials without an additional trust root.

## 6. Proposed component model

The architecture is intentionally split into a general source store and typed semantic authorities.

### 6.1 `SourceObservationStore`

Responsibilities:

- own immutable source revisions;
- own raw and normalized observations;
- own derivation lineage;
- own source-domain coverage records;
- own published producer snapshots;
- enforce record identity and uniqueness;
- expose read-only lookup/enumeration to authority services; and
- retain invalidation relationships between source/observation generations and dependent semantic records.

This is the source-of-authority substrate. It does not decide every opening/wall semantic question itself.

### 6.2 `OpeningObservationAuthority`

Responsibilities:

- establish whether a producer-owned opening observation exists;
- expose its source location and lineage;
- compare producer-owned observations/instances as `PROVEN_SAME`, `PROVEN_DISTINCT`, or `AMBIGUOUS`; and
- resolve independently supported dimension evidence to an exact physical opening identity.

### 6.3 `OpeningUniverseAuthority`

Responsibilities:

- enumerate the complete eligible opening universe from a producer-owned bounded source domain;
- report unresolved and ambiguous members rather than dropping them;
- separate source-domain completeness from downstream filters; and
- expose a stable universe/snapshot identity plus coverage explanation.

### 6.4 `HostUniverseAuthority`

Responsibilities:

- enumerate the complete eligible host universe for the producer-owned domain;
- distinguish host existence and identity from nomination/binding; and
- expose unresolved host observations and coverage gaps.

### 6.5 `HostRelationshipAuthority`

Responsibilities:

- resolve exact opening-to-host physical relationship as `PROVEN_BOUND`, `PROVEN_NOT_BOUND`, or `AMBIGUOUS`;
- retain relationship evidence and competing host candidates; and
- refuse to equate proximity/overlap/containment with binding.

### 6.6 `WallDatumRelationshipAuthority`

Responsibilities:

- resolve exact wall physical identity + exact segment/span + exact datum observation + semantic role;
- distinguish lower and upper datum relationships;
- bind cross-view/source relationships explicitly when such a relationship is established by producer evidence;
- enforce revision/snapshot freshness; and
- refuse scalar authority for split-level, stepped, sloped, or variable walls unless a single scalar relationship is independently proven representative.

### 6.7 `AuthorityInspector`

Responsibilities:

- trace any positive or blocked result to its producer records;
- expose source locations, revision, snapshot, lineage, contradictions, universe coverage, and downgrade conditions; and
- provide an inspectable explanation graph without an opaque `authority=True` shortcut.

## 7. Query boundary

A consumer query is a **request to look up producer state**, not a claim of the answer.

Conceptually:

```text
consumer selector
    -> authority service
        -> SourceObservationStore / producer snapshot
            -> typed result + explanation references
```

Acceptable selector fields include source/document ID, source revision, producer snapshot/evidence snapshot/graph snapshot IDs, page, viewport, target identifier, and a bounded scope selector.

The query API must not contain fields equivalent to:

```text
observation = <caller-created record>
universe = <caller-created members>
complete = true
relationship = <caller-created proof>
authority = true
```

A consumer can construct an object that *looks* identical to a producer record. That copy has no write path into the authority store and is not accepted where an authoritative record identifier is required.

## 8. Source ingestion contract

The intended chain is:

```text
immutable source bytes
    -> decoded native observations and/or OCR/raster observations
    -> producer-owned raw source observations
    -> normalized observations
    -> derived reconstructions where needed
    -> typed semantic relationship decisions
    -> bounded producer snapshots / universes
    -> consumer query
```

### 8.1 Immutable source revision

Before observations are published, the producer records an immutable source revision containing at least:

- producer-assigned document/source identity;
- revision identity;
- source-content hash as an integrity binding;
- immutable byte/object locator or equivalent source reference;
- ingestion run identity;
- decoder/extractor versions; and
- publication generation.

The hash binds a producer-owned revision to content. It is not accepted as proof from a consumer.

### 8.2 Decoding is not authority by itself

PDF vector primitives, OCR tokens, raster detections, reconstructed lines, and parsed annotations are observations with different provenance and uncertainty. Successful decoding does not automatically prove opening identity, host binding, datum binding, or universe completeness.

The producer records decoder coverage and failures separately from semantic results.

### 8.3 Raw observations

A raw observation retains, where applicable:

- immutable source identity;
- revision;
- page;
- view/viewport;
- evidence snapshot;
- graph snapshot when applicable;
- source primitive/evidence IDs;
- producer observation ID;
- observation type;
- raw source geometry;
- raw source text/value;
- decoder/extractor identity/version; and
- source locator sufficient for inspection.

### 8.4 Normalized observations

Normalization can convert units, coordinate representations, text form, or geometry encoding. It must retain a derivation edge to raw inputs and record the transformation version.

Normalization cannot strengthen the raw observation's authority.

### 8.5 Derived reconstruction

Grouping, snapping, wall reconstruction, symbol recognition, topology inference, instance clustering, or similar reconstruction is explicitly marked derived.

Derived reconstruction may reduce uncertainty by combining **independent** source support, but it cannot claim a stronger source fact merely because an algorithm is confident or internally consistent. Its maximum authority is bounded by the support and relationship rules of its inputs.

### 8.6 Semantic relationship decisions

Semantic decisions are first-class producer records, not incidental metadata on a quantity object. They include exact subjects/objects, relationship kind, source support, competing observations, decision rule/version, snapshot, and outcome.

## 9. Minimum producer-owned record model

Names are illustrative, not implementation-prescriptive.

### 9.1 `SourceRevision`

Minimum fields:

- `document_id`
- `revision_id`
- `source_sha256`
- immutable source locator/reference
- `ingestion_id`
- producer version
- decoder/extractor versions
- source page/view inventory
- publication state

### 9.2 `SourceCoverageRecord`

Minimum fields:

- source revision;
- domain/partition identifier;
- page/view/viewport or other bounded source partition;
- decoder/extractor attempted;
- coverage state: complete / partial / unavailable / failed;
- failure reasons;
- unresolved primitive IDs if known; and
- producer generation.

A universe is not complete if a required partition has unresolved coverage that could contain eligible members.

### 9.3 `SourceObservation`

Minimum fields:

- producer-assigned `observation_id`;
- source revision;
- page/view/viewport;
- observation kind;
- source primitive/evidence IDs;
- raw geometry/text/value;
- normalized representation if applicable;
- provenance/derivation edges;
- creation producer/version; and
- immutable publication generation.

### 9.4 `IdentityRelationship`

Minimum fields:

- relationship ID;
- exact participating producer observation/instance IDs;
- outcome: `PROVEN_SAME`, `PROVEN_DISTINCT`, or `AMBIGUOUS`;
- independent support record IDs;
- competing evidence IDs;
- rule/producer version;
- source revision/snapshot; and
- downgrade/invalidation dependencies.

### 9.5 `SemanticRelationship`

Used for dimensions, host binding, and datum binding with a typed relationship kind. Minimum fields:

- relationship ID;
- typed subject ID;
- typed object ID;
- exact scope/segment where applicable;
- semantic role;
- outcome;
- support IDs;
- contradiction IDs;
- producer rule/version;
- revision/snapshot; and
- invalidation dependencies.

### 9.6 `ProducerSnapshot`

Minimum fields:

- producer-owned snapshot ID;
- exact source revision(s) included;
- publication generation;
- included source partitions;
- coverage records;
- observation/relationship generation bounds;
- unresolved/conflicting record counts and references; and
- state: publishable / incomplete / integrity failure.

The snapshot may use content hashes for integrity, but the trusted property comes from obtaining it from the producer-owned channel/store, not from the hash itself.

## 10. Store ownership and mutability

### 10.1 Writers

Only trusted producer ingestion/publication code writes source-authority records. Quantity consumers, UI handlers, measurement resolvers, and arbitrary application callers receive no producer-write capability.

### 10.2 Readers

Authority services receive read access. Ordinary consumers preferably call typed authority services rather than querying raw store tables directly.

### 10.3 Immutability point

A record becomes immutable when included in a published producer snapshot. Corrections create a new record generation and/or source revision; they do not rewrite the historical published record in place.

### 10.4 Revision handling

A source revision is immutable. Changed source bytes require a new revision/generation. Records bound to an older revision become stale for a query requiring the newer revision.

### 10.5 Snapshot creation

Snapshot publication is a producer action. Publication captures source coverage and unresolved/conflicting state as well as positive observations. A snapshot with integrity failure or incomplete required coverage cannot advertise a complete eligible universe.

### 10.6 Replacement and invalidation

Replacing/superseding a source observation, identity decision, relationship record, or coverage record invalidates dependent authority results. Dependents are keyed to exact revision/snapshot/generation and must be recomputed or become stale/blocked.

### 10.7 Deterministic IDs

Deterministic IDs are permitted for stable addressing when derived from producer-owned inputs and a versioned ID rule. Determinism does not itself create authority.

A caller who computes the same string does not thereby create the backing producer record.

### 10.8 Duplicate IDs

Two different contents under the same producer record ID are a producer-integrity failure. The producer must not choose one silently.

### 10.9 Conflicting records

Conflicting producer observations remain represented and cause ambiguity/conflict unless independent resolving evidence exists. “Latest seen,” highest confidence, nearest geometry, or consumer preference is not a generic conflict resolver.

### 10.10 Returned object mutation

Results returned to a consumer are immutable values or detached read models. Even if consumer code mutates a local copy, that mutation cannot change producer-store state or dependent records.

## 11. Capability A — opening observation existence

Opening existence begins with a producer-owned observation tied to inspectable source material.

A positive result must retain or reference:

- immutable source identity;
- revision;
- page;
- viewport/view;
- evidence snapshot;
- graph snapshot where applicable;
- source primitive/evidence IDs;
- observation ID;
- observation type;
- source geometry/text evidence; and
- derivation lineage where derived.

The statement “opening O1 exists” supplied by a consumer is not evidence. A consumer may request `O1`; the producer must independently have `O1` or return `OBSERVATION_UNAVAILABLE`.

A schedule row may be a real schedule observation without proving that a particular physical opening instance exists. Observation type is therefore part of the authority result.

## 12. Capability B — opening lineage and physical instance identity

Identity comparison returns exactly one of:

- `PROVEN_SAME`
- `PROVEN_DISTINCT`
- `AMBIGUOUS`

### 12.1 Evidence that may establish `PROVEN_SAME`

Examples of independently inspectable support include:

- the same producer-owned native source object/instance identity preserved across representations;
- an explicit source cross-reference that independently ties two observations to one physical instance;
- producer lineage showing two normalized/derived observations descend from the same unique source instance without a one-to-many ambiguity; or
- another typed relationship record whose evidence independently establishes physical-instance equivalence.

Multiple weak correlates do not become identity merely by accumulation if they are not independent identity evidence.

### 12.2 Evidence that may establish `PROVEN_DISTINCT`

Examples include:

- independently distinct native instance/object identities in a source that represents physical instances;
- an explicit source relationship proving separate instances;
- source-domain multiplicity that establishes two distinct instance records; or
- mutually exclusive physical/source lineage that cannot describe one instance.

### 12.3 Evidence that is insufficient alone

None of the following alone establishes `PROVEN_SAME`:

- tag equality;
- dimension equality;
- coordinate equality after reconstruction;
- bbox overlap;
- schedule type;
- confidence;
- proximity; or
- a caller-supplied lineage claim.

If independent evidence does not resolve identity, outcome is `AMBIGUOUS`.

## 13. Capability C — opening dimensions

Opening dimension authority is four separate layers:

1. **observed dimension evidence** — the producer-owned notation, schedule cell, native property, or measurable source primitive;
2. **interpreted dimension relationship** — what the observed value means (width, height, rough opening, leaf, nominal size, etc.);
3. **target physical opening identity** — the exact physical instance to which the dimension applies; and
4. **final resolved dimension authority** — the dimension result after contradictions and freshness checks.

A caller-supplied `900 x 2100` proves none of these layers.

A valid dimension attached to the wrong opening is blocked. A valid schedule type dimension does not establish a physical instance merely because a nearby symbol has the same tag.

If multiple independently valid dimensions conflict and no producer-owned resolving evidence exists, the result is `DIMENSION_UNRESOLVED` or `CONFLICTING_PRODUCER_OBSERVATIONS`; it is never resolved by highest confidence or caller preference.

## 14. Capability D — complete eligible opening universe

Opening-universe completeness is evaluated over an **independently bounded producer source domain before consumer-local filtering**.

### 14.1 Universe boundary

A universe boundary is producer-owned and binds at least:

- source/document revision;
- producer snapshot/generation;
- included pages/views/partitions;
- domain kind;
- eligibility-policy version; and
- source coverage records for every required partition.

A consumer radius, selected candidate list, local crop, or search result is a downstream query view, not the source-domain boundary used to claim completeness.

### 14.2 Eligibility predicate

The predicate is versioned and defined by the producer/authority contract. It determines which source observations must be accounted for, but it does not permit a consumer to remove inconvenient members from the producer universe.

### 14.3 Completeness condition

A producer universe is complete only when:

- every required source-domain partition has sufficient successful coverage;
- every observation that could satisfy eligibility is accounted for;
- admitted, unresolved, ambiguous, duplicate, and explicitly excluded observations are represented rather than silently dropped;
- duplicate/conflicting IDs are resolved or cause a typed integrity failure; and
- pagination/streaming has reached producer-declared end-of-universe for the same immutable universe identity.

If a required partition is unavailable or could contain undiscovered eligible openings, the universe is `UNIVERSE_INCOMPLETE`.

### 14.4 Unresolved and ambiguous observations

Unresolved observations remain members of the producer accounting set. They may prevent a downstream quantity from becoming FIRM, but cannot be removed to make the universe look complete.

### 14.5 Pagination and streaming

Pagination is transport, not completeness. Every page carries the same immutable universe/snapshot identity and a continuation/end marker controlled by the producer. A single page is never deemed complete solely because the consumer stopped requesting pages.

## 15. Capability E — complete eligible host universe

Host authority uses the same producer-domain completeness rules as opening authority and explicitly separates:

1. **host nomination** — a heuristic candidate, possibly based on nearest/overlap/containment;
2. **host existence** — producer-owned evidence that the physical host exists;
3. **host universe completeness** — all eligible hosts in the independently bounded producer domain are accounted for;
4. **host identity** — the exact physical host instance; and
5. **physical host binding** — independent relationship evidence that the opening belongs to that host.

Nearest wall, bbox overlap, geometric containment, and proximity may nominate a host only. They do not establish host universe completeness or binding.

## 16. Capability F — exact host binding

Exact host binding returns:

- `PROVEN_BOUND`
- `PROVEN_NOT_BOUND`
- `AMBIGUOUS`

`PROVEN_BOUND` requires independent source/producer relationship evidence tying the exact opening physical identity to the exact host physical identity. Examples may include an explicit native topology relationship, an explicit source annotation/linkage, or another producer-owned relationship whose source semantics establish physical hosting.

`PROVEN_NOT_BOUND` similarly requires independent evidence that rules out the relationship; absence from a consumer candidate list is not proof.

If two plausible hosts remain and neither relationship is independently established, outcome is `AMBIGUOUS`.

Spatial scoring can rank nominations for further evaluation but cannot upgrade the binding outcome.

## 17. Capability G — exact wall-segment to datum relationship

Wall-datum relationship authority is a separate typed service even if it uses the same `SourceObservationStore`.

A positive relationship binds:

- exact wall physical identity;
- exact wall segment/span;
- exact datum observation;
- datum semantic role;
- lower or upper relationship;
- source/view relationship where observations come from different views;
- exact source revision;
- evidence/graph/producer snapshot freshness; and
- scalar representativeness when a scalar height is requested.

A valid datum near a wall is not enough. A valid datum attached to an adjacent wall is not enough. Matching “LEVEL 1” labels across sheets are not enough.

For split-level, stepped, sloped, or variable-height walls, a scalar relationship remains unavailable/ambiguous unless independent producer evidence proves that the scalar is valid for the exact requested segment. Otherwise the eventual consumer must use a supported piecewise/profile representation or remain blocked. The producer never chooses the lowest, highest, nearest, most common, or highest-confidence datum as a generic authority rule.

## 18. Inspectability contract

Every positive authority result and every material block must be explainable by an inspection query.

The minimum inspection interface must answer:

- Which source observation established this result?
- Where exactly in the source is that observation?
- Which source revision does it belong to?
- Which producer/evidence/graph snapshot was used?
- Which lineage records connect raw, normalized, and derived evidence?
- Which competing observations existed?
- Which records were unresolved or excluded, and why?
- Why was this opening/host universe considered complete?
- Which coverage records established the universe boundary?
- Why was this host relationship proven, disproven, or ambiguous?
- Why was this wall-datum relationship proven or blocked?
- What contradiction, revision change, or record replacement would downgrade the result?

An opaque `authority=True` is not a conforming explanation.

A conceptual inspection result contains stable references to producer records, not a prose-only explanation generated after the fact.

## 19. Typed failure states

At minimum, authority APIs expose typed outcomes equivalent to:

| Code | Meaning |
| --- | --- |
| `SOURCE_UNAVAILABLE` | Required immutable source material cannot be obtained/verified by the producer. |
| `STALE_REVISION` | Records/result bind an older or different source revision. |
| `SNAPSHOT_MISMATCH` | Requested/result records do not belong to the required producer/evidence/graph snapshot. |
| `OBSERVATION_UNAVAILABLE` | No producer-owned observation exists for the requested target/scope. |
| `LINEAGE_UNRESOLVED` | Producer cannot establish required lineage between observations/instances. |
| `IDENTITY_AMBIGUOUS` | Physical-instance identity is not uniquely proven. |
| `UNIVERSE_UNAVAILABLE` | No producer-owned universe can be produced for the scope. |
| `UNIVERSE_INCOMPLETE` | Required source-domain coverage/accounting is incomplete. |
| `HOST_UNIVERSE_INCOMPLETE` | Eligible host domain is not completely accounted for. |
| `HOST_BINDING_AMBIGUOUS` | Exact opening-to-host relationship is unresolved. |
| `DIMENSION_UNRESOLVED` | Dimension meaning, target, or conflicting values remain unresolved. |
| `DATUM_RELATIONSHIP_UNAVAILABLE` | Exact wall-segment/datum relationship cannot be established. |
| `CONFLICTING_PRODUCER_OBSERVATIONS` | Independently valid producer records conflict without resolving evidence. |
| `PRODUCER_INTEGRITY_FAILURE` | Store/snapshot/ID/content invariants are violated. |

Failure states are not converted to zero, default dimensions, nearest host, default datum, or empty-universe success.

## 20. Monotonicity requirements

All later implementation must preserve these properties.

### M1 — support removal

Removing supporting producer evidence cannot strengthen authority.

### M2 — contradiction addition

Adding an independently valid contradictory observation cannot strengthen authority. It either preserves the prior result when the contradiction is independently disproven by existing evidence, or downgrades/blocks it.

### M3 — query narrowing

Narrowing a consumer query, crop, radius, candidate set, or page request cannot convert an incomplete producer universe into a complete universe.

### M4 — host ambiguity

Adding another plausible host cannot make binding more certain without additional independent resolving evidence.

### M5 — freshness

Stale source revision, evidence snapshot, graph snapshot, or producer generation cannot remain current.

### M6 — replacement invalidation

Replacing/superseding a producer record invalidates all dependent authority results tied to the old record/generation.

### M7 — ambiguity resolution

`AMBIGUOUS` may become a positive/proven result only when additional independent resolving evidence is ingested or an existing contradiction is independently invalidated. Re-ranking the same ambiguous inputs is not enough.

### M8 — authority attenuation

Normalization and derived reconstruction cannot claim an authority class stronger than their independently supported upstream records and relationships.

## 21. Threat and attack matrix

The classifications below apply to the **target security-sensitive deployment** where consumers do not possess producer write credentials and cannot directly replace the producer service/process. The same-process equal-privilege exception is called out explicitly in attack 21.

| # | Attack | Required disposition | Why |
| ---: | --- | --- | --- |
| 1 | Caller constructs an identical-looking observation object. | **Prevented structurally** | Authority APIs accept selectors/producer IDs and re-fetch producer-owned records; caller record bodies are not authority inputs. |
| 2 | Caller invents a source hash. | **Prevented structurally** | A supplied hash cannot create a `SourceRevision` or observation in the producer store; hashes are checked only as bindings on producer-owned records. |
| 3 | Caller copies a valid record and changes target ID. | **Prevented structurally** | Caller copies are not accepted as stored records; typed relationships are re-fetched by producer-assigned IDs and exact subject/object bindings. |
| 4 | Caller replays a stale record from a previous revision. | **Detected and BLOCKED** | Revision/snapshot/generation freshness is checked against producer state; stale records return `STALE_REVISION`/`SNAPSHOT_MISMATCH`. |
| 5 | Caller truncates the opening universe. | **Prevented structurally** | Universe completeness is generated over producer-owned source coverage, not from a caller member list. |
| 6 | Caller filters out an inconvenient opening. | **Prevented structurally** | Consumer filtering creates a downstream view only and cannot modify the underlying universe/completeness result. |
| 7 | Caller shrinks query radius to hide an opening. | **Detected and BLOCKED** | Radius/crop may scope a downstream lookup but cannot upgrade source-domain completeness; completeness remains bound to the producer universe boundary. |
| 8 | Caller declares its list `complete=True`. | **Prevented structurally** | No consumer completeness boolean is accepted as producer completeness. |
| 9 | Duplicate observation IDs carry different content. | **Detected and BLOCKED** | Store uniqueness/content invariants classify this as `PRODUCER_INTEGRITY_FAILURE`; no record is silently preferred. |
| 10 | The same tag is used for multiple physical openings. | **Detected and BLOCKED** | Tag is non-authoritative for identity; absent independent lineage the result is `IDENTITY_AMBIGUOUS`. |
| 11 | A schedule type is presented as a physical instance. | **Detected and BLOCKED** | Observation type and physical-instance lineage are separate; schedule membership does not establish instance existence. |
| 12 | The nearest wall is presented as the host. | **Detected and BLOCKED** | Nearest/overlap/containment is nomination only; exact host binding requires typed independent relationship evidence. |
| 13 | Host enumeration is incomplete. | **Detected and BLOCKED** | Host-universe coverage/accounting must be producer-complete or return `HOST_UNIVERSE_INCOMPLETE`. |
| 14 | Two hosts are both plausible. | **Detected and BLOCKED** | Additional plausible hosts increase ambiguity unless independent binding evidence resolves one relationship. |
| 15 | Valid dimensions are attached to the wrong opening. | **Detected and BLOCKED** | Dimension observation, dimension semantics, exact target identity, and attachment relationship are independently checked. |
| 16 | A valid datum is attached to the wrong wall. | **Detected and BLOCKED** | Datum authority requires a relationship to exact wall physical identity and exact segment/span. |
| 17 | A split-level wall is given one convenient datum. | **Detected and BLOCKED** | Exact-segment relationship and scalar representativeness are required; convenient selection cannot resolve multiple valid bases/tops. |
| 18 | Producer returns conflicting observations. | **Detected and BLOCKED** | Contradictions remain represented and yield conflict/ambiguity until independent resolving evidence exists. |
| 19 | Consumer mutates a returned record. | **Prevented structurally** | Returned data are immutable/detached read models; consumer mutation cannot write producer-store state or alter the published snapshot. |
| 20 | Consumer swaps snapshot IDs. | **Detected and BLOCKED** | Record/snapshot/revision relationships are revalidated against producer state; mismatches return `SNAPSHOT_MISMATCH`. |
| 21 | Same-process code replaces the authority provider. | **Outside declared threat model** for an equal-privilege in-process deployment | Python module privacy cannot prevent this. The target security-sensitive deployment must use a process/service/credential boundary if this attack must be structurally prevented. |
| 22 | Derived reconstruction claims stronger authority than raw evidence. | **Detected and BLOCKED** | Published lineage and authority-attenuation rules reject a derived semantic result whose claimed support exceeds its upstream observations/relationships. |

### 21.1 Persistent privileged tampering

A malicious actor with producer-store write credentials and control of the producer's trusted revision metadata is outside the baseline G17 threat model. Detecting/resisting that actor requires an additional independently administered trust root. G17 deliberately does not pretend that a hash, JCS encoding, or Merkle root creates such a root.

## 22. Relationship to PR #297

PR #297 contains useful concepts for:

- fail-closed completeness/authenticity verification;
- binding a decision to an exact scoped universe;
- explicit admitted/unresolved/excluded accounting;
- freshness/scope mismatch detection; and
- preventing simple self-certification by absence of supplied conflict.

It is **not sufficient** for G17 because its universe/manifests still require an independent authoritative upstream producer. A caller-constructible `AuthorityUniverseFingerprint` or `CompletenessManifest`, even when internally consistent and recomputable, is not the source-authority boundary.

G17 extracts the fail-closed and accounting concepts only. It does not revive, merge, or stack PR #297.

## 23. Relationship to PR #298

PR #298 contains useful concepts for:

- immutable parent content;
- deterministic scope enumeration;
- independently recomputing a local universe from that parent;
- checking local universe/manifest consistency against the supplied parent; and
- explicitly avoiding the claim that hashing alone proves completeness.

Its own contract correctly states that the complete parent snapshot must be obtained through an upstream producer channel rather than from the quantity caller.

It is **not sufficient** for G17 because it does not itself prove that the supplied parent is genuine complete upstream output. A caller can construct a self-consistent parent object unless integration obtains that parent through a separate producer-owned boundary.

G17 extracts the deterministic-enumeration/recomputation concept only. It does not revive, merge, or stack PR #298.

## 24. Relationship to #304 and #305

### 24.1 #304 opening authority

#304 remains frozen and unchanged. Its fail-closed canonical producer placeholder is compatible with G17 because unavailable authority remains unavailable.

G17 corrects one potential future misinterpretation: `_CURRENT_CANONICAL_PRODUCER` being module-owned/private does not make it a security boundary. Future wiring must obtain authoritative records through the producer trust boundary defined here.

The existing opening invariants remain mandatory:

- same tag/dimensions/coordinates are not physical identity;
- local candidates do not prove completeness;
- proximity nominates only;
- schedule type is not a physical instance;
- unresolved opening is not zero;
- physical void and commercial applicability remain separate; and
- gross may remain FIRM while net blocks.

### 24.2 #305 wall-height authority

#305 correctly keeps caller-constructible wall-datum relationship claims diagnostic and fail closed. G17's `WallDatumRelationshipAuthority` is the missing upstream producer contract that a future implementation would need before any datum-derived height route could be reconsidered.

G17 does not alter current #305 behavior and does not create a datum-derived FIRM route.

## 25. Exact missing interface and upstream data requirement

Because no qualifying producer exists on the governing baseline, the implementation blocker can be stated precisely.

### 25.1 Missing interface

The repository lacks a read-only, producer-backed authority interface with these essential semantics:

```text
SourceObservationStore
  get_source_revision(selector) -> producer-owned source revision or typed failure
  get_observation(observation_id, required_snapshot) -> producer-owned observation or typed failure
  enumerate_source_domain(scope, required_snapshot) -> producer-owned coverage + observations or typed failure
  inspect(record_id) -> immutable source/lineage/contradiction references

OpeningObservationAuthority
  observation_exists(selector) -> observation reference or typed failure
  compare_identity(left_ref, right_ref) -> PROVEN_SAME | PROVEN_DISTINCT | AMBIGUOUS
  resolve_dimensions(opening_ref) -> resolved dimensions or typed failure

OpeningUniverseAuthority
  enumerate_eligible(scope, eligibility_policy_version) -> complete producer universe or typed failure

HostUniverseAuthority
  enumerate_eligible(scope, eligibility_policy_version) -> complete producer host universe or typed failure

HostRelationshipAuthority
  resolve(opening_ref, host_ref) -> PROVEN_BOUND | PROVEN_NOT_BOUND | AMBIGUOUS

WallDatumRelationshipAuthority
  resolve(wall_segment_ref, datum_ref, semantic_role) -> proven relationship | ambiguous/unavailable

AuthorityInspector
  explain(result_or_record_id) -> upstream source, lineage, universe, competing evidence, invalidation conditions
```

These are contract sketches, not Python implementation requirements.

### 25.2 Missing upstream data

The producer cannot be implemented honestly until ingestion can supply at least:

1. immutable source bytes/source revision identity under producer control;
2. complete inventory of source pages/views/partitions relevant to the authority scope;
3. decoder/extractor coverage and failure records for those partitions;
4. producer-assigned raw observation IDs tied to source primitives/locations;
5. preserved raw text/geometry/value evidence;
6. normalization/derivation lineage;
7. typed observation kinds separating schedules/types from physical-instance observations;
8. producer-owned snapshot publication with unresolved/conflicting state;
9. independent identity relationship evidence where SAME/DISTINCT is claimed;
10. independent dimension-to-opening relationship evidence;
11. complete eligible opening and host domain accounting; and
12. independent exact host-binding and wall-segment/datum relationship evidence where those relationships are claimed.

If source material or ingestion cannot supply one of these facts, the corresponding authority stays unavailable/ambiguous. The implementation must not invent the missing fact from metadata.

## 26. Deployment recommendation

The logical interfaces can be implemented in-process initially for development, but two claims must remain separate:

### 26.1 Logical non-self-certification

Even in-process, the API can structurally prevent ordinary callers from passing record bodies, booleans, candidate lists, or proof objects as authority. It can require IDs/selectors and re-fetch records from a producer-owned repository abstraction.

This is valuable and testable.

### 26.2 Security against malicious same-process replacement

An in-process implementation cannot honestly claim protection against equally privileged code replacing the provider/repository or monkey-patching calls.

If resistance to malicious consumer code is required, deploy the authority producer behind a process/service/database credential boundary in which:

- consumers receive read/query credentials only;
- producer ingestion owns write credentials;
- published records/snapshots are immutable to consumers; and
- provider identity/configuration cannot be replaced through the ordinary consumer process.

No cryptographic data structure is mandated unless a later architecture decision identifies a specific attack that needs it.

## 27. Physical void and net wall area boundary

G17 deliberately stops before quantity publication.

Future physical opening deduction requires, in order:

- a producer-owned physical opening observation;
- resolved physical opening identity;
- authoritative complete eligible opening universe;
- independently resolved opening dimensions;
- authoritative complete eligible host universe;
- exact physical host binding; and
- any required geometric relationship sufficient to define the physical void.

Commercial/trade applicability remains a separate downstream decision. A proven physical void does not automatically prove that a commercial measurement standard should deduct it.

Therefore gross wall area may remain FIRM while net wall area remains blocked. An unresolved opening is never interpreted as zero opening.

## 28. Explicit non-goals

G17 architecture does not add or require:

- production implementation;
- a new FIRM route;
- JCS;
- Merkle trees;
- an authenticated spatial index;
- cross-sheet CTM or coordinate-transform work;
- benchmark changes;
- gold changes;
- commercial measurement-standard adapters;
- JobHub wiring;
- Streamlit wiring;
- Cursor parity work; or
- PDF-integrity work.

Cross-sheet coordinate transformation remains a separate architecture decision. If later evidence relationships need it, that dependency must be reviewed without silently making coordinate reconstruction itself an authority source.

## 29. Acceptance gates before production implementation

No production slice should begin until review accepts all of the following:

1. the producer trust/deployment boundary and its explicit limitations;
2. source revision ownership and immutable publication rules;
3. minimum observation + coverage + lineage record schema;
4. query APIs that accept selectors rather than caller-authored authority records;
5. universe completeness semantics independent of consumer filtering;
6. identity/dimension/host/datum typed relationship semantics;
7. inspectability requirements;
8. typed fail-closed outcomes;
9. monotonicity rules;
10. attack-matrix dispositions, especially the same-process replacement limitation; and
11. the first implementation slice has a real upstream data source rather than fabricated fixtures masquerading as runtime authority.

Fixtures may test contracts, but runtime authority must come from the producer ingestion path.

## 30. Future implementation roadmap

After this architecture is approved, implement the smallest producer slice test-first in this order:

1. **opening observation existence + producer lineage**;
2. **physical opening identity**;
3. **authoritative opening universe completeness**;
4. **opening dimensions**;
5. **host universe and exact host binding**; and
6. **physical void and net wall area**.

Exact wall-segment ↔ datum relationship authority uses the same producer substrate but remains a separate typed relationship lane and should be implemented only when its upstream source evidence is available and reviewed.

At every stage, unavailable upstream evidence means typed BLOCKED/AMBIGUOUS output rather than invented authority.
