# Interchange Compliance Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fourth Streamlit page to the Visa Pricing Analyst app that audits assessed interchange against a published rate schedule, flags deviations beyond a configurable tolerance, and quantifies the financial impact.

**Architecture:** A pure function in `utils/compliance.py` (no Streamlit dependency, unit-tested with pytest) does the audit; a new Streamlit page renders KPIs, charts, and a review table; the shared `generate_data.py` injects a controlled set of anomalies into the existing CSV so the monitor has genuine exceptions to catch.

**Tech Stack:** Python, Pandas, NumPy, Altair, Streamlit, pytest — matching the existing project.

## Global Constraints

- Tests import from `utils.*` (pytest.ini sets `pythonpath = streamlit_app`); `testpaths = tests`.
- Pure functions live in `streamlit_app/utils/` and take/return plain values or DataFrames — no Streamlit imports (pattern: `deal_pnl.py`, `opportunity_score.py`).
- Pages import pure functions as `from utils.compliance import ...` and are run from `streamlit_app/`.
- `generate_data.py` is run from `streamlit_app/` and writes `data/visa_pricing_metrics.csv` (relative path).
- Published schedule (expected rates): Retail 0.0180, Travel 0.0220, Dining 0.0195, Healthcare 0.0160, E-commerce 0.0240, Fuel 0.0145.
- Default exception tolerance: 15 basis points. `is_exception` is `abs(deviation_bps) > tolerance_bps` (strictly greater).
- Charts use Storytelling-with-Data styling: muted grey with one accent colour, decluttered axes, insight titles.
- Dataset stays reproducible: anomaly injection uses a dedicated seeded RNG so non-anomalous rows are unchanged from the prior dataset.

---

## File Structure

```
streamlit_app/
├── generate_data.py                       # MODIFY: inject anomalies (separate seeded RNG)
├── data/visa_pricing_metrics.csv          # REGENERATE
├── utils/
│   └── compliance.py                      # CREATE: PUBLISHED_SCHEDULE + compute_compliance_exceptions
└── pages/
    └── 4_interchange_compliance.py        # CREATE: the new page
tests/
└── test_compliance.py                     # CREATE: unit tests for the pure function
README.md                                  # MODIFY: document the 4th page
```

---

## Task 1: Compliance pure function + published schedule

**Files:**
- Create: `streamlit_app/utils/compliance.py`
- Test: `tests/test_compliance.py`

**Interfaces:**
- Produces: `PUBLISHED_SCHEDULE: dict[str, float]` and
  `compute_compliance_exceptions(df: pd.DataFrame, expected_rates: dict, tolerance_bps: float) -> pd.DataFrame`.
  The returned DataFrame is a copy of `df` with added columns: `expected_rate` (float),
  `deviation_bps` (float, signed), `is_exception` (bool), `financial_impact_usd` (float, signed),
  `direction` (str: "Over-assessed" / "Under-assessed" / "Within tolerance").
  Input rows must have columns: `merchant_category`, `interchange_rate`, `transaction_volume`, `avg_transaction_usd`.

- [ ] **Step 1: Write the failing test** — create `tests/test_compliance.py`:

