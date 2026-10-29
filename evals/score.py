#!/usr/bin/env python3
"""Score a study kit produced by the skill against an eval case.

Usage:
    score.py CASE_ID BOOK_DIR [--json]

Workflow:
  1. Run the skill with the case's prompt (cases.json) in a fresh session; it writes
     study-kit/<book-slug>/ (data/, site/, deck.apkg).
  2. score.py CASE_ID study-kit/<book-slug>  → mechanical checks (validator, site checker, expectations).
  3. Score the quality rubric (rubric.md) on a sample, ideally with a reviewer that did not produce it.
Run every case before and after changing SKILL.md, and compare.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/study-kit/skills/study-kit/scripts"))
import check_site  # noqa: E402
import sk_common as C  # noqa: E402
import validate  # noqa: E402


def produced_outputs(book: Path, ch: str) -> set[str]:
    f = C.chapter_files(book / "data", ch)
    d = C.load_json(f["json"])
    out = {"objectives"} if d.get("objectives") else set()
    out |= {k for k in ("map", "quiz", "glossary", "readings", "videos") if d.get(k)}
    if f["notebook"].is_file():
        out.add("notebook")
    if f["cards"].is_file():
        out.add("cards")
    return out


def score(case: dict, book: Path) -> list[tuple[bool, str]]:
    exp = case["expect"]
    src = ROOT / case["source"]
    sources = [str(p) for p in sorted(src.glob("*.md"))] if src.is_dir() else []
    rep = validate.validate(book, sources=sources)
    checks = [(not rep.errors, f"validator: {len(rep.errors)} error(s)")]
    checks += [(False, f"  {i.file}: {i.message}") for i in rep.errors[:10]]

    chapters = sorted(p.stem for p in (book / "data").glob("ch[0-9][0-9].json"))
    checks.append((chapters == sorted(exp["chapters"]), f"chapters {chapters} == expected {exp['chapters']}"))
    for ch in chapters:
        present = produced_outputs(book, ch)
        missing = set(exp["outputs_per_chapter"]) - present
        checks.append((not missing, f"{ch}: required outputs present" + (f" (missing {sorted(missing)})" if missing else "")))
        if exp.get("only_these_outputs"):
            extra = present - set(exp["outputs_per_chapter"])
            checks.append((not extra, f"{ch}: nothing produced beyond the request" + (f" (extra {sorted(extra)})" if extra else "")))
        s = rep.stats.get(ch, {})
        for key, stat in (("cards_per_chapter", "cards"), ("quiz_per_chapter", "quiz_questions")):
            if key in exp and s.get(stat):
                lo, hi = exp[key]
                checks.append((lo <= s[stat] <= hi, f"{ch}: {s[stat]} {stat.replace('_', ' ')} in [{lo}, {hi}]"))

    if "variants" in exp:
        book_json = C.load_json(book / "data/book.json")
        found = sorted(sorted(v.get("chapters", [])) for v in book_json.get("variants") or [])
        checks.append((found == sorted(sorted(v) for v in exp["variants"]),
                       f"variants {found} == only the stated ones {exp['variants']}"))
    if exp.get("site"):
        site = book / "site"
        if (site / "index.html").is_file():
            issues, stats = check_site.static_checks(site)
            errs = [i for i in issues if i["severity"] == "error"]
            checks.append((not errs, f"site: {stats['pages']} pages, {len(errs)} link/markup error(s)"))
            checks += [(False, f"  {i['file']}: {i['message']}") for i in errs[:10]]
        else:
            checks.append((False, "site/index.html built"))
    if exp.get("deck"):
        checks.append(((book / "deck.apkg").is_file(), "deck.apkg built"))
    if exp.get("no_schedule_warnings"):
        sched = [i for i in rep.warnings if "schedule" in i.message]
        checks.append((not sched, f"no schedule language ({len(sched)} hit(s))"))
    return checks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case")
    ap.add_argument("book", type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    cases = {c["id"]: c for c in json.loads((Path(__file__).parent / "cases.json").read_text())["cases"]}
    if a.case not in cases:
        sys.exit(f"unknown case; available: {', '.join(cases)}")
    checks = score(cases[a.case], a.book.resolve())
    top = [c for c in checks if not c[1].startswith("  ")]
    passed = sum(ok for ok, _ in top)
    if a.json:
        print(json.dumps({"case": a.case, "passed": passed, "total": len(top),
                          "checks": [{"ok": ok, "check": m} for ok, m in checks]}, indent=2))
    else:
        for ok, m in checks:
            print(("  " if m.startswith("  ") else ("PASS " if ok else "FAIL ")) + m)
        print(f"\n{a.case}: {passed}/{len(top)} mechanical checks passed — now score rubric.md")
    return 0 if passed == len(top) else 1


if __name__ == "__main__":
    sys.exit(main())
