# Offline Fashion Verdict Evaluation Report

## 1. Overview & Setup

- **User Count:** 1
- **User ID:** `3`
- **Evaluated Positives (n):** 3
- **Positive Selection:** Fewer than 5 wishlist/cart/purchase events found; fell back to **product views / product detail views**.
- **Locally Non-Empty Media Domains:** anilist
- **Negative Sampling:** 99 random catalog negatives per positive (seed 42, same gender pool, kids excluded).
- **Evaluation Total Items per Trial:** 100 (1 positive + 99 negatives).

## 2. Evaluation Results

| Variant | Description | HR@10 | MRR | Mean Percentile Rank | n |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **(A)** | Popularity / Price-only Baseline | 0.0000 | 0.0173 | 32.66% | 3 |
| **(B)** | Direct Only (TF-IDF Cosine) | 1.0000 | 0.2560 | 95.29% | 3 |
| **(C)** | Direct + Price + Redundancy | 0.0000 | 0.0216 | 52.53% | 3 |
| **(D)** | Full (C + Crosswalk) | 0.0000 | 0.0157 | 36.03% | 3 |

## 3. Findings & Analysis

> single-user, small-n: indicative only, not statistically significant

- **Direct Signals (B vs A):** Direct browsing TF-IDF achieves HR@10 = 1.0000 and MRR = 0.2560.
- **Full Engine (D vs C):** Variant D (with crosswalk) yields HR@10 = 0.0000 and MRR = 0.0157 compared to Variant C (0.0000 / 0.0216).
- **Crosswalk Impact:** Crosswalk signals introduced slight variance on this sample; D ≤ C.

*Note: Production weights and thresholds were fixed a priori and not tuned against this evaluation.*