"""Shared helpers for the study-kit scripts: data loading, design tokens, inline text rendering."""
from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"

CH_ID_RE = re.compile(r"^ch\d{2}$")
OBJ_ID_RE = re.compile(r"\bch\d{2}-o\d+\b")
CH_REF_RE = re.compile(r"\bch\d{2}\b")
SLUG_RE = re.compile(r"^(ch\d{2})-[a-z0-9][a-z0-9-]*$")

CARD_HEADER = ["id", "objective", "level", "type", "front", "back",
               "explanation", "source", "media", "tags"]
CARD_TYPES = ["definition", "cloze", "why", "compare", "apply", "derivation", "mistake",
              "intuition", "notation", "code", "diagram", "connection", "counterexample", "reverse"]
LEVELS = ["core", "secondary"]
QUIZ_LEVELS = ["remember", "understand", "apply", "analyze"]
QUIZ_FORMATS = {"mc": "Multiple choice", "open": "Open answer", "compute": "Computation", "tf": "True / false"}
PAGES = [  # (key, file, label) in navigation order
    ("objectives", "index.html", "Objectives"),
    ("map", "map.html", "Map"),
    ("quiz", "quiz.html", "Quiz"),
    ("notebook", "notebook.html", "Notebook"),
    ("glossary", "glossary.html", "Glossary"),
    ("readings", "readings.html", "Readings"),
    ("videos", "videos.html", "Videos"),
    ("cards", "cards.html", "Cards"),
]

# ----------------------------------------------------------------------------- design tokens
# Shared by the site (CSS custom properties) and the Anki deck. Override per book in
# book.json → "theme": {"light": {...}, "dark": {...}, "fonts": {...}}.
TOKENS = {
    "light": {
        "bg": "#f7f5f0", "surface": "#ffffff", "surface-2": "#efece4", "text": "#1d2127",
        "muted": "#5d636b", "border": "#dcd7cc", "accent": "#2c5a86", "accent-soft": "#e3ecf5",
        "core": "#1f5a30", "core-soft": "#dcebdf", "secondary": "#5a4a8a", "secondary-soft": "#ece8f6",
        "success": "#1f6b3a", "success-soft": "#ddefe2", "error": "#a33a22", "error-soft": "#f6e1dc",
        "code-bg": "#f1efe9", "focus": "#c2571c",
    },
    "dark": {
        "bg": "#15171b", "surface": "#1d2025", "surface-2": "#252930", "text": "#e7e5e0",
        "muted": "#a0a6ad", "border": "#343840", "accent": "#8db7e3", "accent-soft": "#223244",
        "core": "#a3dbb0", "core-soft": "#1e3a27", "secondary": "#c9bff2", "secondary-soft": "#2c2842",
        "success": "#9fdcae", "success-soft": "#1d3a26", "error": "#f2a48d", "error-soft": "#45241c",
        "code-bg": "#22262c", "focus": "#f0a066",
    },
    "fonts": {
        "body": '"Source Serif 4", "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif',
        "ui": '"Inter", "Source Sans 3", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
        "mono": '"JetBrains Mono", "Fira Code", "SFMono-Regular", Menlo, Consolas, monospace',
    },
}


def tokens_for(book: dict | None) -> dict:
    theme = (book or {}).get("theme") or {}
    return {k: {**TOKENS[k], **(theme.get(k) or {})} for k in TOKENS}


# ----------------------------------------------------------------------------- loading

def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def kit_paths(book_dir: Path) -> dict:
    d = book_dir / "data"
    return {"data": d, "book": d / "book.json", "site": book_dir / "site"}


def chapter_files(data: Path, ch: str) -> dict:
    return {
        "json": data / f"{ch}.json",
        "cards": data / f"{ch}.cards.tsv",
        "notebook": data / f"{ch}.ipynb",
        "bib": data / f"{ch}.bib",
        "media": data / "media" / ch,
    }


