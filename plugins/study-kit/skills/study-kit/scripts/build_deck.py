#!/usr/bin/env python3
"""Build a styled Anki deck (.apkg) from every data/chNN.cards.tsv of a study kit.

Usage:
    build_deck.py BOOK_DIR [--out deck.apkg] [--title "Book title"]

- One deck for the book, one subdeck per chapter ("<Book>::chNN · <Chapter>").
- Two note types (basic, cloze) with the templates in ../templates/anki, styled with the same
  design tokens as the site (sk_common.TOKENS + book.json "theme").
- Stable ids: model ids are fixed, deck ids and note GUIDs derive from the book slug and card ids,
  so re-importing an updated deck updates notes instead of duplicating them.
- cards.tsv stays the source of truth; the .apkg is a derivative.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sk_common as C  # noqa: E402

try:
    import genanki
    from pygments.formatters import HtmlFormatter
except ImportError as e:  # pragma: no cover
    sys.exit(f"missing dependency ({e.name}); run: pip install -r requirements.txt")

ANKI = C.TEMPLATES / "anki"
# Fixed ids: the note types are shared by every study-kit deck, so styles update in place.
BASIC_MODEL_ID = 1_742_118_201
CLOZE_MODEL_ID = 1_742_118_202
NIGHT = [".nightMode", ".night_mode", ".night-mode"]


def stable_id(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest()[:8], 16) | (1 << 30)


def css(book: dict | None) -> str:
    t = C.tokens_for(book)

    def block(tok):
        return "\n".join(f"  --{k}: {v};" for k, v in tok.items())
    fonts = "\n".join(f"  --font-{k}: {v};" for k, v in t["fonts"].items())
    night = ", ".join([f".card{n}" for n in NIGHT] + [f"{n} .card" for n in NIGHT])
    head = f".card {{\n{block(t['light'])}\n{fonts}\n}}\n{night} {{\n{block(t['dark'])}\n}}\n"
    base = (ANKI / "card.css").read_text(encoding="utf-8")
    light = HtmlFormatter(style="friendly").get_style_defs(".sk-code")
    dark = HtmlFormatter(style="github-dark").get_style_defs([f"{n} .sk-code" for n in NIGHT] +
                                                              [f".card{n} .sk-code" for n in NIGHT])
    strip_bg = lambda s: re.sub(r"\n[^\n]*\{ background: [^}]*\}", "", s)  # noqa: E731
    return head + base + "\n/* code: light */\n" + strip_bg(light) + "\n/* code: dark */\n" + strip_bg(dark) + "\n"


def models(book: dict | None):
    t = lambda n: (ANKI / n).read_text(encoding="utf-8")  # noqa: E731
    style = css(book)
    fields = ["Explanation", "Objective", "Level", "Type", "Source", "Media", "CardId"]
    basic = genanki.Model(
        BASIC_MODEL_ID, "Study Kit · Basic", fields=[{"name": n} for n in ["Front", "Back"] + fields],
        templates=[{"name": "Card", "qfmt": t("front.html"), "afmt": t("back.html")}],
        css=style, sort_field_index=0)
    cloze = genanki.Model(
        CLOZE_MODEL_ID, "Study Kit · Cloze", fields=[{"name": n} for n in ["Text", "Extra"] + fields],
        templates=[{"name": "Cloze", "qfmt": t("cloze_front.html"), "afmt": t("cloze_back.html")}],
        css=style, model_type=genanki.Model.CLOZE)
    return basic, cloze


def render(field: str) -> str:
    """cards.tsv field → Anki HTML (MathJax left as TeX; Anki renders \\( \\) and \\[ \\])."""
    return C.card_html(field, "sk-code")


def tag(s: str) -> str:
    return re.sub(r"\s+", "_", s.strip())


def build(book_dir: Path, out: Path, title: str | None = None) -> dict:
    book_dir = book_dir.resolve()
    paths = C.kit_paths(book_dir)
    book = C.load_json(paths["book"]) if paths["book"].is_file() else {}
    slug = book.get("slug") or book_dir.name
    title = title or C.plain(book.get("title")) or book_dir.name
    order = [c["id"] for c in book.get("chapters", [])] or sorted(
        {p.name.split(".")[0] for p in paths["data"].glob("ch*.cards.tsv")})
    basic, cloze = models(book)
    decks, media_files, counts = [], [], {}
    tmp = Path(tempfile.mkdtemp(prefix="study-kit-media-"))
    try:
        for ch in order:
            files = C.chapter_files(paths["data"], ch)
            if not files["cards"].is_file():
                continue
            d = C.load_json(files["json"]) if files["json"].is_file() else {}
            objs = {o["id"]: o for o in d.get("objectives", [])}
            deck_name = f"{title}::{ch} · {C.plain(d.get('title', ch))}"
            deck = genanki.Deck(stable_id(f"study-kit/{slug}/{ch}"), deck_name)
            header, rows = C.read_cards(files["cards"])
            if header != C.CARD_HEADER:
                raise SystemExit(f"{files['cards']}: bad header; run validate.py first")
            n = 0
            for ln, c in rows:
                if "_cols" in c:
                    raise SystemExit(f"{files['cards']}: line {ln} has {c['_cols']} columns; run validate.py first")
                media_html = ""
                if c["media"]:
                    src = files["media"] / c["media"]
                    if not src.is_file():
                        raise SystemExit(f"{files['cards']}: {c['id']}: media {src} not found")
                    name = f"{slug}_{ch}_{c['media']}"
                    shutil.copy(src, tmp / name)
                    media_files.append(str(tmp / name))
                    media_html = f'<img src="{html.escape(name)}">'
                oid = c["objective"]
                obj = (f'{C.inline(objs[oid]["text"])} <span class="sk-oid">({oid})</span>'
                       if oid in objs else html.escape(oid))
                section = re.search(r"§\s*([\d.]+)", c["source"])
                tags = [tag(t) for t in c["tags"].split()] + [
                    c["level"], c["type"], f"{slug}::{ch}" + (f"::s{section.group(1).rstrip('.')}" if section else "")]
                fields = [render(c["front"]), render(c["back"]), render(c["explanation"]), obj,
                          c["level"], c["type"], C.inline(c["source"]), media_html, c["id"]]
                model = cloze if c["type"] == "cloze" else basic
                deck.add_note(genanki.Note(model=model, fields=fields, tags=sorted(set(tags)),
                                           guid=genanki.guid_for("study-kit", slug, c["id"])))
                n += 1
            decks.append(deck)
            counts[deck_name] = n
        if not decks:
            raise SystemExit("no data/chNN.cards.tsv found")
        pkg = genanki.Package(decks)
        pkg.media_files = media_files
        out.parent.mkdir(parents=True, exist_ok=True)
        pkg.write_to_file(str(out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book", type=Path)
    ap.add_argument("--out", type=Path, help="output file (default BOOK_DIR/deck.apkg)")
    ap.add_argument("--title", help="top-level deck name (default: book.json title)")
    a = ap.parse_args(argv)
    out = a.out or a.book / "deck.apkg"
    counts = build(a.book, out, a.title)
    for name, n in counts.items():
        print(f"{n:4d}  {name}")
    print(f"{sum(counts.values()):4d}  notes → {out}")


if __name__ == "__main__":
    main()
