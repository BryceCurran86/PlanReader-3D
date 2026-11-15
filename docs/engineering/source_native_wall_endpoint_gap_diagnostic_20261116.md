# Original PlanReader: source-native wall endpoint gaps (16 Nov 2026)

**Parent:** draft PR #4347. Diagnostic only; no source-authenticated
physical wall, roof, exterior, room, door, ceiling, area or FIRM output.

The existing source-native wall graph now produces bounded, read-only
cross-component endpoint near-miss receipts. Every receipt records:
- original PDF-point tip coordinates and separation;
- original PDF native path IDs from the two candidate wall bands;
- physical_join_authenticated=False, measurement_authorized=False.

The read-only 2.5 PDF-point radius does NOT alter the original 0.03
proof-contact tolerance, close gaps, insert walls, invent opening hosts,
change source path identity, issue quantities or score frozen120.
Short square glyph/fill candidates are excluded from slender tip search.
Only nearest distinct-source candidate per tip is retained, capped at 64.
The app preview marks these possible unjoined endpoints MAGENTA.

**Actual source replay (private files on owner PC only):**
- Acacia House Brisbane source floor plan p2: 21 disconnected source
  wall-band components, zero qualifying near misses, no room
  candidates, physical exterior ABSTAINED, zero customer quantities.
  This does not rule out distant, non-slender or entirely missing walls.
- 3Laurel A0.3 p3: 157 disconnected native wall-band components,
  14 qualifying near misses (closest 0.4252 PDF points),
  16 unverified candidate regions, physical exterior ABSTAINED,
  zero customer quantities.

Owner-private JSON and PNG in private_packets/PlanReader_Validation_20261116/
source_native_nearmiss_20261116. No original source PDFs committed.

To promote physical joins, independently inspect source path owners,
wall family/thickness, actual junction/door/host evidence and
the real exterior boundary. Near endpoints alone never satisfy
source or commercial physical wall authority.