```python
import pandas as pd
import pytest

from utils.compliance import PUBLISHED_SCHEDULE, compute_compliance_exceptions

EXPECTED = {"Retail": 0.0180, "E-commerce": 0.0240}


def _df(rows):
    return pd.DataFrame(rows)


def test_published_schedule_has_six_categories():
    assert set(PUBLISHED_SCHEDULE) == {
        "Retail", "Travel", "Dining", "Healthcare", "E-commerce", "Fuel"
    }


def test_within_tolerance_not_flagged():
    df = _df([{
        "merchant_category": "Retail", "interchange_rate": 0.0181,
        "transaction_volume": 1_000_000, "avg_transaction_usd": 50.0,
    }])
    out = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert bool(out.loc[0, "is_exception"]) is False
    assert out.loc[0, "direction"] == "Within tolerance"
    assert out.loc[0, "deviation_bps"] == pytest.approx(1.0)


def test_over_assessment_flagged_with_positive_impact():
    df = _df([{
        "merchant_category": "Retail", "interchange_rate": 0.0210,  # +30 bps
        "transaction_volume": 1_000_000, "avg_transaction_usd": 50.0,
    }])
    out = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert bool(out.loc[0, "is_exception"]) is True
    assert out.loc[0, "deviation_bps"] == pytest.approx(30.0)
    assert out.loc[0, "direction"] == "Over-assessed"
    # (0.0210 - 0.0180) * 1_000_000 * 50 = 150_000
    assert out.loc[0, "financial_impact_usd"] == pytest.approx(150_000.0)


def test_under_assessment_flagged_with_negative_impact():
    df = _df([{
        "merchant_category": "E-commerce", "interchange_rate": 0.0210,  # -30 bps
        "transaction_volume": 2_000_000, "avg_transaction_usd": 40.0,
    }])
    out = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert bool(out.loc[0, "is_exception"]) is True
    assert out.loc[0, "deviation_bps"] == pytest.approx(-30.0)
    assert out.loc[0, "direction"] == "Under-assessed"
    # (0.0210 - 0.0240) * 2_000_000 * 40 = -240_000
    assert out.loc[0, "financial_impact_usd"] == pytest.approx(-240_000.0)


def test_lower_tolerance_flags_more():
    df = _df([{
        "merchant_category": "Retail", "interchange_rate": 0.0190,  # +10 bps
        "transaction_volume": 1_000, "avg_transaction_usd": 10.0,
    }])
    strict = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=5)
    loose = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert bool(strict.loc[0, "is_exception"]) is True
    assert bool(loose.loc[0, "is_exception"]) is False


def test_mixed_rows_count_and_directions():
    df = _df([
        {"merchant_category": "Retail", "interchange_rate": 0.0181,
         "transaction_volume": 1_000, "avg_transaction_usd": 10.0},      # +1 bp within
        {"merchant_category": "Retail", "interchange_rate": 0.0210,
         "transaction_volume": 1_000, "avg_transaction_usd": 10.0},      # +30 over
        {"merchant_category": "E-commerce", "interchange_rate": 0.0200,
         "transaction_volume": 1_000, "avg_transaction_usd": 10.0},      # -40 under
    ])
    out = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert int(out["is_exception"].sum()) == 2
    assert set(out["direction"]) == {"Within tolerance", "Over-assessed", "Under-assessed"}


def test_does_not_mutate_input():
    df = _df([{
        "merchant_category": "Retail", "interchange_rate": 0.0210,
        "transaction_volume": 1_000, "avg_transaction_usd": 10.0,
    }])
    compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert "is_exception" not in df.columns


def test_empty_input_returns_empty_with_columns():
    df = pd.DataFrame(columns=[
        "merchant_category", "interchange_rate",
        "transaction_volume", "avg_transaction_usd",
    ])
    out = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert len(out) == 0
    for col in ["expected_rate", "deviation_bps", "is_exception",
                "financial_impact_usd", "direction"]:
        assert col in out.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_compliance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'utils.compliance'`

- [ ] **Step 3: Write the implementation** — create `streamlit_app/utils/compliance.py`:

