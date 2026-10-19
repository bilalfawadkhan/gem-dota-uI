/**
 * Builds the docs-site figures for the desktop app's web view.
 *
 * The figure code is read in place from ../../site/src (never copied, never
 * edited); only the entry pages, the data loader and the plugins are the app's
 * own. Output goes to dist/, which the Qt shell serves.
 */
import { resolve } from "node:path";
import { defineConfig } from "vite";
import { committedData } from "./plugins/committed-data";
import { gemData } from "./plugins/gem-data";

const here = import.meta.dirname;
const site = resolve(here, "../../site");

export default defineConfig({
  root: here,
  // The site's own tsconfig extends astro's, which is not installed here.
  tsconfig: resolve(here, "tsconfig.json"),
  // Relative URLs, so dist/ works under any origin (a custom scheme or a loopback server).
  base: "./",
  resolve: { alias: { "@site": resolve(site, "src") } },
  plugins: [gemData(site, resolve(here, "src/data-loader.ts")), committedData(site)],
  server: { fs: { allow: [resolve(here, "../..")] } },
  build: {
    target: "es2022", // top-level await in the data modules
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      // One page per figure; the app shows each in its own tab.
      input: Object.fromEntries(
        ["fights", "objectives", "lanes", "runes", "lead", "wards"].map((name) => [
          name,
          resolve(here, `${name}.html`),
        ]),
      ),
    },
  },
});
