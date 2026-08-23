# Park Log — Resolving the Parked Review Items

**Date:** 2026-08-23 · **Branch:** `parked/review-2026-08-23`

Each parked item from `docs/improvement-review.md` §2 was discussed, decided,
and implemented as its own commit on this branch. One entry per item below.
The review file is removed in the final housekeeping commit; this log is the
permanent record.

---

## P9 — Event delete precedence (`app/api.py`)

**Was:** `DELETE /api/events?link=X&source=Y` deleted by link and silently
ignored `source`.

**Decision:** reject with **400** when both parameters are given — compound
deletes must be two deliberate calls.

**Changed:** both-given guard in `delete_event`; new contract test
(`test_delete_events_with_both_params_returns_400`). UI unaffected (it never
sends both).
