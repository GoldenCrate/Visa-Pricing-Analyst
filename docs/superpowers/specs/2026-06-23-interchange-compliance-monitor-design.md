# Interchange Compliance Monitor — Design Spec

**Date:** 2026-06-23
**Author:** Leo Chan
**Project:** Visa-Pricing-Analyst (new page added to the existing app)
**Target role:** Analyst, Global Interchange Strategy / Interchange Compliance — Visa Inc.

---

## 1. Purpose

Add a fourth page to the Visa Pricing Analyst app that audits whether each
transaction segment was assessed the **correct** interchange rate versus the
**published rate schedule**, flags deviations beyond a configurable tolerance,
and quantifies the **financial impact** — both over-assessment (clients
overcharged) and under-assessment (revenue not collected).

This extends the project from "pricing strategy / deal-structuring" into the
**interchange compliance & monitoring** work of Visa's Global Interchange
Strategy team.

## 2. Job-posting alignment

| Posting duty | How this feature demonstrates it |
|---|---|
| "ensuring proper levels of interchange are paid and received" | Actual vs published-schedule comparison, both directions |
| "identification and analysis of potential interchange processing issues that may result in financial impact" | Flagged exceptions with signed USD impact |
| "proactive evaluation of interchange assessment and trends" | Financial-impact / exception trend over time |
| "development and maintenance of KPIs/dashboards… presentation to management" | Compliance-rate KPIs + a "flagged for management review" table |
| SQL/BI, quantitative analysis of large datasets, Python | Pandas analysis over the 2,160-row dataset; pure-function modeling |

## 3. Architecture (follows the project's existing pattern)

- **`streamlit_app/utils/compliance.py`** — a `PUBLISHED_SCHEDULE` constant
  (expected interchange rate per merchant category) plus a pure function
  `compute_compliance_exceptions(df, expected_rates, tolerance_bps)`. No Streamlit
  dependency, so it is unit-testable exactly like `deal_pnl.py` / `opportunity_score.py`.
- **`streamlit_app/pages/4_interchange_compliance.py`** — the new Streamlit page.
- **`tests/test_compliance.py`** — pytest unit tests for the pure function.
- **`streamlit_app/generate_data.py`** + regenerated **`data/visa_pricing_metrics.csv`**
  — inject a controlled set of anomalies.

## 4. Published rate schedule (expected rates)

The standard interchange each merchant category should be assessed (the same base
rates the dataset is built around):

| Category | Expected rate |
|---|---|
| Retail | 1.80% |
| Travel | 2.20% |
| Dining | 1.95% |
| Healthcare | 1.60% |
| E-commerce | 2.40% |
| Fuel | 1.45% |

Stored as `PUBLISHED_SCHEDULE` in `utils/compliance.py`.

## 5. Data changes (anomaly injection)

Modify `generate_data.py` so that ~2–3% of rows receive a **material
mis-assessment** — interchange set ≥20 bps off the published schedule, in both
directions — representing real processing errors. Normal random noise remains
small (~±7 bps, plus a slight Q4 seasonal bump), so a default tolerance of ~15 bps
cleanly separates genuine exceptions from noise. No new CSV columns are added —
detecting the anomalies is the tool's job. Injection uses the existing
`random.seed(42)` so the dataset stays reproducible. At 2–3% of rows the effect on
the other pages' aggregate charts is negligible.

## 6. The pure function

```
compute_compliance_exceptions(df, expected_rates, tolerance_bps) -> pd.DataFrame
```

Returns the input dataframe enriched with:
- `expected_rate` — looked up from `expected_rates` by `merchant_category`
- `deviation_bps` — `(interchange_rate − expected_rate) × 10000` (signed)
- `is_exception` — `abs(deviation_bps) > tolerance_bps`
- `financial_impact_usd` — `(interchange_rate − expected_rate) × transaction_volume × avg_transaction_usd` (signed; positive = over-assessed, negative = under-assessed)
- `direction` — `"Over-assessed"` / `"Under-assessed"` / `"Within tolerance"`

Pure and deterministic; no I/O.

## 7. The page (Storytelling-with-Data styling)

- **Tolerance slider** (basis points, default 15) — interactive control, like the deal simulator.
- **KPI cards:** compliance rate %, number of exceptions, total $ at risk (sum of absolute impact), net $ impact (over − under).
- **Narrative takeaway** line summarizing the result.
- **Trend chart:** financial impact (or exception count) by month — line.
- **Concentration chart:** exceptions by merchant category — bar, accent the worst (decision: category, since the schedule is category-based; region is available as a future cut).
- **"Flagged for management review" table:** region · category · card type · month · expected % · actual % · deviation (bps) · $ impact · direction — sorted by absolute $ impact, descending.

Charts follow the project's SWD conventions: muted palette with a single accent
colour, decluttered axes, insight-oriented titles.

## 8. Testing

`tests/test_compliance.py` (pytest), covering the pure function:
- no rows flagged when all deviations are within tolerance
- rows beyond tolerance are flagged (`is_exception` True)
- `deviation_bps` computed correctly (sign and magnitude)
- `financial_impact_usd` correct and correctly signed for both directions
- `direction` labels correct
- empty-input edge case returns an empty result without error

## 9. Documentation

- Update `README.md` to list the new fourth page (and add a screenshot after build).
- Add the implementation plan under `docs/superpowers/plans/`.

## 10. Scope cuts (YAGNI)

- No persistence/database — reads the existing CSV (consistent with the app).
- No per-region schedule — single category-level published schedule (region cut is future work).
- No export/download of the exceptions table (future enhancement).