```python
import numpy as np
import pandas as pd

# Published interchange schedule — the standard rate each merchant category
# should be assessed (the "rate card" compliance is measured against).
PUBLISHED_SCHEDULE = {
    "Retail": 0.0180,
    "Travel": 0.0220,
    "Dining": 0.0195,
    "Healthcare": 0.0160,
    "E-commerce": 0.0240,
    "Fuel": 0.0145,
}


def compute_compliance_exceptions(
    df: pd.DataFrame,
    expected_rates: dict,
    tolerance_bps: float,
) -> pd.DataFrame:
    """
    Audit assessed interchange against the published schedule.

    Adds, per row:
      expected_rate         - published rate for the row's merchant_category
      deviation_bps         - (interchange_rate - expected_rate) * 10000 (signed)
      is_exception          - abs(deviation_bps) > tolerance_bps
      financial_impact_usd  - (interchange_rate - expected_rate)
                              * transaction_volume * avg_transaction_usd (signed;
                              positive = over-assessed, negative = under-assessed)
      direction             - "Over-assessed" / "Under-assessed" / "Within tolerance"

    Returns a new DataFrame; the input is not mutated.
    """
    result = df.copy()
    result["expected_rate"] = result["merchant_category"].map(expected_rates)
    rate_delta = result["interchange_rate"] - result["expected_rate"]
    result["deviation_bps"] = rate_delta * 10000
    result["is_exception"] = result["deviation_bps"].abs() > tolerance_bps
    result["financial_impact_usd"] = (
        rate_delta * result["transaction_volume"] * result["avg_transaction_usd"]
    )
    result["direction"] = np.where(
        ~result["is_exception"],
        "Within tolerance",
        np.where(result["deviation_bps"] > 0, "Over-assessed", "Under-assessed"),
    )
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_compliance.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: all pass (existing deal_pnl + opportunity_score tests + 8 new)

- [ ] **Step 6: Commit**

```bash
git add streamlit_app/utils/compliance.py tests/test_compliance.py
git commit -m "feat: add interchange compliance audit pure function with unit tests"
```

---

## Task 2: Inject compliance anomalies into the dataset

**Files:**
- Modify: `streamlit_app/generate_data.py`
- Regenerate: `streamlit_app/data/visa_pricing_metrics.csv`

**Interfaces:**
- Consumes: `PUBLISHED_SCHEDULE`, `compute_compliance_exceptions` (Task 1) — used only for verification.
- Produces: a regenerated CSV (same 9 columns, 2,160 rows) in which ~2–3% of rows are
  materially mis-assessed (≥20 bps off the published schedule), detectable by the Task 1 function.

- [ ] **Step 1: Add a dedicated anomaly RNG** — in `streamlit_app/generate_data.py`, just after the existing line `random.seed(42)` (line 10), add:

```python
# Dedicated RNG for compliance-anomaly injection. Kept separate from the main
# `random` stream so non-anomalous rows are identical to the prior dataset.
anomaly_rng = random.Random(1234)
anomaly_count = 0
```

- [ ] **Step 2: Inject anomalies after the interchange rate is computed** — in the innermost loop, replace this existing block:

```python
                # interchange rate (slight seasonal bump in Q4)
                seasonal = 1.015 if month.month in (10, 11, 12) else 1.0
                interchange_rate = round(
                    cparams["interchange_base"] * seasonal * random.uniform(0.97, 1.03), 4
                )
```

with:

```python
                # interchange rate (slight seasonal bump in Q4)
                seasonal = 1.015 if month.month in (10, 11, 12) else 1.0
                interchange_rate = round(
                    cparams["interchange_base"] * seasonal * random.uniform(0.97, 1.03), 4
                )

                # Compliance anomaly injection: ~2.5% of rows are materially
                # mis-assessed (20-60 bps off the published schedule, either
                # direction) to simulate interchange processing errors for the
                # Compliance Monitor page. Uses a separate RNG so other rows are
                # unchanged. revenue (computed below) reflects the assessed rate.
                if anomaly_rng.random() < 0.025:
                    delta = anomaly_rng.uniform(0.0020, 0.0060) * anomaly_rng.choice([-1, 1])
                    interchange_rate = round(
                        max(0.0010, cparams["interchange_base"] + delta), 4
                    )
                    anomaly_count += 1
