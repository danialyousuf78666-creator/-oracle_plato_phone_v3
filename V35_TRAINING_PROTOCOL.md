# PLATO v3.5 Full-History Training Protocol

Status: experimental training branch. Frozen v3, v3.2, v3.3 and v3.4 remain controls.

## Data

Use every valid supplied draw, separated by rule era. Total supplied rows: 9,771.

- Powerball: 1,581 rows; eras 5/45 (draws 1–876), 6/40 (877–1143), 7/35 (1144–1581).
- Saturday Lotto: 2,079 rows; 6/45.
- Oz Lotto: 1,699 rows; eras 6/45 (1–608), 7/45 (609–1473), 7/47 (1474–1699).
- Set for Life: 4,051 rows; eras 8/37 (1–1690), 7/44 (1691–4051).
- Weekday Windfall: 361 rows; 6/45.

Raw number-specific signals may learn only inside a compatible rule era. Structural signals may use older eras only after normalization to the era's n and r.

## Pattern coverage

The compact v3.5 trainer maps 35 methods across these 17 pattern groups:
frequency, recency, gaps, pairs, triples, position, ranges, parity, sum, digital_root, adjacency, transition, temporal, structural, pattern_signatures, feature_interactions, regimes.

This is a compact mapped registry for v3.5. It must not be represented as a byte-for-byte recovery of the historical 35-method registry unless the original registry source is restored and verified.

## Validation and distillation

1. Predict each historical target from earlier draws only.
2. Evaluate history windows 100, 150, 200, 250, 500, 1000 and all-prior where available.
3. Penalize methods whose lift changes materially across windows.
4. Fit Machine 1 / Machine 2 reliability only from chronological pre-target predictions.
5. Keep at most eight stability-adjusted methods per game for the phone payload.
6. Heavy 35-method training stays off-device. The phone receives only the distilled method set and weights.
7. Any result from the supplied history is development evidence, not untouched confirmation.
8. No promotion unless a new prospective test beats frozen controls with replicated statistical evidence.

## Source hashes

- Powerball: `64b9d479a2c26dfaa78b649027946e95c4c1d4c6a325ae5ffafa1b8ba799bd08`
- Saturday Lotto: `e95f349e6616cec19ad41b959574beb1d3f0bdc83960c125987b0c92855ced05`
- Oz Lotto: `314841d91b58c8d25f9c8c1ecf8681ee57e6ac7f8398a583ce21358910f4f931`
- Set for Life: `f49c59d8be6a90d60adf3d741fb969dbda862bdc9ca760d2f08c32c6b7bac9d1`
- Weekday Windfall: `912487f8a62d1e55712c034cdc6fe12c132e4482ff81e321de6b2a6054f1b4e9`

## Current training checkpoint

A small chronological development audit was used only to sanity-check the distillation machinery. It is too small for promotion claims:

- Powerball: 3.1667 mean hits vs random expectation 3.0000.
- Saturday Lotto: 2.0000 vs 2.0000.
- Oz Lotto: 2.4167 vs 2.2340.
- Set for Life: 2.1250 vs 2.3864.
- Weekday Windfall: 2.4167 vs 2.0000.

These results are not a verified predictive edge. The next engineering step is to port only the distilled methods into a small v3.5 phone plugin and then freeze it before prospective testing.

## Phone inference alignment (root integration)

The original protocol and distilled weights are preserved unchanged under `audit/`.
The root app now calls the existing v3.5 distilled engine directly and uses the
existing Prize Coverage allocation. No v3.2/v3.4 UI scripts, iframe, or wrapper
are dependencies of live inference. All 9,771 supplied valid records are loaded.

The original checkpoint document incorrectly merged Oz Lotto's 7/45 and 7/47
eras. The 7/47 change began 17 May 2022 (draw 1474 in the supplied data).
Source: https://lotterywest.wa.gov.au/lotterywest/media-centre/bigger-prizes-and-more-winners-with-oz-lotto-game-change
This boundary is corrected above and in the shared era registry.

Raw number identities, gaps, recurrence and pairs are learned only within the
target rule era. Normalized structure uses every prior valid draw: number
positions are divided by the source n; parity, range occupancy, sum and position
statistics account for source r; each draw contributes equal mass before the
existing decay weighting. Normalized positions are projected onto the target
matrix with linear interpolation, rather than pretending old numbers are current
number identities. No outer live-history cutoff is used. Named short/medium/long
frequency and regime features retain their intrinsic horizons; exponential decay
retains the full eligible history. Structural features no longer discard all but
120 or 180 draws.

Selected methods and numerical checkpoint weights are unchanged. The repository
contains the protocol and weight checkpoint, but not the original heavy trainer
or feature-parity fixtures. Therefore this implementation is aligned with the
stated era-separation contract; byte-for-byte agreement with that absent trainer
has not been established. The era correction and normalized port require fresh
prospective evaluation before any claim of predictive improvement.
