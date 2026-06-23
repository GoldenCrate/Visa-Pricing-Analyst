"""Shared Storytelling-with-Data chart styling.

Mute everything to grey and spend one accent colour on what matters, declutter
the chrome, and keep a soft background grid. Used across all dashboard pages so
the app reads as one intentional product.
"""

import streamlit as st

GREY = "#bfbfbf"
ACCENT = "#c00000"   # red — risk / problem framing (gaps, exceptions, $ at risk)
BLUE = "#1434cb"     # Visa blue — opportunity / positive framing (headroom, top performers)
LINE = "#8c8c8c"
TEXT = "#595959"
GRID = "#ebebeb"
INSIGHT_TEXT = "#3b3b3b"  # darker than st.caption for readable insight lines


def fmt_big(value: float, money: bool = False) -> str:
    """Human-readable magnitude: 5.42B, $6.51B, 812.3M, $45.0K.

    Uses a consistent threshold so values never read as e.g. '5421.2M'.
    """
    prefix = "$" if money else ""
    a = abs(value)
    if a >= 1e9:
        return f"{prefix}{value / 1e9:.2f}B"
    if a >= 1e6:
        return f"{prefix}{value / 1e6:.1f}M"
    if a >= 1e3:
        return f"{prefix}{value / 1e3:.1f}K"
    return f"{prefix}{value:,.0f}"


def insight(text: str) -> None:
    """Render a readable one-line insight under a chart.

    Higher contrast than st.caption (which is low-opacity grey). Accepts simple
    inline HTML such as <b>...</b> for emphasis.
    """
    st.markdown(
        f"<p style='font-size:0.9rem; color:{INSIGHT_TEXT}; line-height:1.45; "
        f"margin-top:-0.4rem'>{text}</p>",
        unsafe_allow_html=True,
    )


def style(chart):
    """Apply the shared decluttered, gridded styling to an Altair chart."""
    return (
        chart.configure_view(stroke=None)
        .configure_axis(
            grid=True,
            gridColor=GRID,
            domainColor="#d9d9d9",
            tickColor="#d9d9d9",
            labelColor=TEXT,
            titleColor=TEXT,
        )
        .configure_title(color=TEXT, fontSize=15, anchor="start")
    )
