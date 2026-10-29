#!/usr/bin/env python3
"""Check a built study-kit site: links, anchors, markup, leaked syntax — and, optionally, how it looks.

Usage:
    check_site.py SITE_DIR [--screenshots OUT_DIR] [--pages all|key] [--katex-dir DIR] [--json]

Static checks (always):
  - every relative href/src resolves to a file inside SITE_DIR, and every #anchor exists
  - tags are balanced and every page has exactly one <h1>, a <main>, a <title> and <html lang>
  - no unrendered template syntax ({{ }}, {% %}) or Markdown (**, ](, ```) in visible text
  - no duplicate ids on a page

With --screenshots (needs Playwright + Chromium):
  - renders the home page and every chapter index + quiz page (or all pages with --pages all)
    at 1280px and 390px, light and dark, and saves PNGs to OUT_DIR
  - reports console errors, failed local requests and horizontal page overflow
  - --katex-dir serves KaTeX from a local copy (e.g. node_modules/katex) when the CDN is not reachable

Exit code 1 if any error is found.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source",
        "track", "wbr"}
# SVG/MathML-ish self-closing elements we emit
SELF_CLOSING_OK = {"path", "rect", "circle", "line", "polyline", "polygon", "ellipse", "stop", "use"}
LEAK_RE = re.compile(r"\{\{|\}\}|\{%|%\}|\*\*\S|\]\(|```")
MATH_RE = re.compile(r"\\\(.+?\\\)|\\\[.+?\\\]", re.DOTALL)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.errors = [], [], []
        self.stack = []
        self.h1 = 0
        self.has_main = self.has_title = False
        self.lang = None
        self.skip_text = 0
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "main":
            self.has_main = True
        if tag == "title":
            self.has_title = True
        if "id" in a and a["id"]:
            self.ids.append(a["id"])
        for k in ("href", "src"):
            if a.get(k):
                self.links.append((tag, k, a[k], self.getpos()[0]))
        if tag in ("script", "style", "pre", "code", "svg"):
            self.skip_text += 1
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a and a["id"]:
            self.ids.append(a["id"])
        for k in ("href", "src"):
            if a.get(k):
                self.links.append((tag, k, a[k], self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag in ("script", "style", "pre", "code", "svg"):
            self.skip_text = max(0, self.skip_text - 1)
        if not self.stack:
            self.errors.append(f"line {self.getpos()[0]}: stray </{tag}>")
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        # tolerate implicitly closed <p>/<li>/<dt>/<dd>/<option>
        names = [t for t, _ in self.stack]
        if tag in names:
            while self.stack and self.stack[-1][0] != tag:
                t, ln = self.stack.pop()
                if t not in ("p", "li", "dt", "dd", "option", "tr", "td", "th"):
                    self.errors.append(f"line {ln}: <{t}> not closed before </{tag}>")
            self.stack.pop()
        else:
            self.errors.append(f"line {self.getpos()[0]}: </{tag}> without matching start tag")

    def handle_data(self, data):
        if not self.skip_text:
            self.text.append(data)


def static_checks(site: Path) -> tuple[list[dict], dict]:
    issues = []
    pages = {}
    for p in sorted(site.rglob("*.html")):
        parser = Page()
        parser.feed(p.read_text(encoding="utf-8"))
        parser.close()
        pages[p.resolve()] = parser
    for p, pg in pages.items():
        rel = str(p.relative_to(site.resolve()))
        err = lambda m: issues.append({"severity": "error", "file": rel, "message": m})  # noqa: E731
        for e in pg.errors:
            err(e)
        for t, ln in pg.stack:
            if t not in ("p", "li", "html", "body", "dt", "dd") and t not in SELF_CLOSING_OK:
                err(f"line {ln}: <{t}> never closed")
        if pg.h1 != 1:
            err(f"{pg.h1} <h1> elements (expected exactly 1)")
        if not pg.has_main:
            err("no <main>")
        if not pg.has_title:
            err("no <title>")
        if not pg.lang:
            err("<html> has no lang attribute")
        dup = {i for i in pg.ids if pg.ids.count(i) > 1}
        for i in sorted(dup):
            err(f"duplicate id '{i}'")
        text = MATH_RE.sub(" ", " ".join(pg.text))  # TeX legitimately contains }} and **
        for m in LEAK_RE.finditer(text):
            ctx = text[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")
            err(f"unrendered syntax '{m.group(0)}' in text: …{ctx}…")
        for tag, attr, url, ln in pg.links:
            u = urlsplit(url)
            if u.scheme in ("http", "https", "mailto", "data", "javascript") or url.startswith("//"):
                if u.scheme == "javascript":
                    err(f"line {ln}: javascript: URL")
                continue
            target = p if not u.path else (p.parent / unquote(u.path)).resolve()
            if not str(target).startswith(str(site.resolve())):
                err(f"line {ln}: link leaves the site: {url}")
                continue
            if not target.exists():
                err(f"line {ln}: broken {attr} → {url}")
                continue
            if u.fragment and target.suffix == ".html":
                tp = pages.get(target)
                if tp is not None and unquote(u.fragment) not in tp.ids:
                    err(f"line {ln}: missing anchor #{u.fragment} in {target.relative_to(site.resolve())}")
    return issues, {"pages": len(pages)}


def visual_checks(site: Path, out: Path, which: str, katex_dir: Path | None) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [{"severity": "warning", "file": "-", "message": "playwright not installed: visual checks skipped"}]
    out.mkdir(parents=True, exist_ok=True)
    issues = []
    targets = [site / "index.html"]
    for d in sorted(x for x in site.iterdir() if x.is_dir() and re.match(r"ch\d{2}-", x.name)):
        if which == "all":
            targets += sorted(d.glob("*.html"))
        else:
            targets += [d / "index.html"] + ([d / "quiz.html"] if (d / "quiz.html").exists() else [])
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for theme in ("light", "dark"):
            for width in (1280, 390):
                ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=theme)
                ctx.add_init_script(f"try {{ localStorage.setItem('sk-theme', '{theme}'); }} catch (e) {{}}")
                if katex_dir:
                    base = katex_dir.resolve()

                    def route(r):  # one parameter only: Playwright passes (route, request) to two
                        path = urlsplit(r.request.url).path.split("/dist/", 1)[-1]
                        f = base / "dist" / path
                        if f.is_file():
                            ctype = "text/css" if f.suffix == ".css" else (
                                "application/javascript" if f.suffix == ".js" else
                                "font/woff2" if f.suffix == ".woff2" else "application/octet-stream")
                            r.fulfill(path=str(f), headers={"content-type": ctype, "access-control-allow-origin": "*"})
                        else:
                            r.abort()
                    ctx.route(re.compile(r"https://cdn\.jsdelivr\.net/npm/katex@[^/]+/.*"), route)
                for t in targets:
                    rel = str(t.relative_to(site))
                    page = ctx.new_page()
                    logs = []
                    page.on("console", lambda m, logs=logs: logs.append(m) if m.type == "error" else None)
                    page.on("pageerror", lambda e, logs=logs: logs.append(e))
                    failed = []
                    page.on("requestfailed", lambda r, failed=failed: failed.append(r.url))
                    page.goto(t.as_uri())
                    page.wait_for_load_state("load")
                    page.wait_for_timeout(250)
                    name = rel.replace("/", "__").replace(".html", "")
                    page.screenshot(path=str(out / f"{name}--{width}-{theme}.png"), full_page=True)
                    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    if overflow > 1:
                        issues.append({"severity": "error", "file": rel,
                                       "message": f"horizontal page overflow of {overflow}px at {width}px ({theme})"})
                    for u in failed:
                        sev = "warning" if u.startswith("https://cdn.jsdelivr.net/") else "error"
                        issues.append({"severity": sev, "file": rel, "message": f"request failed: {u}"})
                    for m in logs:
                        text = getattr(m, "text", None) or str(m)
                        if "cdn.jsdelivr.net" in text or "Failed to load resource" in text and failed:
                            continue
                        issues.append({"severity": "error", "file": rel, "message": f"console error ({width}px {theme}): {text}"})
                    page.close()
                ctx.close()
        browser.close()
    # deduplicate identical messages across themes/widths
    seen, uniq = set(), []
    for i in issues:
        k = (i["severity"], i["file"], re.sub(r" \(\d+px \w+\)| at \d+px \(\w+\)", "", i["message"]))
        if k not in seen:
            seen.add(k)
            uniq.append(i)
    return uniq


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site", type=Path)
    ap.add_argument("--screenshots", type=Path, metavar="OUT_DIR")
    ap.add_argument("--pages", choices=["all", "key"], default="key")
    ap.add_argument("--katex-dir", type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not (a.site / "index.html").is_file():
        print(f"{a.site}/index.html not found — run build_site.py first", file=sys.stderr)
        return 2
    issues, stats = static_checks(a.site)
    if a.screenshots:
        issues += visual_checks(a.site.resolve(), a.screenshots, a.pages, a.katex_dir)
    errors = [i for i in issues if i["severity"] == "error"]
    if a.json:
        print(json.dumps({"errors": len(errors), "issues": issues, **stats}, indent=2))
    else:
        for i in issues:
            print(f"{'ERROR' if i['severity'] == 'error' else 'warn '}  {i['file']}: {i['message']}")
        print(f"{stats['pages']} page(s) checked, {len(errors)} error(s), {len(issues) - len(errors)} warning(s)")
        if a.screenshots:
            print(f"screenshots → {a.screenshots}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
