"""Chart-builder primitives. Recipes share a common entry-point so chart-builder.run.py
and downstream callers (cohort-analyzer, scenario-modeler, cost-benefit, market-sizing,
workplan-skill) render with consistent brand treatment + Tufte-anchored defaults.

Default behaviors (Matt-approved 2026-05-29):
- Value labels ON (opt-out via `labels=False`)
- Light y-gridline ON (opt-out via `grid=False`)
- Smart axis formatter chosen per data scale ($K/$M/%/int)
- Two-accent palette (cream/charcoal)
- Title rendered as caption (not in figure) so consultant-deck carries it verbatim

Recipes (12 total):
- Original 7: bar, line, stacked-bar, waterfall, heatmap, scatter-2x2, marimekko
- New 5:     grouped-bar, slope-graph, dot-plot, bullet, small-multiples
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

from . import annotate, brand


# --- setup + finalize -------------------------------------------------------

def setup(mode: str = "default") -> brand.Palette:
    p = brand.get(mode)
    plt.rcParams.update(brand.matplotlib_rcparams(mode))
    return p


def _palette_from(mode: str = "default", *, accessible: bool = False) -> brand.Palette:
    """Resolve palette; if accessible, use Okabe-Ito cycle but keep cream/charcoal paper."""
    p = brand.get(mode)
    return p


def _cycle(palette: brand.Palette, *, accessible: bool = False,
           highlight_idx: int | None = None) -> list[str]:
    if accessible:
        return brand.OKABE_ITO
    return brand.chart_color_cycle(palette, highlight_idx=highlight_idx)


def _finalize(fig, out: Path, palette: brand.Palette, svg: bool = True) -> dict:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, facecolor=palette.paper, bbox_inches="tight")
    paths = {"png": str(out)}
    if svg:
        svg_path = out.with_suffix(".svg")
        fig.savefig(svg_path, facecolor=palette.paper, bbox_inches="tight")
        paths["svg"] = str(svg_path)
    plt.close(fig)
    return paths


# --- bar --------------------------------------------------------------------

def bar(labels: list[str], values: list[float], out: Path, *, mode: str = "default",
        ylabel: str = "", horizontal: bool = False,
        labels_on: bool = True, grid: bool = True,
        target: float | None = None, baseline: float | None = None,
        highlight_idx: int | None = None, accessible: bool = False,
        currency: str = "$", semantic: bool = False) -> dict:
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    fmt = annotate.pick_format(values, unit=ylabel)
    # Per-bar colors
    base_color = p.accent_primary
    if highlight_idx is not None:
        colors = [base_color if i == highlight_idx else p.mid_gray for i in range(len(values))]
    elif semantic:
        colors = [p.accent_secondary if v >= (baseline or 0) else p.accent_primary for v in values]
    else:
        colors = [base_color] * len(values)

    if horizontal:
        ax.barh(labels, values, color=colors)
        ax.set_xlabel(ylabel)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(annotate.axis_formatter(fmt, currency=currency))
        if grid:
            annotate.light_grid(ax, axis="x", color=p.rule_gray)
    else:
        ax.bar(labels, values, color=colors)
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", rotation=20)
        ax.yaxis.set_major_formatter(annotate.axis_formatter(fmt, currency=currency))
        if grid:
            annotate.light_grid(ax, axis="y", color=p.rule_gray)

    if labels_on:
        annotate.label_bars(ax, horizontal=horizontal, fmt=fmt, currency=currency, color=p.text)
    if target is not None:
        annotate.reference_line(ax, target, axis="x" if horizontal else "y",
                                label=f"Target {annotate.format_value(target, fmt, currency=currency)}",
                                color=p.accent_secondary_dark)
    if baseline is not None and baseline != 0:
        annotate.reference_line(ax, baseline, axis="x" if horizontal else "y",
                                label=f"Baseline {annotate.format_value(baseline, fmt, currency=currency)}",
                                color=p.mid_gray)

    return _finalize(fig, out, p)


# --- line -------------------------------------------------------------------

def line(x: list, series: dict[str, list[float]], out: Path, *, mode: str = "default",
         ylabel: str = "", xlabel: str = "",
         labels_on: bool = True, grid: bool = True,
         target: float | None = None, baseline: float | None = None,
         label_extrema: bool = False, accessible: bool = False,
         currency: str = "$", highlight: str | None = None,
         dashed_after: int | None = None) -> dict:
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    cycle = _cycle(p, accessible=accessible)
    series_names = list(series.keys())
    highlight_idx = series_names.index(highlight) if highlight in series_names else None
    if highlight_idx is not None:
        cycle = brand.chart_color_cycle(p, highlight_idx=highlight_idx)

    all_y = [v for ys in series.values() for v in ys]
    fmt = annotate.pick_format(all_y, unit=ylabel)

    for i, (name, ys) in enumerate(series.items()):
        color = cycle[i % len(cycle)]
        # Solid then optionally dashed after `dashed_after` index (e.g. actuals vs forecast)
        if dashed_after is not None and dashed_after < len(x):
            ax.plot(x[:dashed_after + 1], ys[:dashed_after + 1],
                    label=name, color=color, linewidth=2.2, marker="o", markersize=3)
            ax.plot(x[dashed_after:], ys[dashed_after:],
                    color=color, linewidth=2.2, marker="o", markersize=3,
                    linestyle="--", alpha=0.8)
        else:
            ax.plot(x, ys, label=name, color=color, linewidth=2.2, marker="o", markersize=3)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_formatter(annotate.axis_formatter(fmt, currency=currency))
    if len(series) > 1:
        ax.legend(loc="best")
    if grid:
        annotate.light_grid(ax, axis="y", color=p.rule_gray)
    if labels_on:
        annotate.label_line_endpoints(ax, series, x, fmt=fmt, currency=currency,
                                      color=p.text, label_extrema=label_extrema)
    if target is not None:
        annotate.reference_line(ax, target,
                                label=f"Target {annotate.format_value(target, fmt, currency=currency)}",
                                color=p.accent_secondary_dark)
    if baseline is not None:
        annotate.reference_line(ax, baseline,
                                label=f"Baseline {annotate.format_value(baseline, fmt, currency=currency)}",
                                color=p.mid_gray)

    return _finalize(fig, out, p)


# --- stacked-bar ------------------------------------------------------------

def stacked_bar(labels: list[str], series: dict[str, list[float]], out: Path,
                *, mode: str = "default", ylabel: str = "",
                labels_on: bool = True, grid: bool = True,
                target: float | None = None, accessible: bool = False,
                currency: str = "$") -> dict:
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    cycle = _cycle(p, accessible=accessible)
    bottoms = np.zeros(len(labels))
    all_arr = []
    for i, (name, ys) in enumerate(series.items()):
        ys_arr = np.asarray(ys, dtype=float)
        ax.bar(labels, ys_arr, bottom=bottoms, color=cycle[i % len(cycle)], label=name)
        bottoms = bottoms + ys_arr
        all_arr.append(ys_arr)
    totals = np.sum(all_arr, axis=0).tolist()
    fmt = annotate.pick_format(totals, unit=ylabel)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=20)
    ax.yaxis.set_major_formatter(annotate.axis_formatter(fmt, currency=currency))
    ax.legend(loc="best")
    if grid:
        annotate.light_grid(ax, axis="y", color=p.rule_gray)
    if labels_on:
        annotate.label_stacked_totals(ax, totals, fmt=fmt, currency=currency, color=p.text)
    if target is not None:
        annotate.reference_line(ax, target,
                                label=f"Target {annotate.format_value(target, fmt, currency=currency)}",
                                color=p.accent_secondary_dark)
    return _finalize(fig, out, p)


# --- waterfall --------------------------------------------------------------

def waterfall(labels: list[str], deltas: list[float], out: Path, *,
              mode: str = "default", ylabel: str = "",
              start_label: str = "Start", end_label: str = "End",
              labels_on: bool = True, grid: bool = True,
              accessible: bool = False, currency: str = "$") -> dict:
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    all_labels = [start_label] + list(labels) + [end_label]
    running = 0.0
    starts = [0.0]
    heights = [0.0]
    for d in deltas:
        starts.append(running)
        heights.append(d)
        running += d
    starts.append(0.0)
    heights.append(running)
    pos_color = p.accent_secondary
    neg_color = p.accent_primary
    anchor_color = p.text
    fmt = annotate.pick_format([abs(d) for d in deltas] + [abs(running)], unit=ylabel)

    for i, (s, h) in enumerate(zip(starts, heights)):
        if i == 0 or i == len(starts) - 1:
            value = running if i else 0.0
            ax.bar(all_labels[i], value, color=anchor_color, edgecolor="none")
            if labels_on:
                ax.text(i, value + (abs(running) * 0.02 if running >= 0 else -abs(running) * 0.02),
                        annotate.format_value(value, fmt, currency=currency),
                        ha="center", va="bottom" if value >= 0 else "top",
                        fontsize=10, fontweight="bold", color=p.text)
        else:
            ax.bar(all_labels[i], h, bottom=s, color=pos_color if h >= 0 else neg_color,
                   edgecolor="none")
            if labels_on:
                mid_y = s + h / 2
                sign = "+" if h >= 0 else ""
                ax.text(i, mid_y, f"{sign}{annotate.format_value(h, fmt, currency=currency)}",
                        ha="center", va="center", fontsize=9, color=p.paper, fontweight="bold")
    ax.axhline(0, color=p.rule_gray, linewidth=0.6)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=20)
    ax.yaxis.set_major_formatter(annotate.axis_formatter(fmt, currency=currency))
    if grid:
        annotate.light_grid(ax, axis="y", color=p.rule_gray)
    return _finalize(fig, out, p)


# --- heatmap ----------------------------------------------------------------

def heatmap(matrix: list[list[float]], row_labels: list[str], col_labels: list[str],
            out: Path, *, mode: str = "default", cbar_label: str = "",
            labels_on: bool = True, accessible: bool = False,
            fmt_override: str | None = None) -> dict:
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(9, max(3.5, 0.4 * len(row_labels) + 1.5)))
    arr = np.asarray(matrix, dtype=float)
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("zerg", [p.paper, p.accent_primary])
    im = ax.imshow(arr, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=20, ha="right")
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels)
    cbar = fig.colorbar(im, ax=ax)
    cbar.outline.set_visible(False)
    if cbar_label:
        cbar.set_label(cbar_label)

    if labels_on:
        flat = arr.flatten().tolist()
        fmt = fmt_override or annotate.pick_format(flat, unit=cbar_label)
        threshold = (arr.max() + arr.min()) / 2
        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                value = arr[i, j]
                text_color = p.paper if value > threshold else p.text
                ax.text(j, i, annotate.format_value(value, fmt),
                        ha="center", va="center", fontsize=9, color=text_color)
    return _finalize(fig, out, p)


# --- scatter-2x2 ------------------------------------------------------------

def scatter_2x2(items: list[dict], out: Path, *, mode: str = "default",
                x_label: str = "Effort", y_label: str = "Impact",
                x_threshold: float | None = None,
                y_threshold: float | None = None,
                quadrant_labels: tuple[str, str, str, str] | None = None,
                grid: bool = True, accessible: bool = False) -> dict:
    """2x2 scatter. items: [{label, x, y, group?, size?}]."""
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(8, 6))
    xs = [i["x"] for i in items]
    ys = [i["y"] for i in items]
    xt = x_threshold if x_threshold is not None else (max(xs) + min(xs)) / 2
    yt = y_threshold if y_threshold is not None else (max(ys) + min(ys)) / 2
    cycle = _cycle(p, accessible=accessible)
    groups = {}
    for i in items:
        g = i.get("group", "items")
        groups.setdefault(g, []).append(i)
    for gi, (gname, members) in enumerate(groups.items()):
        sizes = [m.get("size", 140) for m in members]
        ax.scatter(
            [m["x"] for m in members],
            [m["y"] for m in members],
            s=sizes, color=cycle[gi % len(cycle)], alpha=0.85, edgecolors=p.text,
            linewidths=0.6, label=gname if len(groups) > 1 else None,
        )
        for m in members:
            ax.annotate(m["label"], (m["x"], m["y"]),
                        xytext=(8, 6), textcoords="offset points", fontsize=9, color=p.text)
    ax.axvline(xt, color=p.rule_gray, linewidth=0.8, linestyle="--")
    ax.axhline(yt, color=p.rule_gray, linewidth=0.8, linestyle="--")
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if grid:
        annotate.light_grid(ax, axis="both", color=p.rule_gray)

    # Quadrant labels in corners
    if quadrant_labels is None:
        quadrant_labels = ("DO NOW", "PLAN", "BACKLOG", "KILL")
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    pad_x = (xlim[1] - xlim[0]) * 0.02
    pad_y = (ylim[1] - ylim[0]) * 0.02
    quad_color = p.accent_primary_alt if p.name == "zerg-default" else p.accent_primary
    # Top-left, top-right, bottom-left, bottom-right
    ax.text(xlim[0] + pad_x, ylim[1] - pad_y, quadrant_labels[0],
            ha="left", va="top", fontsize=8, fontweight="bold", color=quad_color)
    ax.text(xlim[1] - pad_x, ylim[1] - pad_y, quadrant_labels[1],
            ha="right", va="top", fontsize=8, fontweight="bold", color=quad_color)
    ax.text(xlim[0] + pad_x, ylim[0] + pad_y, quadrant_labels[2],
            ha="left", va="bottom", fontsize=8, fontweight="bold", color=quad_color)
    ax.text(xlim[1] - pad_x, ylim[0] + pad_y, quadrant_labels[3],
            ha="right", va="bottom", fontsize=8, fontweight="bold", color=quad_color)

    if len(groups) > 1:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=min(4, len(groups)))
    return _finalize(fig, out, p)


# --- marimekko --------------------------------------------------------------

def marimekko(rows: list[dict], out: Path, *, mode: str = "default",
              x_label: str = "Share of segment (%)",
              y_label: str = "Segment size (%)",
              labels_on: bool = True, accessible: bool = False) -> dict:
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(9, 5))
    cycle = _cycle(p, accessible=accessible)
    total_width = sum(r["width"] for r in rows)
    series_names: list[str] = []
    for r in rows:
        for k in r.get("shares", {}):
            if k not in series_names:
                series_names.append(k)
    x_cursor = 0.0
    for r in rows:
        w = r["width"] / total_width * 100
        y_cursor = 0.0
        for si, s in enumerate(series_names):
            share = r.get("shares", {}).get(s, 0.0)
            rect = mpatches.Rectangle(
                (x_cursor, y_cursor), w, share,
                facecolor=cycle[si % len(cycle)], edgecolor=p.paper, linewidth=1,
            )
            ax.add_patch(rect)
            if labels_on and share >= 8:
                ax.text(x_cursor + w / 2, y_cursor + share / 2, f"{share:.0f}%",
                        ha="center", va="center", fontsize=8, color=p.paper, fontweight="bold")
            y_cursor += share
        # Segment label (above)
        ax.text(x_cursor + w / 2, 102, r["segment"], ha="center", va="bottom", fontsize=9,
                color=p.text)
        # Segment size (below x-axis tick)
        if labels_on:
            ax.text(x_cursor + w / 2, -3, f"{w:.0f}%", ha="center", va="top",
                    fontsize=8, color=p.mid_gray)
        x_cursor += w
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 110)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    legend = [mpatches.Patch(color=cycle[i % len(cycle)], label=s) for i, s in enumerate(series_names)]
    ax.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=min(4, len(series_names)))
    return _finalize(fig, out, p)


# === NEW RECIPES ============================================================

# --- grouped-bar ------------------------------------------------------------

def grouped_bar(labels: list[str], series: dict[str, list[float]], out: Path,
                *, mode: str = "default", ylabel: str = "",
                labels_on: bool = True, grid: bool = True,
                accessible: bool = False, currency: str = "$",
                target: float | None = None) -> dict:
    """Side-by-side grouped bars. labels = categories, series = group name → values per category."""
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(9, 5))
    cycle = _cycle(p, accessible=accessible)
    n_groups = len(series)
    n_cats = len(labels)
    x = np.arange(n_cats)
    total_width = 0.8
    bar_width = total_width / n_groups
    flat_vals = [v for ys in series.values() for v in ys]
    fmt = annotate.pick_format(flat_vals, unit=ylabel)

    for i, (name, ys) in enumerate(series.items()):
        offset = (i - (n_groups - 1) / 2) * bar_width
        bars = ax.bar(x + offset, ys, bar_width, label=name, color=cycle[i % len(cycle)])
        if labels_on:
            for rect in bars:
                v = rect.get_height()
                ax.text(rect.get_x() + rect.get_width() / 2,
                        v + (max(flat_vals) - min(flat_vals)) * 0.015,
                        annotate.format_value(v, fmt, currency=currency),
                        ha="center", va="bottom", fontsize=8, color=p.text)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_formatter(annotate.axis_formatter(fmt, currency=currency))
    ax.legend(loc="best")
    if grid:
        annotate.light_grid(ax, axis="y", color=p.rule_gray)
    if target is not None:
        annotate.reference_line(ax, target,
                                label=f"Target {annotate.format_value(target, fmt, currency=currency)}",
                                color=p.accent_secondary_dark)
    return _finalize(fig, out, p)


# --- slope-graph ------------------------------------------------------------

def slope_graph(items: list[dict], out: Path, *, mode: str = "default",
                left_label: str = "Before", right_label: str = "After",
                labels_on: bool = True, accessible: bool = False,
                currency: str = "$", ylabel: str = "",
                highlight: list[str] | None = None) -> dict:
    """Tufte slope-graph. items: [{label, before, after}]. Lines connect left → right column."""
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(8, 6))
    highlight = highlight or []
    flat_vals = [it["before"] for it in items] + [it["after"] for it in items]
    fmt = annotate.pick_format(flat_vals, unit=ylabel)

    for it in items:
        color = p.accent_primary if it["label"] in highlight else p.mid_gray
        lw = 2.4 if it["label"] in highlight else 1.2
        ax.plot([0, 1], [it["before"], it["after"]], color=color, linewidth=lw,
                marker="o", markersize=5)
        if labels_on:
            # Left label
            ax.text(-0.04, it["before"],
                    f"{it['label']}  {annotate.format_value(it['before'], fmt, currency=currency)}",
                    ha="right", va="center", fontsize=9, color=color,
                    fontweight="bold" if it["label"] in highlight else "normal")
            # Right label
            ax.text(1.04, it["after"],
                    f"{annotate.format_value(it['after'], fmt, currency=currency)}  {it['label']}",
                    ha="left", va="center", fontsize=9, color=color,
                    fontweight="bold" if it["label"] in highlight else "normal")

    ax.set_xlim(-0.3, 1.3)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([left_label, right_label], fontsize=11, fontweight="bold")
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", left=False, labelleft=False)
    ax.tick_params(axis="x", bottom=False)
    return _finalize(fig, out, p)


# --- dot-plot ---------------------------------------------------------------

def dot_plot(labels: list[str], values: list[float], out: Path, *,
             mode: str = "default", ylabel: str = "",
             labels_on: bool = True, grid: bool = True,
             accessible: bool = False, currency: str = "$",
             target: float | None = None, baseline: float | None = None,
             sort: bool = True, highlight_idx: int | None = None) -> dict:
    """Tufte dot plot. Horizontal alternative to bar with better ink ratio."""
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(8, max(3, 0.35 * len(labels) + 1.5)))
    if sort:
        order = sorted(range(len(values)), key=lambda i: values[i])
        labels = [labels[i] for i in order]
        values = [values[i] for i in order]
        if highlight_idx is not None:
            highlight_idx = order.index(highlight_idx)
    fmt = annotate.pick_format(values, unit=ylabel)
    ys = np.arange(len(labels))
    # Banded background
    for i in range(len(labels)):
        if i % 2 == 1:
            ax.axhspan(i - 0.4, i + 0.4, color=p.rule_gray, alpha=0.4, zorder=0)
    colors = [p.mid_gray if (highlight_idx is not None and i != highlight_idx) else p.accent_primary
              for i in range(len(values))]
    # Stem to zero
    for i, v in enumerate(values):
        ax.plot([0, v], [i, i], color=colors[i], linewidth=0.6, alpha=0.5, zorder=1)
    # Dot
    ax.scatter(values, ys, s=120, color=colors, zorder=3, edgecolors=p.paper, linewidths=1)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels)
    ax.set_xlabel(ylabel)
    ax.xaxis.set_major_formatter(annotate.axis_formatter(fmt, currency=currency))
    if grid:
        annotate.light_grid(ax, axis="x", color=p.rule_gray)
    if labels_on:
        for i, v in enumerate(values):
            ax.text(v, i + 0.18, annotate.format_value(v, fmt, currency=currency),
                    ha="center", va="bottom", fontsize=9, color=colors[i])
    if target is not None:
        annotate.reference_line(ax, target, axis="x",
                                label=f"Target {annotate.format_value(target, fmt, currency=currency)}",
                                color=p.accent_secondary_dark)
    if baseline is not None and baseline != 0:
        annotate.reference_line(ax, baseline, axis="x",
                                label=f"Baseline {annotate.format_value(baseline, fmt, currency=currency)}",
                                color=p.mid_gray)
    return _finalize(fig, out, p)


# --- bullet -----------------------------------------------------------------

def bullet(items: list[dict], out: Path, *, mode: str = "default",
           ylabel: str = "", labels_on: bool = True, grid: bool = True,
           accessible: bool = False, currency: str = "$") -> dict:
    """Bullet chart: target vs actual vs qualitative bands.
    items: [{label, actual, target, ranges: [poor, ok, good]}]
    `ranges` is cumulative upper bounds for poor/ok/good bands.
    """
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    fig, ax = plt.subplots(figsize=(9, max(2.5, 0.7 * len(items) + 1)))
    flat = []
    for it in items:
        flat.extend([it.get("actual", 0), it.get("target", 0)])
        flat.extend(it.get("ranges", []) or [])
    fmt = annotate.pick_format(flat, unit=ylabel)

    band_colors = [p.rule_gray, p.light_gray, p.mid_gray]
    actual_color = p.accent_primary
    target_color = p.text

    for i, it in enumerate(items):
        y = len(items) - 1 - i
        # Bands (largest first so they layer correctly)
        ranges = list(it.get("ranges", [])) or []
        for bi, upper in enumerate(reversed(ranges)):
            idx = len(ranges) - 1 - bi
            color = band_colors[idx % len(band_colors)]
            ax.barh(y, upper, color=color, height=0.7, alpha=0.55, zorder=1)
        # Actual bar
        ax.barh(y, it["actual"], color=actual_color, height=0.32, zorder=2)
        # Target marker
        target = it.get("target")
        if target is not None:
            ax.plot([target, target], [y - 0.32, y + 0.32], color=target_color,
                    linewidth=3, zorder=3)
        # Label
        if labels_on:
            ax.text(it["actual"], y, f"  {annotate.format_value(it['actual'], fmt, currency=currency)}",
                    ha="left", va="center", fontsize=9, color=actual_color, fontweight="bold")
            if target is not None:
                ax.text(target, y + 0.42, f"target {annotate.format_value(target, fmt, currency=currency)}",
                        ha="center", va="bottom", fontsize=7, color=target_color)
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([it["label"] for it in reversed(items)])
    ax.set_xlabel(ylabel)
    ax.xaxis.set_major_formatter(annotate.axis_formatter(fmt, currency=currency))
    if grid:
        annotate.light_grid(ax, axis="x", color=p.rule_gray)
    return _finalize(fig, out, p)


# --- small-multiples --------------------------------------------------------

def small_multiples(panels: list[dict], out: Path, *, mode: str = "default",
                    cols: int = 3, ylabel: str = "", xlabel: str = "",
                    accessible: bool = False, currency: str = "$",
                    sub_recipe: str = "line", shared_y: bool = True) -> dict:
    """Faceted grid of small charts. Each panel: {title, x, y} (line) OR {title, labels, values} (bar)."""
    p = _palette_from(mode, accessible=accessible)
    setup(mode)
    n = len(panels)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.2, rows * 2.6),
                             sharey=shared_y, squeeze=False)
    color = p.accent_primary

    all_y = []
    for panel in panels:
        if sub_recipe == "line":
            all_y.extend(panel.get("y", []))
        else:
            all_y.extend(panel.get("values", []))
    fmt = annotate.pick_format(all_y, unit=ylabel)

    for idx, panel in enumerate(panels):
        ax = axes[idx // cols][idx % cols]
        if sub_recipe == "line":
            ax.plot(panel["x"], panel["y"], color=color, linewidth=1.8, marker="o", markersize=2)
        else:
            ax.bar(panel.get("labels", []), panel.get("values", []), color=color)
        ax.set_title(panel.get("title", ""), fontsize=10, loc="left", color=p.text)
        ax.tick_params(axis="both", labelsize=7)
        ax.yaxis.set_major_formatter(annotate.axis_formatter(fmt, currency=currency))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    # Hide unused panels
    for idx in range(n, rows * cols):
        axes[idx // cols][idx % cols].axis("off")
    if xlabel:
        fig.supxlabel(xlabel, fontsize=9, color=p.mid_gray)
    if ylabel:
        fig.supylabel(ylabel, fontsize=9, color=p.mid_gray)
    return _finalize(fig, out, p)


# --- registry + dispatch ----------------------------------------------------

RECIPES = {
    "bar": bar,
    "line": line,
    "stacked-bar": stacked_bar,
    "waterfall": waterfall,
    "heatmap": heatmap,
    "scatter-2x2": scatter_2x2,
    "marimekko": marimekko,
    "grouped-bar": grouped_bar,
    "slope-graph": slope_graph,
    "dot-plot": dot_plot,
    "bullet": bullet,
    "small-multiples": small_multiples,
}


def render(recipe: str, *, out: Path, mode: str = "default", **kwargs) -> dict[str, Any]:
    if recipe not in RECIPES:
        raise ValueError(f"unknown recipe {recipe!r}; supported: {sorted(RECIPES)}")
    return RECIPES[recipe](out=out, mode=mode, **kwargs)


# --- spec validation --------------------------------------------------------

SCHEMA = {
    "bar": {"required": ["labels", "values"], "list_eq": ["labels", "values"]},
    "line": {"required": ["x", "series"], "series_len_match": "x"},
    "stacked-bar": {"required": ["labels", "series"], "series_len_match": "labels"},
    "waterfall": {"required": ["labels", "deltas"], "list_eq": ["labels", "deltas"]},
    "heatmap": {"required": ["matrix", "row_labels", "col_labels"]},
    "scatter-2x2": {"required": ["items"]},
    "marimekko": {"required": ["rows"]},
    "grouped-bar": {"required": ["labels", "series"], "series_len_match": "labels"},
    "slope-graph": {"required": ["items"]},
    "dot-plot": {"required": ["labels", "values"], "list_eq": ["labels", "values"]},
    "bullet": {"required": ["items"]},
    "small-multiples": {"required": ["panels"]},
}


def validate_spec(spec: dict) -> list[tuple[str, str]]:
    """Return list of (severity, message). Empty = OK."""
    findings = []
    recipe = spec.get("recipe")
    if not recipe:
        findings.append(("HIGH", "Missing `recipe` field"))
        return findings
    if recipe not in RECIPES:
        findings.append(("HIGH", f"Unknown recipe {recipe!r}; supported: {sorted(RECIPES)}"))
        return findings
    schema = SCHEMA.get(recipe, {})
    for req in schema.get("required", []):
        if req not in spec:
            findings.append(("HIGH", f"Recipe {recipe!r} missing required field `{req}`"))
    # List-length equality
    if "list_eq" in schema and all(k in spec for k in schema["list_eq"]):
        lens = {k: len(spec[k]) for k in schema["list_eq"]}
        if len(set(lens.values())) > 1:
            findings.append(("HIGH", f"Lists must be equal length: {lens}"))
    # Series x-axis match
    if "series_len_match" in schema:
        ref = schema["series_len_match"]
        if ref in spec and "series" in spec:
            ref_len = len(spec[ref])
            for name, ys in spec["series"].items():
                if len(ys) != ref_len:
                    findings.append(("HIGH",
                                     f"Series {name!r} has {len(ys)} values; expected {ref_len} (matching {ref})"))
    # Pathological data ranges
    if recipe in ("bar", "dot-plot"):
        vals = spec.get("values", [])
        if vals and max(vals) - min(vals) == 0:
            findings.append(("MED", "All values are identical — bar will be flat"))
        if vals and any(v < 0 for v in vals) and not spec.get("baseline"):
            findings.append(("LOW", "Negative values present — consider setting baseline=0 for clarity"))
    if recipe == "stacked-bar":
        for name, ys in (spec.get("series") or {}).items():
            if any(v < 0 for v in ys):
                findings.append(("HIGH", f"Stacked-bar series {name!r} has negative values — illegal stacking"))
    if recipe == "waterfall":
        deltas = spec.get("deltas", [])
        if deltas and all(d == 0 for d in deltas):
            findings.append(("MED", "All deltas zero — waterfall has no story to tell"))
    if recipe == "line":
        all_y = [v for ys in (spec.get("series") or {}).values() for v in ys]
        if all_y and max(all_y) - min(all_y) == 0:
            findings.append(("MED", "All series values identical — line will be flat"))
    if recipe == "scatter-2x2":
        items = spec.get("items", []) or []
        xs = [i.get("x") for i in items if i.get("x") is not None]
        ys = [i.get("y") for i in items if i.get("y") is not None]
        if xs and max(xs) - min(xs) == 0:
            findings.append(("HIGH", "All x values identical — degenerate 2x2"))
        if ys and max(ys) - min(ys) == 0:
            findings.append(("HIGH", "All y values identical — degenerate 2x2"))
    return findings
