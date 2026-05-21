# Known Issues

*Drop entries here as they're discovered. Move resolved ones to the
`## Resolved` section with the resolution date and a short note. The
intent of this file is to be the single place a contributor (human or
AI agent) checks for "is this a known bug or did I just break something?"*

---

## Open

(none — the suite is green as of 2026-05-21)

---

## Resolved

### 3 pre-existing test failures inherited from `preproc/` → `remote_sensing/`
- **Resolved:** 2026-05-21 (task #3 in TASKS.md)
- **Tests:** `test_yield_proxy`, `test_weeds_guidance`, `test_nutrient_stress_score`
- **Root cause:** Each test had drifted out of sync with its function's
  contract. The function implementations were moved verbatim from
  `preproc/` during the 2026-05-13 restructure; the tests had been broken
  before the move and were carried over as-is, then logged here so a
  later commit could address them deliberately.
- **Fix shape:** Updated each test to match the current function contract
  (functions were left alone since their contracts are the ones the rest
  of the codebase relies on).
  - `test_yield_proxy` → asserts on `estimated_yield_t_ha` and `peak_ndvi`
    (the units-explicit keys the function actually returns).
  - `test_weeds_guidance` → reads `result["guidance"]` (function returns
    a dict, not a string) and passes `texture_entropy` to exercise the
    low / moderate / high branches of the narrative.
  - `test_nutrient_stress_score` → uses ratio inputs in the function's
    unclamped band (0.2–0.8) so the relative ordering is meaningful;
    previous inputs both clamped to 0.05 making the `<` assertion
    impossible to satisfy.
