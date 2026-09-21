# The Accountability Project — File Map (site repo)

This repo's own layout. For the full picture across both repos — including
the private working repo's trackers, entry directories, and scripts — see
`~/gjoe/tap-data/docs/superpowers/tap-file-map.md`, the canonical file map.

## `~/gjoe/tap-site/`

GitHub: `tictacjoe/tap`

```
CLAUDE.md                    orientation for Claude Code
index.html                   the site itself
about.html                   About page, linked from index.html's nav-actions bar
publish.py                   run from here, reads ../tap-data
publish_exclude.txt          entries held back from publish

data/                        published JSON, read directly by index.html — not hand-edited
  prosecution.json
  deregulation.json
  government-services.json
  tracker.json               ~14MB — regenerated output, never Read in full

docs/                        site-specific content (separate from the private repo's docs/)
  tap-methodology.md
  tap-homepage-banner.md
  tap-about.md        new-user intro: accuracy methodology + how info is presented
  tap-file-map.md     this file

tests/
  build-detail-html.test.js
  glance-head.test.js
  glance-search-oneliner.test.js
  update-timeline.test.js
test_publish.py
test_timeline_corpus.py
```

## Glance cards

`index.html` has a per-tracker `glanceEnabled` flag in the `TRACKERS` object (all three curated trackers are on as of 2026-09-20; Reporting and User Topics have none). The card code lives in the marked region `/* glance-head:start */ ... /* glance-head:end */` and is covered by `tests/glance-head.test.js` and `tests/glance-search-oneliner.test.js`. A card is drawn only when the flag is on and the entry's `glance` block is valid; otherwise the old card shows.

## Update timeline

`publish.py` adds a derived `timeline` object to each published curated entry that carries `Update` / `Added` markers in its text fields, using `tracker/update_markers.py` from the private repo; the raw prose is published unchanged. `index.html` renders updates newest first from it, in the marked region `/* update-timeline:start */ ... /* update-timeline:end */`, covered by `tests/update-timeline.test.js`. `test_timeline_corpus.py` checks the invariants of the published `timeline` objects against `data/*.json`.

## Live site

`https://tictacjoe.github.io/tap/` — served directly from `data/*.json`
in this repo. No separate build step.

## Standing note

`publish.py` copies data from the private repo into `data/` but never commits
or pushes in either repo — check `git status` in both after any publish run.
