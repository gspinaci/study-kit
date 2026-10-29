"""Tests for the study-kit scripts. Negative tests break one rule on a copy of the example and
check that the validator (or the site checker) reports it."""
import json
import re
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/study-kit/skills/study-kit"
EXAMPLE = ROOT / "examples/study-kit/tiny-linear-models"
SOURCE = sorted((ROOT / "examples/source/tiny-linear-models").glob("*.md"))
sys.path.insert(0, str(SKILL / "scripts"))

import build_deck  # noqa: E402
import build_site  # noqa: E402
import check_site  # noqa: E402
import sk_common  # noqa: E402
import validate  # noqa: E402


@pytest.fixture
def book(tmp_path):
    dst = tmp_path / "tiny-linear-models"
    shutil.copytree(EXAMPLE / "data", dst / "data")
    return dst


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    dst = tmp_path_factory.mktemp("built") / "tiny-linear-models"
    shutil.copytree(EXAMPLE / "data", dst / "data")
    build_site.build(dst, execute=True, vendor=True)
    return dst


def has(rep, pattern, severity="error"):
    return any(re.search(pattern, i.message) for i in rep.issues if i.severity == severity)


def edit_json(book, name, fn):
    p = book / "data" / name
    d = json.loads(p.read_text(encoding="utf-8"))
    fn(d)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def edit_text(path, old, new):
    t = path.read_text(encoding="utf-8")
    assert old in t, f"{old!r} not in {path.name}"
    path.write_text(t.replace(old, new, 1), encoding="utf-8")


def drop_cards(book, ch, ids):
    p = book / "data" / f"{ch}.cards.tsv"
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join(l for l in lines if l.split("\t", 1)[0] not in ids) + "\n", encoding="utf-8")


def quiz(d, qid):
    return next(q for q in d["quiz"] if q["id"] == qid)


# ============================================================ the example is clean

def test_example_validates():
    rep = validate.validate(EXAMPLE, sources=[str(s) for s in SOURCE])
    assert rep.issues == [], rep.issues
    assert rep.stats["ch01"]["cards"] == 14 and rep.stats["ch02"]["readings"] == 2


def test_single_chapter_mode():
    assert not validate.validate(EXAMPLE, only="ch02").errors


# ============================================================ book.json

def test_variant_needs_source(book):
    edit_json(book, "book.json", lambda d: d["variants"][0].pop("source"))
    assert has(validate.validate(book), r"variants\[0\]: missing 'source'")


def test_variants_key_required(book):
    edit_json(book, "book.json", lambda d: d.pop("variants"))
    assert has(validate.validate(book), r"'variants' missing")


def test_requires_must_be_earlier(book):
    edit_json(book, "book.json", lambda d: d["chapters"][0].__setitem__("requires", ["ch02"]))
    assert has(validate.validate(book), r"requires 'ch02', which is not an earlier chapter")


def test_slug_must_match(book):
    edit_json(book, "ch02.json", lambda d: d.__setitem__("slug", "ch02-other"))
    assert has(validate.validate(book), r"differs from book.json")


# ============================================================ modularity

def test_outputs_are_optional(book):
    for f in ["ch01.cards.tsv", "ch01.ipynb", "ch02.cards.tsv", "ch02.bib"]:
        (book / "data" / f).unlink()

    def strip(d):
        for k in ("quiz", "glossary", "readings", "videos"):
            d.pop(k, None)
    edit_json(book, "ch01.json", strip)
    edit_json(book, "ch02.json", strip)
    assert not validate.validate(book).errors
    build_site.build(book, execute=False, vendor=False)
    pages = sorted(p.name for p in (book / "site/ch01-least-squares").glob("*.html"))
    assert pages == ["index.html", "map.html"]
    issues, _ = check_site.static_checks(book / "site")
    assert not [i for i in issues if i["severity"] == "error"], issues


def test_files_without_chapter_json(book):
    (book / "data/ch02.json").unlink()
    assert has(validate.validate(book), r"missing, but other files exist")


