# PLATO v3.5 — Algorithmic Randomness Theorem Notes

These notes preserve the mathematically correct form of the user-supplied statements and define what PLATO may compute without overclaiming.

1. **Martin-Löf test.** A Martin-Löf test is a uniformly effectively open sequence `(U_n)` with `mu(U_n) <= 2^-n` for every `n`.
2. **Martin-Löf randomness.** `X` is Martin-Löf random iff it avoids the intersection of every Martin-Löf test.
3. **Levin–Schnorr theorem.** Using prefix-free Kolmogorov complexity `K`, `X` is Martin-Löf random iff there is a constant `c` such that `K(X↾n) >= n-c` for every `n`.
4. **Martingale fairness.** For a binary fair-coin martingale `m`, `m(sigma) = (m(sigma0)+m(sigma1))/2`.
5. **Martingale success.** A martingale succeeds on `X` when its capital is unbounded, equivalently `limsup_n m(X↾n)=infinity`.
6. **Martingale characterization.** Martin-Löf randomness is characterized by failure of every constructive/lower-semicomputable nonnegative supermartingale (equivalently in standard formulations, constructive martingale variants) to succeed.
7. **Schnorr randomness.** A Schnorr test is a uniformly effectively open sequence with computable measures and `mu(U_n) <= 2^-n`; `X` is Schnorr random iff it avoids every such test. Exact equality `2^-n` is not part of the essential definition.
8. **Finite-string incompressibility.** For a fixed deficiency constant `c`, a finite string `x` is `c`-incompressible when `C(x) >= |x|-c`. Writing `O(1)` for one isolated string is not informative unless the constant is uniform across the family being discussed.
9. **Ville/Doob maximal inequality on a cylinder.** For a nonnegative martingale `F`, finite string `sigma`, and `a>0`, the measure of extensions of `sigma` whose future capital reaches/exceeds `a` is at most `2^-|sigma| F(sigma)/a`. The future time index is `m >= |sigma|`.

## PLATO implementation boundary

PLATO does **not** claim to decide Martin-Löf randomness, Schnorr randomness, or exact Kolmogorov complexity from finite lottery data. Exact `K`/`C` is uncomputable and the randomness notions concern infinite sequences.

The live app therefore uses this material only as a zero-weight audit diagnostic. It converts each historical draw to a calibrated fair bit using the parity of a bijective combinatorial rank inside that draw's own rules era. When an era has an odd number of legal combinations, exactly one rank is omitted so the retained parity classes are equal under the uniform lottery null.

A computable nonnegative martingale mixture is then run on those bits. If its capital crosses `2^k`, the associated finite-horizon event has null measure at most `2^-k` by Ville's inequality. Dictionary phrase count, entropy, monobit balance and runs are stored as finite descriptive/compression diagnostics only. They have **zero live ticket-selection weight** until a pre-registered chronological out-of-sample experiment demonstrates incremental value.


## Stable implementation and sharper bound

The fixed four-strategy mixture now accumulates log capital using log-sum-exp.
Long sequences cannot destroy the running calculation through capital overflow or
underflow. Displayed capital is capped to finite floating-point values when needed;
log capital remains available, and tiny numerical bounds are conservatively floored.

For a fixed nonnegative martingale with initial capital 1, Ville gives
`P(sup_t M_t >= a) <= 1/a`. The reported bound is therefore
`min(1, 1 / max_{s<=t} M_s)`, sharper than rounding the maximum down to `2^k`.
A separate union-bound adjustment multiplies it by the five declared games.
This adjustment does not cover unrecorded, post-hoc searches over transforms or
strategies. The uniform independent-draw null, fixed bit transform, and fixed
strategy mixture are essential assumptions; historical diagnostics remain exploratory.
See Howard et al., [Time-uniform Chernoff bounds via nonnegative supermartingales](https://arxiv.org/abs/1808.03204).

The compression routine is a dictionary-phrase proxy. The older `lz76*` API field
names remain compatibility aliases, not a claim to compute exact LZ76 or Kolmogorov
complexity. These diagnostics retain zero ticket-ranking weight.

## Set sums, digital roots and Q

`TSUM(A)` sums the main numbers. For positive integers, `DRoot(x) = 1 + (x-1) mod 9`;
`DRoot(0) = 0`, and a set's root is `DRoot(TSUM(A))`. Each individual number also
gets its own root. Powerball's bonus root is reported separately.

`Q_t = abs(TSUM(A_t) - TSUM(B_t))`. Historical sets compare with the preceding draw
inside the same rule era; generated sets compare with the latest eligible draw.
The first draw in an era has no comparison. Both signed difference and absolute Q
are stored, with the reference draw ID and Q's digital root. `sumDifference(A, B)`
is also available for an explicitly supplied pair of sets. Q is an observed set
comparison; it is not a theorem establishing future-number predictability.
