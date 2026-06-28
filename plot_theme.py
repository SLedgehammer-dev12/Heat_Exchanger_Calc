from __future__ import annotations

import os

import matplotlib as mpl
import matplotlib.pyplot as plt


def apply_theme() -> None:
    """Apply a modern, clean matplotlib style for all heat exchanger plots.

    Call once at application startup.  After this, every plot inherits the
    same fonts, sizes, grid style, and colour palette.
    """
    if os.environ.get("DISPLAY") is None and os.name != "nt":
        mpl.use("Agg")

    plt.style.use("seaborn-v0_8")

    rc = {
        "font.family": "sans-serif",
        "font.sans-serif": [
            "Inter",
            "SF Pro Display",
            "Segoe UI",
            "system-ui",
            "Helvetica Neue",
            "Arial",
        ],
        "font.size": 11,
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
        "axes.labelsize": 13,
        "axes.labelweight": "bold",
        "axes.facecolor": "#ffffff",
        "axes.edgecolor": "#cbd5e1",
        "axes.linewidth": 1.0,
        "axes.grid": True,
        "axes.grid.which": "major",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": "#e2e8f0",
        "grid.alpha": 0.6,
        "grid.linestyle": "-",
        "grid.linewidth": 0.5,
        "xtick.color": "#64748b",
        "xtick.labelsize": 10,
        "ytick.color": "#64748b",
        "ytick.labelsize": 10,
        "legend.fontsize": 11,
        "legend.frameon": True,
        "legend.fancybox": True,
        "legend.facecolor": "#ffffff",
        "legend.edgecolor": "#cbd5e1",
        "legend.shadow": False,
        "figure.facecolor": "#ffffff",
        "figure.dpi": 120,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.15,
    }
    mpl.rcParams.update(rc)  # type: ignore[arg-type]


PALETTE = {
    "hot_in": "#ef4444",
    "hot_out": "#f97316",
    "cold_in": "#3b82f6",
    "cold_out": "#06b6d4",
    "body_fill": "#f8fafc",
    "body_edge": "#94a3b8",
    "tube_fill": "#cbd5e1",
    "tube_edge": "#64748b",
    "zigzag": "#94a3b8",
    "fill_between": "#fbbf24",
    "grid": "#e2e8f0",
    "text_muted": "#64748b",
    "text_dark": "#1e293b",
    "success": "#22c55e",
    "warning": "#eab308",
}
"""Modern colour palette inspired by Tailwind CSS (slate + primary colours)."""


SCHEMATIC_SIZE = (10, 5)
"""Default figure size for the enhanced schematic (inches)."""

TEMP_PROFILE_SIZE = (9, 4.5)
"""Default figure size for the temperature profile plot (inches)."""
