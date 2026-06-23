"""Shared Storytelling-with-Data chart styling.

Mute everything to grey and spend one accent colour on what matters, declutter
the chrome, and keep a soft background grid. Used across all dashboard pages so
the app reads as one intentional product.
"""

import streamlit as st

GREY = "#bfbfbf"
ACCENT = "#c00000"
LINE = "#8c8c8c"
TEXT = "#595959"
GRID = "#ebebeb"
INSIGHT_TEXT = "#3b3b3b"  # darker than st.caption for readable insight lines


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
