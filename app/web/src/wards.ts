/**
 * The wards figure as its own page: the docs site's markup and behaviour,
 * on data given at run time.
 */
import data from "@site/data/wards.json";
import { wardsFigure } from "@site/figures/wards";
import { mountWardsFigure } from "@site/lib/wards-figure";
import type { WardsData } from "@site/lib/wards-data";
import { dataBase } from "./data-loader";
import { renderFigurePage } from "./figure-page";

renderFigurePage(
  wardsFigure(dataBase() ?? ""),
  "Every ward placed in the match: where, when, by whom, and how long it lasted.",
  (figure) => mountWardsFigure(figure, data as unknown as WardsData),
);
