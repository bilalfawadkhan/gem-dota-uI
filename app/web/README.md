# app/web: the figures for the desktop app

Builds the docs site's figures into static files for the Qt web view. The figure
code is **read in place** from `../../site/src` (never copied, never edited). This
folder holds only the entry pages, the data loader, the figure API and two Vite
plugins.

```bash
cd app/web
npm install
npm run build      # -> dist/  (fights.html + assets)
npm test           # plugin tests (also fail if upstream changes the block we rewrite)
npx tsc --noEmit   # typecheck, including the site files read in place
```

Needs Node 22+. Users of the installed app need no Node: `dist/` ships inside it.

## How data reaches a figure

Open a page with `?data=<url of a data folder>` (or set `window.gemData`). The
folder holds what the site keeps in `site/src/data` (`home.json`,
`fights/index.json`, `fights/<n>.json`, ...) plus `figures/` for the map images.
`plugins/gem-data.ts` resolves the site's committed-JSON imports to that folder.

For development, `npm run dev` / `npx vite preview` serve the site's committed demo
data under `/__committed/`:

    http://localhost:5173/fights.html?data=/__committed

## Page API (`window.gemFigure`)

`selectFight(n)`, `seekSeconds(s)`, `highlightHero(indexOrName)`, `play()`,
`pause()`, `setSpeed(x)`, `getState()` (playing, clock, seconds, duration, speed), and `on("fightSelected" | "timeChanged" | "heroFollowed", fn)`. Times are the figure's own
(seconds into a fight, match clock text); converting ticks is the Python side's job.

## Qt bridge

`src/bridge.ts` connects this API to the desktop app's QWebChannel object `gem` when the page runs
inside Qt (it loads `./qwebchannel.js`, which the app serves from Qt's resources). Outside Qt it
does nothing. See `app/gemstudio/bridge.py` for the Python side.

## When upstream changes

- `plugins/gem-data.ts` rewrites the `FILES` block of `site/src/lib/fights-figure.ts`.
  If upstream edits that block, the build fails with a message naming the plugin.
- A site figure that gains a new data file needs no change here; one that loads data
  another way (a new `import.meta.glob`) needs a matching rule in the plugin.

## Entries

| Page | Figure |
|---|---|
| `fights.html` | fights, with the player and the page API; its layout is `src/fights-layout.css` (replay 60% / log 40% on top, the all-fights map behind a button); `src/fight-nav.ts` adds Previous / Next fight arrows and makes the timeline click-to-open (a drag does nothing, because the site treats it as a filter that closes the replay) |
| `objectives.html`, `lanes.html`, `runes.html`, `lead.html`, `wards.html` | the other recipe figures (`src/figure-page.ts` is the shared set-up) |

The site's lead figure cannot draw an empty curve, so `lead.ts` checks for data first and shows a message
(`renderEmptyPage`). A link to a fight inside a figure is reported to the app (`connectPageBridge`).
