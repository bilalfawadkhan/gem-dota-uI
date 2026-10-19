/**
 * The gold and xp lead figure as its own page: the docs site's markup and behaviour,
 * on data given at run time.
 */
import data from "@site/data/lead.json";
import { leadFigure } from "@site/figures/lead";
import { mountLeadFigure } from "@site/lib/lead-figure";
import type { LeadData } from "@site/lib/lead-data";
import { dataBase } from "./data-loader";
import { renderEmptyPage, renderFigurePage } from "./figure-page";

const lead = data as unknown as LeadData;
if (lead.times.length < 2) {
  renderEmptyPage("No minute-by-minute gold or XP data was recorded in this replay.");
} else {
  renderFigurePage(
    leadFigure(dataBase() ?? ""),
    "Each side's earned gold and XP by source, minute by minute, and the lead between them.",
    (figure) => mountLeadFigure(figure, data as unknown as LeadData),
  );
}
