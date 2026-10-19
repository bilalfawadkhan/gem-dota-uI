/**
 * Where the figures' data comes from at run time.
 *
 * The Qt shell opens a figure page with `?data=<url>` (or sets `window.gemData`)
 * naming the folder the Python exporter wrote: the same files and names as the
 * site's `src/data` (`home.json`, `fights/index.json`, `fights/7.json`, ...),
 * plus `figures/` for the map images. Bulk data never goes through the bridge.
 */

declare global {
  interface Window {
    gemData?: string;
  }
}

/** The data folder's URL without a trailing slash, or null when none was given. */
export function dataBase(): string | null {
  const given = new URLSearchParams(location.search).get("data") ?? window.gemData;
  return given ? given.replace(/\/+$/, "") : null;
}

function requireBase(): string {
  const base = dataBase();
  if (!base) throw new Error("No data location: open this page with ?data=<url of the data folder>.");
  return base;
}

/** Fetch one JSON file from the data folder, e.g. "lanes.json" or "fights/7.json". */
export async function loadJson(name: string): Promise<unknown> {
  const url = `${requireBase()}/${name}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url}: ${response.status}`);
  return response.json();
}

/**
 * Load a data file named the way the site's code names it ("../data/fights/7.json").
 *
 * Returns:
 *   A module-shaped `{ default }`, like the dynamic `import()` it replaces.
 */
export async function loadDataFile(path: string): Promise<{ default: any }> {
  return { default: await loadJson(path.replace(/^(\.\.\/)?data\//, "")) };
}
