/**
 * Vite plugin that lets the docs site's figures take their data at run time.
 *
 * The site (`../../site/src`, read in place and never edited) imports its data as
 * committed JSON (`../data/lanes.json`). Here those imports resolve to a virtual
 * module that fetches the same file from the location the app passes in
 * (`?data=<url>`), so the figure code runs unchanged on a replay's own data.
 *
 * `fights-figure.ts` is the one file that needs rewriting as it is built: it
 * loads each fight through `import.meta.glob`, which would bake the committed
 * fights into the bundle. `patchFightsFigure` swaps that block for a loader and
 * throws if upstream changes it, so a site update fails the build, not the app.
 */
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import type { Plugin } from "vite";

const PREFIX = "\0gem-data:";

/** The `FILES` block in site/src/lib/fights-figure.ts: the per-fight glob and fight.json. */
const FILES_BLOCK = /const FILES = \{[\s\S]*?\n\};/;

/**
 * Rewrite fights-figure.ts so each fight's JSON comes from the data location.
 *
 * Args:
 *   code: The source of site/src/lib/fights-figure.ts.
 *   loaderPath: Absolute path of the module exporting `loadDataFile`.
 *
 * Returns:
 *   The source with `FILES` replaced by a loader over the data location.
 *
 * Throws:
 *   Error: If the `FILES` block is no longer in the file.
 */
export function patchFightsFigure(code: string, loaderPath: string): string {
  if (!FILES_BLOCK.test(code)) {
    throw new Error(
      "gem-data: the FILES block in site/src/lib/fights-figure.ts changed upstream; " +
        "update plugins/gem-data.ts (patchFightsFigure) to match.",
    );
  }
  // The icons the site globs are only the demo match's heroes; the app bundles every
  // hero and item (app/web/icons, filled by scripts/collect_icons.py).
  for (const kind of ["heroes", "items"]) {
    const site = `"../assets/icons/${kind}/*.png"`;
    if (!code.includes(site)) {
      throw new Error(
        `gem-data: the ${kind} icon glob in site/src/lib/fights-figure.ts changed upstream; ` +
          "update plugins/gem-data.ts (patchFightsFigure) to match.",
      );
    }
    code = code.replace(site, `"/icons/${kind}/*.png"`);
  }
  const loader =
    `import { loadDataFile as __gemLoadFile } from ${JSON.stringify(loaderPath)};\n` +
    "const FILES = new Proxy({}, { get: (_t, key) => () => __gemLoadFile(String(key)) }) as " +
    "Record<string, () => Promise<{ default: FightData }>>;";
  return loader + "\n" + code.replace(FILES_BLOCK, "");
}

/**
 * The data file a module imports, named relative to the site's `src/data`.
 *
 * Returns:
 *   "lanes.json" or "fights/index.json", or null when the import is not a site data file.
 */
export function dataNameOf(source: string, importer: string | undefined, siteData: string): string | null {
  if (!importer || !source.split("?")[0].endsWith(".json")) return null;
  const from = importer.split("?")[0];
  // An absolute path may use forward slashes (the resolver's ids do), so normalise it.
  const path = resolve(dirname(from), source.split("?")[0]);
  const rel = relative(siteData, path);
  if (rel === "" || rel.startsWith("..") || isAbsolute(rel)) return null;
  return rel.split(sep).join("/");
}

/** Whether `id` (a module id, possibly with a query) is a real file under the site's data folder. */
export function isSiteData(id: string, siteData: string): boolean {
  const rel = relative(siteData, resolve(id.split("?")[0]));
  return !id.startsWith("\0") && !rel.startsWith("..") && !isAbsolute(rel) && rel !== "";
}

/** Build the plugin for a checkout where the site is at `siteRoot`. */
export function gemData(siteRoot: string, loaderPath: string): Plugin {
  const siteData = resolve(siteRoot, "src/data");
  const fightsFigure = resolve(siteRoot, "src/lib/fights-figure.ts");
  const loader = loaderPath.split(sep).join("/");
  return {
    name: "gem-data",
    enforce: "pre",
    resolveId: {
      order: "pre",
      async handler(source, importer, options) {
        let path = source;
        if (!source.startsWith(".") && !source.startsWith("/") && !/^[A-Za-z]:/.test(source)) {
          // An alias such as @site/data/...: let the resolver turn it into a path first.
          const resolved = await this.resolve(source, importer, { ...options, skipSelf: true });
          if (!resolved) return null;
          path = resolved.id;
        }
        const name = dataNameOf(path, importer, siteData);
        // No ".json" on the id: Vite's JSON plugin would try to parse the module as JSON.
        return name ? PREFIX + name.slice(0, -".json".length) : null;
      },
    },
    load(id) {
      // Every site data import must have become a run-time fetch. A real file loaded here
      // means one slipped through (and the demo data would be bundled into the app).
      if (isSiteData(id, siteData)) {
        throw new Error(
          `gem-data: ${id} would be bundled into the app instead of loaded at run time. ` +
            "Check how it is imported (plugins/gem-data.ts, dataNameOf).",
        );
      }
      if (!id.startsWith(PREFIX)) return null;
      const name = id.slice(PREFIX.length) + ".json";
      return `import { loadJson } from ${JSON.stringify(loader)};\nexport default await loadJson(${JSON.stringify(name)});`;
    },
    transform(code, id) {
      if (resolve(id.split("?")[0]) !== fightsFigure) return null;
      return { code: patchFightsFigure(code, loader), map: null };
    },
  };
}
