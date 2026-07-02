"""Chart annotation primitives.

Value labels, smart axis formatters, reference lines, callouts, gridlines.
Used by every chart-builder recipe.

Design: small focused helpers, callable from any matplotlib `ax`. No global state.
"""
from __future__ import annotations

from typing import Any

import matplotlib.ticker as mticker
import numpy as np


# --- Smart number formatting ------------------------------------------------

def _abbreviate(value: float, *, currency: str = "", decimals: int = 1) -> str:
    """3500 → '3.5K'. 1_200_000 → '1.2M'. Handles negative + zero."""
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000_000:
        return f"{sign}{currency}{v/1_000_000_000:.{decimals}f}B"
    if v >= 1_000_000:
        return f"{sign}{currency}{v/1_000_000:.{decimals}f}M"
    if v >= 1_000:
        return f"{sign}{currency}{v/1_000:.{decimals}f}K"
    if v == int(v):
        return f"{sign}{currency}{int(v)}"
    return f"{sign}{currency}{v:.{decimals}f}"


def pick_format(values: list[float] | np.ndarray, *, unit: str = "") -> str:
    """Pick the best format string for a series. Returns format-style name:
    'currency', 'percent', 'thousands', 'int', 'float'."""
    if not len(values):
        return "int"
    mx = max(abs(v) for v in values)
    unit_low = unit.lower()
    if "%" in unit or "percent" in unit_low or "rate" in unit_low or (0 < mx <= 1.0 and unit == ""):
        return "percent"
    if "$" in unit or "usd" in unit_low or "gbp" in unit_low or "currency" in unit_low:
        return "currency"
    if mx >= 1000:
        return "thousands"
    if all(float(v).is_integer() for v in values):
        return "int"
    return "float"


def format_value(value: float, fmt: str, *, currency: str = "$") -> str:
    """Format one value per `fmt`."""
    if fmt == "currency":
        return _abbreviate(value, currency=currency)
    if fmt == "percent":
        # If max < 1.0 we assume fraction; else assume already in pct points
        if -1.0 <= value <= 1.0:
            return f"{value*100:.1f}%"
        return f"{value:.1f}%"
    if fmt == "thousands":
        return _abbreviate(value)
    if fmt == "int":
        return f"{int(value):,}"
    return f"{value:,.1f}"


def axis_formatter(fmt: str, *, currency: str = "$") -> mticker.Formatter:
    """Return a matplotlib FuncFormatter that formats axis ticks per `fmt`."""
    def _fn(x, _pos):  # noqa: ANN001
        return format_value(x, fmt, currency=currency)
    return mticker.FuncFormatter(_fn)


# --- Bar / scatter labels ---------------------------------------------------

def label_bars(ax, *, horizontal: bool = False, fmt: str = "int",
               currency: str = "$", color: str | None = None,
               offset: float = 0.02) -> None:
    """Label every bar with its value. Horizontal = labels to the right of bar."""
    rects = [c for c in ax.containers if hasattr(c, "patches")]
    if not rects:
        rects = [ax.patches]
    # Compute axis-relative offset
    if horizontal:
        xmin, xmax = ax.get_xlim()
        pad = (xmax - xmin) * offset
    else:
        ymin, ymax = ax.get_ylim()
        pad = (ymax - ymin) * offset
    for rect_set in rects:
        for rect in rect_set:
            if horizontal:
                v = rect.get_width()
                x = v + (pad if v >= 0 else -pad)
                y = rect.get_y() + rect.get_height() / 2
                ha = "left" if v >= 0 else "right"
                va = "center"
            else:
                v = rect.get_height()
                x = rect.get_x() + rect.get_width() / 2
                y = v + (pad if v >= 0 else -pad)
                ha = "center"
                va = "bottom" if v >= 0 else "top"
            ax.text(x, y, format_value(v, fmt, currency=currency),
                    ha=ha, va=va, fontsize=9, color=color or "#111514")


