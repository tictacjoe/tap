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
test_publish.py
```

## Live site

`https://tictacjoe.github.io/tap/` — served directly from `data/*.json`
in this repo. No separate build step.

## Standing note

`publish.py` copies data from the private repo into `data/` but never commits
or pushes in either repo — check `git status` in both after any publish run.
