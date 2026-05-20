# Known Issues

## Failing tests (pre-existing, inherited from `preproc/` → `remote_sensing/` move)

These three tests fail because their assertions don't match the function
signatures of the code they exercise. The function implementations were
moved verbatim from `preproc/` during the 2026-05-13 restructure; the tests
were broken before that move, not caused by it.

### 1. `tests/remote_sensing/analysis/test_detections.py::test_yield_proxy`

- **File:** [tests/remote_sensing/analysis/test_detections.py:39](../tests/remote_sensing/analysis/test_detections.py#L39)
- **Failure:** `assert "estimated_yield" in result` — but `yield_proxy()` returns key `"estimated_yield_t_ha"`.
- **Fix options:**
  - Update the test to assert `"estimated_yield_t_ha"`, OR
  - Add an `"estimated_yield"` alias in [src/jeevn/remote_sensing/analysis/detections.py](../src/jeevn/remote_sensing/analysis/detections.py) `yield_proxy()`.

### 2. `tests/remote_sensing/analysis/test_detections.py::test_weeds_guidance`

- **File:** [tests/remote_sensing/analysis/test_detections.py:49](../tests/remote_sensing/analysis/test_detections.py#L49)
- **Failure:** Test expects `"Low NDVI"` substring in a plain-string return; `weeds_guidance()` now returns a dict `{"weed_pressure_score": ..., "guidance": "..."}`.
- **Fix:** Update the test to read `result["guidance"]` and adjust the substring expectations to match the new sentences (`"Uniform canopy structure"` / `"Moderate variance"` / `"Significant structural variance"`).

### 3. `tests/remote_sensing/analysis/test_indices.py::test_nutrient_stress_score`

- **File:** [tests/remote_sensing/analysis/test_indices.py:78](../tests/remote_sensing/analysis/test_indices.py#L78)
- **Failure:** `assert score_good < score_moderate` but both clamp to `0.05` (the function's lower clip floor in [src/jeevn/remote_sensing/analysis/signals.py](../src/jeevn/remote_sensing/analysis/signals.py) `nutrient_stress_score`).
- **Root cause:** With `red_edge_ndvi/ndvi` ratios of ~0.86 (0.6/0.7) and ~0.80 (0.4/0.5), the formula `1.0 - ((ratio - 0.2) / 0.6)` produces negative values which both clip to `0.05`.
- **Fix options:**
  - Pick test inputs that exercise the unclamped range (e.g. `red_edge_ndvi=0.3` vs `0.5`), OR
  - Revisit the formula — the current clipping behaviour likely doesn't match real-world expectations.
