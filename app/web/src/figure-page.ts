/**
 * Shared set-up for the recipe-figure pages (objectives, lanes, runes, lead, wards).
 *
 * Each page renders the docs site's own figure markup and mounts its own behaviour, on data
 * given at run time (see data-loader.ts). Inside the desktop app it also tells Python when a
 * link in the figure points at a fight, so the app can switch to the Fights tab instead of
 * letting the web view navigate away.
 */
import "@fontsource-variable/source-serif-4/opsz.css";
import "@fontsource-variable/source-serif-4/opsz-italic.css";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "@site/styles/tokens.css";
import "@site/styles/base.css";
import "@site/styles/prose.css";
import "@site/styles/figures.css";
import { connectPageBridge } from "./bridge";

/**
 * Render a figure into the page and mount it.
 *
 * Args:
 *   markup: The figure's opening and closing HTML from the site's `figures/<name>.ts`.
 *   caption: The text between them (the figure's caption).
 *   mount: The site's `mount<Name>Figure`, called with the figure element.
 */
export function renderFigurePage(
  markup: { open: string; close: string },
  caption: string,
  mount: (figure: HTMLElement) => void,
): void {
  const host = document.getElementById("figure")!;
  host.innerHTML = markup.open + caption + markup.close;
  const figure = host.querySelector<HTMLElement>("[data-recipe-figure]")!;
  mount(figure);
  void connectPageBridge();
}

/**
 * Show a short message instead of a figure that has nothing to draw.
 *
 * The site's figure code assumes a full match (the lead curve, for one, builds an invalid path
 * from no data), so a page checks first and says what is missing instead of throwing.
 *
 * Args:
 *   message: What the replay does not have, stated as a fact.
 */
export function renderEmptyPage(message: string): void {
  const host = document.getElementById("figure")!;
  const note = document.createElement("p");
  note.textContent = message;
  note.style.opacity = "0.7";
  host.replaceChildren(note);
  void connectPageBridge();
}
