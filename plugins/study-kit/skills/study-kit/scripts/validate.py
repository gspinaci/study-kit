#!/usr/bin/env python3
"""Validate a study kit's data/ against the study-kit rules (run before build_site.py).

Usage:
    validate.py BOOK_DIR [--chapter chNN] [--source FILE ...] [--json] [--strict]

BOOK_DIR contains data/book.json and data/chNN.json (+ chNN.cards.tsv, chNN.ipynb, chNN.bib).
Only the outputs that exist are checked: every output is optional.
Exit code: 0 if no errors (and no warnings with --strict), 1 otherwise, 2 on usage problems.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sk_common as C  # noqa: E402

SCHEDULE_RE = re.compile(
    r"\b(\d+\s*(?:-\s*\d+\s*)?(?:minutes?|mins?|hours?|hrs?)\s+(?:a|per|each|every)\b"
    r"|(?:week|day|month)\s+\d+\b"
    r"|per\s+(?:day|week)\b|every\s+(?:day|morning|evening|week)\b"
    r"|study\s+for\b|spend\s+(?:about\s+)?\d+|\bschedule\b|\bdeadline\b|\btimeline\b)",
    re.IGNORECASE)
RAW_HTML_RE = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")


@dataclass
class Issue:
    severity: str
    file: str
    message: str


@dataclass
class Report:
    issues: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def error(self, f, msg):
        self.issues.append(Issue("error", str(f), msg))

    def warn(self, f, msg):
        self.issues.append(Issue("warning", str(f), msg))

    @property
    def errors(self):
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self):
        return [i for i in self.issues if i.severity == "warning"]


def words(text: str):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def texts(obj, path=""):
    """Yield (json-path, string) for every string in a JSON structure."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if not k.startswith("_"):
                yield from texts(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from texts(v, f"{path}[{i}]")


def need(rep, f, obj, keys, where):
    ok = True
    for k in keys:
        v = obj.get(k) if isinstance(obj, dict) else None
        if v is None or (isinstance(v, (str, list)) and not v):
            rep.error(f, f"{where}: missing '{k}'")
            ok = False
    return ok


# ============================================================================= book.json

def check_book(book: dict, rep: Report) -> dict:
    f = "data/book.json"
    need(rep, f, book, ["title", "slug", "chapters"], "book")
    if not isinstance(book.get("source"), dict) or not book["source"].get("citation"):
        rep.error(f, "book: 'source.citation' is required (shown in every page footer)")
    if "variants" not in book:
        rep.error(f, "book: 'variants' missing (use [] when the book and syllabi state none)")
    if "syllabi" not in book:
        rep.error(f, "book: 'syllabi' missing (use [] when none were verified)")
    meta, seen_slug = {}, set()
    for i, c in enumerate(book.get("chapters") or []):
        w = f"chapters[{i}]"
        if not need(rep, f, c, ["id", "slug", "title"], w):
            continue
        ch = c["id"]
        if not C.CH_ID_RE.match(ch):
            rep.error(f, f"{w}: id '{ch}' must be chNN")
        if ch in meta:
            rep.error(f, f"{w}: duplicate chapter id {ch}")
        m = C.SLUG_RE.match(c["slug"])
        if not m or m.group(1) != ch:
            rep.error(f, f"{ch}: slug '{c['slug']}' must be '{ch}-<lowercase-slug>'")
        if c["slug"] in seen_slug:
            rep.error(f, f"{ch}: duplicate slug")
        seen_slug.add(c["slug"])
        if not c.get("scope"):
            rep.warn(f, f"{ch}: no 'scope'")
        for r in c.get("requires") or []:
            if r not in meta:
                rep.error(f, f"{ch}: requires '{r}', which is not an earlier chapter")
        meta[ch] = c
    order = list(meta)
    for ch, c in meta.items():
        for fl in c.get("forward_links") or []:
            t = fl.get("chapter") if isinstance(fl, dict) else None
            if t not in meta:
                rep.error(f, f"{ch}: forward link to unknown chapter '{t}'")
            elif order.index(t) <= order.index(ch):
                rep.error(f, f"{ch}: forward link to {t}, which is not a later chapter")
    syl_ids = set()
    for i, s in enumerate(book.get("syllabi") or []):
        w = f"syllabi[{i}]"
        if need(rep, f, s, ["id", "course", "institution", "url"], w):
            syl_ids.add(s["id"])
            if not re.match(r"^https?://", s["url"]):
                rep.error(f, f"{w}: url must be http(s)")
        for ch in s.get("chapters") or []:
            if ch not in meta:
                rep.error(f, f"{w}: unknown chapter {ch}")
    for ch, c in meta.items():
        for s in c.get("syllabi") or []:
            if s not in syl_ids:
                rep.error(f, f"{ch}: syllabus '{s}' not in 'syllabi'")
    for i, v in enumerate(book.get("variants") or []):
        w = f"variants[{i}]"
        need(rep, f, v, ["id", "title", "chapters", "source"], w)
        for ch in v.get("chapters") or []:
            if ch not in meta:
                rep.error(f, f"{w}: unknown chapter {ch}")
    return meta


# ============================================================================= chapter

def check_chapter(ch: str, d: dict, meta: dict, book: dict, rep: Report) -> dict:
    f = f"data/{ch}.json"
    if d.get("id") != ch:
        rep.error(f, f"id must be '{ch}'")
    if meta and d.get("slug") != meta.get("slug"):
        rep.error(f, f"slug '{d.get('slug')}' differs from book.json ('{meta.get('slug')}')")
    need(rep, f, d, ["title", "goal", "objectives"], ch)
    if d.get("goal") and len(words(d["goal"])) < 15:
        rep.warn(f, "goal is shorter than 2–3 sentences")
    objs = {}
    syl = {s.get("id") for s in book.get("syllabi") or []}
    for i, o in enumerate(d.get("objectives") or []):
        w = f"objectives[{i}]"
        if not need(rep, f, o, ["id", "level", "text", "source"], w):
            if o.get("id"):
                objs[o["id"]] = o
            continue
        oid = o["id"]
        if not re.fullmatch(rf"{ch}-o\d+", oid):
            rep.error(f, f"{oid}: id must be {ch}-oN")
        if oid in objs:
            rep.error(f, f"{oid}: duplicate objective id")
        if o["level"] not in C.LEVELS:
            rep.error(f, f"{oid}: level must be core or secondary")
        if not o["text"].lower().startswith("after this chapter you can"):
            rep.warn(f, f"{oid}: text should start with 'After this chapter you can …'")
        if o["level"] == "core" and not (o.get("why_core") and len(words(o["why_core"])) >= 3):
            rep.error(f, f"{oid}: core objective needs 'why_core'")
        so = o.get("syllabus_outcome")
        if isinstance(so, dict) and so.get("syllabus") not in syl:
            rep.error(f, f"{oid}: syllabus_outcome references unknown syllabus '{so.get('syllabus')}'")
        objs[oid] = o
    if not objs:
        rep.error(f, "no objectives")
    return objs


def check_refs(f, where, ids, all_objs, rep, required=True):
    if not ids:
        if required:
            rep.error(f, f"{where}: no objective ids")
        return []
    for i in ids:
        if i not in all_objs:
            rep.error(f, f"{where}: unknown objective '{i}'")
    return ids


def check_map(ch, d, objs, all_objs, rep):
    f = f"data/{ch}.json"
    used, secs = set(), set()
    for i, s in enumerate(d.get("map") or []):
        w = f"map[{i}]"
        need(rep, f, s, ["section", "title"], w)
        if s.get("section") in secs:
            rep.error(f, f"{w}: duplicate section {s.get('section')}")
        secs.add(s.get("section"))
        used |= set(check_refs(f, w, s.get("objectives"), all_objs, rep))
    if d.get("map"):
        for oid in objs:
            if oid not in used:
                rep.warn(f, f"{oid} does not appear in the map")


def check_quiz(ch, d, objs, all_objs, earlier_exist, rep):
    f = f"data/{ch}.json"
    quiz = d.get("quiz") or []
    ids, covered, foreign = set(), set(), False
    for i, q in enumerate(quiz):
        w = f"quiz[{i}]"
        qid = q.get("id", w)
        if not re.fullmatch(r"Q\d+", str(q.get("id", ""))):
            rep.error(f, f"{w}: id must be QN")
        if qid in ids:
            rep.error(f, f"{qid}: duplicate question id")
        ids.add(qid)
        need(rep, f, q, ["prompt", "solution", "source"], qid)
        if q.get("level") not in C.QUIZ_LEVELS:
            rep.error(f, f"{qid}: level must be one of {', '.join(C.QUIZ_LEVELS)}")
        fmt = q.get("format")
        if fmt not in C.QUIZ_FORMATS:
            rep.error(f, f"{qid}: format must be one of {', '.join(C.QUIZ_FORMATS)}")
        refs = check_refs(f, qid, q.get("objectives"), all_objs, rep)
        covered |= set(refs)
        foreign |= any(r.split("-")[0] != ch for r in refs)
        if fmt == "mc":
            opts = q.get("options") or []
            if len(opts) < 3:
                rep.error(f, f"{qid}: multiple choice needs ≥3 options")
            if sum(bool(o.get("correct")) for o in opts) != 1:
                rep.error(f, f"{qid}: exactly one option must be correct")
            keys = [o.get("key") for o in opts]
            if len(set(keys)) != len(keys) or not all(keys):
                rep.error(f, f"{qid}: option keys must be unique and non-empty")
            for o in opts:
                if not o.get("text"):
                    rep.error(f, f"{qid}: option {o.get('key')} has no text")
                if not o.get("why") or len(words(o["why"])) < 4:
                    rep.error(f, f"{qid}: option {o.get('key')} needs a 'why' (the mistake it encodes, or why it is right)")
        elif fmt == "tf":
            if not isinstance(q.get("answer"), bool):
                rep.error(f, f"{qid}: true/false question needs 'answer': true|false")
        elif q.get("options"):
            rep.warn(f, f"{qid}: options on a non-mc question are ignored")
        if q.get("solution") and len(words(q["solution"])) < 12:
            rep.warn(f, f"{qid}: solution looks too short to show the reasoning")
    if quiz:
        for oid, o in objs.items():
            if o.get("level") == "core" and oid not in covered:
                rep.error(f, f"{oid} (core) has no quiz question")
        if earlier_exist and not foreign:
            rep.warn(f, "no cumulative question referencing an earlier chapter's objective")
        if len({q.get("format") for q in quiz}) < 2 and len(quiz) >= 4:
            rep.warn(f, "all questions use the same format")
        levels = {q.get("level") for q in quiz}
        if len(quiz) >= 6 and len(levels) < 3:
            rep.warn(f, "questions cover fewer than 3 difficulty levels")
    return len(quiz)


def check_glossary(ch, d, all_objs, rep):
    f = f"data/{ch}.json"
    terms = set()
    for i, g in enumerate(d.get("glossary") or []):
        w = f"glossary[{i}]"
        need(rep, f, g, ["term", "definition"], w)
        t = C.slugify(g.get("term", ""))
        if t in terms:
            rep.error(f, f"{w}: duplicate term '{g.get('term')}'")
        terms.add(t)
        check_refs(f, w, g.get("objectives"), all_objs, rep)
    return len(d.get("glossary") or [])


def check_readings(ch, d, all_objs, files, rep):
    f = f"data/{ch}.json"
    rs = d.get("readings") or []
    if len(rs) > 5:
        rep.error(f, f"{len(rs)} readings, max 5")
    keys = set()
    if files["bib"].is_file():
        keys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", files["bib"].read_text(encoding="utf-8")))
    for i, r in enumerate(rs):
        w = f"readings[{i}]"
        need(rep, f, r, ["key", "citation", "kind", "adds"], w)
        key = r.get("key", w)
        if r.get("kind") not in ("core", "deepening"):
            rep.error(f, f"{key}: kind must be core or deepening")
        if len(words(r.get("adds"))) < 15:
            rep.error(f, f"{key}: 'adds' must say in 2–3 sentences what it adds beyond the book (≥15 words)")
        if not r.get("doi") and not r.get("url"):
            rep.error(f, f"{key}: needs a 'doi' or an official/open-access 'url'")
        if r.get("doi") and not re.match(r"^10\.\d{4,9}/\S+$", r["doi"]):
            rep.error(f, f"{key}: doi '{r['doi']}' is not a bare DOI (10.xxxx/…)")
        if keys and r.get("key") not in keys:
            rep.error(f, f"{key}: not found in data/{ch}.bib")
        check_refs(f, key, r.get("objectives"), all_objs, rep)
    return len(rs)


def check_videos(ch, d, all_objs, map_sections, rep):
    f = f"data/{ch}.json"
    vs = d.get("videos") or []
    if len(vs) > 3:
        rep.warn(f, f"{len(vs)} videos: the skill asks for 1–3 per chapter")
    for i, v in enumerate(vs):
        w = f"videos[{i}]"
        need(rep, f, v, ["title", "by", "url", "sections"], w)
        if v.get("url") and not v["url"].startswith("https://"):
            rep.error(f, f"{w}: url must be https")
        for s in v.get("sections") or []:
            if map_sections and s not in map_sections:
                rep.warn(f, f"{w}: section {s} is not in the map")
        check_refs(f, w, v.get("objectives"), all_objs, rep)
    return len(vs)


def check_cards(ch, files, objs, path_chapters, rep, seen_ids):
    f = f"data/{ch}.cards.tsv"
    header, rows = C.read_cards(files["cards"])
    if header != C.CARD_HEADER:
        rep.error(f, "header must be: " + "\\t".join(C.CARD_HEADER))
        return 0
    per_obj = {o: [] for o in objs}
    n_def = cards = 0
    for ln, c in rows:
        if "_cols" in c:
            rep.error(f, f"line {ln}: expected {len(C.CARD_HEADER)} columns, got {c['_cols']}")
            continue
        cards += 1
        cid = c["id"]
        where = f"line {ln} ({cid or 'no id'})"
        if not re.fullmatch(rf"{ch}-c\d{{3}}", cid):
            rep.error(f, f"{where}: id must match {ch}-cNNN")
        if cid in seen_ids:
            rep.error(f, f"{where}: duplicate card id")
        seen_ids.add(cid)
        required = ["id", "objective", "level", "type", "front", "source", "explanation"]
        if c["type"] != "cloze":
            required.append("back")
        for k in required:
            if not c[k]:
                rep.error(f, f"{where}: empty '{k}'")
        if c["type"] not in C.CARD_TYPES:
            rep.error(f, f"{where}: unknown type '{c['type']}'")
        if c["objective"] not in objs:
            rep.error(f, f"{where}: objective '{c['objective']}' not in data/{ch}.json")
        else:
            per_obj[c["objective"]].append(c["type"])
            if c["level"] != objs[c["objective"]].get("level"):
                rep.error(f, f"{where}: level '{c['level']}' differs from the objective's "
                             f"'{objs[c['objective']].get('level')}'")
        if c["type"] in ("definition", "cloze"):
            n_def += 1
        if c["type"] == "cloze" and not re.search(r"\{\{c\d+::.+?\}\}", c["front"]):
            rep.error(f, f"{where}: cloze card without {{{{c1::…}}}} in front")
        if c["type"] != "cloze" and "{{c" in c["front"]:
            rep.error(f, f"{where}: cloze syntax in a non-cloze card")
        if c["type"] == "diagram" and not c["media"]:
            rep.error(f, f"{where}: diagram card needs a media file")
        if c["media"] and not (files["media"] / c["media"]).is_file():
            rep.error(f, f"{where}: media file data/media/{ch}/{c['media']} not found")
        if c["type"] == "connection":
            others = set(C.CH_REF_RE.findall(" ".join([c["front"], c["back"], c["explanation"]]))) - {ch}
            if not others:
                rep.error(f, f"{where}: connection card must name another chapter (chNN)")
            elif path_chapters and not others & path_chapters:
                rep.warn(f, f"{where}: connection card names chapters not in book.json: {sorted(others)}")
        if c["type"] == "code" and "`" not in c["front"] + c["back"]:
            rep.warn(f, f"{where}: code card without code formatting")
        if re.search(r"\blist all\b|\bname all\b", c["front"], re.IGNORECASE):
            rep.warn(f, f"{where}: enumeration card ('list all…') is not atomic")
        if any(re.search(r"\\n(?![a-zA-Z])", c[k]) for k in ("front", "back", "explanation")):
            rep.warn(f, f"{where}: literal '\\n' found; use <br> for line breaks")
        for k in ("front", "back", "explanation", "source"):
            if RAW_HTML_RE.search(C.MATH_RE.sub(" ", C.BR_RE.sub("", c[k]))):
                rep.error(f, f"{where}: raw HTML in '{k}' (only <br> is allowed)")
        if len(c["front"]) > 400:
            rep.warn(f, f"{where}: front longer than 400 characters")
    if cards == 0:
        rep.error(f, "no cards")
        return 0
    if n_def / cards > 0.25:
        rep.error(f, f"definition+cloze cards are {n_def}/{cards} ({n_def / cards:.0%}), max 25%")
    for oid, types in per_obj.items():
        if objs[oid].get("level") == "core":
            if len(types) < 3:
                rep.error(f, f"{oid} (core) has {len(types)} cards, needs ≥3")
            if not {"why", "apply"} & set(types):
                rep.error(f, f"{oid} (core) needs at least one 'why' or 'apply' card")
            if len(types) >= 3 and len(set(types)) < 2:
                rep.warn(f, f"{oid} (core) uses a single card type")
        elif not types:
            rep.error(f, f"{oid} (secondary) has no cards")
    return cards


def notebook_objectives(ch, files, all_objs, rep):
    f = f"data/{ch}.ipynb"
    try:
        nb = json.loads(files["notebook"].read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        rep.error(f, f"invalid JSON: {e}")
        return set()
    cells = nb.get("cells", [])
    md = "\n".join("".join(c.get("source", "")) for c in cells if c.get("cell_type") == "markdown")
    code = ["".join(c.get("source", "")) for c in cells if c.get("cell_type") == "code"]
    ids = set(C.OBJ_ID_RE.findall(md))
    if not ids:
        rep.error(f, "no objective id referenced in markdown cells")
    for i in ids - set(all_objs):
        rep.error(f, f"references unknown objective {i}")
    if "§" not in md:
        rep.warn(f, "markdown cells do not reference source sections (§)")
    if re.search(r"exercise", md, re.IGNORECASE) and not any(c.lstrip().startswith("# SOLUTION") for c in code):
        rep.warn(f, "exercises found but no '# SOLUTION' cell")
    if code and not any("seed" in c for c in code):
        rep.warn(f, "no random seed set")
    return ids


# ============================================================================= global lints

def lint_text(ch, d, rep):
    f = f"data/{ch}.json"
    for path, s in texts(d):
        if path.endswith(("url", ".doi")) or path in ("id", "slug"):
            continue
        if RAW_HTML_RE.search(C.MATH_RE.sub(" ", s)):
            rep.error(f, f"{path}: raw HTML is not allowed in data (use the inline subset)")
        m = SCHEDULE_RE.search(s)
        if m:
            rep.warn(f, f"{path}: possible schedule/timing language '{m.group(0)}' (no durations or study instructions)")


def lint_verbatim(label, text, src_shingles, n, rep, n_err=25):
    w = words(text)
    run = longest = 0
    for i in range(len(w) - n + 1):
        if tuple(w[i:i + n]) in src_shingles:
            run = run + 1 if run else n
            longest = max(longest, run)
        else:
            run = 0
    if longest >= n_err:
        rep.error(label, f"~{longest} consecutive words copied from the source; paraphrase")
    elif longest >= n:
        rep.warn(label, f"~{longest} consecutive words shared with the source; check it is paraphrased")


# ============================================================================= driver

def validate(book_dir: Path, only: str | None = None, sources=None) -> Report:
    rep = Report()
    book_dir = book_dir.resolve()
    p = C.kit_paths(book_dir)
    if not p["book"].is_file():
        rep.error("data/book.json", "not found")
        return rep
    try:
        book = C.load_json(p["book"])
    except json.JSONDecodeError as e:
        rep.error("data/book.json", f"invalid JSON: {e}")
        return rep
    meta = check_book(book, rep)
    for path, s in texts({k: v for k, v in book.items() if k != "theme"}):
        if not path.endswith("url") and RAW_HTML_RE.search(s):
            rep.error("data/book.json", f"{path}: raw HTML is not allowed")
        m = SCHEDULE_RE.search(s)
        if m:
            rep.warn("data/book.json", f"{path}: possible schedule/timing language '{m.group(0)}'")

    # stray files
    for f in sorted(p["data"].glob("ch*")):
        m = re.match(r"^(ch\d{2})\.(json|cards\.tsv|ipynb|bib)$", f.name)
        if f.is_file() and not m:
            rep.warn(f"data/{f.name}", "unexpected file name (chNN.json, chNN.cards.tsv, chNN.ipynb, chNN.bib)")
        elif m and m.group(1) not in meta:
            rep.error(f"data/{f.name}", f"chapter {m.group(1)} is not listed in book.json")

    chapters = {}
    for ch in meta:
        files = C.chapter_files(p["data"], ch)
        if files["json"].is_file():
            try:
                chapters[ch] = (C.load_json(files["json"]), files)
            except json.JSONDecodeError as e:
                rep.error(f"data/{ch}.json", f"invalid JSON: {e}")
        elif any(files[k].exists() for k in ("cards", "notebook", "bib")):
            rep.error(f"data/{ch}.json", "missing, but other files exist for this chapter: objectives are the spine")
    if only and only not in chapters:
        rep.error(only, "chapter not produced (no data/chNN.json)")
        return rep

    objectives = {ch: check_chapter(ch, d, meta.get(ch, {}), book, rep) for ch, (d, _) in chapters.items()}
    all_objs = {k: v for o in objectives.values() for k, v in o.items()}

    src_shingles, n = set(), 12
    if sources:
        sw = []
        for s in sources:
            sw += words(Path(s).read_text(encoding="utf-8", errors="ignore"))
        src_shingles = {tuple(sw[i:i + n]) for i in range(len(sw) - n + 1)}

    seen_cards: set[str] = set()
    served: dict[str, int] = {}
    order = list(meta)
    for ch, (d, files) in chapters.items():
        objs = objectives[ch]
        if only and ch != only:
            # still collect card ids and back-links across chapters
            if files["cards"].is_file():
                _, rows = C.read_cards(files["cards"])
                seen_cards |= {c.get("id") for _, c in rows if "id" in c}
            continue
        s = {"objectives_core": sum(o.get("level") == "core" for o in objs.values()),
             "objectives_secondary": sum(o.get("level") == "secondary" for o in objs.values())}
        earlier = any(c in chapters for c in order[:order.index(ch)])
        check_map(ch, d, objs, all_objs, rep)
        s["quiz_questions"] = check_quiz(ch, d, objs, all_objs, earlier, rep)
        s["glossary_terms"] = check_glossary(ch, d, all_objs, rep)
        s["readings"] = check_readings(ch, d, all_objs, files, rep)
        s["videos"] = check_videos(ch, d, all_objs, {m.get("section") for m in d.get("map") or []}, rep)
        if files["cards"].is_file():
            s["cards"] = check_cards(ch, files, objs, set(meta), rep, seen_cards)
        if files["notebook"].is_file():
            s["notebook"] = 1
        lint_text(ch, d, rep)
        if src_shingles:
            lint_verbatim(f"data/{ch}.json", " ".join(t for p_, t in texts(d)
                          if not p_.endswith(("citation", "url", "doi", "title"))), src_shingles, n, rep)
            if files["cards"].is_file():
                lint_verbatim(f"data/{ch}.cards.tsv", files["cards"].read_text(encoding="utf-8"), src_shingles, n, rep)
        rep.stats[ch] = s

    # every objective is served by ≥1 item (computed over all chapters: cumulative items count)
    for ch, (d, files) in chapters.items():
        for key in ("map", "quiz", "glossary", "readings", "videos"):
            for item in d.get(key) or []:
                for oid in item.get("objectives") or []:
                    served[oid] = served.get(oid, 0) + 1
        if files["cards"].is_file():
            _, rows = C.read_cards(files["cards"])
            for _, c in rows:
                if c.get("objective"):
                    served[c["objective"]] = served.get(c["objective"], 0) + 1
        if files["notebook"].is_file():
            for oid in notebook_objectives(ch, files, all_objs, rep if (not only or ch == only) else Report()):
                served[oid] = served.get(oid, 0) + 1
    for ch in chapters:
        if only and ch != only:
            continue
        for oid in objectives[ch]:
            if not served.get(oid):
                rep.error(f"data/{ch}.json", f"{oid} is not served by any produced item (no back-links)")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book", type=Path)
    ap.add_argument("--chapter", help="validate only this chapter id (chNN)")
    ap.add_argument("--source", nargs="*", default=[], help="source text(s) for the verbatim-copy check")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="fail on warnings too")
    a = ap.parse_args(argv)
    if not a.book.exists():
        print(f"not found: {a.book}", file=sys.stderr)
        return 2
    rep = validate(a.book, a.chapter, a.source)
    if a.json:
        print(json.dumps({"errors": len(rep.errors), "warnings": len(rep.warnings),
                          "issues": [asdict(i) for i in rep.issues], "stats": rep.stats}, indent=2))
    else:
        for i in rep.issues:
            print(f"{'ERROR' if i.severity == 'error' else 'warn '}  {i.file}: {i.message}")
        if rep.stats:
            print("\nchapter  obj core/sec  cards  quiz  gloss  read  videos  nb")
            for ch, s in rep.stats.items():
                print(f"{ch:8} {s['objectives_core']:>4}/{s['objectives_secondary']:<7} "
                      f"{s.get('cards', '-'):>5}  {s['quiz_questions']:>4}  {s['glossary_terms']:>5}  "
                      f"{s['readings']:>4}  {s['videos']:>6}  {'yes' if s.get('notebook') else '-':>2}")
        print(f"\n{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors or (a.strict and rep.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
