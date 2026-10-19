/**
 * Dev/preview only: serves the site's committed demo data (src/data and
 * public/figures) under `/__committed/`, so a figure can be opened with
 * `?data=/__committed` before the Python exporter exists. Not part of the build.
 */
import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, resolve, sep } from "node:path";
import type { Connect, Plugin } from "vite";

const TYPES: Record<string, string> = {
  ".json": "application/json",
  ".webp": "image/webp",
  ".png": "image/png",
  ".jpg": "image/jpeg",
};

/** Build the middleware plugin for a checkout where the site is at `siteRoot`. */
export function committedData(siteRoot: string): Plugin {
  const data = resolve(siteRoot, "src/data");
  const figures = resolve(siteRoot, "public/figures");
  const handler: Connect.NextHandleFunction = (req, res, next) => {
    const url = (req.url ?? "").split("?")[0];
    if (!url.startsWith("/__committed/")) return next();
    const rest = decodeURIComponent(url.slice("/__committed/".length));
    const [root, name] = rest.startsWith("figures/") ? [figures, rest.slice(8)] : [data, rest];
    const file = resolve(root, name);
    if (!file.startsWith(root + sep) || !existsSync(file) || !statSync(file).isFile()) {
      res.statusCode = 404;
      res.end("not found");
      return;
    }
    res.setHeader("Content-Type", TYPES[extname(file)] ?? "application/octet-stream");
    createReadStream(file).pipe(res);
  };
  return {
    name: "committed-data",
    configureServer: (server) => void server.middlewares.use(handler),
    configurePreviewServer: (server) => void server.middlewares.use(handler),
  };
}
