/**
 * The runes figure as its own page: the docs site's markup and behaviour,
 * on data given at run time.
 */
import data from "@site/data/runes.json";
import { runesFigure } from "@site/figures/runes";
import { mountRunesFigure } from "@site/lib/runes-figure";
import type { RunesData } from "@site/lib/runes-data";
import { dataBase } from "./data-loader";
import { renderFigurePage } from "./figure-page";

renderFigurePage(
  runesFigure(dataBase() ?? ""),
  "Every rune in the match: when it spawned, its type and place, and how it ended.",
  (figure) => mountRunesFigure(figure, data as unknown as RunesData),
);
