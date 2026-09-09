# PLATO v3.3 Prospective Validation Protocol

Status: **frozen before prospective scoring**.

## Frozen controls

- Live/classic control: PLATO v3 on `main`.
- Experimental comparator: PLATO v3.2 from branch `plato-v3.2-cooperative`.
- Shortlist size: 15 unless a game requires a larger minimum equal to its draw size.
- Primary game: Weekday Windfall.
- Primary minimum: 30 genuinely new draws recorded after the protocol is frozen.
- Historical draws already inspected or used for development remain audit/development data and cannot count as untouched confirmation.

## Prediction rule

Before each next draw, store both shortlists and the v3.2 fitted state. After the actual draw is entered, score the stored prediction only. Never recompute an old prediction after seeing its result.

Only one pending prediction per game is allowed. Pending records are immutable during the trial.

## Promotion gate

v3.2 cannot replace classic v3 unless the prospective audit shows all of the following:

1. Higher paired mean hits than v3 on the fixed primary sample.
2. 95% paired confidence interval for `v3.2 - v3` entirely above zero.
3. Hit variance no greater than classic v3 on the primary sample.
4. Corrected statistical significance at 5% when all confirmatory game tests are considered.
5. No scoring, feature, blend, regularization, shortlist-allocation, or evaluation parameter changes after prospective scoring begins.

Secondary games may be collected concurrently, but they cannot rescue a failed primary Weekday Windfall result by retrospective selection.

## Reset rule

Any change to the prediction algorithm or fixed parameters creates a new experimental version and resets the prospective sample for that version. Existing results remain archived and are never relabeled as untouched.

## Interpretation

Shortlist capture is not purchased-ticket return and does not establish a lottery advantage unless a prospective out-of-sample effect survives the fixed protocol and statistical audit.
