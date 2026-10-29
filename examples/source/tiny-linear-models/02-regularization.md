# Chapter 2 — Regularization

## 2.1 When least squares struggles

The normal equations of Chapter 1 need XᵀX to be invertible. That fails outright when there are more features than samples (d > n), because the rank of X is then at most n. It also fails in a softer way when features are strongly correlated: XᵀX is invertible but ill-conditioned, and small changes in the data produce large swings in the estimated weights. In both cases the least-squares estimate has high variance.

## 2.2 Ridge regression

Ridge regression adds a penalty on the size of the weights: it minimizes ‖y − Xw‖² + λ‖w‖², with λ > 0. Setting the gradient −2Xᵀ(y − Xw) + 2λw to zero gives (XᵀX + λI)w = Xᵀy, so

  ŵ_ridge = (XᵀX + λI)⁻¹Xᵀy.

XᵀX is positive semidefinite; adding λI raises every eigenvalue by λ, which makes the matrix positive definite and therefore invertible for any λ > 0, whatever the shape of X. The penalty shrinks the weights toward zero, smoothly and without usually setting any of them exactly to zero. With λ = 0 ridge is ordinary least squares.

The penalty treats all weights alike, so the scale of a feature changes how strongly its weight is shrunk. Features are therefore standardized before fitting, and the intercept is not penalized.

## 2.3 The lasso

The lasso replaces the squared penalty with the sum of absolute values, λ‖w‖₁. The absolute value is not differentiable at zero, so in general there is no closed-form solution; the problem is solved iteratively, typically by coordinate descent. The reward is that the lasso sets some weights exactly to zero, so it performs feature selection and yields sparser, more interpretable models. As λ grows, more weights become zero.

## 2.4 Choosing λ

λ trades bias for variance. A larger λ constrains the weights more: the fit depends less on the particular sample (less variance) but moves away from the best unconstrained fit (more bias). Training error cannot guide the choice, because it only grows with λ. Instead λ is chosen by cross-validation over a grid of values; if the best value sits at the edge of the grid, the grid is extended. Any preprocessing learned from data, such as the means and standard deviations used for standardization, must be fitted on the training folds only, otherwise information from the validation folds leaks into the model.

## Exercises

2.1 Show that XᵀX + λI is positive definite for every λ > 0.

2.2 Plot the coefficient paths of ridge and lasso as λ varies on the same data, and explain the difference.

2.3 Select λ for ridge by 5-fold cross-validation, fitting the standardization inside each fold.

## Further reading

Ridge regression was introduced by Hoerl and Kennard (1970); the lasso by Tibshirani (1996).
