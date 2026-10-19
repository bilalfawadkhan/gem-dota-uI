/**
 * Stepping through the fights: Previous / Next arrows, and a timeline that opens a fight on a click.
 *
 * The site's fights figure lets you drag across its timeline to pick a stretch. That works as a
 * filter: only the fights in the stretch stay listed, and when the open fight is not one of them
 * the replay is swapped for another fight, or closed when the stretch holds none. In the app that
 * made the replay vanish and reappear. So here a drag does nothing, a click on a fight's bar opens
 * that fight, and the arrows step to the fight before or after the open one.
 *
 * All of it works through the figure's own DOM (the fight list's buttons), so the site's code is
 * not changed: opening a fight is a click on its list button, exactly as a user would.
 */
import type { FightsData } from "@site/lib/fights-data";

/** A click this close to a fight's bar (a fraction of the timeline) opens it. */
const NEAR_FRACTION = 0.025;
/** A press and release this close together (in pixels) are a click; farther apart is a drag. */
const CLICK_SLOP_PX = 4;

/** The fights the list currently shows, in time order (the size filter decides which). */
function listedFights(figure: HTMLElement): HTMLElement[] {
  return [...figure.querySelectorAll<HTMLElement>(".fights-fig-list [data-fight]")];
}

function openIndex(items: HTMLElement[]): number {
  return items.findIndex((b) => b.getAttribute("aria-pressed") === "true");
}

function makeButton(text: string, label: string): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "chip";
  button.textContent = text;
  button.setAttribute("aria-label", label);
  return button;
}

/** Add the arrows above the replay and keep them in step with the open fight. */
function addArrows(figure: HTMLElement): void {
  const nav = document.createElement("div");
  nav.className = "fight-nav";
  nav.setAttribute("role", "group");
  nav.setAttribute("aria-label", "Step through the fights");
  const previous = makeButton("◀ Previous fight", "Previous fight");
  const next = makeButton("Next fight ▶", "Next fight");
  const label = document.createElement("span");
  label.className = "fight-nav-label";
  const kind = document.createElement("span");
  kind.className = "fight-nav-kind";
  const middle = document.createElement("div");
  middle.className = "fight-nav-middle";
  middle.append(label, kind);
  nav.append(previous, middle, next);
  figure.prepend(nav);

  const refresh = () => {
    const items = listedFights(figure);
    const at = openIndex(items);
    previous.disabled = at <= 0;
    next.disabled = at < 0 || at >= items.length - 1;
    if (at < 0) {
      label.textContent = items.length ? "No fight open" : "No fights";
      kind.textContent = "";
      return;
    }
    const open = items[at];
    const time = open.querySelector("time")?.textContent ?? "";
    label.textContent = `Fight ${open.dataset.fight} · ${time}  (${at + 1} of ${items.length})`;
    // The list says "· playback" for a fight that has a map replay.
    const hasMap = (open.textContent ?? "").includes("playback");
    kind.textContent = hasMap ? "Map replay" : "Breakdown only: no map replay";
    kind.dataset.map = String(hasMap);
  };

  const step = (by: number) => {
    const items = listedFights(figure);
    items[openIndex(items) + by]?.click();
  };
  previous.addEventListener("click", () => step(-1));
  next.addEventListener("click", () => step(1));

  // The figure redraws its list and panel itself; follow it.
  let queued = false;
  const observer = new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      refresh();
    });
  });
  for (const selector of ["[data-list]", "[data-panel]"]) {
    const part = figure.querySelector(selector);
    if (part) observer.observe(part, { subtree: true, childList: true, attributes: true, attributeFilter: ["aria-pressed"] });
  }
  refresh();
}

/** Turn the timeline's drag-to-filter into click-to-open (see the file comment). */
function openFightOnClick(figure: HTMLElement, data: FightsData): void {
  const timeline = figure.querySelector<SVGSVGElement>("[data-timeline] svg");
  if (!timeline) return;
  timeline.style.cursor = "pointer";
  const hint = figure.querySelector(".strip-hint");
  if (hint) hint.textContent = "Click a fight to open its replay";

  // Capture phase, and stopping every other listener: the site's drag picker never sees these.
  // A press and release that stay put are a click and open a fight; a drag does nothing.
  let pressedAt: number | null = null;
  const stop = (event: Event) => event.stopImmediatePropagation();
  timeline.addEventListener(
    "pointerdown",
    (event) => {
      stop(event);
      pressedAt = (event as PointerEvent).clientX;
    },
    true,
  );
  timeline.addEventListener("pointermove", stop, true);
  timeline.addEventListener(
    "pointercancel",
    (event) => {
      stop(event);
      pressedAt = null;
    },
    true,
  );
  timeline.addEventListener(
    "pointerup",
    (event) => {
      stop(event);
      const x = (event as PointerEvent).clientX;
      const dragged = pressedAt === null || Math.abs(x - pressedAt) > CLICK_SLOP_PX;
      pressedAt = null;
      if (dragged) return;
      const box = timeline.getBoundingClientRect();
      const fraction = Math.min(1, Math.max(0, (x - box.left) / (box.width || 1)));
      const span = data.end_s - data.start_s;
      const at = data.start_s + fraction * span;
      const listed = new Map(listedFights(figure).map((b) => [Number(b.dataset.fight), b]));
      // The fight whose bar the click is on or nearest to; when bars overlap, the one whose
      // middle is closest.
      let best: HTMLElement | undefined;
      let bestScore: [number, number] = [span * NEAR_FRACTION, Infinity];
      for (const fight of data.fights) {
        const button = listed.get(fight.n);
        if (!button) continue; // hidden by the size filter
        const end = fight.start_s + fight.duration;
        const distance = at < fight.start_s ? fight.start_s - at : at > end ? at - end : 0;
        const fromMiddle = Math.abs(at - (fight.start_s + end) / 2);
        if (distance < bestScore[0] || (distance === bestScore[0] && fromMiddle < bestScore[1])) {
          best = button;
          bestScore = [distance, fromMiddle];
        }
      }
      best?.click();
    },
    true,
  );
}

/**
 * Add the app's ways of moving between fights to a mounted fights figure.
 *
 * Args:
 *   figure: The mounted fights figure.
 *   data: The fights index the figure was mounted with.
 */
export function addFightNavigation(figure: HTMLElement, data: FightsData): void {
  addArrows(figure);
  openFightOnClick(figure, data);
}
