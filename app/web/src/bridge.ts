/**
 * The page's side of the Qt bridge (QWebChannel).
 *
 * Inside the desktop app the page can talk to Python through one small object, `gem`: only
 * ids, names and seconds cross it, never data (the figures load their data by URL).
 *
 *   Python -> page:  signals `selectFightRequested(n)`, `highlightHeroRequested(name)`,
 *                    `seekRequested(seconds)`, `playRequested()`, `pauseRequested()`,
 *                    `speedRequested(x)`
 *   page -> Python:  slots `ready()`, `fightSelected(n)`, `heroFollowed(name)`,
 *                    `playbackChanged(available, playing, clock, seconds, duration, speed)`,
 *                    `openFight(n)` (a link in another figure pointed at a fight)
 *
 * Outside Qt (a browser, the dev server) there is no transport and this does nothing, so the
 * figure page works the same on its own.
 */
import type { FigureApi, PlaybackState } from "./api";

interface GemBridge {
  selectFightRequested: { connect(fn: (n: number) => void): void };
  highlightHeroRequested: { connect(fn: (hero: string) => void): void };
  seekRequested: { connect(fn: (seconds: number) => void): void };
  playRequested: { connect(fn: () => void): void };
  pauseRequested: { connect(fn: () => void): void };
  speedRequested: { connect(fn: (speed: number) => void): void };
  ready(): void;
  fightSelected(n: number): void;
  heroFollowed(hero: string): void;
  openFight(number: number): void;
  playbackChanged(
    available: boolean,
    playing: boolean,
    clock: string,
    seconds: number,
    duration: number,
    speed: number,
  ): void;
}

/** How often the page checks the player for changes to report (it only sends real changes). */
const POLL_MS = 200;

declare global {
  interface Window {
    qt?: { webChannelTransport?: unknown };
    QWebChannel?: new (transport: unknown, ready: (channel: { objects: { gem?: GemBridge } }) => void) => unknown;
  }
}

function loadQtScript(): Promise<boolean> {
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = "./qwebchannel.js"; // served by the app's gem:// handler from Qt's own copy
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.head.append(script);
  });
}

/**
 * Connect the figure's API to Python, when running inside the app.
 *
 * Args:
 *   api: The figure API from `installFigureApi`.
 */
export async function connectBridge(api: FigureApi): Promise<void> {
  if (!window.qt?.webChannelTransport) return;
  if (!(await loadQtScript()) || !window.QWebChannel) return;
  new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
    const gem = channel.objects.gem;
    if (!gem) return;
    // Commands from Python.
    gem.selectFightRequested.connect((n) => api.selectFight(n));
    gem.highlightHeroRequested.connect((hero) => api.highlightHero(hero));
    gem.seekRequested.connect((seconds) => api.seekSeconds(seconds));
    gem.playRequested.connect(() => api.play());
    gem.pauseRequested.connect(() => api.pause());
    gem.speedRequested.connect((speed) => api.setSpeed(speed));
    // Events from the figure.
    api.on("fightSelected", (detail) => gem.fightSelected(detail.n));
    api.on("heroFollowed", (detail) => gem.heroFollowed(detail.hero));
    reportPlayback(api, gem);
    gem.ready();
  });
}

/** Tell Python what the player is doing, whenever it changes (seconds to a tenth). */
function reportPlayback(api: FigureApi, gem: GemBridge): void {
  let last = "";
  const send = (s: PlaybackState) => {
    const key = [s.available, s.playing, s.clock, s.seconds.toFixed(1), s.duration, s.speed].join("|");
    if (key === last) return;
    last = key;
    gem.playbackChanged(s.available, s.playing, s.clock, s.seconds, s.duration, s.speed);
  };
  setInterval(() => send(api.getState()), POLL_MS);
}

/**
 * Connect a figure page that has no fight player (objectives, lanes, runes, lead, wards).
 *
 * It only says it is ready, and reports clicks on links that point at a fight (`...#fight-6`)
 * so the app can open that fight in the Fights tab. Outside Qt a click is left alone.
 */
export async function connectPageBridge(): Promise<void> {
  if (!window.qt?.webChannelTransport) return;
  if (!(await loadQtScript()) || !window.QWebChannel) return;
  new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
    const gem = channel.objects.gem;
    if (!gem) return;
    document.addEventListener(
      "click",
      (event) => {
        const link = (event.target as Element).closest<HTMLAnchorElement>("a[href*='#fight-']");
        const found = link ? /#fight-(\d+)$/.exec(link.getAttribute("href") ?? "") : null;
        if (!found) return;
        event.preventDefault();
        gem.openFight(Number(found[1]));
      },
      true,
    );
    gem.ready();
  });
}
