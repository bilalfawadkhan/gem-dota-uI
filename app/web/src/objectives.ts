/**
 * The objectives figure as its own page: the docs site's markup and behaviour,
 * on data given at run time.
 */
import data from "@site/data/objectives.json";
import { objectivesFigure } from "@site/figures/objectives";
import { mountObjectivesFigure } from "@site/lib/objectives-figure";
import type { ObjectivesData } from "@site/lib/objectives-data";
import { dataBase } from "./data-loader";
import { renderFigurePage } from "./figure-page";

renderFigurePage(
  objectivesFigure(dataBase() ?? ""),
  "Towers, barracks, Roshan and Tormentor kills on the map, in the order they happened, and the fights around them.",
  (figure) => mountObjectivesFigure(figure, data as unknown as ObjectivesData),
);
