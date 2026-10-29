---
name: "study-kit"
description: "Generate a book-level study path plus modular per-chapter study materials (objectives, Anki deck, notebook, quiz, glossary, readings, videos) from a provided book, chapter, paper or syllabus."
---

# Study kit from existing sources

Turn an authoritative source (book, chapter, scientific paper, syllabus, course slides) into a study path and study materials, delivered as a **styled static HTML website**. The source decides content and order: never invent curricula, topics, prerequisites or paths the source (or a cited real syllabus) does not contain.

Two levels:
1. **Book path** (site home page `index.html`): the structure of the whole book, its prerequisites, the variants stated by the book or by real courses that adopt it, and links to every material produced.
2. **Chapter kits**: modular materials per chapter, one page per output.

A whole book is processed in **one request**, but **chapter by chapter**: each chapter is read in full, produced and checked before moving to the next. Never batch-generate shallow material for many chapters at once. Keep a task list with one item per chapter.

## Tools shipped with this skill

The agent writes **data only**; rendering and checking are done by the scripts next to this file. Never hand-write HTML or a site generator.

- `references/data-format.md` — exact schema of `book.json`, `chNN.json`, `chNN.cards.tsv`, `chNN.ipynb`. Read it before writing data.
- `references/card-types.md` — the card types with examples and the quality bar for each.
- `scripts/validate.py BOOK_DIR [--chapter chNN] [--source source.txt]` — every rule below that can be checked mechanically, plus schedule-language and verbatim-copy lints.
- `scripts/build_site.py BOOK_DIR` — renders `data/` → `site/` (Jinja2, templates in `templates/site/`), executes notebooks, and vendors itself into `BOOK_DIR/_tools/` with a `BOOK_DIR/build_site.py` wrapper so the kit rebuilds without the skill.
- `scripts/check_site.py BOOK_DIR/site [--screenshots DIR] [--katex-dir DIR]` — link/anchor crawl, markup and leaked-syntax checks; with `--screenshots`, Playwright renders at 1280px and 390px in light and dark and reports overflow and console errors.
- `scripts/build_deck.py BOOK_DIR` — `deck.apkg` from all `chNN.cards.tsv`, styled with the site's design tokens.
- `scripts/preview_cards.py BOOK_DIR --theme light|dark` — the Anki note design in a browser.
- `requirements.txt` — `pip install -r requirements.txt` if `jinja2`, `genanki`, `nbformat`, `nbclient`, `mistune`, `pygments` or `playwright` are missing.

## Modularity

- **Every output is optional.** The user picks any subset (per book or per chapter); if unspecified, produce all.
- **Whatever is produced is part of the path.** The home page links every produced page of every chapter; every produced item (card, question, notebook section, reading, video, glossary term) references a chapter objective id and links to it. Nothing produced floats outside the path.
- Objectives are the spine: they are written for a chapter whenever any other output is produced for that chapter, because every item hooks onto them. If the user asks explicitly for no objectives, items reference section ids from the map instead.
- Checks below apply only to the outputs actually produced.

## Defaults

- **Language: English** for all outputs (content and site UI labels), unless the user asks otherwise. Set `<html lang>` accordingly.
- **No scheduling or coaching.** "Path" means structure and dependencies, never a timeline. No durations, time estimates, routines, pacing advice, or instructions on what to do and when. Variants are presented as options with their source, never as recommendations. The user chooses their own path.
- **Grounding.** Every objective, card, question, path variant and reading traces back to: the source (section/page), a real syllabus that adopts the source (course, institution, year, URL), or a cited reading.
- **Output format: HTML website.** Markdown is never a deliverable. Content is authored as structured data and rendered to HTML by a build script (see "Site build").

## Input

- One or more files (PDF, EPUB, .tex, .md, slides) or a reference to a book/chapter already in the library.
- Optional: which outputs, which chapters, target level, card language.
- If no source is given, ask for it.
- If only a single chapter or paper is given, the home page is reduced to that chapter's entry.

## Output layout

