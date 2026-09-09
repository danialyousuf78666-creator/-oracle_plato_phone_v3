# PLATO v3.4 Adaptive Pool Protocol

Status: experimental. This does not replace classic v3, v3.2, or the fixed v3.3 prospective protocol.

## Purpose

Choose shortlist size from 12–18 using only the disagreement between the frozen top-15 classic-v3 and v3.1 rankings. The rule is fixed before future evaluation and must not be retuned after seeing outcomes.

## Frozen rule

- agreement 11–15 / 15 -> pool 12
- agreement 9–10 / 15 -> pool 13
- agreement 8 / 15 -> pool 14
- agreement 6–7 / 15 -> pool 15
- agreement 4–5 / 15 -> pool 16
- agreement 3 / 15 -> pool 17
- agreement 0–2 / 15 -> pool 18

The rule treats v3/v3.1 agreement as a simple consensus proxy. It does not claim calibrated probability or predictive confidence.

## Evaluation

Compare adaptive-k against fixed k=15 prospectively. Use the same pre-draw engine state and ticket budget. Report shortlist hit count, ticket best hit, 3+/4+/5+/6+/7 capture where applicable, pool size, and v3/v3.1 agreement. No promotion claim is allowed from historical reuse alone.

Any change to thresholds or pool bounds creates a new version and resets prospective evidence for the adaptive-pool rule.
