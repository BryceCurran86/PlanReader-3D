# Opening Vertical Placement Authority V1

**TEST-ONLY / EXPECTED-RED FOUNDATION — DO NOT MERGE OR FREEZE YET**

Base: `bb61a8dee24c71b12cffcbb19e8dd89965b6e4fe` (merged authenticated host-binding V3).

This contract proves one proposition only:

> an already authenticated physical opening instance is vertically placed from `z0` to `z1` by exact producer-owned source evidence.

It does not prove host binding, width, height, physical void, deduction permission, net wall area, commercial publication, or JobHub publication.

## Positive route

The first admissible route is deliberately narrow and source-explicit:

1. merged schedule-row ↔ physical-opening-instance binding identifies the exact governing row;
2. a producer-owned semantic row authority independently re-resolves that exact row from trusted native source text;
3. the row/header explicitly identifies rough/structural-opening sill/bottom and rough/structural-opening head/top semantics;
4. physical units are explicit in the source and normalized only after unit proof;
5. `z1 > z0` and the vertical span is consistent with separately authenticated opening height before a later physical-void layer may consume both.

A generic `SILL`, `HEAD`, `HEIGHT`, frame/leaf/clear-opening value, nearby elevation text, repeated type mark, OCR-only text, or the fact that an opening is called a door cannot establish physical wall-void placement.

No rule may assume door sill = floor level or window sill/head defaults. Missing placement is unknown, never zero.

## Separation of authorities

The implementation should keep two propositions distinct:

- `ScheduleRowVerticalPlacementAuthority`: this exact authenticated schedule row contains explicit rough/structural-opening bottom/top evidence.
- `OpeningVerticalPlacementAuthority`: that semantic row evidence applies to this exact physical opening because the merged schedule-instance binding proves the relationship.

The row authority must not know or invent physical opening identity. The opening authority must not parse raw caller text or accept caller `z0/z1`.

## Public caller firewall

Ordinary public inputs may contain selectors/lineage only. They must not accept:

- `z0`, `z1`, sill/head values, centre elevation;
- raw height, width, area or opening polygon;
- raw schedule text, OCR text or header text;
- caller units, conversion factors or basis labels;
- default/typical sill/head/height;
- confidence, nearest/first/radius tie-breakers;
- caller completeness/authenticated flags.

## Required fail-closed behavior

- no exact schedule-instance binding -> ABSTAIN/CONFLICT;
- no explicit rough/structural sill/bottom + head/top -> ABSTAIN;
- generic sill/head headings -> ABSTAIN;
- frame/leaf/clear-opening vertical values -> ABSTAIN;
- missing units -> ABSTAIN;
- conflicting explicit units -> CONFLICT;
- top <= bottom -> CONFLICT/ABSTAIN, never positive;
- wrong document/revision/source SHA/snapshot/row/opening -> ABSTAIN;
- duplicate/ambiguous governing rows remain upstream conflict;
- added contradictory placement evidence cannot strengthen authority;
- caller-invented row ids cannot mint placement.

## Freeze rule

This validator is not frozen when first opened because it is authored with the production contract. Freeze only after an independent review confirms the attack matrix, exact test blob, baseline expected-RED replay, and zero production-file changes. Production must then satisfy that exact frozen blob unchanged.