```

- [ ] **Step 3: Report the anomaly count** — replace the final line:

```python
print(f"Written {len(rows):,} rows to {out_path}")
```

with:

```python
print(f"Written {len(rows):,} rows to {out_path}")
print(f"Injected {anomaly_count} interchange anomalies")
```

- [ ] **Step 4: Regenerate the dataset**

Run: `cd streamlit_app && python generate_data.py`
Expected: prints `Written 2,160 rows to data/visa_pricing_metrics.csv` and `Injected <N> interchange anomalies` where N is roughly 45–65.

- [ ] **Step 5: Verify the audit function detects the anomalies (and nothing else at default tolerance)**

Run (from `streamlit_app/`):
```bash
python -c "import pandas as pd; from utils.compliance import PUBLISHED_SCHEDULE, compute_compliance_exceptions; df=pd.read_csv('data/visa_pricing_metrics.csv'); out=compute_compliance_exceptions(df, PUBLISHED_SCHEDULE, 15); print('rows', len(out), 'exceptions', int(out['is_exception'].sum()), 'over', int((out['direction']=='Over-assessed').sum()), 'under', int((out['direction']=='Under-assessed').sum()))"
```
Expected: `rows 2160 exceptions <N>` where `<N>` equals the injected count from Step 4 (roughly 45–65), split across over- and under-assessed. (Normal noise stays under 15 bps, so only injected anomalies are flagged.)

- [ ] **Step 6: Commit**

```bash
git add streamlit_app/generate_data.py streamlit_app/data/visa_pricing_metrics.csv
git commit -m "feat: inject interchange anomalies into dataset for compliance monitor"
```

---

## Task 3: Interchange Compliance page + README

**Files:**
- Create: `streamlit_app/pages/4_interchange_compliance.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `PUBLISHED_SCHEDULE`, `compute_compliance_exceptions` (Task 1); the regenerated CSV (Task 2).

- [ ] **Step 1: Create the page** — create `streamlit_app/pages/4_interchange_compliance.py`:

```python
import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
from utils.compliance import PUBLISHED_SCHEDULE, compute_compliance_exceptions

st.set_page_config(page_title="Interchange Compliance", page_icon="🛡️", layout="wide")

# Storytelling-with-Data palette: mute to grey, reserve one accent colour.
GREY = "#bfbfbf"
ACCENT = "#c00000"
TEXT = "#595959"
GRID = "#ebebeb"


def style(chart):
    return (
        chart.configure_view(stroke=None)
        .configure_axis(grid=True, gridColor=GRID, domainColor="#d9d9d9",
                        tickColor="#d9d9d9", labelColor=TEXT, titleColor=TEXT)
        .configure_title(color=TEXT, fontSize=15, anchor="start")
    )


st.title("Interchange Compliance Monitor")
st.caption(
    "Audits assessed interchange against the published rate schedule, flags "
    "deviations beyond tolerance, and quantifies the financial impact."
)


@st.cache_data
def load_data() -> pd.DataFrame:
    path = Path(__file__).parent.parent / "data" / "visa_pricing_metrics.csv"
    return pd.read_csv(path, parse_dates=["month"])


df = load_data()

tolerance_bps = st.slider(
    "Exception tolerance (basis points)",
    min_value=5, max_value=40, value=15, step=1,
    help="Deviations from the published schedule larger than this are flagged "
         "as compliance exceptions.",
)

audited = compute_compliance_exceptions(df, PUBLISHED_SCHEDULE, tolerance_bps)
exceptions = audited[audited["is_exception"]].copy()

# ── KPI cards (most decision-relevant first) ──────────────────────────────────
total_rows = len(audited)
n_exceptions = int(len(exceptions))
compliance_rate = (1 - n_exceptions / total_rows) * 100 if total_rows else 100.0
dollars_at_risk = float(exceptions["financial_impact_usd"].abs().sum())
net_impact = float(exceptions["financial_impact_usd"].sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("Compliance rate", f"{compliance_rate:.1f}%")
k2.metric("Exceptions flagged", f"{n_exceptions:,}")
k3.metric("Total $ at risk", f"${dollars_at_risk / 1e6:.1f}M")
k4.metric("Net $ impact", f"${net_impact / 1e6:+.1f}M")

# ── Narrative takeaway (lead with the story) ──────────────────────────────────
over = exceptions[exceptions["direction"] == "Over-assessed"]
under = exceptions[exceptions["direction"] == "Under-assessed"]
if n_exceptions:
    st.markdown(
        f"**{n_exceptions:,} interchange assessments deviate beyond "
        f"{tolerance_bps} bps from the published schedule — "
        f"${dollars_at_risk / 1e6:.1f}M of assessment at risk "
        f"({len(over):,} over-assessed, {len(under):,} under-assessed).**"
    )
else:
    st.success(
        f"No assessments deviate beyond {tolerance_bps} bps from the published schedule."
    )

# ── Charts + review table ─────────────────────────────────────────────────────
if n_exceptions:
    exceptions["abs_impact"] = exceptions["financial_impact_usd"].abs()
    left, right = st.columns(2)

    with left:
        monthly = exceptions.groupby("month", as_index=False)["abs_impact"].sum()
        line = (
            alt.Chart(monthly)
            .mark_line(color=GREY, point=alt.OverlayMarkDef(color=ACCENT, size=55))
            .encode(
                x=alt.X("month:T", title="Month"),
                y=alt.Y("abs_impact:Q", title="$ at risk",
                        axis=alt.Axis(format="$.2s")),
            )
            .properties(title="Assessment $ at risk over time", height=300)
        )
        st.altair_chart(style(line), use_container_width=True)

    with right:
        by_cat = (
            exceptions.groupby("merchant_category", as_index=False)["abs_impact"].sum()
            .sort_values("abs_impact", ascending=False)
        )
        top_cat = str(by_cat.iloc[0]["merchant_category"])
        bars = (
            alt.Chart(by_cat)
            .mark_bar(size=24)
            .encode(
                y=alt.Y("merchant_category:N", sort="-x", title=None),
                x=alt.X("abs_impact:Q", title="$ at risk",
                        axis=alt.Axis(format="$.2s")),
                color=alt.condition(
                    alt.FieldEqualPredicate(field="merchant_category", equal=top_cat),
                    alt.value(ACCENT), alt.value(GREY),
                ),
            )
            .properties(title="Where exceptions concentrate", height=300)
        )
        st.altair_chart(style(bars), use_container_width=True)

    st.subheader("Flagged for management review")
    review = exceptions.sort_values(
        "financial_impact_usd", key=lambda s: s.abs(), ascending=False
    )
    display_df = pd.DataFrame({
        "Region": review["region"].values,
        "Category": review["merchant_category"].values,
        "Card": review["card_type"].values,
        "Month": review["month"].dt.strftime("%Y-%m").values,
        "Expected": (review["expected_rate"] * 100).map("{:.3f}%".format).values,
        "Actual": (review["interchange_rate"] * 100).map("{:.3f}%".format).values,
        "Deviation (bps)": review["deviation_bps"].map("{:+.0f}".format).values,
        "$ Impact": review["financial_impact_usd"].map("${:,.0f}".format).values,
        "Direction": review["direction"].values,
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)

st.caption(
    "Financial impact = (assessed rate − published rate) × transaction volume × "
    "avg transaction value. Positive = over-assessed (client overcharged); "
    "negative = under-assessed (revenue not collected). Published schedule: "
    + ", ".join(f"{k} {v * 100:.2f}%" for k, v in PUBLISHED_SCHEDULE.items()) + "."
)
```

- [ ] **Step 2: Validate the page logic and chart specs against the real data**