def read_cards(p: Path) -> tuple[list[str], list[tuple[int, dict]]]:
    """Return (header, [(line_no, row_dict)]). Rows keep raw strings; malformed rows are dicts with '_cols'."""
    with p.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))
    if not rows:
        return [], []
    out = []
    for ln, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row):
            continue
        if len(row) != len(CARD_HEADER):
            out.append((ln, {"_cols": len(row)}))
            continue
        out.append((ln, dict(zip(CARD_HEADER, (x.strip() for x in row)))))
    return rows[0], out


# ----------------------------------------------------------------------------- text rendering

MATH_RE = re.compile(r"\\\((.+?)\\\)|\\\[(.+?)\\\]", re.DOTALL)
FENCE_RE = re.compile(r"```([\w+-]*)\n(.*?)```", re.DOTALL)
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _protect(text: str, pattern: re.Pattern, store: list, fn=lambda m: m.group(0)) -> str:
    def sub(m):
        store.append(fn(m))
        return f"\x00{len(store) - 1}\x00"
    return pattern.sub(sub, text)


def _restore(text: str, store: list) -> str:
    while "\x00" in text:
        text = re.sub(r"\x00(\d+)\x00", lambda m: store[int(m.group(1))], text)
    return text


def inline(text: str | None) -> str:
    """Minimal inline Markdown → HTML for data fields.

    Supports *em*, **strong**, `code`, [text](url) and math in \\( \\) / \\[ \\] (left as TeX for
    KaTeX/MathJax). Everything else is HTML-escaped: raw HTML in data is never rendered.
    """
    if not text:
        return ""
    store: list[str] = []
    t = _protect(text, MATH_RE, store, lambda m: html.escape(m.group(0), quote=False))
    t = _protect(t, re.compile(r"`([^`]+)`"), store, lambda m: f"<code>{html.escape(m.group(1))}</code>")
    links: list[tuple[str, str]] = []

    def link(m):
        links.append((m.group(1), m.group(2)))
        return f"\x01{len(links) - 1}\x01"
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, t)
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)

    def unlink(m):
        label, url = links[int(m.group(1))]
        safe = url if re.match(r"^(https?://|mailto:|#|\.{0,2}/|[\w.-]+(\.html|/)?(#[\w.-]+)?$)", url) else "#"
        ext = ' rel="noopener"' if safe.startswith("http") else ""
        return f'<a href="{html.escape(safe)}"{ext}>{html.escape(label, quote=False)}</a>'
    t = re.sub(r"\x01(\d+)\x01", unlink, t)
    return _restore(t, store)


def block(text: str | None) -> str:
    """Multi-paragraph field: blank line → new paragraph, single newline → <br>."""
    if not text:
        return ""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return "".join(f"<p>{inline(p).replace(chr(10), '<br>')}</p>" for p in paras)


def card_html(field: str, code_class: str = "sk-code") -> str:
    """cards.tsv field → HTML: <br> line breaks, fenced code highlighted with Pygments, inline markdown."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import TextLexer, get_lexer_by_name
    from pygments.util import ClassNotFound

    text = BR_RE.sub("\n", field or "")
    store: list[str] = []

    def code_block(m):
        lang, code = m.group(1) or "text", m.group(2)
        try:
            lexer = get_lexer_by_name(lang)
        except ClassNotFound:
            lexer = TextLexer()
        return highlight(code.rstrip("\n"), lexer, HtmlFormatter(cssclass=code_class))
    text = _protect(text, FENCE_RE, store, code_block)
    text = re.sub(r"(\x00\d+\x00)\n", r"\1", text)
    parts = re.split(r"(\x00\d+\x00)", text.strip("\n"))
    out = "".join(p if re.fullmatch(r"\x00\d+\x00", p) else inline(p).replace("\n", "<br>") for p in parts)
    return _restore(out, store)


def plain(text: str | None) -> str:
    """Strip inline markup for search indexes, titles and lints."""
    if not text:
        return ""
    t = BR_RE.sub(" ", text)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    return re.sub(r"[*`]", "", t)


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", plain(s).lower())
    return re.sub(r"[\s_]+", "-", s).strip("-") or "x"