def label_stacked_totals(ax, totals: list[float], *, fmt: str = "int",
                         currency: str = "$", color: str | None = None,
                         offset: float = 0.02) -> None:
    """Label the total above each stacked-bar."""
    ymin, ymax = ax.get_ylim()
    pad = (ymax - ymin) * offset
    xticks = ax.get_xticks()
    for x, total in zip(xticks, totals):
        ax.text(x, total + pad, format_value(total, fmt, currency=currency),
                ha="center", va="bottom", fontsize=9, fontweight="bold",
                color=color or "#111514")


def label_line_endpoints(ax, series: dict[str, list[float]], xs: list,
                         *, fmt: str = "int", currency: str = "$",
                         color: str | None = None, label_extrema: bool = False) -> None:
    """Label the last point of every series; optionally label max/min too."""
    for name, ys in series.items():
        if not ys:
            continue
        # Last point
        ax.annotate(
            format_value(ys[-1], fmt, currency=currency),
            xy=(xs[-1], ys[-1]),
            xytext=(6, 0), textcoords="offset points",
            ha="left", va="center", fontsize=9, color=color or "#111514",
        )
        if label_extrema and len(ys) > 2:
            mx_i = max(range(len(ys)), key=lambda i: ys[i])
            mn_i = min(range(len(ys)), key=lambda i: ys[i])
            if mx_i not in (0, len(ys) - 1):
                ax.annotate(
                    format_value(ys[mx_i], fmt, currency=currency),
                    xy=(xs[mx_i], ys[mx_i]),
                    xytext=(0, 8), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8,
                    color=color or "#111514", fontweight="bold",
                )


# --- Reference lines + callouts --------------------------------------------

def reference_line(ax, value: float, *, axis: str = "y", label: str = "",
                   color: str = "#52605c", style: str = "--", width: float = 0.8) -> None:
    """Horizontal (default) or vertical reference line with optional label."""
    if axis == "y":
        ax.axhline(value, color=color, linestyle=style, linewidth=width, zorder=1)
        if label:
            xlim = ax.get_xlim()
            ax.text(xlim[1], value, f" {label}", ha="left", va="center",
                    fontsize=8, color=color)
    else:
        ax.axvline(value, color=color, linestyle=style, linewidth=width, zorder=1)
        if label:
            ylim = ax.get_ylim()
            ax.text(value, ylim[1], f" {label}", ha="left", va="top",
                    fontsize=8, color=color, rotation=90)


def callout(ax, *, xy: tuple[float, float], text: str,
            xytext: tuple[float, float] = (40, 20),
            color: str = "#b3662f") -> None:
    """Arrow-pointing callout at a datapoint."""
    ax.annotate(
        text, xy=xy, xytext=xytext, textcoords="offset points",
        ha="left", va="center", fontsize=9, color=color, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=color, lw=1.2,
                        connectionstyle="arc3,rad=0.2"),
        bbox=dict(boxstyle="round,pad=0.3", fc="none", ec=color, lw=0.8),
    )


# --- Gridlines + spines -----------------------------------------------------

def light_grid(ax, *, axis: str = "y", color: str = "#dad6cb") -> None:
    """Light minor gridline on the y-axis only (default). Major gridline if axis='both'."""
    if axis == "y":
        ax.yaxis.grid(True, color=color, linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)
    elif axis == "x":
        ax.xaxis.grid(True, color=color, linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)
    else:
        ax.grid(True, color=color, linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)


# --- Color encoding ---------------------------------------------------------

def mute_others(colors: list[str], highlight_idx: int, *, muted: str = "#9aa39d") -> list[str]:
    """Return a copy where every entry except highlight_idx is muted."""
    return [c if i == highlight_idx else muted for i, c in enumerate(colors)]


def semantic_color(value: float, palette: Any, *, baseline: float = 0.0) -> str:
    """Pick accent_secondary for positive, accent_primary for negative."""
    if value >= baseline:
        return palette.accent_secondary
    return palette.accent_primary
