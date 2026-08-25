# Mathematics · X20 response surface

## 1. State vector

At time `t`, the system constructs a normalized vector

```text
x(t) = [x₁(t), …, x₂₀(t)]ᵀ ∈ [-1, 1]²⁰.
```

Normalization bounds the influence of feed errors and lets unlike units coexist. Production calibration must fit transforms using training data only.

## 2. Quadratic signal surface

```text
z(x) = β₀ + βᵀx + ½xᵀHx,
p(up | x) = 1 / (1 + exp(-z)).
```

`H` is symmetric. Off-diagonal terms represent interactions. For example, positive news with low credibility must not have the same effect as positive news confirmed by an SEC filing.

## 3. Gradient

For symmetric `H`:

```text
∂z/∂xᵢ = βᵢ + Σⱼ Hᵢⱼxⱼ,
∇z = β + Hx.
```

The dashboard ranks `|∂z/∂xᵢ|`. This is local sensitivity, not causal proof.

## 4. Multivariate chain rule

Every factor changes with time. The instantaneous signal velocity is

```text
dz/dt = Σᵢ (∂z/∂xᵢ)(dxᵢ/dt) = ∇z · ẋ.
```

This distinction matters: a factor can have a large partial derivative but contribute little right now if it is not moving.

## 5. Hessian and stress tests

Because the surface is quadratic, its Hessian is exactly `H`. For a scenario shock `h`,

```text
z(x + h) - z(x) = ∇z(x)·h + ½hᵀHh.
```

The second-order term measures interaction/curvature effects that a linear weighted score would miss.

## 6. Uncertainty

The v0.1 interval deliberately widens for short history, missing coverage and high realized volatility:

```text
u = u₀ + history_penalty + coverage_penalty + volatility_penalty.
90% interval = expected_return ± 1.645u.
```

This is an engineering uncertainty envelope, not yet a statistically calibrated confidence interval. v0.3 must measure empirical coverage with purged walk-forward evaluation.

## 7. Tests

`tests/test_model.py` compares the analytic gradient with central finite differences and verifies exact second-order stress decomposition. These tests show the calculus implementation is correct; they do not prove market forecasting skill.

