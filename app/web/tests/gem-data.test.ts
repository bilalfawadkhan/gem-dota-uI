import { readFileSync } from "node:fs";
import { resolve, sep } from "node:path";
import { describe, expect, it } from "vitest";
import { dataNameOf, isSiteData, patchFightsFigure } from "../plugins/gem-data";

const site = resolve(import.meta.dirname, "../../../site");
const siteData = resolve(site, "src/data");
const loader = "/app/web/src/data-loader.ts";

describe("patchFightsFigure", () => {
  const source = readFileSync(resolve(site, "src/lib/fights-figure.ts"), "utf8");

  it("replaces the per-fight glob and fight.json import in the site's file", () => {
    expect(source).toContain('import.meta.glob<{ default: FightData }>("../data/fights/');
    const patched = patchFightsFigure(source, loader);
    expect(patched).not.toContain("../data/fights/[0-9]*.json");
    expect(patched).not.toContain('import("../data/fight.json")');
    expect(patched).toContain("__gemLoadFile");
    // The icon globs point at the app's full icon set, not the demo match's heroes.
    expect(patched).not.toContain("../assets/icons/");
    expect(patched).toContain('"/icons/heroes/*.png"');
    expect(patched).toContain('"/icons/items/*.png"');
  });

  it("fails loudly when upstream changes an icon glob", () => {
    const changed = source.replace("../assets/icons/items/*.png", "../assets/item-icons/*.png");
    expect(() => patchFightsFigure(changed, loader)).toThrow(/items icon glob .* changed upstream/);
  });

  it("fails loudly when upstream changes the block", () => {
    const changed = source.replace("const FILES = {", "const FIGHT_FILES = {");
    expect(() => patchFightsFigure(changed, loader)).toThrow(/FILES block .* changed upstream/);
  });
});

describe("dataNameOf", () => {
  const importer = resolve(site, "src/figures/lanes.ts");

  it("names a site data file relative to src/data", () => {
    expect(dataNameOf("../data/lanes.json", importer, siteData)).toBe("lanes.json");
    expect(dataNameOf("../data/fights/index.json", importer, siteData)).toBe("fights/index.json");
  });

  it("accepts an already-resolved absolute path", () => {
    expect(dataNameOf(resolve(siteData, "home.json"), importer, siteData)).toBe("home.json");
  });

  it("accepts an absolute path with forward slashes, as an aliased import resolves to", () => {
    const aliased = resolve(siteData, "fights/index.json").split(sep).join("/");
    expect(dataNameOf(aliased, importer, siteData)).toBe("fights/index.json");
    expect(dataNameOf(`${aliased}?import`, importer, siteData)).toBe("fights/index.json");
  });

  it("recognises a real site data file, but not a virtual module", () => {
    expect(isSiteData(resolve(siteData, "home.json"), siteData)).toBe(true);
    expect(isSiteData(resolve(siteData, "fights/3.json").split(sep).join("/"), siteData)).toBe(true);
    expect(isSiteData("\0gem-data:home", siteData)).toBe(false);
    expect(isSiteData(resolve(site, "src/lib/wards-data.ts"), siteData)).toBe(false);
  });

  it("ignores JSON outside src/data and non-JSON imports", () => {
    expect(dataNameOf("../../package.json", importer, siteData)).toBeNull();
    expect(dataNameOf("../lib/lanes-data", importer, siteData)).toBeNull();
    expect(dataNameOf("../data/lanes.json", undefined, siteData)).toBeNull();
  });
});
