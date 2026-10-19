/**
 * `window.gemFigure`: a small control surface over the fights figure, driven
 * through the figure's own `data-*` hooks so the site's code stays unchanged.
 *
 * Times are the figure's own: seconds into the fight and the match clock text.
 * Converting a replay tick to seconds is the Python side's job (`game_clock`).
 */

export type FigureEvent = "fightSelected" | "timeChanged" | "heroFollowed";

/** What the fight player is doing now (the native controls mirror this). */
export interface PlaybackState {
  /** Whether a fight is open with a player to control. */
  available: boolean;
  playing: boolean;
  /** The match clock text the player shows, e.g. "14:30". */
  clock: string;
  /** Seconds into the open fight, and the fight's length in seconds. */
  seconds: number;
  duration: number;
  /** Playback speed multiplier (0.25 to 4). */
  speed: number;
}

export interface FigureApi {
  /** Open fight `n` (false when the current filters hide it). */
  selectFight(n: number): boolean;
  /** Move the open fight's playback to `seconds` into the fight. */
  seekSeconds(seconds: number): boolean;
  /** Follow a hero in the open fight, by position in the fight's hero list or by name. */
  highlightHero(hero: number | string): boolean;
  play(): void;
  pause(): void;
  /** Set the playback speed; false when the player has no such speed. */
  setSpeed(speed: number): boolean;
  /** A snapshot of the open fight's playback. */
  getState(): PlaybackState;
  /** Subscribe to a figure event; returns the unsubscribe function. */
  on(event: FigureEvent, listener: (detail: any) => void): () => void;
}

/** Attach the API to `figure` and expose it as `window.gemFigure`. */
export function installFigureApi(figure: HTMLElement): FigureApi {
  const listeners = new Map<FigureEvent, Set<(detail: any) => void>>();
  const emit = (event: FigureEvent, detail: unknown) => listeners.get(event)?.forEach((fn) => fn(detail));
  const q = <T extends Element>(selector: string) => figure.querySelector<T>(selector);

  // A pick on the map, the list or the timeline all carry data-fight.
  figure.addEventListener(
    "click",
    (event) => {
      const target = (event.target as Element).closest("[data-fight]");
      if (target) emit("fightSelected", { n: Number(target.getAttribute("data-fight")) });
    },
    true,
  );

  // Following a hero: a click on its status box, or on its badge on the map.
  figure.addEventListener(
    "click",
    (event) => {
      const target = event.target as Element;
      const box = target.closest(".fight-status-hero");
      const badge = target.closest(".fight-hero");
      const name = box
        ? (box.getAttribute("title") ?? "").replace(/^Follow /, "")
        : (badge?.querySelector("title")?.textContent ?? "");
      if (name) emit("heroFollowed", { hero: name });
    },
    true,
  );

  let last = "";
  const reportTime = () => {
    const clock = q<HTMLElement>("[data-clock]")?.textContent ?? "";
    if (clock === last) return;
    last = clock;
    emit("timeChanged", { clock, seconds: Number(q<HTMLInputElement>("[data-scrub]")?.value ?? 0) });
  };
  new MutationObserver(reportTime).observe(figure, { subtree: true, childList: true, characterData: true });
  figure.addEventListener("input", reportTime, true);

  const api: FigureApi = {
    selectFight(n) {
      const button = q<HTMLElement>(`.fights-fig-list [data-fight="${n}"]`);
      button?.click();
      return Boolean(button);
    },
    seekSeconds(seconds) {
      const scrub = q<HTMLInputElement>("[data-scrub]");
      if (!scrub) return false;
      scrub.value = String(seconds);
      scrub.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    },
    highlightHero(hero) {
      const boxes = [...figure.querySelectorAll<HTMLElement>("[data-status] .fight-status-hero")];
      const box = typeof hero === "number" ? boxes[hero] : boxes.find((b) => b.title === `Follow ${hero}`);
      box?.click();
      return Boolean(box);
    },
    setSpeed(speed) {
      const chip = [...figure.querySelectorAll<HTMLElement>("[data-speeds] button")].find(
        (b) => parseFloat(b.textContent ?? "") === speed,
      );
      chip?.click();
      return Boolean(chip);
    },
    getState() {
      const scrub = q<HTMLInputElement>("[data-scrub]");
      const bar = q<HTMLElement>("[data-playback]");
      const pressed = q<HTMLElement>("[data-speeds] [aria-pressed=true]");
      return {
        available: Boolean(scrub && bar && !bar.hidden),
        playing: Boolean(q(".is-playing")),
        clock: q<HTMLElement>("[data-clock]")?.textContent ?? "",
        seconds: Number(scrub?.value ?? 0),
        duration: Number(scrub?.max ?? 0),
        speed: parseFloat(pressed?.textContent ?? "") || 1,
      };
    },
    play() {
      if (!q(".is-playing")) q<HTMLElement>("[data-play]")?.click();
    },
    pause() {
      if (q(".is-playing")) q<HTMLElement>("[data-play]")?.click();
    },
    on(event, listener) {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event)!.add(listener);
      return () => listeners.get(event)?.delete(listener);
    },
  };
  (window as unknown as { gemFigure: FigureApi }).gemFigure = api;
  return api;
}