```
study-kit/<book-slug>/
├── data/                          # source of truth (not published) — the only thing the agent writes
│   ├── book.json                  # path, variants, syllabi, chapter order, optional theme
│   ├── chNN.json                  # objectives, map, quiz, glossary, readings, videos
│   ├── chNN.cards.tsv             # cards (if produced)
│   ├── chNN.ipynb                 # notebook source (if produced)
│   ├── chNN.bib                   # BibTeX for the readings (optional)
│   └── media/chNN/                # recreated figures for diagram cards
├── build_site.py                  # wrapper written by the build: rebuilds site/ (and the deck with --deck)
├── _tools/                        # vendored copy of the skill's scripts and templates
├── deck.apkg                      # whole book, one subdeck per chapter (if cards produced)
└── site/                          # the deliverable — regenerated from scratch on every build
    ├── index.html                 # book path
    ├── glossary.html              # book-wide glossary (union of chapters, filterable)
    ├── assets/
    │   ├── style.css
    │   └── site.js
    └── chNN-<chapter-slug>/
        ├── index.html             # chapter overview: goal + objectives
        ├── map.html
        ├── quiz.html
        ├── glossary.html
        ├── readings.html  + readings.bib
        ├── videos.html
        ├── notebook.html  + notebook.ipynb   # executed copy
        ├── cards.html  + cards.tsv           # browsable cards + downloadable copy
        └── media/
```

Cards keep `data/chNN.cards.tsv` as their source of truth and the notebook keeps `data/chNN.ipynb`; `site/` only holds rendered pages and copies, so it can be deleted and rebuilt at any time. Everything else lives in `data/*.json`.

### Chapter JSON schema (minimum)

```json
{
  "id": "ch03", "slug": "ch03-...", "title": "...", "source_ref": "...",
  "goal": "...",
  "objectives": [{"id": "ch03-o1", "level": "core|secondary", "text": "...",
                  "source": "§3.2", "why_core": "...", "syllabus_outcome": null}],
  "map": [{"section": "3.1", "title": "...", "url": "...", "concepts": ["..."], "objectives": ["ch03-o1"]}],
  "quiz": [{"id": "Q1", "level": "remember|understand|apply|analyze", "format": "mc|open|compute|tf",
            "prompt": "...", "options": [{"key": "A", "text": "...", "correct": true, "why": "..."}],
            "answer": null, "solution": "...", "objectives": ["ch03-o1"], "source": "§3.1"}],
  "glossary": [{"term": "...", "original": "...", "definition": "...", "notation": "...", "objectives": ["ch03-o1"]}],
  "readings": [{"key": "bibkey", "citation": "...", "doi": "...", "url": "...", "kind": "core|deepening",
                "adds": "...", "objectives": ["ch03-o2"]}],
  "videos": [{"title": "...", "by": "...", "year": 2020, "url": "...", "duration": "...",
              "sections": ["3.2"], "objectives": ["ch03-o2"], "note": "..."}]
}
```

`answer` is `true`/`false` for `tf` questions. The full schema, including `book.json`, is in `references/data-format.md`.

Text fields may contain a small inline subset (`*em*`, `**strong**`, `` `code` ``, links, math in `\( \)` / `\[ \]`), rendered by the build script with a minimal Markdown-to-HTML converter; never paste raw HTML into data.

## Phase 1 — Book path (home page)

1. Read the front matter: preface, "how to read this book", table of contents, chapter introductions, any chapter-dependency diagram, chapters marked optional/advanced/starred.
2. Find **real courses that adopt the book** (university syllabi, course pages). For each, verify with a fetch and record: course, institution, year, URL, chapters used, stated learning outcomes. Aim for 2–5; zero is acceptable if none exist.
3. Write `data/book.json` and render `site/index.html`:
   - **Linear sequence** in book order, as a list of chapter cards. Per chapter: title, one-line scope, chapter goal, prerequisites (earlier chapters/sections, background stated by the book), optional/advanced flag if the book says so, forward links (where its concepts are reused later), which syllabi include it, counts (objectives core/secondary, quiz questions, cards, readings, videos) and **links to every page produced for that chapter**. Chapters not yet produced appear greyed out without links.
   - **Dependency view**: an inline SVG (generated by the build script, no external library) of chapters as nodes and prerequisite/forward links as edges, nodes clickable.
   - **Variants** (e.g. "theory only", "applied track", "one-semester course"): only if stated by the book or derived from a cited syllabus. Each variant lists its chapters and its source; selecting a variant highlights its chapters. If none exist, say so explicitly; do not invent one.
   - **Syllabi** section with the verified courses and their URLs.
