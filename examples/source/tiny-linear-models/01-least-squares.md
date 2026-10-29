# Chapter 1 — Least Squares

## 1.1 The model

We observe n samples, each described by d numbers called features, and a target value for each sample. Stacking the samples as rows gives the design matrix X, of size n by d, and the targets form a vector y of length n. A linear model predicts every target with the same weight vector w of length d: the prediction for all samples at once is the vector Xw. When the model should include an intercept, a column of ones is appended to X and w gains one more entry.

The difference between what we observe and what we predict, r = y − Xw, is called the residual vector. Fitting the model means choosing w so that the residuals are small.

## 1.2 The squared loss

There are many ways to measure how small a vector of residuals is. Least squares uses the sum of squared residuals, L(w) = ‖y − Xw‖². The square is differentiable everywhere, it treats positive and negative errors alike, and it punishes a large error much more than several small ones. If the noise on the targets is Gaussian, minimizing this loss is the same as maximizing the likelihood of the data.

## 1.3 The normal equations

L(w) is a convex quadratic function of w. Its gradient is ∇L(w) = −2Xᵀ(y − Xw). Setting the gradient to zero yields the normal equations,

  XᵀX w = Xᵀy.

When the columns of X are linearly independent, the d by d matrix XᵀX is invertible and the minimizer is unique: ŵ = (XᵀX)⁻¹Xᵀy. Linear independence requires at least as many samples as features (n ≥ d). If one column is a combination of others, XᵀX is singular and infinitely many weight vectors give the same predictions.

## 1.4 Geometry of the fit

Every possible prediction Xw is a combination of the columns of X, so the predictions live in the column space of X. The least-squares prediction Xŵ is the point of that subspace closest to y: it is the orthogonal projection of y onto the column space. Rewriting the normal equations as Xᵀ(y − Xŵ) = 0 shows the same fact from the algebraic side: the residual is orthogonal to every column of X.

Two consequences follow. If X contains a column of ones, the residuals sum to zero. And enlarging X with an extra column can only enlarge the column space, so the training sum of squared residuals can never increase when a feature is added.

## 1.5 Computing the solution in practice

The formula with the explicit inverse is useful on paper but is a poor algorithm. Forming XᵀX squares the condition number of the problem, so rounding errors are amplified when columns are nearly dependent. Numerical libraries instead solve the least-squares problem through an orthogonal factorization of X (QR or the singular value decomposition), for example `numpy.linalg.lstsq`. On well-conditioned problems both routes agree to many digits; on ill-conditioned ones they can differ noticeably.

## Exercises

1.1 Show that, when X contains a column of ones, the residuals of the least-squares fit sum to zero.

1.2 Implement the normal equations with NumPy and compare the result with `numpy.linalg.lstsq` on random data.

1.3 Give a design matrix with three rows and two columns for which XᵀX is singular.
