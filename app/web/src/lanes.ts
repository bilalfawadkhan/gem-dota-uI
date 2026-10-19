/**
 * The lanes figure as its own page: the docs site's markup and behaviour,
 * on data given at run time.
 */
import data from "@site/data/lanes.json";
import { lanesFigure } from "@site/figures/lanes";
import { mountLanesFigure } from "@site/lib/lanes-figure";
import type { LanesData } from "@site/lib/lanes-data";
import { renderFigurePage } from "./figure-page";

renderFigurePage(
  lanesFigure(),
  "Each lane's heroes, each side's numbers at 6:00 and 10:00, and what happened in the lane up to then.",
  (figure) => mountLanesFigure(figure, data as unknown as LanesData),
);