4. Re-run the build after each chapter so the home page matches what exists.

## Phase 2 — Chapter kits (one chapter at a time)

### Read
Read the whole chapter (long PDFs: `pdftotext -layout`; inspect formula-heavy pages and figures visually). Record section and page numbers. Read the end-of-chapter exercises.

### Objectives (chapter `index.html`; written first, everything else links to it)
- **Chapter goal**: 2–3 sentences on what the chapter is for and where it sits in the path.
- **Learning objectives**, phrased as "After this chapter you can …" with observable verbs (derive, explain, implement, compare, choose, diagnose). Typically 4–8.
- Each objective has: id (`ch03-o2`, also its HTML anchor), level **core** or **secondary**, source section/pages, the matching syllabus learning outcome when one exists (cited), and auto-generated back-links to every item that serves it (quiz questions, notebook sections, glossary terms, readings, videos, cards) — the build script computes these from the data, never by hand.
- **Core** = the concept is reused in later chapters (per forward links in the path), is required by the end-of-chapter exercises, or appears in a syllabus outcome. Otherwise **secondary**.

### Map (`map.html`)
Sections in the source's order, key concepts per section, each tagged with the objective id(s) it serves (as links), plus section/page references and links to the source when it is online.

### Cards (`cards.tsv` → `deck.apkg`, plus `cards.html`)
Columns: `id`, `objective`, `level` (core|secondary), `type`, `front`, `back`, `explanation`, `source`, `media`, `tags`.

Card types:
- `definition`, `cloze` (formulas/definitions, `{{c1::...}}`)
- `why` — why X instead of Y / why this step
- `compare` — difference between A and B and when to choose which
- `apply` — mini-scenario: "you have … what do you use and why?"
- `derivation` — which step leads from (1) to (2)
- `mistake` — what is wrong in this reasoning
- `intuition` — what does … represent geometrically/conceptually
- `notation` — what a symbol means in this book's notation
- `code` — what this snippet returns / complete the missing line (consistent with the notebook, if produced)
- `diagram` — question on a figure **recreated** with matplotlib/SVG, never cropped from the book
- `connection` — where X reappears later and in what role (only between chapters linked in the path)
- `counterexample` — a case where hypothesis H fails and the result breaks
- `reverse` — from the description to the concept name

Content rules:
- One card = one atomic idea; no "list all the…" cards.
- Every **core** objective has ≥3 cards, including ≥1 `why` or `apply`. Every secondary objective has ≥1.
- `definition` + `cloze` ≤ 25% of the chapter's cards.
- Mix types across the chapter; size scales with the objectives (typically 20–40 cards).
- Front: short and unambiguous. Back: the short answer. `explanation`: 1–3 sentences of context (the why, a pitfall, a link).
- Math in MathJax `\( ... \)` / `\[ ... \]`. Paraphrased text, never copied paragraphs.
- Tags: `<book>::chNN::section`, plus `core`/`secondary` and the card type.

Note type and design (genanki):
- One custom model with fields `Front, Back, Explanation, Objective, Level, Type, Source, Media`; stable model id and deck ids derived from a hash of the book slug, so re-imports update instead of duplicating.
- One `deck.apkg` for the book, one subdeck per chapter (`Book::Ch03 Title`), built from all `cards.tsv`; media packaged.
- Front template: type badge + level badge (core and secondary visually distinct) above the question.
- Back template: answer → divider → explanation → objective text → source reference in small type.
- CSS: reuse the site's design tokens (same palette and badges) so deck and site look like one system; readable font stack, comfortable line-height, centered column with max-width, generous padding; layout that works on AnkiDroid/mobile; light and dark themes (`.nightMode` / `.night_mode` selectors) with sufficient contrast.
- Code: pre-highlighted with Pygments as inline-styled HTML (no runtime JS), monospace, horizontal scroll on overflow.
- `cards.html`: the same cards as flip-cards in the site (click/Enter to reveal back + explanation), filterable by objective, type and level.