def test_objective_must_be_served(book):
    def add(d):
        d["objectives"].append({"id": "ch02-o9", "level": "secondary", "source": "§2.4",
                                "text": "After this chapter you can do something nothing tests."})
    edit_json(book, "ch02.json", add)
    rep = validate.validate(book)
    assert has(rep, r"ch02-o9 is not served by any produced item")


# ============================================================ objectives

def test_core_objective_needs_reason(book):
    edit_json(book, "ch01.json", lambda d: d["objectives"][2].__setitem__("why_core", None))
    assert has(validate.validate(book), r"ch01-o3: core objective needs 'why_core'")


def test_unknown_objective_reference(book):
    edit_json(book, "ch01.json", lambda d: d["glossary"][0].__setitem__("objectives", ["ch01-o99"]))
    assert has(validate.validate(book), r"unknown objective 'ch01-o99'")


# ============================================================ cards

def test_core_objective_needs_three_cards(book):
    drop_cards(book, "ch01", {"ch01-c010", "ch01-c013"})
    assert has(validate.validate(book), r"ch01-o3 \(core\) has 2 cards")


def test_core_objective_needs_why_or_apply(book):
    drop_cards(book, "ch01", {"ch01-c011", "ch01-c012"})
    assert has(validate.validate(book), r"ch01-o3 \(core\) needs at least one 'why' or 'apply'")


def test_definition_ratio(book):
    p = book / "data/ch02.cards.tsv"
    t = p.read_text(encoding="utf-8")
    for x in ("\tapply\t", "\twhy\t", "\tmistake\t"):
        t = t.replace(x, "\tdefinition\t")
    p.write_text(t, encoding="utf-8")
    assert has(validate.validate(book), r"definition\+cloze cards are .* max 25%")


def test_level_must_match_objective(book):
    edit_text(book / "data/ch01.cards.tsv", "ch01-c014\tch01-o4\tsecondary", "ch01-c014\tch01-o4\tcore")
    assert has(validate.validate(book), r"differs from the objective's")


def test_diagram_needs_media(book):
    shutil.rmtree(book / "data/media")
    assert has(validate.validate(book), r"media file data/media/ch01/projection.png not found")


def test_raw_html_in_cards(book):
    edit_text(book / "data/ch01.cards.tsv", "One sample:", "<b>One</b> sample:")
    assert has(validate.validate(book), r"raw HTML in 'back'")


def test_connection_names_other_chapter(book):
    p = book / "data/ch02.cards.tsv"
    p.write_text(p.read_text(encoding="utf-8").replace("ch01", "chapter one"), encoding="utf-8")
    assert has(validate.validate(book), r"connection card must name another chapter")


# ============================================================ quiz

def test_quiz_every_core_objective(book):
    def f(d):
        for q in d["quiz"]:
            q["objectives"] = [o for o in q["objectives"] if o != "ch01-o3"] or ["ch01-o1"]
    edit_json(book, "ch01.json", f)
    assert has(validate.validate(book), r"ch01-o3 \(core\) has no quiz question")


def test_mc_every_option_needs_why(book):
    edit_json(book, "ch01.json", lambda d: quiz(d, "Q2")["options"][2].pop("why"))
    assert has(validate.validate(book), r"Q2: option C needs a 'why'")


def test_mc_exactly_one_correct(book):
    edit_json(book, "ch01.json", lambda d: quiz(d, "Q2")["options"][0].__setitem__("correct", True))
    assert has(validate.validate(book), r"Q2: exactly one option must be correct")


def test_tf_needs_answer(book):
    edit_json(book, "ch01.json", lambda d: quiz(d, "Q5").pop("answer"))
    assert has(validate.validate(book), r"Q5: true/false question needs 'answer'")


def test_cumulative_warning(book):
    def f(d):
        for q in d["quiz"]:
            q["objectives"] = [o for o in q["objectives"] if o.startswith("ch02")]
    edit_json(book, "ch02.json", f)
    assert has(validate.validate(book), r"no cumulative question", severity="warning")


# ============================================================ readings / videos

