# Data format

Everything the agent writes lives in `study-kit/<book-slug>/data/`. `scripts/validate.py` checks it; `scripts/build_site.py` renders it to `site/`; `scripts/build_deck.py` builds `deck.apkg`. Never write HTML by hand.

```
data/
├── book.json            path, variants, syllabi, chapter order, theme
├── chNN.json            one per produced chapter
├── chNN.cards.tsv       cards (source of truth for the deck and cards.html)
├── chNN.ipynb           notebook source (executed at build time)
├── chNN.bib             BibTeX for the chapter's readings (optional; generated from fields if absent)
└── media/chNN/          recreated figures used by cards
```

Ids: chapter `chNN` (two digits) · objective `chNN-oN` · card `chNN-cNNN` · quiz question `QN` (unique within the chapter).

## Text fields

Plain text with a small inline subset: `*em*`, `**strong**`, `` `code` ``, `[label](url)`, math in `\( … \)` / `\[ … \]` (rendered with KaTeX on the site, MathJax in Anki). Raw HTML is never allowed and is escaped. In `solution`, `goal`, `adds` and `note`, a blank line starts a new paragraph and a single newline is a line break.

In JSON remember to escape backslashes: `"\\(X^\\top X\\)"`.

## `book.json`

```json
{
  "title": "Mathematics for Machine Learning",
  "subtitle": "optional",
  "slug": "mml",
  "language": "en",
  "source": {
    "citation": "Deisenroth, Faisal & Ong (2020). Mathematics for Machine Learning. Cambridge University Press.",
    "url": "https://mml-book.github.io/",
    "license": "© the authors; free PDF for personal use"
  },
  "theme": {
    "light": {"accent": "#2c5a86"},
    "dark": {"accent": "#8db7e3"},
    "fonts": {"body": "Georgia, serif"}
  },
  "chapters": [
    {
      "id": "ch02",
      "slug": "ch02-linear-algebra",
      "title": "Linear Algebra",
      "scope": "Vectors, matrices, linear maps, bases.",
      "goal": "The algebraic language used by every later chapter.",
      "prerequisites": "High-school algebra (stated in the preface).",
      "requires": [],
      "flags": ["required"],
      "forward_links": [{"chapter": "ch03", "note": "inner products build on §2.7"}],
      "syllabi": ["tum-mml-2025"]
    }
  ],
  "variants": [
    {"id": "part-1", "title": "Part I only", "chapters": ["ch02", "ch03", "ch04"],
     "source": "Preface, \"How to read this book\", p. 3"}
  ],
  "syllabi": [
    {"id": "tum-mml-2025", "course": "Mathematics for ML", "institution": "TU Munich", "year": 2025,
     "url": "https://…", "chapters": ["ch02", "ch03"], "outcomes": ["solve systems of linear equations"]}
  ]
}
```

- `chapters` lists every chapter of the book in book order, produced or not; a chapter is *produced* when `data/chNN.json` exists. Unproduced chapters render greyed out.
- `requires`: earlier chapter ids this chapter depends on (edges of the dependency view). `forward_links`: later chapters that reuse it.
- `flags`: only what the book states (`required`, `optional`, `advanced`, `starred`…).
- `variants: []` and `syllabi: []` are valid: the site then states explicitly that none are stated / verified. Never invent either.
- `theme` is optional: override any design token (see `sk_common.TOKENS`) to give the subject its own visual direction. The deck uses the same tokens.

## `chNN.json`