### Notebook (`notebook.ipynb` + `notebook.html`)
Built with `nbformat`: intuition → from-scratch NumPy implementation → comparison with the standard library (scikit-learn/PyTorch/astropy, as fits the field) → exercises, solutions in separate cells marked `# SOLUTION`. Synthetic or open datasets; fixed seeds; each theory cell references the source section and objective id (in the section heading, e.g. `## Gaussian elimination (§2.3 · ch02-o1)`). `build_site.py` executes it (nbclient), then renders it inside the site template — site header/navigation and theme, highlighted code, embedded figures, a section table of contents, headings as anchors that feed the objectives' back-links; solution cells are collapsed by default (`<details>`). The executed `.ipynb` is linked as a download.

### Quiz (`quiz.html`)
- At least one question per core objective; typically 12–20 questions.
- Graded difficulty, grouped by level: remember → understand → apply → analyze (one section each, with a jump nav).
- Mixed formats: open answer, by-hand computation, multiple choice, true/false with justification.
- Multiple-choice distractors are built from **real common mistakes** for the concept, never absurd options.
- From the second chapter on, include cumulative questions linking to earlier chapters, using the path.
- Solutions: step-by-step reasoning, for multiple choice why each distractor is wrong, objective id (linked) and section reference.
- Interaction (progressive enhancement; the page must be fully readable with JS off): multiple-choice options are clickable — choosing one marks it right/wrong and reveals that option's explanation plus the full solution; open/compute/tf questions show the solution in a `<details>` toggle. A "show all solutions" control and a print view with solutions at the end. No scores, timers or progress tracking.

### Glossary (`glossary.html`, plus book-wide `glossary.html`)
Terms with paraphrased definitions, the original-language term when translating, the notation used by the source, and the objective id(s) they serve (linked). Alphabetical, with a client-side filter box; the book-wide page merges all chapters and shows which chapter each term comes from.

### Readings (`readings.html` + `readings.bib`)
- Up to 5 works, taken first from the source's bibliography, then closely related classic papers. Zero is acceptable.
- A reading is included **only if it serves a specific objective**. Each entry states: full reference, objective id, **core** or **deepening**, and 2–3 sentences on what it adds beyond the book (written after checking abstract or official page; paraphrased).
- Verify title, authors, year and DOI with a search. Never download or attach protected PDFs: metadata and DOI/official or open-access links only. BibTeX compatible with Zotero/Better BibTeX, linked from the page; each entry has a "copy BibTeX" button.

### Videos (`videos.html`)
1–3 supporting videos per chapter (university lectures, agency and observatory channels, recognized educational channels), each verified with a search; note which section and objective it supports, duration and available subtitle languages when known. Show as link cards (title, channel, year, duration); do not embed iframes. Never fabricated links.

## Site build

`scripts/build_site.py` (Python 3, Jinja2) reads `data/`, executes the notebooks and writes `site/`. It is idempotent and re-run after every chapter. The design rules below are implemented in `templates/site/` and `sk_common.TOKENS`; per book, set `theme` in `book.json` (token overrides and fonts) to choose the visual direction. Change the templates only to fix a real defect, and then in the skill, not in a kit.

