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

A computable nonnegative martingale mixture is then run on those bits. If its capital crosses `2^k`, the associated finite-horizon event has null measure at most `2^-k` by Ville's inequality. LZ76 phrase count, entropy, monobit balance and runs are stored as finite descriptive/compression diagnostics only. They have **zero live ticket-selection weight** until a pre-registered chronological out-of-sample experiment demonstrates incremental value.
