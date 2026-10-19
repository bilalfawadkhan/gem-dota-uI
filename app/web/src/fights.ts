/**
 * The fights figure as its own page: the docs site's markup and behaviour
 * (src/figures/fights.ts, src/lib/fights-figure.ts), on data given at run time.
 *
 * The app lays it out its own way (fights-layout.css): the replay and the fight log on top
 * (60/40), the fight picker below, and the map of all fights behind a button.
 */
import "@fontsource-variable/source-serif-4/opsz.css";
import "@fontsource-variable/source-serif-4/opsz-italic.css";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "@site/styles/tokens.css";
import "@site/styles/base.css";
import "@site/styles/prose.css";
import "@site/styles/figures.css";
import "@site/styles/fight-player.css";
import "./fights-layout.css";
import index from "@site/data/fights/index.json";
import { fightsFigure } from "@site/figures/fights";
import { mountFightsFigure } from "@site/lib/fights-figure";
import type { FightsData } from "@site/lib/fights-data";
import { installFigureApi } from "./api";
import { connectBridge } from "./bridge";
import { addFightNavigation } from "./fight-nav";
import { dataBase } from "./data-loader";

const CAPTION =
  "The open fight's replay and its log are on top. Step through the fights with the arrows, or click " +
  "one on the timeline or in the list; the button shows every fight on the map.";

/** Add the button that shows or hides the map of all fights. */
function addAllFightsButton(figure: HTMLElement): void {
  const controls = figure.querySelector<HTMLElement>("[data-controls]");
  if (!controls) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "chip all-fights-toggle";
  const sync = () => {
    const open = figure.classList.contains("gem-all-map");
    button.textContent = open ? "Hide the all-fights map" : "All fights map";
    button.setAttribute("aria-pressed", String(open));
  };
  button.addEventListener("click", () => {
    figure.classList.toggle("gem-all-map");
    sync();
  });
  sync();
  controls.append(button);
}

const { open, close } = fightsFigure(dataBase() ?? "");
const host = document.getElementById("figure")!;
host.innerHTML = open + CAPTION + close;
const figure = host.querySelector<HTMLElement>("[data-recipe-figure]")!;
mountFightsFigure(figure, index as unknown as FightsData);
addAllFightsButton(figure);
addFightNavigation(figure, index as unknown as FightsData);
void connectBridge(installFigureApi(figure));
