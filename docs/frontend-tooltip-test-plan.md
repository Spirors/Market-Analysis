# Frontend tooltip / global refresh / news chips — manual test plan

Scope: the tooltip system (static/js/tooltip.js), the single global Refresh
affordance, and the news filter chips. Run against a live dashboard at
http://127.0.0.1:8000 (start with `python run.py`, wait for the first
`/api/dashboard` load).

## 1. Keyboard tab order through every card

1. Press Tab repeatedly from the page top.
2. Expect the focus order to walk: Refresh → per-card reorder ↑/↓ → info (ⓘ)
   buttons → any card controls (week select, chips, tag pills, earnings
   controls) → footer reset-layout.
3. Every info button shows a visible focus ring (blue outline) and reads
   "About the <card> card" to a screen reader.
4. Per-card ↻ is **removed everywhere** — no card carries a refresh icon. The
   header **Refresh** button is the single refresh affordance.
5. Note: the Fragility card is hidden when it has no flags, so its controls
   are not in the tab order — expected. When it is revealed, its ⓘ tooltip
   ("Sub-card of risk …") is keyboard-reachable like every other card.

## 2. Tooltip behavior: hover, focus, Escape

1. Hover any card's ⓘ icon → the tooltip appears above the icon (below it
   when the icon sits near the top of the viewport), dark surface, white
   text, "Depends on …" pills.
2. Move the mouse onto the tooltip surface → it stays open; move off both →
   it closes after ~120 ms.
3. Keyboard: Tab to an ⓘ icon → tooltip appears on focus; Tab away → closes.
4. With focus still on the icon, press Escape → tooltip closes and stays
   closed until the icon is re-focused or hovered.
5. Resize the window while a tooltip is open → it repositions to stay
   anchored to its icon.
6. Only one tooltip is open at a time.

## 3. Narrow-viewport placement

1. Shrink the window to ~380 px wide.
2. Hover the ⓘ on the first card (Risk divergence) → tooltip appears BELOW
   the icon (top placement flips), and its right edge stays inside the
   viewport (clamped).
3. Hover the ⓘ on the last card (Market events timeline) → tooltip appears
   ABOVE the icon when "bottom" would run off-screen.
4. No horizontal scrollbar appears because of the tooltip.

## 4. Global refresh

1. Click the header **Refresh** button → it reads "Refreshing…" and is
   disabled; on completion it returns to "Refresh".
2. The header "As of" timestamp advances, and every card re-renders with the
   new payload.
3. Coverage badges (e.g. "2/3" on Risk when a source is missing) and the
   per-card vintage stamps still appear after the refresh, now in the full
   "As of YYYY-MM-DD HH:MM ET" format (same as the page-level header).
4. No card carries a per-card ↻. The Analysis card's run history still loads
   automatically on first render and after every global refresh.

## 5. News filter chips

1. Region chips (US / Global / Asia / Europe / Middle East / Russia/Ukraine /
   Korea / Japan / China / Other) are multi-select: click several, the
   timeline narrows to events matching any selected region.
2. Source-weight chips (High / Med / Low) are single-select: clicking Med
   while High is active replaces it; clicking the active chip clears it.
3. Topic chips (Rates / Equity / Macro / Micro) are multi-select and derived
   from category + keywords.
4. All chip rows show per-week counts that match the selected timeline week.
5. Chips compose with the existing tag chips (including the "ai" tag) — e.g.
   tag "ai" + region "US" keeps only AI-tagged US events.

## 6. Event row metadata

1. Every timeline row shows a colored region pill (e.g. "US", "Korea"),
   a source-weight badge (High = filled blue, Med = outlined, Low = muted),
   and a finance-relevance chip (0–10, color-graded: grey/amber/blue/red).
2. The region pill is the single place the region appears — the generic tag
   pills no longer repeat it.

## 7. Seed-only toggle

1. Check **Seed items only** in the week toolbar → only Wikipedia / Curated
   (gauge) events remain.
2. Uncheck → live RSS events return.
3. The toggle persists across a page reload and composes with every other
   filter.
4. The toggle must never be removed — it is the legacy Wikipedia view
   (hard rule).

## 8. Persistence

1. Select a region chip, a weight chip, a topic chip, and the seed toggle.
2. Reload the page → all selections and the toggle are restored; the
   timeline reflects them immediately.
3. Card order (dashLayout) survives unchanged — including layouts saved by
   older versions (one-time migration on read).