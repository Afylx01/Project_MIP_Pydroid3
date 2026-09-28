"""
Project MIP Pydroid 3: Mobile Visualization & Tearsheet Engine
Directive: DIR-PROD-PYDROID3-PORT-01 (Institutional Wall Street Edition)

Leverages Pydroid 3 native visualization libraries:
  - Matplotlib: Generates institutional, publication-quality PNG charts:
      1. Market Overview 3-Panel Dashboard
      2. Sector Rotation RRG & 30-Day Trajectory
      3. Market Breadth Trends & 52-Week Net Highs
  - Plotly: Generates standalone interactive HTML tearsheets
"""

import sys
import json
import shutil
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from .data_engine import get_base_dir

# Institutional Theme Palette (Wall Street / Bloomberg Terminal Dark)
THEME = {
    "bg_canvas": "#0B0F19",       # Deep Obsidian Navy
    "bg_card": "#131C2E",         # Midnight Slate Panel
    "border": "#24324D",          # Crisp subtle border
    "text_primary": "#F8FAFC",    # Bright Crisp Off-White
    "text_secondary": "#94A3B8",  # Slate-400
    "text_muted": "#64748B",      # Slate-500
    "green": "#10B981",           # Emerald Green (Bullish/Expansion)
    "green_tint": "#064E3B",
    "green_soft": "#34D399",
    "red": "#F43F5E",             # Coral Rose Red (Bearish/Contraction)
    "red_tint": "#881337",
    "red_soft": "#FB7185",
    "blue": "#38BDF8",            # Electric Sky Blue
    "blue_dark": "#0284C7",
    "amber": "#F59E0B",           # Warm Amber (Warning/Neutral)
    "purple": "#A855F7",          # Bright Violet
    "cyan": "#06B6D4",            # Cyan / Flow
    "orange": "#F97316",          # Orange
    "grid": "#24324D",
    "grid_alpha": 0.45,
}

SECTOR_PALETTE = {
    "PHARMA": "#10B981",       # Emerald
    "METALS": "#06B6D4",       # Cyan
    "AUTO": "#F59E0B",         # Amber
    "CAPGOODS": "#A855F7",     # Violet
    "CONSDUR": "#EC4899",      # Pink
    "ENERGY": "#F97316",       # Orange
    "IT": "#38BDF8",           # Sky Blue
    "FINSERV": "#6366F1",      # Indigo
    "FMCG": "#14B8A6",         # Teal
    "REALTY": "#EAB308",       # Yellow
    "CHEMICALS": "#84CC16",    # Lime
    "INFRA_MEDIA": "#94A3B8",  # Slate
    "OTHER": "#64748B",
}


def _clean_slug(universe_label: str) -> str:
    return str(universe_label).strip().replace(" ", "").replace("(", "").replace(")", "").replace("-", "_")


def _apply_ax_styling(ax, title: str, subtitle: Optional[str] = None):
    """Applies institutional slate card styling, grid, and typography to an axis."""
    ax.set_facecolor(THEME["bg_card"])
    for spine in ax.spines.values():
        spine.set_color(THEME["border"])
        spine.set_linewidth(1.0)
    ax.grid(True, linestyle="--", linewidth=0.6, color=THEME["grid"], alpha=THEME["grid_alpha"])
    ax.tick_params(colors=THEME["text_secondary"], labelsize=9)
    if title:
        if subtitle:
            ax.set_title(f"{title}\n", color=THEME["text_primary"], fontsize=11, fontweight="bold", pad=12, loc="left")
            ax.text(0.0, 1.02, subtitle, transform=ax.transAxes, color=THEME["text_muted"], fontsize=8.5, va="bottom")
        else:
            ax.set_title(title, color=THEME["text_primary"], fontsize=11, fontweight="bold", pad=10, loc="left")


