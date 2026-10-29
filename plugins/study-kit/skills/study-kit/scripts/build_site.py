#!/usr/bin/env python3
"""Render a study-kit (data/ → site/): a static, offline-capable HTML website.

Usage:
    build_site.py BOOK_DIR [--no-execute] [--no-vendor]

BOOK_DIR contains data/book.json and data/chNN.json (+ chNN.cards.tsv, chNN.ipynb, chNN.bib,
media/chNN/). The build is idempotent: site/ is regenerated from scratch every time.

- Notebooks are executed (nbclient) unless --no-execute, then rendered into the site template.
- By default the build tools are vendored into BOOK_DIR/_tools/ with a BOOK_DIR/build_site.py
  wrapper, so the kit can be rebuilt without the skill installed.
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sk_common as C  # noqa: E402

try:
    import jinja2
    from markupsafe import Markup
except ImportError as e:  # pragma: no cover
    sys.exit(f"missing dependency ({e.name}); run: pip install -r requirements.txt")

KATEX = "0.16.11"
SITE_TEMPLATES = C.TEMPLATES / "site"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


# ============================================================================= model

class Kit:
    def __init__(self, book_dir: Path):
        self.dir = book_dir.resolve()
        p = C.kit_paths(self.dir)
        self.data, self.site = p["data"], p["site"]
        if not p["book"].is_file():
            raise SystemExit(f"{p['book']} not found")
        self.book = C.load_json(p["book"])
        self.tokens = C.tokens_for(self.book)
        self.meta = {c["id"]: c for c in self.book.get("chapters", [])}
        self.order = [c["id"] for c in self.book.get("chapters", [])]
        self.chapters: dict[str, dict] = {}
        for ch in self.order:
            f = C.chapter_files(self.data, ch)
            if f["json"].is_file():
                d = C.load_json(f["json"])
                d["_files"] = f
                self.chapters[ch] = d
        self.produced = [ch for ch in self.order if ch in self.chapters]

    def slug(self, ch: str) -> str:
        return self.meta.get(ch, {}).get("slug") or self.chapters.get(ch, {}).get("slug") or ch

    def obj_url(self, oid: str) -> str:
        ch = oid.split("-")[0]
        return f"{self.slug(ch)}/index.html#{oid}" if ch in self.chapters else ""

    def objectives(self) -> dict:
        return {o["id"]: {**o, "chapter": ch} for ch, d in self.chapters.items() for o in d.get("objectives", [])}


# ============================================================================= cards

def load_cards(kit: Kit, ch: str) -> list[dict]:
    f = kit.chapters[ch]["_files"]["cards"]
    if not f.is_file():
        return []
    _, rows = C.read_cards(f)
    cards = []
    for _, c in rows:
        if "_cols" in c:
            continue
        cards.append(c)
    return cards


def cloze_sides(text: str) -> tuple[str, str]:
    gap = "⟦GAP⟧"
    front = re.sub(r"\{\{c\d+::(.+?)(?:::[^}]*)?\}\}", gap, text)
    back = re.sub(r"\{\{c\d+::(.+?)(?:::[^}]*)?\}\}", "⟦C⟧\\1⟦/C⟧", text)
    f = C.card_html(front, "hl").replace(gap, '<span class="cloze-gap">[…]</span>')
    b = (C.card_html(back, "hl").replace("⟦C⟧", '<span class="cloze">')
         .replace("⟦/C⟧", "</span>"))
    return f, b


def site_cards(cards: list[dict], objs: dict) -> list[dict]:
    out = []
    for c in cards:
        if c["type"] == "cloze":
            front, revealed = cloze_sides(c["front"])
            back = C.card_html(c["back"], "hl") if c["back"] else ""
        else:
            front, revealed = C.card_html(c["front"], "hl"), ""
            back = C.card_html(c["back"], "hl")
        out.append({**c, "front_html": Markup(front), "revealed_html": Markup(revealed),
                    "back_html": Markup(back), "expl_html": Markup(C.card_html(c["explanation"], "hl")),
                    "source_html": Markup(C.inline(c["source"])),
                    "objective_text": objs.get(c["objective"], {}).get("text", "")})
    return out


# ============================================================================= notebook

def _md(text: str) -> str:
    import mistune
    store: list[str] = []
    t = C.MATH_RE.sub(lambda m: (store.append(html.escape(m.group(0), quote=False)), f"@@MATH{len(store) - 1}@@")[1],
                      text)
    md = mistune.create_markdown(escape=True, plugins=["table", "strikethrough"])
    out = md(t)
    return re.sub(r"@@MATH(\d+)@@", lambda m: store[int(m.group(1))], out)


def _shift_headings(h: str) -> str:
    return re.sub(r"<(/?)h([1-5])\b", lambda m: f"<{m.group(1)}h{int(m.group(2)) + 1}", h)


def render_outputs(outputs) -> str:
    parts = []
    for o in outputs:
        t = o.get("output_type")
        if t == "stream":
            parts.append(f'<pre class="nb-stream">{html.escape(o.get("text", ""))}</pre>')
        elif t == "error":
            tb = ANSI_RE.sub("", "\n".join(o.get("traceback", [])))
            parts.append(f'<pre class="nb-error">{html.escape(tb)}</pre>')
        elif t in ("execute_result", "display_data"):
            d = o.get("data", {})
            if "image/png" in d:
                parts.append(f'<img class="nb-img" alt="Notebook figure" src="data:image/png;base64,{d["image/png"].strip()}">')
            elif "image/svg+xml" in d:
                svg = d["image/svg+xml"]
                svg = "".join(svg) if isinstance(svg, list) else svg
                b64 = base64.b64encode(svg.encode()).decode()
                parts.append(f'<img class="nb-img" alt="Notebook figure" src="data:image/svg+xml;base64,{b64}">')
            elif "text/html" in d:
                h = d["text/html"]
                parts.append(f'<div class="nb-html scroll-x">{"".join(h) if isinstance(h, list) else h}</div>')
            elif "text/plain" in d:
                p = d["text/plain"]
                parts.append(f'<pre class="nb-result">{html.escape("".join(p) if isinstance(p, list) else p)}</pre>')
    return "".join(parts)


def render_notebook(kit: Kit, ch: str, execute: bool):
    import nbformat
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import PythonLexer

    src = kit.chapters[ch]["_files"]["notebook"]
    nb = nbformat.read(src, as_version=4)
    if execute:
        from nbclient import NotebookClient
        NotebookClient(nb, timeout=600, kernel_name="python3",
                       resources={"metadata": {"path": str(kit.data)}}).execute()
    cells, sections = [], []
    for i, cell in enumerate(nb.cells):
        source = cell.get("source", "")
        if cell.cell_type == "markdown":
            body = _shift_headings(_md(source))
            if re.match(r"\s*#\s", source):  # notebook title: the page already has the h1
                body = re.sub(r"<h2>.*?</h2>", "", body, count=1)
            m = re.search(r"<h([2-4])>(.*?)</h\1>", body)
            if m and not re.match(r"\s*#\s", source):  # a top-level "# …" cell is the notebook title
                anchor = f"nb-{i}"
                body = body.replace(m.group(0), f'<h{m.group(1)} id="{anchor}">{m.group(2)}</h{m.group(1)}>', 1)
                title = re.sub(r"<[^>]+>", "", m.group(2))
                head_ids = C.OBJ_ID_RE.findall(html.unescape(title))
                sections.append({"anchor": anchor, "title": html.unescape(title),
                                 "objectives": sorted(set(head_ids or C.OBJ_ID_RE.findall(source)))})
            cells.append(f'<div class="nb-md">{body}</div>')
        elif cell.cell_type == "code":
            code = highlight(source, PythonLexer(), HtmlFormatter(cssclass="hl"))
            out = render_outputs(cell.get("outputs", []))
            inner = f'<div class="nb-in">{code}</div>' + (f'<div class="nb-out">{out}</div>' if out else "")
            if source.lstrip().startswith("# SOLUTION"):
                cells.append(f'<details class="nb-cell nb-solution"><summary>Solution</summary>{inner}</details>')
            else:
                cells.append(f'<div class="nb-cell">{inner}</div>')
    return Markup("\n".join(cells)), sections, nb


# ============================================================================= bibtex

BIB_ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")


def parse_bib(text: str) -> dict[str, str]:
    out, starts = {}, list(BIB_ENTRY_RE.finditer(text))
    for i, m in enumerate(starts):
        depth, j = 0, m.end() - 1
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out[m.group(2)] = text[m.start():j + 1].strip()
    return out


def bib_for(r: dict) -> str:
    fields = [f"  title = {{{C.plain(r.get('citation', ''))}}}"]
    if r.get("doi"):
        fields.append(f"  doi = {{{r['doi']}}}")
    if r.get("url"):
        fields.append(f"  url = {{{r['url']}}}")
    return "@misc{" + r["key"] + ",\n" + ",\n".join(fields) + "\n}"


# ============================================================================= dependency view

def dependency_svg(kit: Kit) -> Markup:
    order = kit.order
    if not order:
        return Markup("")
    level: dict[str, int] = {}
    for ch in order:
        reqs = [r for r in kit.meta[ch].get("requires", []) if r in level]
        level[ch] = 1 + max((level[r] for r in reqs), default=-1)
    cols: dict[int, list[str]] = defaultdict(list)
    for ch in order:
        cols[level[ch]].append(ch)
    W, H, GX, GY, PAD = 188, 60, 64, 22, 12
    pos = {}
    for lv, chs in cols.items():
        for k, ch in enumerate(chs):
            pos[ch] = (PAD + lv * (W + GX), PAD + k * (H + GY))
    width = PAD * 2 + (max(cols) + 1) * W + max(cols) * GX
    height = PAD * 2 + max(len(v) for v in cols.values()) * (H + GY) - GY
    edges = []
    seen = set()
    for ch in order:
        for r in kit.meta[ch].get("requires", []):
            if r in pos:
                seen.add((r, ch))
                edges.append((r, ch, "req"))
        for fl in kit.meta[ch].get("forward_links", []):
            t = fl.get("chapter")
            if t in pos and (ch, t) not in seen:
                seen.add((ch, t))
                edges.append((ch, t, "fwd"))
    parts = [f'<svg class="depgraph" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
             f'role="img" aria-labelledby="dep-title"><title id="dep-title">Chapter dependencies</title>'
             '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
             'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="dep-arrow"/></marker></defs>']
    for a, b, kind in edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        if level[b] > level[a]:
            sx, sy, tx, ty = x1 + W, y1 + H / 2, x2, y2 + H / 2
            mx = (sx + tx) / 2
            d = f"M{sx},{sy} C{mx},{sy} {mx},{ty} {tx - 2},{ty}"
        else:  # same column: arc on the right side
            sx, sy, tx, ty = x1 + W, y1 + H / 2, x2 + W, y2 + H / 2
            d = f"M{sx},{sy} C{sx + 40},{sy} {tx + 40},{ty} {tx + 2},{ty}"
        parts.append(f'<path class="dep-edge dep-{kind}" d="{d}" marker-end="url(#arrow)" '
                     f'data-from="{a}" data-to="{b}"/>')
    for ch in order:
        x, y = pos[ch]
        m = kit.meta[ch]
        title = m.get("title", ch)
        short = title if len(title) <= 22 else title[:21] + "…"
        produced = ch in kit.chapters
        node = (f'<g class="dep-node {"is-produced" if produced else "is-pending"}" data-chapter="{ch}">'
                f'<title>{html.escape(ch)} · {html.escape(title)}{"" if produced else " (not produced yet)"}</title>'
                f'<rect x="{x}" y="{y}" width="{W}" height="{H}" rx="10"/>'
                f'<text x="{x + 14}" y="{y + 23}" class="dep-id">{html.escape(ch)}</text>'
                f'<text x="{x + 14}" y="{y + 44}" class="dep-title">{html.escape(short)}</text></g>')
        if produced:
            node = f'<a href="{html.escape(kit.slug(ch))}/index.html">{node}</a>'
        parts.append(node)
    parts.append("</svg>")
    return Markup("".join(parts))


# ============================================================================= css

def css(kit: Kit) -> str:
    from pygments.formatters import HtmlFormatter

    def block(tokens):
        return "\n".join(f"  --{k}: {v};" for k, v in tokens.items())
    t = kit.tokens
    fonts = "\n".join(f"  --font-{k}: {v};" for k, v in t["fonts"].items())
    head = (f":root {{\n{block(t['light'])}\n{fonts}\n  color-scheme: light;\n}}\n"
            f"@media (prefers-color-scheme: dark) {{\n  :root:not([data-theme=\"light\"]) {{\n{block(t['dark'])}\n"
            f"  color-scheme: dark;\n  }}\n}}\n"
            f":root[data-theme=\"dark\"] {{\n{block(t['dark'])}\n  color-scheme: dark;\n}}\n")
    base = (SITE_TEMPLATES / "style.css").read_text(encoding="utf-8")
    light = HtmlFormatter(style="friendly").get_style_defs([".hl"])
    dark_sel = HtmlFormatter(style="github-dark").get_style_defs([':root[data-theme="dark"] .hl'])
    dark_mq = HtmlFormatter(style="github-dark").get_style_defs([':root:not([data-theme="light"]) .hl'])
    strip_bg = lambda s: re.sub(r"\n[^\n]*\{ background: [^}]*\}", "", s)  # noqa: E731
    return (head + "\n" + base + "\n/* syntax: light */\n" + strip_bg(light) +
            "\n/* syntax: dark */\n" + strip_bg(dark_sel) +
            "\n@media (prefers-color-scheme: dark) {\n" + strip_bg(dark_mq) + "\n}\n")


# ============================================================================= build

def counts_for(d: dict, cards: list, has_nb: bool) -> dict:
    objs = d.get("objectives", [])
    return {"core": sum(o.get("level") == "core" for o in objs),
            "secondary": sum(o.get("level") == "secondary" for o in objs),
            "quiz": len(d.get("quiz") or []), "cards": len(cards),
            "readings": len(d.get("readings") or []), "videos": len(d.get("videos") or []),
            "glossary": len(d.get("glossary") or []), "notebook": has_nb}


def build(book_dir: Path, execute: bool = True, vendor: bool = True) -> dict:
    kit = Kit(book_dir)
    objs = kit.objectives()
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(SITE_TEMPLATES)),
                             autoescape=jinja2.select_autoescape(["html"]),
                             undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    env.filters["md"] = lambda s: Markup(C.inline(s))
    env.filters["mdblock"] = lambda s: Markup(C.block(s))
    env.filters["plain"] = C.plain
    env.filters["slug"] = C.slugify

    # ---------------------------------------------------------------- per-chapter models
    model: dict[str, dict] = {}
    backlinks: dict[str, list] = defaultdict(list)

    def link(oid, kind, label, href):
        backlinks[oid].append({"kind": kind, "label": label, "href": href})

    for ch in kit.produced:
        d = kit.chapters[ch]
        slug = kit.slug(ch)
        cards = load_cards(kit, ch)
        has_nb = d["_files"]["notebook"].is_file()
        pages = {"objectives": True, "map": bool(d.get("map")), "quiz": bool(d.get("quiz")),
                 "notebook": has_nb, "glossary": bool(d.get("glossary")),
                 "readings": bool(d.get("readings")), "videos": bool(d.get("videos")), "cards": bool(cards)}
        model[ch] = {"data": d, "slug": slug, "cards": cards, "pages": pages,
                     "counts": counts_for(d, cards, has_nb)}
        for s in d.get("map") or []:
            for oid in s.get("objectives", []):
                link(oid, "map", f"§{s['section']}", f"{slug}/map.html#sec-{C.slugify(s['section'])}")
        for q in d.get("quiz") or []:
            for oid in q.get("objectives", []):
                link(oid, "quiz", q["id"] if oid.startswith(ch) else f"{ch} {q['id']}", f"{slug}/quiz.html#{q['id']}")
        for g in d.get("glossary") or []:
            for oid in g.get("objectives", []):
                link(oid, "glossary", g["term"], f"{slug}/glossary.html#term-{C.slugify(g['term'])}")
        for r in d.get("readings") or []:
            for oid in r.get("objectives", []):
                link(oid, "readings", r["key"], f"{slug}/readings.html#{r['key']}")
        for i, v in enumerate(d.get("videos") or [], start=1):
            for oid in v.get("objectives", []):
                link(oid, "videos", v["title"], f"{slug}/videos.html#v{i}")
        for c in cards:
            link(c["objective"], "cards", c["id"], f"{slug}/cards.html#{c['id']}")

    # notebooks (may need execution; rendered before pages so sections feed back-links)
    for ch in kit.produced:
        m = model[ch]
        if m["pages"]["notebook"]:
            m["nb_html"], m["nb_sections"], m["nb_executed"] = render_notebook(kit, ch, execute)
            for s in m["nb_sections"]:
                for oid in s["objectives"]:
                    link(oid, "notebook", s["title"], f"{m['slug']}/notebook.html#{s['anchor']}")

    # ---------------------------------------------------------------- write site
    if kit.site.exists():
        shutil.rmtree(kit.site)
    (kit.site / "assets").mkdir(parents=True)
    (kit.site / "assets" / "style.css").write_text(css(kit), encoding="utf-8")
    shutil.copy(SITE_TEMPLATES / "site.js", kit.site / "assets" / "site.js")

    book_glossary = []
    for ch in kit.produced:
        for g in model[ch]["data"].get("glossary") or []:
            book_glossary.append({**g, "chapter": ch, "chapter_title": kit.chapters[ch]["title"],
                                  "href": f"{model[ch]['slug']}/glossary.html#term-{C.slugify(g['term'])}"})
    book_glossary.sort(key=lambda g: C.plain(g["term"]).lower())

    common = {"book": kit.book, "katex": KATEX, "obj_url": kit.obj_url, "objs": objs,
              "has_glossary": bool(book_glossary), "page_list": C.PAGES, "quiz_formats": C.QUIZ_FORMATS}

    def write(rel: str, template: str, **ctx):
        depth = rel.count("/")
        out = kit.site / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        html_ = env.get_template(template).render(root="../" * depth, **common, **ctx)
        out.write_text(html_, encoding="utf-8")

    chapters_view = []
    for ch in kit.order:
        meta = kit.meta[ch]
        m = model.get(ch)
        chapters_view.append({"meta": meta, "produced": m is not None, "slug": kit.slug(ch),
                              "goal": (m["data"].get("goal") if m else None) or meta.get("goal"),
                              "counts": m["counts"] if m else None, "pages": m["pages"] if m else None})
    write("index.html", "home.html", page="home", chapters=chapters_view, svg=dependency_svg(kit),
          variants=kit.book.get("variants") or [], syllabi=kit.book.get("syllabi") or [],
          syllabus_names={s["id"]: s for s in kit.book.get("syllabi") or []})
    if book_glossary:
        write("glossary.html", "book_glossary.html", page="glossary", entries=book_glossary)

    for idx, ch in enumerate(kit.produced):
        m = model[ch]
        d = m["data"]
        slug = m["slug"]
        prev_ch = kit.produced[idx - 1] if idx > 0 else None
        next_ch = kit.produced[idx + 1] if idx + 1 < len(kit.produced) else None
        ctx = {"ch": ch, "chapter": d, "meta": kit.meta[ch], "pages": m["pages"],
               "prev": {"id": prev_ch, "slug": kit.slug(prev_ch), "title": kit.chapters[prev_ch]["title"]} if prev_ch else None,
               "next": {"id": next_ch, "slug": kit.slug(next_ch), "title": kit.chapters[next_ch]["title"]} if next_ch else None}
        grouped = {}
        for o in d.get("objectives", []):
            g = defaultdict(list)
            for b in backlinks.get(o["id"], []):
                g[b["kind"]].append(b)
            grouped[o["id"]] = dict(g)
        write(f"{slug}/index.html", "chapter.html", page="objectives", backlinks=grouped,
              syllabus_names={s["id"]: s for s in kit.book.get("syllabi") or []}, **ctx)
        if m["pages"]["map"]:
            write(f"{slug}/map.html", "map.html", page="map", **ctx)
        if m["pages"]["quiz"]:
            quiz = d["quiz"]
            by_level = [(lv, [q for q in quiz if q.get("level") == lv]) for lv in C.QUIZ_LEVELS]
            write(f"{slug}/quiz.html", "quiz.html", page="quiz", levels=[x for x in by_level if x[1]], **ctx)
        if m["pages"]["glossary"]:
            entries = sorted(d["glossary"], key=lambda g: C.plain(g["term"]).lower())
            write(f"{slug}/glossary.html", "glossary.html", page="glossary", entries=entries, **ctx)
        if m["pages"]["readings"]:
            bibf = d["_files"]["bib"]
            bib = parse_bib(bibf.read_text(encoding="utf-8")) if bibf.is_file() else {}
            entries = [{**r, "bibtex": bib.get(r["key"]) or bib_for(r)} for r in d["readings"]]
            (kit.site / slug).mkdir(parents=True, exist_ok=True)
            (kit.site / slug / "readings.bib").write_text("\n\n".join(e["bibtex"] for e in entries) + "\n",
                                                          encoding="utf-8")
            write(f"{slug}/readings.html", "readings.html", page="readings", entries=entries, **ctx)
        if m["pages"]["videos"]:
            write(f"{slug}/videos.html", "videos.html", page="videos", videos=d["videos"], **ctx)
        if m["pages"]["notebook"]:
            import nbformat
            (kit.site / slug).mkdir(parents=True, exist_ok=True)
            nbformat.write(m["nb_executed"], kit.site / slug / "notebook.ipynb")
            write(f"{slug}/notebook.html", "notebook.html", page="notebook", nb_html=m["nb_html"],
                  sections=m["nb_sections"], **ctx)
        if m["pages"]["cards"]:
            media = d["_files"]["media"]
            if media.is_dir():
                shutil.copytree(media, kit.site / slug / "media")
            shutil.copy(d["_files"]["cards"], kit.site / slug / "cards.tsv")
            cards = site_cards(m["cards"], objs)
            rank = {t: i for i, t in enumerate(C.CARD_TYPES)}
            types = sorted({c["type"] for c in cards}, key=lambda t: (rank.get(t, 99), t))
            write(f"{slug}/cards.html", "cards.html", page="cards", cards=cards, types=types, **ctx)

    if vendor:
        vendor_tools(kit.dir)
    return {ch: model[ch]["counts"] for ch in kit.produced}


def vendor_tools(book_dir: Path):
    """Copy the build tools into BOOK_DIR/_tools and write a BOOK_DIR/build_site.py wrapper."""
    here = Path(__file__).resolve().parent
    tools = book_dir / "_tools"
    if here.is_relative_to(book_dir.resolve()):
        return  # running from a vendored copy already
    if tools.exists():
        shutil.rmtree(tools)
    (tools / "scripts").mkdir(parents=True)
    for f in ["sk_common.py", "build_site.py", "build_deck.py", "validate.py", "check_site.py"]:
        if (here / f).is_file():
            shutil.copy(here / f, tools / "scripts" / f)
    shutil.copytree(C.TEMPLATES, tools / "templates")
    req = here.parent / "requirements.txt"
    if req.is_file():
        shutil.copy(req, tools / "requirements.txt")
    (book_dir / "build_site.py").write_text(
        '#!/usr/bin/env python3\n'
        '"""Rebuild this study kit: data/ -> site/ (and deck.apkg with --deck). '
        'Requirements: pip install -r _tools/requirements.txt"""\n'
        'import subprocess, sys\nfrom pathlib import Path\n\n'
        'here = Path(__file__).resolve().parent\nscripts = here / "_tools" / "scripts"\n'
        'args = [a for a in sys.argv[1:] if a != "--deck"]\n'
        'rc = subprocess.call([sys.executable, str(scripts / "validate.py"), str(here)])\n'
        'rc = rc or subprocess.call([sys.executable, str(scripts / "build_site.py"), str(here), *args])\n'
        'if not rc and "--deck" in sys.argv:\n'
        '    rc = subprocess.call([sys.executable, str(scripts / "build_deck.py"), str(here)])\n'
        'sys.exit(rc)\n', encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book", type=Path)
    ap.add_argument("--no-execute", action="store_true", help="render notebooks with their stored outputs")
    ap.add_argument("--no-vendor", action="store_true", help="do not copy the tools into BOOK_DIR/_tools")
    a = ap.parse_args(argv)
    counts = build(a.book, execute=not a.no_execute, vendor=not a.no_vendor)
    print("chapter  obj core/sec  quiz  cards  gloss  read  videos  nb")
    for ch, c in counts.items():
        print(f"{ch:8} {c['core']:>4}/{c['secondary']:<7} {c['quiz']:>4}  {c['cards']:>5}  {c['glossary']:>5}  "
              f"{c['readings']:>4}  {c['videos']:>6}  {'yes' if c['notebook'] else '-':>2}")
    print(f"site → {(a.book / 'site').resolve()}")


if __name__ == "__main__":
    main()
