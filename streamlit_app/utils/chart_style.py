"""Shared Storytelling-with-Data chart styling.

Mute everything to grey and spend one accent colour on what matters, declutter
the chrome, and keep a soft background grid. Used across all dashboard pages so
the app reads as one intentional product.
"""

GREY = "#bfbfbf"
ACCENT = "#c00000"
LINE = "#8c8c8c"
TEXT = "#595959"
GRID = "#ebebeb"


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
