// Reusable tooltip component.
//
// attachTooltip(el, { text, placement = "top", ariaLabel, deps = [] })
//   el        — trigger element (button/icon, focusable)
//   text      — main body copy (plain text, rendered via textContent)
//   placement — "top" (default) or "bottom"; flips to the other side when the
//               chosen side would run off the viewport
//   ariaLabel — optional accessible name for the trigger (falls back to a
//               generic "About …" label)
//   deps      — optional list of cross-section dependency hints, rendered as
//               small pills inside the tooltip (aria-hidden: decorative)
//
// Accessibility contract (WCAG 2.1 AA):
//   - surface carries role="tooltip"
//   - trigger carries aria-describedby -> surface id
//   - shows on hover (mouse) and on focus (keyboard)
//   - hides on mouseleave, blur, and Escape while the trigger/surface has focus
//   - repositions on window resize and scroll
//   - survives the mouse hopping from trigger onto the tooltip surface
//     (and focus moving between the two) without flickering closed

let ttSeq = 0;
let open = null; // the single visible tooltip { surface, trigger, placement, hide }

const GAP = 8; // px between trigger and tooltip

function _makeSurface(text, deps) {
  const surface = document.createElement("div");
  surface.className = "tt";
  surface.setAttribute("role", "tooltip");
  surface.id = `tt-${++ttSeq}`;
  surface.hidden = true;

  const body = document.createElement("div");
  body.className = "tt-body";
  body.textContent = text;
  surface.appendChild(body);

  if (deps && deps.length) {
    const row = document.createElement("div");
    row.className = "tt-deps";
    row.setAttribute("aria-hidden", "true"); // decorative hints, not re-read
    const label = document.createElement("span");
    label.className = "tt-dep-label";
    label.textContent = "Depends on";
    row.appendChild(label);
    for (const d of deps) {
      const pill = document.createElement("span");
      pill.className = "tt-dep";
      pill.textContent = d;
      row.appendChild(pill);
    }
    surface.appendChild(row);
  }
  return surface;
}

// Surface is position:fixed, so viewport coordinates are used directly.
function _position(surface, trigger, placement) {
  const r = trigger.getBoundingClientRect();
  const s = surface.getBoundingClientRect();
  let top;
  if (placement === "bottom") {
    top = r.bottom + GAP;
    if (top + s.height > window.innerHeight - GAP) top = r.top - s.height - GAP;
  } else {
    top = r.top - s.height - GAP;
    if (top < GAP) {
      placement = "bottom";
      top = r.bottom + GAP;
    }
  }
  let left = Math.round(r.left + r.width / 2 - s.width / 2);
  left = Math.max(GAP, Math.min(left, window.innerWidth - s.width - GAP));
  surface.setAttribute("data-placement", placement);
  surface.style.left = `${left}px`;
  surface.style.top = `${Math.max(GAP, top)}px`;
}

function _repositionOpen() {
  if (open) _position(open.surface, open.trigger, open.placement);
}
window.addEventListener("resize", _repositionOpen);
window.addEventListener("scroll", _repositionOpen, true);

// One shared Escape handler: only the open tooltip whose trigger/surface has
// focus is dismissed.
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || !open) return;
  const t = document.activeElement;
  if (t === open.trigger || open.surface.contains(t)) open.hide();
});

export function attachTooltip(el, opts = {}) {
  const text = opts.text || "";
  const placement = opts.placement === "bottom" ? "bottom" : "top";
  const deps = Array.isArray(opts.deps) ? opts.deps : [];
  const surface = _makeSurface(text, deps);
  document.body.appendChild(surface);

  if (opts.ariaLabel) el.setAttribute("aria-label", opts.ariaLabel);
  el.setAttribute("aria-describedby", surface.id);

  const state = { surface, trigger: el, placement, hover: false, focus: false, shown: false };
  let hideTimer = null;

  const isActive = () => state.hover || state.focus;

  const show = () => {
    if (state.shown) return;
    if (open && open !== state) open.hide();
    surface.hidden = false;
    _position(surface, el, placement);
    state.shown = true;
    open = state;
  };

  const hide = () => {
    clearTimeout(hideTimer);
    if (!state.shown) return;
    surface.hidden = true;
    state.shown = false;
    if (open === state) open = null;
  };
  state.hide = hide;

  // Small grace period so moving between the trigger and the surface (or a
  // focus hand-off between the two) never flashes the tooltip closed.
  const scheduleHide = () => {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => { if (!isActive()) hide(); }, 120);
  };

  // Mouse: hover the trigger or the surface keeps it open.
  el.addEventListener("mouseenter", () => { state.hover = true; clearTimeout(hideTimer); show(); });
  el.addEventListener("mouseleave", (e) => {
    if (e.relatedTarget && surface.contains(e.relatedTarget)) return; // hopping onto the surface
    state.hover = false;
    scheduleHide();
  });
  surface.addEventListener("mouseenter", () => { state.hover = true; clearTimeout(hideTimer); });
  surface.addEventListener("mouseleave", (e) => {
    if (e.relatedTarget && (e.relatedTarget === el || el.contains(e.relatedTarget))) return;
    state.hover = false;
    scheduleHide();
  });

  // Keyboard: focus the trigger (or, defensively, the surface) keeps it open.
  el.addEventListener("focus", () => { state.focus = true; clearTimeout(hideTimer); show(); });
  el.addEventListener("blur", (e) => {
    if (e.relatedTarget && surface.contains(e.relatedTarget)) return;
    state.focus = false;
    scheduleHide();
  });
  surface.addEventListener("focusin", () => { state.focus = true; clearTimeout(hideTimer); });
  surface.addEventListener("focusout", (e) => {
    if (e.relatedTarget && (e.relatedTarget === el || el.contains(e.relatedTarget))) return;
    state.focus = false;
    scheduleHide();
  });

  return { show, hide, surface };
}