def generate_matplotlib_dashboard(
    breadth_data: Dict,
    sector_data: Dict,
    top_df: pd.DataFrame,
    output_png: Optional[Path] = None,
    universe_label: str = "NIFTY 500",
) -> Path:
    """
    Generates a 3-panel institutional quantitative market overview graphic using Matplotlib:
      Panel 1: Market Breadth Gauge & Participation Indicators
      Panel 2: Sector 1M Alpha vs Benchmark (Sorted with collision-free labels)
      Panel 3: Top Candidates Relative Rotation Graph (RRG) Quadrants
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base_dir = get_base_dir()
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_png or (reports_dir / "market_overview_chart.png")

    as_of = breadth_data.get("as_of_date", "LIVE")
    regime = breadth_data.get("regime", {})
    regime_str = regime.get("label", "NORMAL (AGGRESSIVE)")
    clean_regime = regime_str.replace("🟢", "").replace("🔴", "").replace("🟡", "").strip()

    fig, axes = plt.subplots(1, 3, figsize=(21, 6.8), facecolor=THEME["bg_canvas"])
    fig.suptitle(
        f"PROJECT MIP: QUANTITATIVE DESK OVERVIEW  •  {as_of}",
        fontsize=15,
        fontweight="bold",
        color=THEME["text_primary"],
        x=0.05,
        y=0.97,
        ha="left",
    )
    fig.text(
        0.05, 0.93,
        f"Target Universe: {universe_label}  |  Benchmark Regime: {clean_regime}  |  Survivorship-Free Point-In-Time Architecture",
        fontsize=9.5,
        color=THEME["text_secondary"],
        ha="left",
    )
    fig.text(
        0.95, 0.02,
        "Source: Project MIP Quantitative Desk • NSE Bhavcopy Archives • Algorithmic Factor Engine",
        fontsize=8,
        color=THEME["text_muted"],
        ha="right",
    )

    # ── Panel 1: Market Breadth Indicators ──
    ax1 = axes[0]
    _apply_ax_styling(ax1, "MARKET BREADTH PARTICIPATION", "Trend Alignment & 52-Week High Proximity")
    tp = breadth_data.get("trend_participation", {})
    hp = breadth_data.get("high_proximity", {})

    breadth_metrics = [
        ("% > 200 EMA", tp.get("pct_above_200_ema", 0.0), "Long-Term Trend"),
        ("% > 50 EMA", tp.get("pct_above_50_ema", 0.0), "Medium-Term Trend"),
        ("% > 20 EMA", tp.get("pct_above_20_ema", 0.0), "Short Momentum"),
        ("Within 20% 52wH", hp.get("pct_within_20pct_52wh", 0.0), "High Proximity"),
        ("Within 5% 52wH", hp.get("pct_within_5pct_52wh", 0.0), "Breakout Zone"),
    ]
    labels = [m[0] for m in reversed(breadth_metrics)]
    values = [m[1] for m in reversed(breadth_metrics)]
    sub_labels = [m[2] for m in reversed(breadth_metrics)]

    # Shaded regime zones
    ax1.axvspan(60, 100, color=THEME["green"], alpha=0.08, label="Expansion (>60%)")
    ax1.axvspan(40, 60, color=THEME["text_muted"], alpha=0.04, label="Neutral (40-60%)")
    ax1.axvspan(0, 40, color=THEME["red"], alpha=0.08, label="Contraction (<40%)")

    bar_colors = [THEME["green"] if v >= 50.0 else THEME["red"] for v in values]
    bars = ax1.barh(labels, values, color=bar_colors, height=0.52, edgecolor=THEME["border"], linewidth=1.0, zorder=3)
    ax1.axvline(50, color=THEME["text_secondary"], linestyle="--", linewidth=1.1, alpha=0.8, zorder=4)

    ax1.set_xlim(0, 105)
    for bar, val, sub in zip(bars, values, sub_labels):
        x_pos = val + 2.0 if val < 75 else val - 12.0
        txt_col = THEME["text_primary"] if val < 75 else "#FFFFFF"
        status_tag = "BULL" if val >= 50 else "BEAR"
        ax1.text(
            val + 2.0,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}%  [{status_tag}]",
            va="center",
            color=THEME["text_primary"],
            fontweight="bold",
            fontsize=9.5,
            zorder=5,
        )

    # ── Panel 2: Sector Alpha vs Benchmark (1M) ──
    ax2 = axes[1]
    _apply_ax_styling(ax2, "SECTOR 1M ALPHA VS BENCHMARK", "1-Month Excess Return Relative to NIFTY 500 (%)")
    sectors = sector_data.get("sectors", [])[:9]
    # Sort so best performing is on top
    sectors_sorted = sorted(sectors, key=lambda s: float(s.get("alpha_1m", 0.0)))
    sec_names = [s["sector"] for s in sectors_sorted]
    sec_alphas = [float(s.get("alpha_1m", 0.0)) for s in sectors_sorted]
    sec_colors = [THEME["green"] if a >= 0 else THEME["red"] for a in sec_alphas]

    bars2 = ax2.barh(sec_names, sec_alphas, color=sec_colors, height=0.52, edgecolor=THEME["border"], linewidth=1.0, zorder=3)
    ax2.axvline(0, color=THEME["text_primary"], linestyle="-", linewidth=1.2, alpha=0.9, zorder=4)

    min_a = min(sec_alphas) if sec_alphas else -5.0
    max_a = max(sec_alphas) if sec_alphas else 5.0
    pad_a = max(2.5, max(abs(min_a), abs(max_a)) * 0.35)
    ax2.set_xlim(min_a - pad_a, max_a + pad_a)

    for bar, a in zip(bars2, sec_alphas):
        if a >= 0:
            ax2.text(
                a + 0.25,
                bar.get_y() + bar.get_height() / 2,
                f"+{a:.2f}%",
                va="center",
                ha="left",
                color=THEME["green_soft"],
                fontweight="bold",
                fontsize=9.5,
                zorder=5,
            )
        else:
            ax2.text(
                a - 0.25,
                bar.get_y() + bar.get_height() / 2,
                f"{a:.2f}%",
                va="center",
                ha="right",
                color=THEME["red_soft"],
                fontweight="bold",
                fontsize=9.5,
                zorder=5,
            )

    # ── Panel 3: Relative Rotation Graph (RRG) Quadrants (Top 20 Candidates) ──
    ax3 = axes[2]
    _apply_ax_styling(ax3, "TOP CANDIDATES RRG SCATTER", "RS-Ratio vs RS-Momentum Relative to Benchmark")

    # Fixed clean boundaries centered on 100
    x_vals = top_df["rrg_rs_ratio"].dropna().tolist() if not top_df.empty and "rrg_rs_ratio" in top_df.columns else [100]
    y_vals = top_df["rrg_rs_momentum"].dropna().tolist() if not top_df.empty and "rrg_rs_momentum" in top_df.columns else [100]

    min_x, max_x = min(x_vals), max(x_vals)
    min_y, max_y = min(y_vals), max(y_vals)
    span_x = max(10.0, (max_x - min_x) * 1.3)
    span_y = max(10.0, (max_y - min_y) * 1.3)

    lim_x0 = min(92.0, min_x - 3.0)
    lim_x1 = max(108.0, max_x + 3.0)
    lim_y0 = min(92.0, min_y - 3.0)
    lim_y1 = max(108.0, max_y + 3.0)

    ax3.set_xlim(lim_x0, lim_x1)
    ax3.set_ylim(lim_y0, lim_y1)

    ax3.axhline(100, color=THEME["text_muted"], linestyle="--", linewidth=1.1, zorder=2)
    ax3.axvline(100, color=THEME["text_muted"], linestyle="--", linewidth=1.1, zorder=2)

    # Quadrant Shading using actual plot limits
    ax3.fill_between([100, lim_x1 + 10], 100, lim_y1 + 10, color=THEME["green"], alpha=0.08, zorder=1)
    ax3.fill_between([lim_x0 - 10, 100], 100, lim_y1 + 10, color=THEME["blue"], alpha=0.08, zorder=1)
    ax3.fill_between([100, lim_x1 + 10], lim_y0 - 10, 100, color=THEME["amber"], alpha=0.08, zorder=1)
    ax3.fill_between([lim_x0 - 10, 100], lim_y0 - 10, 100, color=THEME["red"], alpha=0.08, zorder=1)

    # Quadrant Title Badges inside the plot frame using axes coordinates
    q_badge_props = dict(boxstyle="round,pad=0.35", alpha=0.85, linewidth=0.8)
    ax3.text(0.96, 0.95, "LEADING", transform=ax3.transAxes, ha="right", va="top", color=THEME["green_soft"], fontweight="bold", fontsize=9, bbox=dict(facecolor=THEME["bg_card"], edgecolor=THEME["green"], **q_badge_props))
    ax3.text(0.04, 0.95, "IMPROVING", transform=ax3.transAxes, ha="left", va="top", color=THEME["blue"], fontweight="bold", fontsize=9, bbox=dict(facecolor=THEME["bg_card"], edgecolor=THEME["blue"], **q_badge_props))
    ax3.text(0.96, 0.05, "WEAKENING", transform=ax3.transAxes, ha="right", va="bottom", color=THEME["amber"], fontweight="bold", fontsize=9, bbox=dict(facecolor=THEME["bg_card"], edgecolor=THEME["amber"], **q_badge_props))
    ax3.text(0.04, 0.05, "LAGGING", transform=ax3.transAxes, ha="left", va="bottom", color=THEME["red_soft"], fontweight="bold", fontsize=9, bbox=dict(facecolor=THEME["bg_card"], edgecolor=THEME["red"], **q_badge_props))

    # Scatter points with collision-free labels
    if not top_df.empty and "rrg_rs_ratio" in top_df.columns:
        quad_colors = {
            "LEADING": THEME["green"],
            "IMPROVING": THEME["blue"],
            "WEAKENING": THEME["amber"],
            "LAGGING": THEME["red"],
        }
        for idx, (_, r) in enumerate(top_df.iterrows()):
            rx = float(r.get("rrg_rs_ratio", 100.0))
            ry = float(r.get("rrg_rs_momentum", 100.0))
            q = str(r.get("rrg_quadrant", "WEAKENING"))
            c = quad_colors.get(q, THEME["blue"])
            vs = float(r.get("volar_score", 1.0))
            pt_size = max(50, min(220, int(vs * 35)))

            ax3.scatter(rx, ry, color=c, s=pt_size, edgecolors="#FFFFFF", linewidth=1.2, alpha=0.9, zorder=5)

            # Annotate top 8 candidates with alternating offset angles
            if idx < 8:
                offsets = [(6, 6), (6, -12), (-12, 6), (-12, -12), (10, 0), (-14, 0), (0, 10), (0, -14)]
                dx, dy = offsets[idx % len(offsets)]
                ax3.annotate(
                    r["symbol"],
                    (rx, ry),
                    xytext=(dx, dy),
                    textcoords="offset points",
                    color="#FFFFFF",
                    fontsize=8.5,
                    fontweight="bold",
                    zorder=6,
                    bbox=dict(boxstyle="round,pad=0.2", facecolor=THEME["bg_card"], edgecolor=c, alpha=0.85, linewidth=0.6),
                )

    ax3.set_xlabel("RS-Ratio (Trend Relative to Benchmark)", color=THEME["text_secondary"], fontsize=9.5)
    ax3.set_ylabel("RS-Momentum (Velocity of Change)", color=THEME["text_secondary"], fontsize=9.5)

    plt.tight_layout(rect=[0.02, 0.04, 0.98, 0.92])
    plt.savefig(out_path, dpi=220, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"✓ Institutional Matplotlib dashboard exported: {out_path}")
    return out_path


def generate_sector_rotation_history_chart(
    sector_data: Dict,
    ind_hist_df: Optional[pd.DataFrame] = None,
    output_png: Optional[Path] = None,
    universe_label: str = "NIFTY 500",
) -> Path:
    """
    Generates an institutional 2-panel Sector Rotation & Trajectory graphic:
      Panel 1: Relative Rotation Graph (RRG) across all 12 Primary Sectors with smart label offset.
      Panel 2: Sector Breadth Trajectory (% > 200 EMA) with end-of-line callouts and regime zones.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base_dir = get_base_dir()
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_png or (reports_dir / "sector_rotation_history.png")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(21, 8.5), facecolor=THEME["bg_canvas"])
    fig.suptitle(
        f"PROJECT MIP: SECTOR ROTATION & RELATIVE ROTATION GRAPH (RRG)",
        fontsize=15,
        fontweight="bold",
        color=THEME["text_primary"],
        x=0.04,
        y=0.97,
        ha="left",
    )
    fig.text(
        0.04, 0.935,
        f"Target Universe: {universe_label}  |  Dynamic Benchmark Alignment  |  30-Session Trend & Breadth Trajectory",
        fontsize=9.5,
        color=THEME["text_secondary"],
        ha="left",
    )
    fig.text(
        0.96, 0.02,
        "Source: Project MIP Quantitative Desk • Multi-Sector Factor Rotation Engine",
        fontsize=8,
        color=THEME["text_muted"],
        ha="right",
    )

    # ── Panel 1: Primary Sector RRG Quadrants ──
    _apply_ax_styling(ax1, "PRIMARY SECTOR RELATIVE ROTATION GRAPH", "Bubble Area = Sector Equities Count | Quadrant Threshold = 100.0")

    sec_list = sector_data.get("sectors", [])
    x_pts = [float(s.get("rrg_rs_ratio", 100.0)) for s in sec_list] if sec_list else [100.0]
    y_pts = [float(s.get("rrg_rs_momentum", 100.0)) for s in sec_list] if sec_list else [100.0]

    min_x, max_x = min(x_pts), max(x_pts)
    min_y, max_y = min(y_pts), max(y_pts)
    pad_x = max(2.5, (max_x - min_x) * 0.4)
    pad_y = max(2.5, (max_y - min_y) * 0.4)

    lim_x0 = min(94.0, min_x - pad_x)
    lim_x1 = max(106.0, max_x + pad_x)
    lim_y0 = min(94.0, min_y - pad_y)
    lim_y1 = max(106.0, max_y + pad_y)

    ax1.set_xlim(lim_x0, lim_x1)
    ax1.set_ylim(lim_y0, lim_y1)

    ax1.axhline(100, color=THEME["text_muted"], linestyle="--", linewidth=1.2, zorder=2)
    ax1.axvline(100, color=THEME["text_muted"], linestyle="--", linewidth=1.2, zorder=2)

    # Quadrant Shading
    ax1.fill_between([100, lim_x1 + 10], 100, lim_y1 + 10, color=THEME["green"], alpha=0.08, zorder=1)
    ax1.fill_between([lim_x0 - 10, 100], 100, lim_y1 + 10, color=THEME["blue"], alpha=0.08, zorder=1)
    ax1.fill_between([100, lim_x1 + 10], lim_y0 - 10, 100, color=THEME["amber"], alpha=0.08, zorder=1)
    ax1.fill_between([lim_x0 - 10, 100], lim_y0 - 10, 100, color=THEME["red"], alpha=0.08, zorder=1)

    # Institutional Corner Badges
    q_props = dict(boxstyle="round,pad=0.4", alpha=0.88, linewidth=0.8)
    ax1.text(0.96, 0.95, "LEADING\n(Overweight / Core Long)", transform=ax1.transAxes, ha="right", va="top", color=THEME["green_soft"], fontweight="bold", fontsize=9, bbox=dict(facecolor=THEME["bg_card"], edgecolor=THEME["green"], **q_props))
    ax1.text(0.04, 0.95, "IMPROVING\n(Accumulate / Early Turn)", transform=ax1.transAxes, ha="left", va="top", color=THEME["blue"], fontweight="bold", fontsize=9, bbox=dict(facecolor=THEME["bg_card"], edgecolor=THEME["blue"], **q_props))
    ax1.text(0.96, 0.05, "WEAKENING\n(Reduce / Tighten Stops)", transform=ax1.transAxes, ha="right", va="bottom", color=THEME["amber"], fontweight="bold", fontsize=9, bbox=dict(facecolor=THEME["bg_card"], edgecolor=THEME["amber"], **q_props))
    ax1.text(0.04, 0.05, "LAGGING\n(Avoid / Underweight)", transform=ax1.transAxes, ha="left", va="bottom", color=THEME["red_soft"], fontweight="bold", fontsize=9, bbox=dict(facecolor=THEME["bg_card"], edgecolor=THEME["red"], **q_props))

    # Fan out sector callouts gracefully into open quadrant territory
    sec_acronyms = {
        "PHARMA": "PH", "METALS": "MT", "AUTO": "AU", "CAPGOODS": "CG",
        "CONSDUR": "CD", "ENERGY": "EN", "IT": "IT", "FINSERV": "FS",
        "FMCG": "FM", "REALTY": "RL", "CHEMICALS": "CH", "INFRA_MEDIA": "IM"
    }

    # Group sectors by quadrant to fan out callouts
    quad_groups = {"LEADING": [], "IMPROVING": [], "WEAKENING": [], "LAGGING": []}
    for s in sec_list:
        rx = float(s.get("rrg_rs_ratio", 100.0))
        ry = float(s.get("rrg_rs_momentum", 100.0))
        if rx >= 100 and ry >= 100:
            quad_groups["LEADING"].append(s)
        elif rx < 100 and ry >= 100:
            quad_groups["IMPROVING"].append(s)
        elif rx >= 100 and ry < 100:
            quad_groups["WEAKENING"].append(s)
        else:
            quad_groups["LAGGING"].append(s)

    quad_vectors = {
        "LEADING": (1, 1),
        "IMPROVING": (-1, 1),
        "WEAKENING": (1, -1),
        "LAGGING": (-1, -1),
    }

    for q_name, s_group in quad_groups.items():
        vx, vy = quad_vectors[q_name]
        # Sort by distance from center
        s_group_sorted = sorted(s_group, key=lambda s: (float(s.get("rrg_rs_ratio", 100))-100)**2 + (float(s.get("rrg_rs_momentum", 100))-100)**2)
        for i, s in enumerate(s_group_sorted):
            sec = s["sector"]
            rx = float(s.get("rrg_rs_ratio", 100.0))
            ry = float(s.get("rrg_rs_momentum", 100.0))
            c = SECTOR_PALETTE.get(sec, THEME["blue"])
            count = int(s.get("stock_count", s.get("total_symbols", 30)))
            bubble_size = max(180, min(580, count * 8))

            ax1.scatter(rx, ry, color=c, s=bubble_size, edgecolors="#FFFFFF", linewidth=1.5, alpha=0.9, zorder=5)
            acr = sec_acronyms.get(sec, sec[:2])
            ax1.text(rx, ry, acr, color="#FFFFFF", fontweight="bold", fontsize=8.5, ha="center", va="center", zorder=6)

            # Stagger callouts radially away from (100, 100)
            base_dist_x = 32 + (i * 26)
            base_dist_y = 16 + (i * 18)
            ox = vx * base_dist_x
            oy = vy * base_dist_y

            ax1.annotate(
                f"{sec} ({rx:.1f}, {ry:.1f})",
                (rx, ry),
                xytext=(ox, oy),
                textcoords="offset points",
                color="#FFFFFF",
                fontweight="bold",
                fontsize=8.5,
                ha="left" if vx > 0 else "right",
                va="center",
                zorder=7,
                arrowprops=dict(arrowstyle="->", color=c, lw=0.9, alpha=0.85),
                bbox=dict(boxstyle="round,pad=0.25", facecolor=THEME["bg_card"], edgecolor=c, alpha=0.95, linewidth=0.8),
            )

    ax1.set_xlabel("RS-Ratio (Relative Strength vs Nifty Benchmark)", color=THEME["text_secondary"], fontsize=9.5)
    ax1.set_ylabel("RS-Momentum (Rate of Relative Change)", color=THEME["text_secondary"], fontsize=9.5)

    # ── Panel 2: Sector Breadth Trajectory Over 30 Sessions ──
    _apply_ax_styling(ax2, "TOP SECTOR BREADTH TRAJECTORY", "30-Day Trend Participation (% of Equities > 200 EMA)")

    # Regime Shading for Breadth
    ax2.axhspan(60, 100, color=THEME["green"], alpha=0.08, label="Expansion (>60%)")
    ax2.axhspan(40, 60, color=THEME["text_muted"], alpha=0.04, label="Neutral (40-60%)")
    ax2.axhspan(0, 40, color=THEME["red"], alpha=0.08, label="Contraction (<40%)")

    ax2.axhline(60, color=THEME["green"], linestyle=":", linewidth=1.0, alpha=0.6)
    ax2.axhline(50, color=THEME["text_secondary"], linestyle="--", linewidth=1.2, alpha=0.7)
    ax2.axhline(40, color=THEME["red"], linestyle=":", linewidth=1.0, alpha=0.6)

    if ind_hist_df is not None and not ind_hist_df.empty and "Date" in ind_hist_df.columns:
        dates = sorted(ind_hist_df["Date"].unique())
        top_secs = [s["sector"] for s in sec_list[:6]]
        end_callouts = []

        for idx, sec in enumerate(top_secs):
            s_data = ind_hist_df[ind_hist_df["Sector"] == sec].sort_values("Date")
            if not s_data.empty:
                col = SECTOR_PALETTE.get(sec, THEME["blue"])
                ax2.plot(
                    s_data["Date"],
                    s_data["% > 200 EMA"],
                    label=sec,
                    color=col,
                    linewidth=2.4,
                    marker="o",
                    markersize=4.0,
                    alpha=0.95,
                    zorder=4,
                )
                last_val = s_data["% > 200 EMA"].iloc[-1]
                end_callouts.append((sec, last_val, col))

        # Adjust overlapping end labels vertically
        end_callouts.sort(key=lambda x: x[1])
        staggered_y = []
        for i, (sec, val, col) in enumerate(end_callouts):
            y_target = val
            if staggered_y and abs(y_target - staggered_y[-1]) < 3.5:
                y_target = staggered_y[-1] + 3.8
            staggered_y.append(y_target)
            ax2.annotate(
                f"{sec}: {val:.1f}%",
                (len(dates) - 1, val),
                xytext=(len(dates) - 1 + 0.3, y_target),
                color="#FFFFFF",
                fontsize=8,
                fontweight="bold",
                va="center",
                zorder=6,
                bbox=dict(boxstyle="round,pad=0.2", facecolor=THEME["bg_card"], edgecolor=col, alpha=0.9, linewidth=0.8),
            )

        ax2.set_ylim(0, 105)
        step = max(1, len(dates) // 7)
        tick_dates = dates[::step]
        if dates[-1] not in tick_dates:
            tick_dates.append(dates[-1])
        ax2.set_xticks(tick_dates)
        ax2.set_xticklabels([d[5:] for d in tick_dates], rotation=25, ha="right", color=THEME["text_secondary"])
        ax2.set_ylabel("% Above 200 EMA", color=THEME["text_secondary"], fontsize=9.5)
        ax2.legend(loc="upper left", facecolor=THEME["bg_card"], edgecolor=THEME["border"], labelcolor=THEME["text_primary"], fontsize=8.5, ncol=2)
    else:
        ax2.text(0.5, 0.5, "Industry History Time-Series Actively Accumulating", color=THEME["text_muted"], ha="center", va="center", transform=ax2.transAxes)

    plt.tight_layout(rect=[0.02, 0.04, 0.98, 0.92])
    plt.savefig(out_path, dpi=220, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"✓ Institutional Sector rotation history chart exported: {out_path}")
    return out_path


def generate_market_breadth_history_chart(
    breadth_hist_df: pd.DataFrame,
    output_png: Optional[Path] = None,
    universe_label: str = "NIFTY 500",
) -> Path:
    """
    Generates an institutional 2-panel Market Breadth & Net Highs Historical Trend graphic:
      Panel 1: Trend Participation (% > 200, 50, 20 EMA) over 60 sessions with regime bands.
      Panel 2: 52-Week Net Highs/Lows Daily Bars & 5-Day Smoothed Trend Line with area fill.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base_dir = get_base_dir()
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_png or (reports_dir / "market_breadth_history.png")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(21, 10.5), facecolor=THEME["bg_canvas"], sharex=True)
    fig.suptitle(
        f"PROJECT MIP: MARKET BREADTH & PARTICIPATION DYNAMICS",
        fontsize=15,
        fontweight="bold",
        color=THEME["text_primary"],
        x=0.04,
        y=0.97,
        ha="left",
    )
    fig.text(
        0.04, 0.945,
        f"Target Universe: {universe_label}  |  60-Session Empirical Trend Participation & Net 52-Week Expansion Pressure",
        fontsize=9.5,
        color=THEME["text_secondary"],
        ha="left",
    )
    fig.text(
        0.96, 0.02,
        "Source: Project MIP Quantitative Desk • Institutional Breadth Engine • Point-In-Time Survivorship-Free",
        fontsize=8,
        color=THEME["text_muted"],
        ha="right",
    )

    if breadth_hist_df is not None and not breadth_hist_df.empty and "Date" in breadth_hist_df.columns:
        b_df = breadth_hist_df.sort_values("Date").reset_index(drop=True)
        dates = b_df["Date"].tolist()
        x_indices = np.arange(len(dates))

        # ── Panel 1: Trend Participation ──
        _apply_ax_styling(ax1, "60-SESSION MARKET BREADTH PARTICIPATION", "Percentage of Equities Trading Above Key Exponential Moving Averages")

        # Shaded Regime Bands
        ax1.axhspan(60, 100, color=THEME["green"], alpha=0.08)
        ax1.axhspan(40, 60, color=THEME["text_muted"], alpha=0.04)
        ax1.axhspan(0, 40, color=THEME["red"], alpha=0.08)

        ax1.text(0.98, 0.85, "EXPANSION REGIME (>60%)", transform=ax1.transAxes, ha="right", color=THEME["green_soft"], fontsize=8, fontweight="bold", alpha=0.8)
        ax1.text(0.98, 0.50, "NEUTRAL REGIME (40-60%)", transform=ax1.transAxes, ha="right", color=THEME["text_secondary"], fontsize=8, fontweight="bold", alpha=0.8)
        ax1.text(0.98, 0.15, "DEFENSIVE REGIME (<40%)", transform=ax1.transAxes, ha="right", color=THEME["red_soft"], fontsize=8, fontweight="bold", alpha=0.8)

        # Plot 3 moving average breadth lines
        ax1.plot(x_indices, b_df["% > 200 EMA"], label="> 200 EMA (Primary Structural Trend)", color=THEME["green"], linewidth=2.6, zorder=4)
        ax1.plot(x_indices, b_df["% > 50 EMA"], label="> 50 EMA (Medium-Term Cycle)", color=THEME["blue"], linewidth=2.0, zorder=4)
        ax1.plot(x_indices, b_df["% > 20 EMA"], label="> 20 EMA (Short-Term Tactical Momentum)", color=THEME["amber"], linewidth=1.8, linestyle=":", zorder=4)

        # Threshold lines
        ax1.axhline(60, color=THEME["green"], linestyle=":", linewidth=1.0, alpha=0.6)
        ax1.axhline(50, color=THEME["text_primary"], linestyle="--", linewidth=1.2, alpha=0.7)
        ax1.axhline(40, color=THEME["red"], linestyle=":", linewidth=1.0, alpha=0.6)

        # End of series value callout badges
        last_x = len(dates) - 1
        p200_val = b_df["% > 200 EMA"].iloc[-1]
        p50_val = b_df["% > 50 EMA"].iloc[-1]
        p20_val = b_df["% > 20 EMA"].iloc[-1]

        ax1.scatter([last_x], [p200_val], color=THEME["green"], s=45, zorder=6)
        ax1.scatter([last_x], [p50_val], color=THEME["blue"], s=45, zorder=6)
        ax1.scatter([last_x], [p20_val], color=THEME["amber"], s=45, zorder=6)

        callouts = [
            (p200_val, f"200 EMA: {p200_val:.1f}%", THEME["green"]),
            (p50_val, f"50 EMA: {p50_val:.1f}%", THEME["blue"]),
            (p20_val, f"20 EMA: {p20_val:.1f}%", THEME["amber"]),
        ]
        for val, txt, col in callouts:
            ax1.annotate(
                txt,
                (last_x, val),
                xytext=(8, 0),
                textcoords="offset points",
                color="#FFFFFF",
                fontsize=8.5,
                fontweight="bold",
                va="center",
                bbox=dict(boxstyle="round,pad=0.25", facecolor=THEME["bg_card"], edgecolor=col, alpha=0.92, linewidth=0.8),
                zorder=7,
            )

        ax1.set_ylim(0, 105)
        ax1.set_ylabel("Breadth Participation %", color=THEME["text_secondary"], fontsize=9.5)
        ax1.legend(loc="upper left", facecolor=THEME["bg_card"], edgecolor=THEME["border"], labelcolor=THEME["text_primary"], fontsize=8.5, ncol=3)

        # ── Panel 2: Net 52-Week Highs / Lows ──
        _apply_ax_styling(ax2, "52-WEEK NET HIGHS DYNAMICS", "Daily New 52-Week Highs minus Lows & 5-Session Smoothed Trajectory")

        net_highs = b_df["Net Highs"].values
        bar_colors = [THEME["green"] if v >= 0 else THEME["red"] for v in net_highs]
        ax2.bar(x_indices, net_highs, color=bar_colors, width=0.68, edgecolor=THEME["border"], linewidth=0.8, zorder=3)
        ax2.axhline(0, color=THEME["text_primary"], linestyle="-", linewidth=1.2, alpha=0.9, zorder=4)

        # 5-day rolling average of Net Highs with shaded regime fill
        if len(net_highs) >= 3:
            roll_net = pd.Series(net_highs).rolling(5, min_periods=1).mean().values
            ax2.plot(x_indices, roll_net, color=THEME["cyan"], linewidth=2.4, label="5-Session Rolling Net Highs", zorder=5)
            ax2.fill_between(x_indices, 0, roll_net, where=(roll_net >= 0), color=THEME["green"], alpha=0.15, zorder=2)
            ax2.fill_between(x_indices, 0, roll_net, where=(roll_net < 0), color=THEME["red"], alpha=0.15, zorder=2)

            # Latest reading badge
            latest_net = net_highs[-1]
            latest_roll = roll_net[-1]
            ax2.annotate(
                f"Latest Net: {latest_net:+d}  |  5D MA: {latest_roll:+.1f}",
                (last_x, latest_net),
                xytext=(0, 20 if latest_net >= 0 else -25),
                textcoords="offset points",
                ha="center",
                color="#FFFFFF",
                fontsize=8.5,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=THEME["bg_card"], edgecolor=THEME["cyan"], alpha=0.95, linewidth=1.0),
                arrowprops=dict(arrowstyle="->", color=THEME["cyan"], lw=1.0),
                zorder=7,
            )
            ax2.legend(loc="upper left", facecolor=THEME["bg_card"], edgecolor=THEME["border"], labelcolor=THEME["text_primary"], fontsize=8.5)

        ax2.set_ylabel("Net Highs (Highs - Lows)", color=THEME["text_secondary"], fontsize=9.5)

        # Format X-axis
        step = max(1, len(dates) // 8)
        tick_indices = list(range(0, len(dates), step))
        if (len(dates) - 1) not in tick_indices:
            tick_indices.append(len(dates) - 1)
        ax2.set_xticks(tick_indices)
        ax2.set_xticklabels([dates[i][5:] for i in tick_indices], rotation=25, ha="right", color=THEME["text_secondary"])
    else:
        ax1.text(0.5, 0.5, "Breadth History Time-Series Actively Accumulating", color=THEME["text_muted"], ha="center", transform=ax1.transAxes)
        ax2.text(0.5, 0.5, "Breadth History Time-Series Actively Accumulating", color=THEME["text_muted"], ha="center", transform=ax2.transAxes)

    plt.tight_layout(rect=[0.02, 0.04, 0.98, 0.93])
    plt.savefig(out_path, dpi=220, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"✓ Institutional Market breadth history chart exported: {out_path}")
    return out_path


def generate_plotly_tearsheet(
    breadth_data: Dict,
    sector_data: Dict,
    top_df: pd.DataFrame,
    output_html: Optional[Path] = None,
    universe_label: str = "NIFTY 500",
) -> Path:
    """
    Generates a mobile-friendly interactive Plotly HTML tearsheet.
    """
    base_dir = get_base_dir()
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_html or (reports_dir / "mip_mobile_tearsheet.html")

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "Market Breadth Participation (%)",
                "Sector Alpha 1M vs NIFTY 500",
                "Top Momentum Candidates RRG Scatter",
                "Sector Internal Breadth (% > 200 EMA)"
            ),
            vertical_spacing=0.15,
            horizontal_spacing=0.12
        )

        # 1. Breadth Bar Chart
        tp = breadth_data.get("trend_participation", {})
        hp = breadth_data.get("high_proximity", {})
        b_labels = ["% > 200 EMA", "% > 50 EMA", "% > 20 EMA", "% Near 52wH"]
        b_vals = [
            tp.get("pct_above_200_ema", 0),
            tp.get("pct_above_50_ema", 0),
            tp.get("pct_above_20_ema", 0),
            hp.get("pct_within_20pct_52wh", 0)
        ]
        fig.add_trace(
            go.Bar(
                x=b_labels, y=b_vals,
                marker_color=[THEME["green"] if v >= 50 else THEME["red"] for v in b_vals],
                name="Breadth %"
            ),
            row=1, col=1
        )

        # 2. Sector Alpha Bar Chart
        sectors = sector_data.get("sectors", [])
        sec_names = [s["sector"] for s in sectors]
        sec_alphas = [s.get("alpha_1m", 0.0) for s in sectors]
        fig.add_trace(
            go.Bar(
                x=sec_names, y=sec_alphas,
                marker_color=[THEME["green"] if a >= 0 else THEME["red"] for a in sec_alphas],
                name="Sector Alpha 1M"
            ),
            row=1, col=2
        )

        # 3. RRG Scatter
        if not top_df.empty and "rrg_rs_ratio" in top_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=top_df["rrg_rs_ratio"],
                    y=top_df["rrg_rs_momentum"],
                    mode="markers+text",
                    text=top_df["symbol"],
                    textposition="top center",
                    marker=dict(size=11, color=THEME["blue"], line=dict(color="#FFFFFF", width=1.2)),
                    name="Top Candidates"
                ),
                row=2, col=1
            )

        # 4. Sector Breadth Bar Chart
        sec_breadths = [s.get("breadth_200_pct", 0.0) for s in sectors]
        fig.add_trace(
            go.Bar(
                x=sec_names, y=sec_breadths,
                marker_color=THEME["purple"],
                name="Sector % > 200 EMA"
            ),
            row=2, col=2
        )

        fig.update_layout(
            paper_bgcolor=THEME["bg_canvas"],
            plot_bgcolor=THEME["bg_card"],
            font=dict(color=THEME["text_primary"], family="sans-serif"),
            title=f"Project MIP - Mobile Quantitative Tearsheet ({breadth_data.get('as_of_date', 'LIVE')}) [{universe_label}]",
            height=850,
            showlegend=False
        )

        fig.write_html(str(out_path))
        print(f"✓ Institutional Plotly interactive HTML tearsheet exported: {out_path}")
        return out_path

    except ImportError:
        return generate_pure_html_fallback(breadth_data, sector_data, top_df, out_path, universe_label)


def generate_pure_html_fallback(
    breadth_data: Dict,
    sector_data: Dict,
    top_df: pd.DataFrame,
    out_path: Path,
    universe_label: str = "NIFTY 500",
) -> Path:
    """Generates a standalone styled HTML report with zero external dependencies."""
    as_of = breadth_data.get("as_of_date", "LIVE")
    regime = breadth_data.get("regime", {})
    tp = breadth_data.get("trend_participation", {})

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Project MIP Mobile Tearsheet - {as_of} [{universe_label}]</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0f19; color: #f8fafc; margin: 15px; }}
h1 {{ color: #38bdf8; font-size: 20px; }}
.card {{ background: #131c2e; border: 1px solid #24324d; border-radius: 8px; padding: 15px; margin-bottom: 15px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #24324d; }}
th {{ background: #1e293b; color: #94a3b8; }}
.green {{ color: #10b981; font-weight: bold; }}
.red {{ color: #f43f5e; font-weight: bold; }}
</style>
</head>
<body>
<h1>🚀 Project MIP: Mobile Quantitative Tearsheet</h1>
<p>As of Date: <b>{as_of}</b> | Universe: <b>{universe_label}</b> | Regime: <b>{regime.get('label', 'N/A')}</b></p>

<div class="card">
  <h3>Market Breadth Summary</h3>
  <p>% > 200 EMA: <b>{tp.get('pct_above_200_ema', 0)}%</b> | % > 50 EMA: <b>{tp.get('pct_above_50_ema', 0)}%</b> | % > 20 EMA: <b>{tp.get('pct_above_20_ema', 0)}%</b></p>
</div>

<div class="card">
  <h3>Top Momentum Candidates</h3>
  <table>
    <tr><th>Rank</th><th>Symbol</th><th>Close</th><th>Sector</th><th>Volar</th><th>RRG</th></tr>
"""
    for _, r in top_df.head(20).iterrows():
        html += f"<tr><td>{int(r.get('rank', 0))}</td><td><b>{r['symbol']}</b></td><td>₹{r['close']:.2f}</td><td>{r.get('sector','')}</td><td>{r.get('volar_score',0):.2f}</td><td>{r.get('rrg_quadrant','')}</td></tr>\n"

    html += """
  </table>
</div>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Pure-HTML tearsheet exported: {out_path}")
    return out_path


def generate_all_visuals(
    as_of_date: str,
    breadth_data: Dict,
    sector_data: Dict,
    top_df: pd.DataFrame,
    ind_hist_df: Optional[pd.DataFrame] = None,
    breadth_hist_df: Optional[pd.DataFrame] = None,
    universe_label: str = "NIFTY 500",
) -> Dict[str, Path]:
    """
    Orchestrates creation of all visual deliverables with unique naming:
      1. Market Overview 3-Panel Dashboard (PNG)
      2. Sector Rotation RRG & 30-Day Trajectory (PNG)
      3. Market Breadth 60-Day Trends (PNG)
      4. Interactive Plotly Tearsheet (HTML)
    Mirrors all artifacts to reports/ and /sdcard/Documents/deliverables/.
    """
    base_dir = get_base_dir()
    reports_dir = base_dir / "reports"
    charts_dir = reports_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    deliv_dir = Path("/sdcard/Documents/deliverables")
    deliv_dir.mkdir(parents=True, exist_ok=True)

    slug = _clean_slug(universe_label)

    # Unique filenames
    overview_png = charts_dir / f"market_overview_{as_of_date}_{slug}.png"
    sector_png = charts_dir / f"sector_rotation_rrg_{as_of_date}_{slug}.png"
    breadth_png = charts_dir / f"market_breadth_trend_{as_of_date}_{slug}.png"
    html_path = reports_dir / f"mip_mobile_tearsheet_{as_of_date}_{slug}.html"

    # Canonical paths
    c_overview = reports_dir / "market_overview_chart.png"
    c_html = reports_dir / "mip_mobile_tearsheet.html"

    p1 = generate_matplotlib_dashboard(breadth_data, sector_data, top_df, output_png=overview_png, universe_label=universe_label)
    p2 = generate_sector_rotation_history_chart(sector_data, ind_hist_df=ind_hist_df, output_png=sector_png, universe_label=universe_label)
    p3 = generate_market_breadth_history_chart(breadth_hist_df, output_png=breadth_png, universe_label=universe_label)
    p4 = generate_plotly_tearsheet(breadth_data, sector_data, top_df, output_html=html_path, universe_label=universe_label)

    # Copy to canonical paths
    shutil.copyfile(p1, c_overview)
    shutil.copyfile(p4, c_html)

    # Mirror to deliverables/
    for p in [p1, p2, p3, p4, c_overview, c_html]:
        try:
            shutil.copyfile(p, deliv_dir / p.name)
        except Exception:
            pass

    return {
        "overview_png": p1,
        "sector_rrg_png": p2,
        "breadth_trend_png": p3,
        "tearsheet_html": p4,
        "canonical_overview": c_overview,
        "canonical_html": c_html,
    }