```json
{
  "id": "ch03", "slug": "ch03-analytic-geometry", "title": "Analytic Geometry",
  "source_ref": "Chapter 3, pp. 70–104",
  "goal": "Two or three sentences …",
  "objectives": [
    {"id": "ch03-o1", "level": "core",
     "text": "After this chapter you can compute the orthogonal projection of a vector onto a subspace.",
     "source": "§3.8", "why_core": "Used in ch09 (least squares) and exercises 3.4–3.6.",
     "syllabus_outcome": {"syllabus": "tum-mml-2025", "text": "compute projections"}}
  ],
  "map": [
    {"section": "3.8", "title": "Orthogonal projections", "pages": "pp. 92–98", "url": null,
     "concepts": ["projection matrix", "projection onto a line"], "objectives": ["ch03-o1"]}
  ],
  "quiz": [
    {"id": "Q1", "level": "understand", "format": "mc",
     "prompt": "Which statement is always true …?",
     "options": [
       {"key": "A", "text": "…", "correct": false, "why": "The common mistake it encodes."},
       {"key": "B", "text": "…", "correct": true, "why": "Why it is right."}
     ],
     "solution": "Step-by-step reasoning …", "objectives": ["ch03-o1"], "source": "§3.8"},
    {"id": "Q2", "level": "analyze", "format": "tf", "answer": false,
     "prompt": "Statement …", "solution": "False. …", "objectives": ["ch03-o1", "ch02-o4"], "source": "§3.8"}
  ],
  "glossary": [
    {"term": "Projection", "original": null, "definition": "…", "notation": "\\(\\pi_U(x)\\)", "objectives": ["ch03-o1"]}
  ],
  "readings": [
    {"key": "strang2016", "citation": "Strang, G. (2016). Introduction to Linear Algebra (5th ed.).",
     "doi": null, "url": "https://math.mit.edu/~gs/linearalgebra/", "kind": "deepening",
     "adds": "Two or three sentences on what it adds beyond the book …", "objectives": ["ch03-o1"]}
  ],
  "videos": [
    {"title": "Projections onto subspaces", "by": "MIT OpenCourseWare", "year": 2009,
     "url": "https://www.youtube.com/watch?v=…", "duration": "48 min", "subtitles": ["en"],
     "sections": ["3.8"], "objectives": ["ch03-o1"], "note": "Lecture 15 of 18.06."}
  ]
}
```

Rules checked by `validate.py`:

- `id`/`slug` match `book.json`; objective ids start with the chapter id; `level` is `core` or `secondary`; every objective has `source`; core objectives have `why_core`.
- Every id in any `objectives` list exists (cumulative items may reference earlier chapters).
- Quiz: `level` ∈ remember/understand/apply/analyze; `format` ∈ mc/open/compute/tf; `mc` has ≥3 options, exactly one `correct`, a `why` on every option; `tf` has `answer`; every question has `solution` and `source`; every core objective has ≥1 question.
- Readings: ≤5, `kind` ∈ core/deepening, `adds` ≥15 words, a `doi` or `url`.
- Videos: https `url`, ≥1 section and objective; more than 3 per chapter is flagged.
- Every objective is served by at least one item (back-link) in the produced outputs.
- Optional outputs: omit the key, or leave the list empty, and the page is not generated.

## `chNN.cards.tsv`

Tab-separated, UTF-8, header exactly:

```
id	objective	level	type	front	back	explanation	source	media	tags
```

- `level` equals the objective's level; `type` from `card-types.md`.
- Line breaks: `<br>` (never `\n`, which collides with `\nabla`). Code: fenced block with `<br>` line breaks, e.g. ` ```python<br>x = np.ones(3)<br>``` `. No tabs or real newlines inside a field.
- Inline markup as in text fields; inside math use `\lt` / `\gt` instead of `<` / `>`.
- `cloze`: `front` contains `{{c1::…}}`; `back` may be empty.
- `media`: file name in `data/media/chNN/` (required for `diagram`).
- `tags`: space-separated; `core`/`secondary`, the type and `<book>::chNN::<section>` are added automatically.

## `chNN.ipynb`

Built with `nbformat`. Markdown section headings name the source section and objective id, e.g. `## Gaussian elimination (§2.3 · ch02-o1)`: the build turns them into anchors and objective back-links. Exercise solutions are separate code cells whose first line is `# SOLUTION` (rendered collapsed). Set seeds. Relative paths resolve from `data/`.
