# Quality rubric

`score.py` checks what can be checked mechanically. A reviewer (a person, or a model that did not produce the output) scores the rest on a sample: 5 cards per chapter, all quiz questions, all objectives. 0 = fails, 1 = partly, 2 = fully.

## Objectives
1. Each objective uses an observable verb and could be tested by an exam question.
2. "Core because" points at something real: a later chapter, an exercise, a syllabus outcome.
3. Together, the objectives cover what the chapter's exercises require.

## Cards
4. `why` cards give a cause on the back, not a restatement of the front.
5. `apply` cards contain a concrete scenario with one defensible answer.
6. Explanations add something the back does not say (a reason, a pitfall, a link).
7. No card can be answered without having studied the chapter (no giveaways in the front).
8. Notation matches the source.

## Quiz
9. Difficulty actually increases from Remember to Analyze.
10. Every multiple-choice distractor encodes a mistake a learner would plausibly make.
11. Solutions show the reasoning, and computations are correct (re-run them).
12. Cumulative questions really need the earlier chapter.

## Path
13. Variants and prerequisites come from the source or a cited syllabus — nothing invented.
14. No timeline, duration, or instruction on when to study, anywhere.

## Site (look at the check_site.py screenshots)
15. From the home page you can reach every produced page in two clicks, and every objective shows what serves it.
16. The visual direction (theme tokens) suits the subject, and both themes read comfortably on a phone.
17. Math, code and figures render correctly; nothing overflows the page.

Report: total out of 34, plus one line per item scored 0.
