// Frontend (no-browser) coverage for the UTC timestamp contract shared with
// the backend. `app/news.py:_to_iso` now emits an explicit "Z"; legacy
// `data/events.json` values are naive. `events.js parseUtc`/`weekStart` must
// treat a missing designator as UTC so week labels and `.tl-date` agree with
// the stored UTC date (the header/card as-of is ET).
//
// These are pure-function assertions — no page/browser is launched, so the
// spec is deterministic regardless of the runner's local timezone.

import { test, expect } from "@playwright/test";
import { parseUtc, weekStart } from "../../static/js/events.js";

test.describe("news timestamps are parsed as UTC", () => {
  test("naive legacy and Z-suffixed values are the same instant", () => {
    const naive = parseUtc("2026-09-24T00:00:00");
    const aware = parseUtc("2026-09-24T00:00:00Z");
    expect(naive).not.toBeNull();
    expect(aware).not.toBeNull();
    expect(naive.getTime()).toBe(aware.getTime());
    expect(naive.toISOString()).toBe("2026-09-24T00:00:00.000Z");
  });

  test("an explicit offset normalises to its UTC instant", () => {
    expect(parseUtc("2026-09-24T09:00:00+09:00").toISOString())
      .toBe("2026-09-24T00:00:00.000Z");
  });

  test("empty / malformed values are null (undated bucket)", () => {
    expect(parseUtc("")).toBeNull();
    expect(parseUtc(null)).toBeNull();
    expect(parseUtc("garbage")).toBeNull();
  });

  test("week bucket is UTC and identical for naive and aware input", () => {
    // 2026-09-24 is a Thursday; its Monday-start week begins 2026-09-21.
    const naive = weekStart("2026-09-24T00:00:00");
    const aware = weekStart("2026-09-24T00:00:00Z");
    expect(naive).not.toBeNull();
    expect(naive.toISOString()).toBe("2026-09-21T00:00:00.000Z");
    expect(aware.getTime()).toBe(naive.getTime());
    // The bucket key is on the UTC calendar — it agrees with the row's UTC
    // `.tl-date`, so the timeline can't disagree with itself across zones.
    expect(naive.toISOString().slice(0, 10)).toBe("2026-09-21");
  });

  test("undated input yields no week bucket", () => {
    expect(weekStart("")).toBeNull();
    expect(weekStart("garbage")).toBeNull();
  });
});
