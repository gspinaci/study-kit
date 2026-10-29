# Card types

Every card hooks onto one objective. Pick the type that tests what the objective asks for: an objective with "derive" needs `derivation` cards, one with "choose" needs `apply` and `compare` cards. Definitions and clozes are the floor, not the deck (≤25%).

| type | tests | front pattern | quality bar |
|---|---|---|---|
| `definition` | recall of a term | "What is X (in this book's sense)?" | precise, not a paraphrase of the term itself |
| `cloze` | a formula or key statement | "The OLS estimate is {{c1::\((X^\top X)^{-1}X^\top y\)}}" | one deletion per idea; the rest of the sentence gives context |
| `why` | the reason behind a choice or step | "Why does ridge add \(\lambda I\) before inverting?" | the back gives a cause, not a restatement |
| `compare` | discrimination between neighbours | "Ridge vs lasso: what differs in the solutions, and when do you prefer each?" | names the deciding criterion |
| `apply` | choosing/using a method in a scenario | "You have 50 samples and 200 correlated features. What do you fit, and why?" | a concrete scenario, one defensible answer |
| `derivation` | a single step of an argument | "From \(\nabla_w \|Xw-y\|^2 = 0\), what equation follows?" | one step, not the whole proof |
| `mistake` | spotting a common error | "A student standardizes the test set with its own mean. What is wrong?" | the error is a real one, the back says why it matters |
| `intuition` | geometric/conceptual meaning | "What does \(X\hat w\) represent geometrically?" | an image the learner can hold |
| `notation` | the book's symbols | "In this book, what does \(\Phi\) denote?" | only notation the book actually uses |
| `code` | reading or completing code | "What shape does `X @ w` have if X is (n, d)?" | consistent with the notebook, runnable |
| `diagram` | reading a figure | "In the figure, which point has the largest residual?" | figure recreated in `media/`, never cropped |
| `connection` | links across chapters | "Where does the normal equation reappear in ch02, and what changes?" | both chapters are linked in `path.md` |
| `counterexample` | limits of a result | "Give a case where \(X^\top X\) is not invertible." | minimal, checkable example |
| `reverse` | from description to name | "Penalizing \(\|w\|_1\) in least squares is called…?" | description is unique to the concept |

## Front / back / explanation

- **front**: one question, answerable in a few seconds by someone who met the objective.
- **back**: the shortest complete answer.
- **explanation**: 1–3 sentences: why the answer holds, the typical pitfall, or a link to another concept. This is where depth lives.

## Mix per chapter

- Core objective: ≥3 cards, at least one `why` or `apply`, ideally covering 3 different types.
- Secondary objective: ≥1 card.
- Use `connection` cards from the second chapter on, following forward links in `path.md`.
