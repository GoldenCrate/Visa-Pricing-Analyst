import streamlit as st
import pandas as pd
import altair as alt
from utils.data_loader import load_data
from utils.chart_style import ACCENT, GREY, LINE, insight, style

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Market Overview",
    page_icon="💳",
    layout="wide",
)

# ── Load data ─────────────────────────────────────────────────────────────────
df = load_data()

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.title("Filters")

all_regions = sorted(df["region"].unique())
selected_regions = st.sidebar.multiselect("Region", all_regions, default=all_regions)

all_categories = sorted(df["merchant_category"].unique())
selected_categories = st.sidebar.multiselect(
    "Merchant Category", all_categories, default=all_categories
)

all_card_types = sorted(df["card_type"].unique())
selected_card_types = st.sidebar.multiselect(
    "Card Type", all_card_types, default=all_card_types
)

min_date = df["month"].min().to_pydatetime()
max_date = df["month"].max().to_pydatetime()
date_range = st.sidebar.slider(
    "Date Range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    format="MMM YYYY",
)

# ── Apply filters ─────────────────────────────────────────────────────────────
mask = (
    df["region"].isin(selected_regions)
    & df["merchant_category"].isin(selected_categories)
    & df["card_type"].isin(selected_card_types)
    & df["month"].between(date_range[0], date_range[1])
)
filtered = df[mask].copy()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Visa Pricing Analytics Dashboard")
st.caption("Synthesized data — built to demonstrate pricing strategy analytics skills.")

if filtered.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── KPI cards ─────────────────────────────────────────────────────────────────
total_volume   = filtered["transaction_volume"].sum()
total_revenue  = filtered["revenue_usd"].sum()
avg_interchange = (
    (filtered["interchange_rate"] * filtered["transaction_volume"]).sum()
    / filtered["transaction_volume"].sum()
)
avg_acceptance  = filtered["acceptance_rate"].mean()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Transactions",   f"{total_volume / 1_000_000:.1f}M")
k2.metric("Total Revenue",        f"${total_revenue / 1_000_000:.1f}M")
k3.metric("Avg Interchange Rate", f"{avg_interchange * 100:.2f}%")
k4.metric("Avg Acceptance Rate",  f"{avg_acceptance * 100:.2f}%")

st.divider()

# ── Row 1: Volume over time │ Interchange rate by category ────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("Transaction Volume Over Time")
    vol_by_month = (
        filtered.groupby("month", as_index=False)["transaction_volume"]
        .sum()
        .rename(columns={"transaction_volume": "volume"})
    )
    chart_vol = (
        alt.Chart(vol_by_month)
        .mark_line(color=LINE, point=alt.OverlayMarkDef(color=LINE))
        .encode(
            x=alt.X("month:T", title="Month"),
            y=alt.Y("volume:Q", title="Transactions", axis=alt.Axis(format=".2s")),
            tooltip=[
                alt.Tooltip("month:T", title="Month", format="%b %Y"),
                alt.Tooltip("volume:Q", title="Transactions", format=","),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(style(chart_vol), use_container_width=True)
    insight(
        "What to look for: the overall trend — steady growth signals expanding "
        "network volume; flat or dipping stretches flag seasonal or regional softness."
    )

with col2:
    st.subheader("Avg Interchange Rate by Merchant Category")
    ir_by_cat = (
        filtered.groupby("merchant_category", as_index=False)["interchange_rate"]
        .mean()
        .sort_values("interchange_rate", ascending=False)
    )
    ir_by_cat["rate_pct"] = ir_by_cat["interchange_rate"] * 100
    top_category = str(ir_by_cat.iloc[0]["merchant_category"])  # highest rate
    chart_ir = (
        alt.Chart(ir_by_cat)
        .mark_bar()
        .encode(
            x=alt.X("rate_pct:Q", title="Interchange Rate (%)"),
            y=alt.Y("merchant_category:N", sort="-x", title=""),
            color=alt.condition(
                alt.FieldEqualPredicate(field="merchant_category", equal=top_category),
                alt.value(ACCENT), alt.value(GREY),
            ),
            tooltip=[
                alt.Tooltip("merchant_category:N", title="Category"),
                alt.Tooltip("rate_pct:Q", title="Rate (%)", format=".3f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(style(chart_ir), use_container_width=True)
    insight(
        f"<b>{top_category}</b> carries the highest interchange rate — the category "
        "with the most revenue headroom per transaction to structure deals around."
    )

# ── Row 2: Acceptance rate by region │ Revenue by card type ───────────────────
col3, col4 = st.columns(2)

with col3:
    st.subheader("Avg Acceptance Rate by Region")
    acc_by_region = (
        filtered.groupby("region", as_index=False)["acceptance_rate"]
        .mean()
        .sort_values("acceptance_rate", ascending=False)
    )
    acc_by_region["accept_pct"] = acc_by_region["acceptance_rate"] * 100
    lowest_region = str(acc_by_region.iloc[-1]["region"])  # lowest acceptance = the gap
    chart_acc = (
        alt.Chart(acc_by_region)
        .mark_bar()
        .encode(
            x=alt.X("accept_pct:Q", title="Acceptance Rate (%)", scale=alt.Scale(zero=False)),
            y=alt.Y("region:N", sort="-x", title=""),
            color=alt.condition(
                alt.FieldEqualPredicate(field="region", equal=lowest_region),
                alt.value(ACCENT), alt.value(GREY),
            ),
            tooltip=[
                alt.Tooltip("region:N", title="Region"),
                alt.Tooltip("accept_pct:Q", title="Acceptance Rate (%)", format=".2f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(style(chart_acc), use_container_width=True)
    insight(
        f"<b>{lowest_region}</b> has the lowest acceptance rate — the biggest "
        "network-improvement opportunity and the most revenue left on the table."
    )

with col4:
    st.subheader("Revenue Share by Card Type")
    rev_by_card = (
        filtered.groupby("card_type", as_index=False)["revenue_usd"]
        .sum()
        .sort_values("revenue_usd", ascending=False)
    )
    rev_by_card["revenue_m"] = rev_by_card["revenue_usd"] / 1_000_000
    rev_by_card["share_pct"] = (
        rev_by_card["revenue_usd"] / rev_by_card["revenue_usd"].sum() * 100
    )
    top_card = str(rev_by_card.iloc[0]["card_type"])  # largest revenue share
    chart_rev = (
        alt.Chart(rev_by_card)
        .mark_bar()
        .encode(
            x=alt.X("share_pct:Q", title="Share of Revenue (%)"),
            y=alt.Y("card_type:N", sort="-x", title=""),
            color=alt.condition(
                alt.FieldEqualPredicate(field="card_type", equal=top_card),
                alt.value(ACCENT), alt.value(GREY),
            ),
            tooltip=[
                alt.Tooltip("card_type:N", title="Card Type"),
                alt.Tooltip("share_pct:Q", title="Share (%)", format=".1f"),
                alt.Tooltip("revenue_m:Q", title="Revenue ($M)", format=".1f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(style(chart_rev), use_container_width=True)
    insight(
        f"<b>{top_card}</b> drives the largest share of revenue — the card type "
        "where a pricing change moves the needle most."
    )

# ── Row 3: Raw data expander ───────────────────────────────────────────────────
with st.expander("View raw data"):
    st.dataframe(
        filtered.sort_values(["month", "region", "merchant_category"]),
        use_container_width=True,
        height=350,
    )
