# Contributing

Thanks for helping. The most useful contributions are:

- **Eval cases from real books** (`evals/cases.json`): a prompt, the expected outputs, and what went wrong before.
- **Validator rules** for mistakes you have seen in generated material, with a test that breaks the rule.
- **Card types** that test something the current 14 miss (`references/card-types.md`).
- **Design fixes** in `templates/`, with screenshots.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user
python -m playwright install chromium   # for visual checks
pytest -q
```

## Before opening a PR

```bash
S=plugins/study-kit/skills/study-kit/scripts
E=examples/study-kit/tiny-linear-models
python3 $S/validate.py   $E --strict --source examples/source/tiny-linear-models/*.md
python3 $S/build_site.py $E
python3 $S/check_site.py $E/site --screenshots /tmp/shots --pages all
```

## Ground rules

- **No copyrighted book text** in issues, tests or examples. The example book is written for this repo; keep new examples original or openly licensed.
- **Never invent curricula.** A change that lets the skill produce paths, variants or prerequisites not stated by a source or a verified syllabus will not be merged.
- **No schedules.** The kit produces structure and materials, never timelines or study instructions.
- **Data in, HTML out.** The agent writes data; scripts render it. Do not add features that make the model write HTML.
- Changes to `SKILL.md` should come with eval results before and after.
- Keep the skill portable: plain `SKILL.md`, Python scripts, no agent-specific APIs.