Run (from `streamlit_app/`):
```bash
python -c "
import pandas as pd, altair as alt
from utils.compliance import PUBLISHED_SCHEDULE, compute_compliance_exceptions
df = pd.read_csv('data/visa_pricing_metrics.csv', parse_dates=['month'])
a = compute_compliance_exceptions(df, PUBLISHED_SCHEDULE, 15)
ex = a[a['is_exception']].copy(); ex['abs_impact'] = ex['financial_impact_usd'].abs()
m = ex.groupby('month', as_index=False)['abs_impact'].sum()
c = ex.groupby('merchant_category', as_index=False)['abs_impact'].sum().sort_values('abs_impact', ascending=False)
top = str(c.iloc[0]['merchant_category'])
line = alt.Chart(m).mark_line(point=alt.OverlayMarkDef()).encode(x='month:T', y='abs_impact:Q')
bars = alt.Chart(c).mark_bar().encode(y=alt.Y('merchant_category:N', sort='-x'), x='abs_impact:Q', color=alt.condition(alt.FieldEqualPredicate(field='merchant_category', equal=top), alt.value('#c00000'), alt.value('#bfbfbf')))
assert line.to_dict() and bars.to_dict()
review = ex.sort_values('financial_impact_usd', key=lambda s: s.abs(), ascending=False)
print('exceptions', len(ex), 'top category', top, 'review rows', len(review), 'CHART SPECS OK')
"
```
Expected: prints `exceptions <N> top category <name> review rows <N> CHART SPECS OK` with no traceback.

- [ ] **Step 3: Update the README** — make these edits in `README.md`:

(a) Replace the Dashboard line in the Tech Stack table:
```
| Dashboard | Streamlit (three-page multipage app) |
```
with:
```
| Dashboard | Streamlit (four-page multipage app) |
```

(b) In the "## Dashboard Preview" section, after the Deal Simulator image block (the two lines for `### Deal Simulator` and its image), add:
```

### Interchange Compliance Monitor
Audits assessed interchange against the published rate schedule, flags deviations beyond a configurable tolerance, and quantifies the financial impact (over- vs under-assessment) — with a management-review queue. Tailored to Visa's Global Interchange Strategy / Compliance work.
```

(c) In the "## Repository Structure" tree, replace this line:
```
    │   │   └── 3_ecommerce_targets.py    # Page 3: E-commerce Merchant Targets
```
with:
```
    │   │   ├── 3_ecommerce_targets.py    # Page 3: E-commerce Merchant Targets
    │   │   └── 4_interchange_compliance.py  # Page 4: Interchange Compliance Monitor
```

(d) In the "## Repository Structure" tree, replace this line:
```
    │   │   └── opportunity_score.py      # Merchant opportunity scoring (pure function)
```
with:
```
    │   │   ├── opportunity_score.py      # Merchant opportunity scoring (pure function)
    │   │   └── compliance.py             # Interchange compliance audit (pure function)
```

(e) In the "## Repository Structure" tree, replace this line:
```
    │   └── test_opportunity_score.py     # 7 unit tests for the opportunity score function
```
with:
```
    │   ├── test_opportunity_score.py     # 7 unit tests for the opportunity score function
    │   └── test_compliance.py            # 8 unit tests for the compliance audit function
```

- [ ] **Step 4: Confirm the full test suite still passes**

Run: `pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add streamlit_app/pages/4_interchange_compliance.py README.md
git commit -m "feat: add Interchange Compliance Monitor page and update README"
```

---

## Self-Review (completed during planning)

**Spec coverage:** Published schedule → Task 1 (`PUBLISHED_SCHEDULE`). Pure audit function with all five output columns and the financial-impact sign convention → Task 1. Anomaly injection (~2–3%, ≥20 bps, both directions, reproducible, minimal disruption) → Task 2. Page with tolerance slider, KPI cards, narrative takeaway, trend chart, category concentration chart, and management-review table in SWD styling → Task 3. pytest coverage (within tolerance, both directions, deviation, signed impact, tolerance behaviour, empty edge, no-mutation) → Task 1. README docs → Task 3. All spec sections map to a task.

**Placeholder scan:** No TBD/TODO; every code step has complete code; every command has an expected result.

**Type consistency:** `compute_compliance_exceptions(df, expected_rates, tolerance_bps)` and `PUBLISHED_SCHEDULE` are used identically in Tasks 1–3. Output columns (`expected_rate`, `deviation_bps`, `is_exception`, `financial_impact_usd`, `direction`) referenced by the page and verification match the function's definition. The default tolerance (15 bps) and the injected-anomaly magnitude (≥20 bps) are consistent across spec, generator, and verification so injected anomalies are always flagged while normal noise (≤~11 bps) is not.
