# Attune current-product / Roboflow proposal comparison

This receipt compares source-bound outputs; it is not an accuracy score.
Generated images are integration/proposal-review evidence only, not real-camera or expert truth.

| Subject | Attune valid / 9 | Skin type | Roboflow 8% | Roboflow 50% |
| --- | ---: | --- | ---: | ---: |
| 1.England | 9 | oily | 19 | 5 |
| 2.Germany | 9 | dry | 40 | 1 |
| 3.Kenya | 9 | oily | 24 | 1 |
| 4.Scotland | 9 | dry | 40 | 2 |
| 5.Turkey | 9 | dry | 29 | 5 |
| 6.usa | 6 | oily | 72 | 3 |

Attune values retain their per-criterion quality and limitation receipts in the JSON output.
Roboflow counts are proposals recomputed from the single 8% response per image.
Neither system's output is treated as ground truth for the other.
