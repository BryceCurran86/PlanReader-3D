# Opening Host Frame Authority V1

**TEST-ONLY / EXPECTED-RED / SELF-AUTHORED / NOT FROZEN / DO NOT MERGE**

Base: `bb61a8dee24c71b12cffcbb19e8dd89965b6e4fe`.

This authority proves one source-space proposition only:

> this exact authenticated physical opening and exact authenticated host binding occupy this deterministic interval in a shared source-space host-wall frame.

It does not prove scale, physical width/height, vertical placement, a metric physical void, deduction permission, net wall area or commercial publication.

## Positive prerequisites

- G17 physical-opening existence from producer-owned visible native PDF geometry;
- exact local physical-opening identity;
- merged #381 unique host binding for that same opening and exact source scope;
- complete source-backed `PhysicalWallCandidateAuthority` for the same page/scope;
- the binding's exact member wall-candidate IDs must resolve back to producer-owned `WallCandidate.centerline_pts`;
- those authenticated members must deterministically form the supported straight two-face host band;
- the unique G17 jamb-bounded geometry must re-resolve from producer-owned source observations;
- opening, host binding and wall scope lineage must agree exactly.

## Positive record

A positive source-space frame may carry:

- exact document/revision/source SHA/snapshot/page/decision scope lineage;
- exact opening identity and host-binding record identities;
- host-wall scoped binding identifier (address only, not stronger physical-wall identity);
- deterministic source-space origin at the canonical start of the authenticated host baseline;
- deterministic canonical host axis and normal;
- the opening's source-space interval `u0_pt .. u1_pt` projected into that shared host baseline;
- source-space wall thickness in PDF points;
- declared coordinate unit `pdf_point`;
- immutable source observation IDs used to re-prove the opening geometry.

For the six-segment validator fixture, the authenticated wall band spans x=20..280 with centreline y=90 and the jamb aperture spans x=120..160. Therefore the shared frame is `origin_pt=(20, 90)`, `u0_pt=100`, `u1_pt=140`, thickness `20` PDF points. The opening must **not** reset itself to `u0_pt=0`.

No millimetre/metre values may be published here. Physical unit mapping is a separate authority (#409 foundation).

## Public firewall

Callers may provide only source observation and host-binding selectors at publication time. The producer itself may be constructed only from sealed producer-owned opening, host-binding and physical-wall-candidate authorities. Callers cannot submit host IDs, candidate lists, raw wall geometry, origin, axis, normal, jambs, u0/u1, thickness, scale, conversion factors, confidence, nearest/first/radius, or completeness claims.

## Invariants

- cross-wired host binding -> ABSTAIN/CONFLICT;
- wrong opening selector -> ABSTAIN/CONFLICT;
- missing/incomplete/mismatched wall scope -> ABSTAIN/CONFLICT;
- curved or non-deterministic host geometry is unsupported in V1 and fails closed;
- raw-mode/non-visible physical opening -> ABSTAIN;
- ambiguous G17 aperture -> ABSTAIN/CONFLICT;
- ambiguous host binding -> ABSTAIN/CONFLICT;
- translating the source drawing changes the source origin but preserves the opening's shared-wall `u` interval and thickness;
- reversing primitive segment direction must not reverse the canonical shared host frame;
- equivalent rotations may rotate the source frame but must preserve the wall-local interval/thickness;
- candidate wall IDs remain addresses only; authenticated geometry comes from the sealed source-backed wall authority;
- no scale or physical units are inferred from PDF-point spans.

## Freeze rule

This validator is self-authored and remains **NOT FROZEN** after this shared-frame correction. It must not be frozen without independent review plus a pinned expected-RED baseline replay. Production must satisfy the eventual exact frozen blob unchanged.
