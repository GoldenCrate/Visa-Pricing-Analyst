import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
from utils.opportunity_score import compute_opportunity_score
from utils.chart_style import ACCENT, GREY, style

st.set_page_config(page_title="E-commerce Targets", page_icon="🎯", layout="wide")

st.title("E-commerce Merchant Targets")
st.caption(
    "Merchants ranked by deal opportunity score — combines volume, "
    "growth trajectory, and network improvement potential."
)

# ── Load merchant data ────────────────────────────────────────────────────────
@st.cache_data
def load_merchants() -> pd.DataFrame:
    path = Path(__file__).parent.parent / "data" / "ecommerce_merchants.csv"
    return pd.read_csv(path)

df = load_merchants()

# ── Compute opportunity scores ────────────────────────────────────────────────
df["raw_score"] = df.apply(
    lambda r: compute_opportunity_score(
        annual_volume_m=r["annual_volume_m"],
        avg_transaction_usd=r["avg_transaction_usd"],
        interchange_rate=r["interchange_rate"],
        acceptance_rate=r["acceptance_rate"],
        yoy_growth_rate=r["yoy_growth_rate"],
    ),
    axis=1,
)

# Normalize to 0–100
min_s, max_s = df["raw_score"].min(), df["raw_score"].max()
df["score"] = ((df["raw_score"] - min_s) / (max_s - min_s) * 100).round(1)

df = df.sort_values("score", ascending=False).reset_index(drop=True)

# Priority tiers
df["priority"] = pd.cut(
    df["score"],
    bins=[-1, 34, 64, 100],
    labels=["Low", "Medium", "High"],
)

# ── KPI cards ─────────────────────────────────────────────────────────────────
total_volume = df["annual_volume_m"].sum()
high_priority_count = (df["priority"] == "High").sum()

k1, k2, k3 = st.columns(3)
k1.metric("Total Addressable Volume", f"{total_volume:.0f}M txns/yr")
k2.metric("High-Priority Targets", f"{high_priority_count} merchants")
k3.metric("Avg Interchange Rate", f"{df['interchange_rate'].mean() * 100:.3f}%")

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("Opportunity Score by Merchant")
    bar = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("score:Q", title="Opportunity Score (0–100)"),
            y=alt.Y("merchant_name:N", sort="-x", title=""),
            color=alt.condition(
                alt.FieldEqualPredicate(field="priority", equal="High"),
                alt.value(ACCENT), alt.value(GREY),
            ),
            tooltip=[
                alt.Tooltip("merchant_name:N", title="Merchant"),
                alt.Tooltip("score:Q", title="Score", format=".1f"),
                alt.Tooltip("priority:N", title="Priority"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(style(bar), use_container_width=True)
    st.caption(
        "High-priority targets (red) combine large volume, strong growth, and "
        "acceptance headroom — begin deal outreach at the top of this list."
    )

with col2:
    st.subheader("Volume vs Acceptance Rate")
    scatter = (
        alt.Chart(df)
        .mark_circle()
        .encode(
            x=alt.X("acceptance_rate:Q", title="Acceptance Rate",
                     axis=alt.Axis(format=".0%"), scale=alt.Scale(zero=False)),
            y=alt.Y("annual_volume_m:Q", title="Annual Volume (M txns)"),
            size=alt.Size("score:Q", title="Opportunity Score",
                          scale=alt.Scale(range=[100, 1200])),
            color=alt.condition(
                alt.FieldEqualPredicate(field="priority", equal="High"),
                alt.value(ACCENT), alt.value(GREY),
            ),
            tooltip=[
                alt.Tooltip("merchant_name:N", title="Merchant"),
                alt.Tooltip("annual_volume_m:Q", title="Volume (M)", format=".0f"),
                alt.Tooltip("acceptance_rate:Q", title="Acceptance Rate", format=".1%"),
                alt.Tooltip("score:Q", title="Score", format=".1f"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(style(scatter), use_container_width=True)
    st.caption(
        "Top-right = high volume; further left = lower acceptance (more upside to "
        "win). The largest red dots are the highest-scoring, high-priority targets."
    )

# ── Ranked table ──────────────────────────────────────────────────────────────
st.subheader("Ranked Merchant Table")

display_df = pd.DataFrame({
    "Rank": range(1, len(df) + 1),
    "Merchant": df["merchant_name"].values,
    "Region": df["region"].values,
    "Volume (M txns/yr)": df["annual_volume_m"].map("{:.0f}".format).values,
    "Avg Transaction": df["avg_transaction_usd"].map("${:.0f}".format).values,
    "Acceptance Rate": df["acceptance_rate"].map("{:.1%}".format).values,
    "YoY Growth": df["yoy_growth_rate"].map("{:.0%}".format).values,
    "Interchange Rate": df["interchange_rate"].map("{:.3%}".format).values,
    "Score": df["score"].map("{:.1f}".format).values,
    "Priority": df["priority"].astype(str).values,
})

st.dataframe(display_df, use_container_width=True, hide_index=True)

st.caption(
    "Opportunity Score = gross revenue potential × growth multiplier × network gap multiplier. "
    "Network gap = 2 − acceptance rate (lower acceptance = more upside from network improvements). "
    "Scores normalized 0–100 across this merchant set."
)
