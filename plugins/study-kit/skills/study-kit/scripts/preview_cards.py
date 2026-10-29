#!/usr/bin/env python3
"""Preview the Anki note design (front + back) in a browser, without Anki.

Usage:
    preview_cards.py BOOK_DIR [--out preview.html] [--theme light|dark] [--chapter chNN] [--limit N]

Uses the same templates and CSS as build_deck.py (Anki's night mode is simulated with the
.nightMode class). MathJax is loaded from a CDN, as Anki does. The site's cards.html is a
different view of the same cards; this preview is for checking the deck itself.
"""
from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sk_common as C  # noqa: E402
from build_deck import ANKI, css, render  # noqa: E402

MATHJAX = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml-full.js"


def fill(template: str, fields: dict) -> str:
    """Minimal Anki template engine: {{#F}}…{{/F}}, {{F}}, {{cloze:F}}."""
    out = re.sub(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", lambda m: m.group(2) if fields.get(m.group(1)) else "",
                 template, flags=re.DOTALL)
    out = re.sub(r"\{\{cloze:(\w+)\}\}", lambda m: fields.get("__cloze__", ""), out)
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fields.get(m.group(1), ""), out)


def cloze(text: str, reveal: bool) -> str:
    return re.sub(r"\{\{c\d+::(.+?)(?:::[^}]*)?\}\}",
                  lambda m: f'<span class="cloze">{m.group(1) if reveal else "[…]"}</span>', text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--chapter")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    paths = C.kit_paths(a.book.resolve())
    book = C.load_json(paths["book"])
    tpl = {n: (ANKI / n).read_text(encoding="utf-8") for n in
           ["front.html", "back.html", "cloze_front.html", "cloze_back.html"]}
    night = " nightMode night_mode" if a.theme == "dark" else ""
    blocks = []
    for ch in [c["id"] for c in book.get("chapters", [])]:
        files = C.chapter_files(paths["data"], ch)
        if (a.chapter and ch != a.chapter) or not files["cards"].is_file():
            continue
        d = C.load_json(files["json"]) if files["json"].is_file() else {}
        objs = {o["id"]: o for o in d.get("objectives", [])}
        for _, c in C.read_cards(files["cards"])[1]:
            if "_cols" in c:
                continue
            media = ""
            if c["media"] and (files["media"] / c["media"]).is_file():
                p = files["media"] / c["media"]
                mime = mimetypes.guess_type(p.name)[0] or "image/png"
                media = f'<img src="data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}">'
            oid = c["objective"]
            f = {"Front": render(c["front"]), "Back": render(c["back"]), "Extra": render(c["back"]),
                 "Explanation": render(c["explanation"]),
                 "Objective": f'{C.inline(objs[oid]["text"])} <span class="sk-oid">({oid})</span>' if oid in objs else oid,
                 "Level": c["level"], "Type": c["type"], "Source": C.inline(c["source"]), "Media": media}
            if c["type"] == "cloze":
                text = render(c["front"])
                front = fill(tpl["cloze_front.html"], {**f, "__cloze__": cloze(text, False)})
                back = fill(tpl["cloze_back.html"], {**f, "__cloze__": cloze(text, True)})
            else:
                front, back = fill(tpl["front.html"], f), fill(tpl["back.html"], f)
            blocks.append(f'<section class="pv"><h2 class="pv-id">{html.escape(c["id"])}</h2><div class="pv-pair">'
                          f'<div class="card{night}">{front}</div><div class="card{night}">{back}</div></div></section>')
            if a.limit and len(blocks) >= a.limit:
                break
        if a.limit and len(blocks) >= a.limit:
            break
    bg = "#0e0f12" if a.theme == "dark" else "#e6e2d9"
    page = f"""<!doctype html><html lang="{book.get('language', 'en')}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Deck preview · {html.escape(C.plain(book.get('title', '')))}</title>
<style>{css(book)}
body {{ margin: 0; padding: 24px 16px; background: {bg}; }}
.pv {{ max-width: 1360px; margin: 0 auto 28px; }}
.pv-id {{ font: 600 12px/1 ui-monospace, monospace; color: #888; margin: 0 0 8px; }}
.pv-pair {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
.pv-pair .card {{ border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.18); }}
</style>
<script>window.MathJax = {{ tex: {{ inlineMath: [['\\\\(', '\\\\)']], displayMath: [['\\\\[', '\\\\]']] }} }};</script>
<script src="{MATHJAX}" async></script></head><body>{''.join(blocks)}</body></html>"""
    out = a.out or a.book / f"deck-preview-{a.theme}.html"
    out.write_text(page, encoding="utf-8")
    print(f"{len(blocks)} cards → {out}")


if __name__ == "__main__":
    main()