def test_reading_needs_adds(book):
    edit_json(book, "ch02.json", lambda d: d["readings"][0].__setitem__("adds", "A classic."))
    assert has(validate.validate(book), r"hoerl1970ridge: 'adds' must say")


def test_reading_needs_bib_entry(book):
    edit_text(book / "data/ch02.bib", "@article{tibshirani1996lasso", "@article{lasso96")
    assert has(validate.validate(book), r"tibshirani1996lasso: not found in data/ch02.bib")


def test_video_needs_https(book):
    edit_json(book, "ch02.json", lambda d: d["videos"][0].__setitem__("url", "http://example.org/v"))
    assert has(validate.validate(book), r"url must be https")


# ============================================================ lints

def test_raw_html_in_json(book):
    edit_json(book, "ch01.json", lambda d: d.__setitem__("goal", d["goal"] + " <script>x</script>"))
    assert has(validate.validate(book), r"goal: raw HTML is not allowed")


def test_math_is_not_html(book):
    edit_json(book, "ch01.json", lambda d: d.__setitem__("goal", d["goal"] + r" Note \(a < b\) and \(c > d\)."))
    assert not has(validate.validate(book), r"raw HTML")


def test_schedule_language(book):
    edit_json(book, "ch01.json", lambda d: d.__setitem__("goal", d["goal"] + " Spend 2 hours per day on it."))
    assert has(validate.validate(book), r"schedule/timing language", severity="warning")


def test_verbatim_copy(book):
    src = (ROOT / "examples/source/tiny-linear-models/01-least-squares.md").read_text(encoding="utf-8")
    para = re.search(r"## 1.4 Geometry of the fit\n\n(.+?)\n", src).group(1)
    edit_json(book, "ch01.json", lambda d: d["glossary"][0].__setitem__("definition", para))
    assert has(validate.validate(book, sources=[str(s) for s in SOURCE]), r"copied from the source")


# ============================================================ site

def test_site_pages(built):
    site = built / "site"
    ch1 = sorted(p.name for p in (site / "ch01-least-squares").glob("*.html"))
    assert ch1 == ["cards.html", "glossary.html", "index.html", "map.html", "notebook.html", "quiz.html", "videos.html"]
    ch2 = sorted(p.name for p in (site / "ch02-regularization").glob("*.html"))
    assert ch2 == ["cards.html", "index.html", "map.html", "quiz.html", "readings.html", "videos.html"]
    assert (site / "glossary.html").is_file() and (site / "ch02-regularization/readings.bib").is_file()
    assert (site / "ch01-least-squares/notebook.ipynb").is_file()


def test_site_static_checks(built):
    issues, stats = check_site.static_checks(built / "site")
    assert stats["pages"] == 15
    assert not [i for i in issues if i["severity"] == "error"], issues


def test_site_links_and_backlinks(built):
    home = (built / "site/index.html").read_text(encoding="utf-8")
    assert 'href="ch01-least-squares/quiz.html"' in home and "<svg class=\"depgraph\"" in home
    assert "Ordinary least squares only" in home and "No syllabi verified." in home
    idx = (built / "site/ch01-least-squares/index.html").read_text(encoding="utf-8")
    assert 'id="ch01-o3"' in idx
    assert "../ch02-regularization/quiz.html#Q3" in idx  # cumulative question back-links to ch01-o2
    assert "cards.html?objective=ch01-o1" in idx


def test_site_escapes_raw_html(book):
    edit_json(book, "ch01.json", lambda d: d["glossary"][0].__setitem__("definition", "x <img src=y onerror=alert(1)>"))
    build_site.build(book, execute=False, vendor=False)
    g = (book / "site/ch01-least-squares/glossary.html").read_text(encoding="utf-8")
    assert "<img src=y" not in g and "&lt;img src=y" in g


def test_quiz_progressive_enhancement(built):
    q = (built / "site/ch01-least-squares/quiz.html").read_text(encoding="utf-8")
    assert q.count('<details class="solution">') == 6       # every solution readable without JS
    assert 'data-correct="true"' in q and "print-solutions" in q
    assert "Answer: <strong>False</strong>" in q


