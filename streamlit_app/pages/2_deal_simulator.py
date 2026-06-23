import streamlit as st
import pandas as pd
import altair as alt
from utils.data_loader import load_data
from utils.deal_pnl import compute_deal_pnl
from utils.chart_style import BLUE, GREY, insight, style

st.set_page_config(page_title="Deal Simulator", page_icon="🤝", layout="wide")

st.title("Deal Simulator")
st.caption(
    "Model the P&L of a merchant acceptance deal. "
    "Baseline interchange rates are derived from historical data."
)

df = load_data()

left, right = st.columns([1, 2])

with left:
    st.subheader("Deal Inputs")
    merchant_name = st.text_input("Merchant Name", value="Acme Retail Co.")
    category = st.selectbox("Merchant Category", sorted(df["merchant_category"].unique()))
    region = st.selectbox("Region", sorted(df["region"].unique()))
    deal_term = st.slider("Deal Term (years)", min_value=1, max_value=5, value=3)
    committed_volume_m = st.number_input(
        "Committed Annual Volume (M transactions)",
        min_value=1.0,
        max_value=500.0,
        value=50.0,
        step=1.0,
    )
    discount_pct = st.slider("Discount Rate off Standard Interchange (%)", 0, 30, 10)
    growth_pct = st.slider("Expected Volume Growth Rate (% YoY)", 0, 20, 5)

segment_mask = (df["merchant_category"] == category) & (df["region"] == region)
segment_df = df[segment_mask] if segment_mask.any() else df
baseline_rate = segment_df["interchange_rate"].mean()
avg_txn_usd = segment_df["avg_transaction_usd"].mean()

discount_rate = discount_pct / 100
growth_rate = growth_pct / 100

pnl_df = compute_deal_pnl(
    baseline_interchange_rate=baseline_rate,
    committed_volume_m=committed_volume_m,
    avg_transaction_usd=avg_txn_usd,
    discount_rate=discount_rate,
    deal_term_years=deal_term,
    volume_growth_rate=growth_rate,
)

total_net_revenue = pnl_df["net_revenue"].sum()
deal_npv = pnl_df["npv_contribution"].sum()

# Volume uplift needed so that discounted revenue = un-discounted revenue at committed volume.
# Derivation: V_committed x rate = V_needed x rate x (1 - discount)
#             V_needed = V_committed / (1 - discount)
#             Uplift   = V_needed - V_committed
breakeven_uplift_m = (
    committed_volume_m / (1 - discount_rate) - committed_volume_m
    if discount_rate < 1
    else float("inf")
)

with right:
    st.subheader(f"Deal Output: {merchant_name}")

    if discount_pct <= 10:
        st.success("Favorable — within standard pricing band")
    elif discount_pct <= 20:
        st.warning("Conditional — requires volume commitment verification")
    else:
        st.error("Requires senior approval — above standard discount threshold")

    k1, k2, k3 = st.columns(3)
    k1.metric("Total Net Revenue", f"${total_net_revenue / 1_000_000:.1f}M")
    k2.metric("Deal NPV (8% hurdle)", f"${deal_npv / 1_000_000:.1f}M")
    k3.metric(
        "Volume Uplift to Break Even",
        f"{breakeven_uplift_m:.1f}M txns/yr",
        help=(
            "Additional annual volume the merchant must bring to offset this discount. "
            "Formula: committed_volume / (1 - discount_rate) - committed_volume"
        ),
    )

    st.divider()

    chart_data = pnl_df[["year", "gross_revenue", "net_revenue"]].melt(
        id_vars="year", var_name="type", value_name="revenue"
    )
    chart_data["revenue_m"] = chart_data["revenue"] / 1_000_000
    chart_data["type"] = chart_data["type"].map(
        {"gross_revenue": "Gross Revenue", "net_revenue": "Net Revenue"}
    )

    bar_chart = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            x=alt.X("year:O", title="Year"),
            y=alt.Y("revenue_m:Q", title="Revenue (USD M)"),
            color=alt.Color(
                "type:N", title="",
                scale=alt.Scale(
                    domain=["Net Revenue", "Gross Revenue"],
                    range=[BLUE, GREY],
                ),
            ),
            xOffset="type:N",
            tooltip=[
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip("type:N", title="Type"),
                alt.Tooltip("revenue_m:Q", title="Revenue ($M)", format=".2f"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(style(bar_chart), use_container_width=True)
    insight(
        "Net revenue (blue) is what remains after the discount; the gap to gross "
        "is the deal's cost. Watch whether net still grows across the term — if it "
        "shrinks, the discount is outpacing volume growth."
    )

    st.subheader("Year-by-Year P&L")
    display_df = pd.DataFrame({
        "Year": pnl_df["year"],
        "Volume (M txns)": pnl_df["volume_m"].map("{:.1f}".format),
        "Gross Revenue": pnl_df["gross_revenue"].map("${:,.0f}".format),
        "Discount Cost": pnl_df["discount_cost"].map("${:,.0f}".format),
        "Net Revenue": pnl_df["net_revenue"].map("${:,.0f}".format),
        "NPV Contribution": pnl_df["npv_contribution"].map("${:,.0f}".format),
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.caption(
        f"Baseline interchange rate for {category} / {region}: "
        f"{baseline_rate * 100:.3f}% | Avg transaction: ${avg_txn_usd:.2f}"
    )
