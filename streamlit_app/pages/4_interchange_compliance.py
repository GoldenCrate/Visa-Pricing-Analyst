import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
from utils.compliance import PUBLISHED_SCHEDULE, compute_compliance_exceptions
from utils.chart_style import ACCENT, GREY, LINE, style

st.set_page_config(page_title="Interchange Compliance", page_icon="🛡️", layout="wide")

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

# KPI cards (most decision-relevant first)
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

# Lead with the takeaway
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

if n_exceptions:
    exceptions["abs_impact"] = exceptions["financial_impact_usd"].abs()
    left, right = st.columns(2)

    with left:
        monthly = exceptions.groupby("month", as_index=False)["abs_impact"].sum()
        monthly["is_peak"] = monthly["abs_impact"] == monthly["abs_impact"].max()
        base = alt.Chart(monthly).encode(
            x=alt.X("month:T", title="Month"),
            y=alt.Y("abs_impact:Q", title="$ at risk", axis=alt.Axis(format="$.2s")),
        )
        line = base.mark_line(color=LINE)
        points = base.mark_point(filled=True, size=70).encode(
            color=alt.condition(
                "datum.is_peak", alt.value(ACCENT), alt.value(GREY)
            ),
        )
        trend = (line + points).properties(
            title="Assessment $ at risk over time", height=300
        )
        st.altair_chart(style(trend), use_container_width=True)
        st.caption(
            "The red point marks the month of greatest assessment exposure — "
            "start the investigation there to find what drove the spike."
        )

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
        st.caption(
            f"**{top_cat}** concentrates the most assessment at risk — "
            "prioritise compliance review and root-cause analysis there."
        )

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
