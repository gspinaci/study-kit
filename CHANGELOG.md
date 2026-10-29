# Changelog

## 0.3.0 — 2026-10-29

The deliverable is now a **static website**, built from structured data.

- The agent writes data only (`data/book.json`, `chNN.json`, `chNN.cards.tsv`, `chNN.ipynb`, `chNN.bib`); Markdown is no longer a deliverable.
- `build_site.py`: Jinja2 site with a home page (sequence, dependency graph, variants, syllabi), chapter pages (objectives with computed back-links, map, quiz, notebook, glossary, readings, videos, cards) and a book-wide glossary. Offline from `file://`, KaTeX from a pinned CDN with readable fallback, light/dark with a persistent toggle, responsive to 360 px, print stylesheet.
- Interactive quiz (progressive enhancement), flip cards with filters, glossary filter, copy-BibTeX, variant highlighting.
- Notebooks executed at build time and rendered in the site template, solutions collapsed.
- `check_site.py`: link and anchor crawl, markup and leaked-syntax checks, Playwright screenshots at 1280/390 px in both themes with overflow and console-error detection.
- `validate.py` rewritten for the JSON schema (incl. "every objective is served", one correct option per multiple choice, `tf` answers, DOI format, raw-HTML ban).
- Deck and site share design tokens; per-book `theme` in `book.json`.
- Kits are self-rebuilding: tools vendored into `_tools/` with a `build_site.py` wrapper.
- CI publishes the example site to GitHub Pages.

## 0.2.0 — 2026-10-23

- Book-level path, chapter objectives as the spine, 14 card types and depth rules, styled Anki note types, graded quizzes, readings tied to objectives, modular outputs.
- `validate.py`, `build_deck.py`, `preview_cards.py`, `check_notebook.sh`; example, tests, evals, CI.

## 0.1.0

- First version: per-chapter materials only.