### Design
- One shared `assets/style.css` and `assets/site.js`; no CSS framework, no build toolchain. The only external dependency allowed is KaTeX (pinned version from cdn.jsdelivr.net) for math, with the raw TeX left readable if it fails to load. Otherwise fully offline: the site works opened from disk (`file://`) — relative links only, no fetches of local JSON.
- **Design tokens** as CSS custom properties on `:root` (background, surface, text, muted, border, accent, core, secondary, success, error, code background), redefined for dark mode under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`. A theme toggle in the header stores the choice in `localStorage` (wrapped in try/catch). `body` has an explicit background.
- Choose a visual direction suited to the subject (e.g. a deep-space palette for astronomy, a paper/ink palette for humanities) and keep it consistent; core vs secondary badges must be distinguishable without relying on color alone (label text + shape).
- Typography: a readable system or Google-Fonts pair (one serif or humanist sans for body, one monospace for code), body ~17–18px, line-height 1.6, measure ≤ 72ch.
- Layout: sticky header with book title, breadcrumb (Book › Chapter › Page), theme toggle; on chapter pages a tab bar/side nav for Objectives · Map · Quiz · Notebook · Glossary · Readings · Videos · Cards (only the pages that exist), plus previous/next chapter links. Responsive down to 360px with a 16px gutter and no horizontal page scroll (tables scroll inside their own container).
- Accessibility: semantic landmarks (`header`, `nav`, `main`, `footer`), one `h1` per page, visible focus styles, keyboard-operable interactions, WCAG AA contrast in both themes, `prefers-reduced-motion` respected.
- Print stylesheet: hides nav and toggles, expands all `<details>`, black on white.
- Footer on every page: source citation and license of the source when known.

### Optional publishing
When an Artifact tool that supports multi-file publishing is available, offer to publish `site/` as an artifact (home page as the page, other files via `files`); otherwise deliver it as a zip.

## Checks before moving to the next chapter (only for outputs produced)

Run, fix every error, read every warning:

```bash
python3 <skill>/scripts/validate.py   study-kit/<book> --chapter chNN --source source.txt
python3 <skill>/scripts/build_site.py study-kit/<book>
python3 <skill>/scripts/check_site.py study-kit/<book>/site --screenshots <scratch>/shots
```

Then look at the screenshots. The scripts cover the mechanical rules below; the quality ones (does each `why` card explain a why, are distractors plausible mistakes) need reading.

- Data validates against the schema; every objective has a source reference; every core objective states why it is core.
- Every produced item references an existing objective id; every objective has ≥1 back-link; the home page links every produced page of the chapter.
- Cards: core objectives have ≥3 cards including ≥1 `why`/`apply`; definitions + cloze ≤ 25%; no duplicate ids, no empty required fields, every row has `source`; diagram cards have their media file.
- Quiz: every core objective has ≥1 question; every multiple-choice option has a `why`.
- Readings: each tied to an objective and summarized.
- Notebook: `jupyter nbconvert --to notebook --execute notebook.ipynb` completes without errors; `notebook.html` exists.
- HTML: every internal link and anchor resolves (crawl `site/` with a script); the pages parse without errors; no unrendered template or Markdown syntax leaks into output.
- Visual check: render the chapter index and quiz pages with headless Chromium (Playwright) at 1280px and 390px in light and dark theme, look at the screenshots, and fix overflow, contrast or layout problems.
- No long verbatim quotes from the source (short phrases only, quoted and referenced).
- No topic absent from the source, cited syllabi or cited readings.
- No schedules, durations or study instructions anywhere.

## Checks before delivering the book

`validate.py study-kit/<book>` (whole book), `build_site.py`, `check_site.py … --screenshots … --pages all`, and `build_deck.py` (its per-subdeck counts must match the `cards.tsv` rows).

- Home page: every variant and syllabus has a verified source; the link crawl over the whole `site/` reports zero broken links.
- If cards were produced: `deck.apkg` contains as many notes as all `cards.tsv` rows combined, one subdeck per chapter; open a sample of cards in light and dark mode to check rendering.
- The site opens from `file://` with no console errors (check with Playwright).

## Delivery

Send `site/` as a zip (plus `deck.apkg` if produced; `data/` and `build_site.py` included so the kit can be rebuilt), or publish it as described above. In chat, a compact table: one row per chapter with the outputs produced and their counts (objectives core/secondary, cards, quiz questions, readings). No recommendations on how or when to study.