# Guided-review corrections reshape the canonical room topology (user-assisted, default none)

Date: 2026-11-26. Order: owner update on #4764 (7188986762, item 2); MAX continuation 7189639065; claim 7189460183. Design approved by the owner before the build. Base: `main` `b6de14959`; packet format of #4795 head `99bed5343`.

## Observed behaviour

- #4791/#4795 turn saved review marks into a packet: exact source PDF hash, page, native page frame, revision, and per mark a category and native points. Status `USER_CORRECTIONS_PENDING_CONSUMER`; nothing is regenerated.
- Mark categories: external wall, internal wall, swing door, cavity slider, garage door, window, other opening, finish boundary, room outline, exclusion area, known dimension line, reject a candidate.
- The app's rooms come from `pb_next_wall_ring_preview.build_layered_wall_doorway_room_rings`, called by `source_native_trace_preview`. Before this change it took no user input.
- That tracer holds back a room next to a wall interruption it could not explain, even when something else closes the space.
- Points placed by hand are only as precise as a screen pixel unless the editor's snap caught a source end.

## Inference

The corrections should enter the same room tracer as extra, clearly labelled barriers. A second geometry engine would drift from what the app shows.

## Change

1. A new consumer that refuses a packet unless its hash, flags, source hash, page and page frame all match the PDF.
2. Each mark gets one role, and one outcome that says what happened to it:
   - **Wall marks:** a user wall that closes rooms. Never a finished face or an authenticated wall.
   - **Door, window and opening marks:** a temporary closure that closes rooms. Never solid wall; opening deductions unchanged.
   - **Finish boundary:** splits finish areas; not a wall.
   - **Reject:** applied only when the mark crosses exactly one candidate closure or wall piece; otherwise reported as unclear, nothing removed.
   - **Exclusion:** rooms inside it are flagged excluded, not deleted.
   - **Room outline:** compared with the traced rooms; never creates one.
   - **Dimension line:** not geometry; left to the scale step.
3. A user line connects to existing geometry only within the existing 2.5 pt snap at its ends, to every piece in range; an end that touches nothing is reported open.
4. The tracer takes an optional `barrier_view` hook (default none) called just before rooms are formed; `source_native_trace_preview(review_packet=None)` uses it. The automatic result is unchanged; a separate `user_assisted_review` block returns the corrected rooms, each mark's outcome, finish regions and the places still open (`status` + `endpoint_pdf_pts`, the shape the editor's location list reads). A user barrier that runs the whole length of a wall interruption (within the snap) stops it holding a room back; one that covers only part of it does not.
5. Everything stays user-assisted: no measurement, quantity, price, benchmark or automatic authority. MAX wires the screen.

## Verification

- `tests/test_user_assisted_review_topology_v1.py`: 39 synthetic tests (a missing wall piece; a missing partition with an open door; open ends; rejects; exclusion, outline, finish and dimension marks; interruptions only partly covered; packet tampering and foreign source, page and frame; mark order; the preview; the editor's own packet builder, skipped until it is on this branch and passed with #4795's files alongside). 15 single-line mutants each fail a test.
- Preview and tracer suites with originals: 530 passed, 1 skipped; canonical route guard OK.
- 3Laurel floor-plan page with packets from the editor's builder (counts only): automatic summary and PNG unchanged; six temporary closures across open interruptions joined both sides; one reject removed one closure (18 to 17 rooms); one wall mark across the largest room split it into two equal rooms (18 to 19); no authority flag set. Preview time rose from about 40 s to about 60 s with marks.

## Limits

- Rooms only: user wall marks do not complete the building's outer outline.
- Pages over the tracer's 20,000-primitive cap, or without traced walls, abstain with a reason.
- The screen (#4795) still has to pass the packet and draw the block; that is MAX's change.

## Benchmark observations that must not influence the implementation

None used.
