---
sidebar_position: 2
title: Math Rendering Test
description: Testing KaTeX math rendering capabilities
---

# Math Rendering with KaTeX

This page demonstrates mathematical formula rendering using KaTeX.

## Inline Math

The quadratic formula is $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$ which solves $ax^2 + bx + c = 0$.

Einstein's famous equation $E = mc^2$ relates energy and mass.

The probability of event A given B is $P(A|B) = \frac{P(B|A) \cdot P(A)}{P(B)}$.

## Block Math

### Gaussian Distribution

The probability density function of the normal distribution:

$$
f(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{1}{2}\left(\frac{x-\mu}{\sigma}\right)^2}
$$

### Summation Notation

Expected loss calculation:

$$
EL = \sum_{i=1}^{n} PD_i \times LGD_i \times EAD_i
$$

### Integration

The cumulative distribution function:

$$
F(x) = \int_{-\infty}^{x} f(t) \, dt
$$

## Matrix Notation

### Risk Correlation Matrix

$$
\mathbf{R} = \begin{pmatrix}
1 & \rho_{12} & \rho_{13} \\
\rho_{21} & 1 & \rho_{23} \\
\rho_{31} & \rho_{32} & 1
\end{pmatrix}
$$

### Covariance Matrix

$$
\Sigma = \begin{bmatrix}
\sigma_1^2 & \sigma_{12} & \cdots & \sigma_{1n} \\
\sigma_{21} & \sigma_2^2 & \cdots & \sigma_{2n} \\
\vdots & \vdots & \ddots & \vdots \\
\sigma_{n1} & \sigma_{n2} & \cdots & \sigma_n^2
\end{bmatrix}
$$

## Greek Letters

| Symbol | Meaning | Formula |
|--------|---------|---------|
| $\alpha$ | Significance level | $P(\text{Type I error}) = \alpha$ |
| $\beta$ | Beta coefficient | $\beta = \frac{Cov(r_i, r_m)}{Var(r_m)}$ |
| $\sigma$ | Standard deviation | $\sigma = \sqrt{Var(X)}$ |
| $\mu$ | Mean | $\mu = E[X]$ |
| $\lambda$ | Rate parameter | $P(X=k) = \frac{\lambda^k e^{-\lambda}}{k!}$ |

## Complex Formulas

### Value at Risk (VaR)

$$
VaR_\alpha(X) = \inf\{x \in \mathbb{R} : P(X \leq x) \geq \alpha\}
$$

### Black-Scholes Formula

$$
C(S,t) = N(d_1)S - N(d_2)Ke^{-r(T-t)}
$$

where:

$$
d_1 = \frac{\ln(S/K) + (r + \sigma^2/2)(T-t)}{\sigma\sqrt{T-t}}
$$

$$
d_2 = d_1 - \sigma\sqrt{T-t}
$$

### Capital Allocation

$$
RC_i = \frac{MC_i}{\sum_{j=1}^{n} MC_j} \times EC
$$

Where:
- $RC_i$ = Risk capital allocated to unit $i$
- $MC_i$ = Marginal contribution of unit $i$
- $EC$ = Total economic capital

<Tip title="KaTeX vs MathJax">
KaTeX renders math much faster than MathJax and supports most LaTeX math commands. For unsupported commands, refer to the [KaTeX documentation](https://katex.org/docs/supported.html).
</Tip>
