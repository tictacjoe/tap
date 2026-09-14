# CLAUDE.md

This is the public site repo for **The Accountability Project** — live at
`https://tictacjoe.github.io/tap/`. It holds the built site
(`index.html`), published tracker data (`data/*.json`), and site-specific
docs. The private working repo (`~/gjoe/tap-data/`) holds raw
research/entry data and is what `publish.py` reads from — see
`~/gjoe/tap-data/CLAUDE.md` and its `docs/` folder for full architecture,
schemas, and workflows. This file is a pointer, not a source of truth.

## This repo

- `index.html` — the live site
- `data/*.json` — `deregulation.json`, `government-services.json`,
  `prosecution.json`, `tracker.json` (Reporting) — written by `publish.py`,
  not hand-edited
- `docs/tap-homepage-banner.md`, `docs/tap-methodology.md` —
  site-specific content
- `docs/tap-file-map.md` — this repo's own file map; points to the
  private repo's `docs/superpowers/tap-file-map.md` for the full two-repo picture
- `publish_exclude.txt` — entries withheld from publish; needs periodic
  review against each entry's *current* confidence, not just checked when
  originally excluded (see `~/gjoe/tap-data/docs/handoffs/` for the
  Waltz entry incident)
- `tests/`, `test_publish.py` — run with `pytest -q`

## Large generated files — never read in full

- `data/tracker.json` (~14MB, the Reporting tracker's published data) is
  regenerated output, not source data — large enough to blow the context
  window if `Read` in full. Use `jq`/`grep`/`head` for targeted lookups
  instead.

## The one rule that matters most

**Two repos, both need a commit.** `publish.py` copies data from
`~/gjoe/tap-data` into this repo's `data/` folder but never commits or
pushes in either repo. After any publish run, check `git status` in both
`~/gjoe/tap-data` and `~/gjoe/tap-site` before considering work
done.