def test_notebook_rendered_and_solutions_collapsed(built):
    nb = (built / "site/ch01-least-squares/notebook.html").read_text(encoding="utf-8")
    assert '<details class="nb-cell nb-solution">' in nb
    assert 'id="nb-' in nb and "((50, 4), (50,))" in nb      # executed output present


def test_vendored_tools_rebuild(built):
    assert (built / "build_site.py").is_file() and (built / "_tools/scripts/build_site.py").is_file()
    import subprocess
    r = subprocess.run([sys.executable, str(built / "build_site.py"), "--no-execute"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_broken_link_is_caught(built, tmp_path):
    site = tmp_path / "site"
    shutil.copytree(built / "site", site)
    edit_text(site / "ch01-least-squares/map.html", 'href="index.html"', 'href="nowhere.html"')
    issues, _ = check_site.static_checks(site)
    assert any("broken href" in i["message"] for i in issues)


def test_missing_anchor_is_caught(built, tmp_path):
    site = tmp_path / "site"
    shutil.copytree(built / "site", site)
    edit_text(site / "ch01-least-squares/index.html", 'id="ch01-o3"', 'id="ch01-oX"')
    issues, _ = check_site.static_checks(site)
    assert any("missing anchor #ch01-o3" in i["message"] for i in issues)


def test_inline_renderer():
    out = sk_common.inline(r"**a** *b* `c<d` [e](https://x.org) \(x < y\) <b>z</b> [bad](javascript:alert(1))")
    assert "<strong>a</strong>" in out and "<em>b</em>" in out and "<code>c&lt;d</code>" in out
    assert '<a href="https://x.org" rel="noopener">e</a>' in out
    assert r"\(x &lt; y\)" in out and "&lt;b&gt;z&lt;/b&gt;" in out
    assert "javascript:" not in out


# ============================================================ deck

def test_build_deck(book, tmp_path):
    out = tmp_path / "deck.apkg"
    counts = build_deck.build(book, out)
    assert sum(counts.values()) == 27 and len(counts) == 2
    with zipfile.ZipFile(out) as z:
        (tmp_path / "c.anki2").write_bytes(z.read("collection.anki2"))
    con = sqlite3.connect(tmp_path / "c.anki2")
    assert con.execute("select count(*) from notes").fetchone()[0] == 27
    flds = " ".join(r[0] for r in con.execute("select flds from notes"))
    assert 'class="sk-code' in flds and "tiny-linear-models_ch01_projection.png" in flds
    css = con.execute("select models from col").fetchone()[0]
    assert sk_common.TOKENS["light"]["accent"] in css   # deck uses the site's tokens
    g1 = {r[0] for r in con.execute("select guid from notes")}
    build_deck.build(book, tmp_path / "deck2.apkg")
    with zipfile.ZipFile(tmp_path / "deck2.apkg") as z:
        (tmp_path / "c2.anki2").write_bytes(z.read("collection.anki2"))
    assert g1 == {r[0] for r in sqlite3.connect(tmp_path / "c2.anki2").execute("select guid from notes")}


def test_card_html_keeps_mathjax_commands():
    out = sk_common.card_html(r"\(\nabla L \neq 0\)<br>```python<br>x = 1<br>```<br>after")
    assert r"\nabla" in out and r"\neq" in out and 'class="sk-code' in out and "after" in out


# ============================================================ skills metadata

@pytest.mark.parametrize("skill_md", sorted((ROOT / "plugins/study-kit/skills").glob("*/SKILL.md")))
def test_skill_frontmatter(skill_md):
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "missing frontmatter"
    fm = {k: v.strip().strip('"') for k, v in re.findall(r"^(\w[\w-]*):\s*(.+)$", m.group(1), re.MULTILINE)}
    assert fm["name"] == skill_md.parent.name
    assert re.fullmatch(r"[a-z0-9-]{1,64}", fm["name"])
    assert 0 < len(fm["description"]) <= 1024 and "<" not in fm["description"]


def test_skill_references_exist():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for rel in re.findall(r"`((?:scripts|references)/[\w./-]+\.(?:py|md))", text):
        assert (SKILL / rel).is_file(), rel
