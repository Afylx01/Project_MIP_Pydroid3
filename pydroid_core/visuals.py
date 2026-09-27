"""
Project MIP Pydroid 3: Mobile Visualization & Tearsheet Engine
Directive: DIR-PROD-PYDROID3-PORT-01

Leverages Pydroid 3 native visualization libraries:
  - Matplotlib: Generates high-resolution publication-quality PNG charts:
      1. Market Overview 3-Panel Dashboard
      2. Sector Rotation RRG & 30-Day Trajectory
      3. Market Breadth Trends & 52-Week Net Highs
  - Plotly: Generates standalone interactive HTML tearsheets
"""

import sys
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from .data_engine import get_base_dir


def _clean_slug(universe_label: str) -> str:
    return str(universe_label).strip().replace(" ", "").replace("(", "").replace(")", "").replace("-", "_")


def generate_matplotlib_dashboard(
    breadth_data: Dict,
    sector_data: Dict,
    top_df: pd.DataFrame,
    output_png: Optional[Path] = None,
    universe_label: str = "NIFTY 500",
) -> Path:
    """
    Generates a 3-panel quantitative market overview graphic using Matplotlib.
    Saves to reports/market_overview_chart.png (or uniquely named target).
    """
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend for mobile headless rendering
    import matplotlib.pyplot as plt

    base_dir = get_base_dir()
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_png or (reports_dir / "market_overview_chart.png")

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), facecolor="#0e1117")
    fig.suptitle(
        f"PROJECT MIP: QUANTITATIVE DESK OVERVIEW ({breadth_data.get('as_of_date', 'LIVE')}) [{universe_label}]",
        fontsize=15,
        fontweight="bold",
        color="#ffffff",
        y=0.98
    )

    # Panel 1: Market Breadth Indicators
    ax1 = axes[0]
    ax1.set_facecolor("#161b22")
    tp = breadth_data.get("trend_participation", {})
    hp = breadth_data.get("high_proximity", {})

    breadth_metrics = [
        ("% > 200 EMA", tp.get("pct_above_200_ema", 0)),
        ("% > 50 EMA", tp.get("pct_above_50_ema", 0)),
        ("% > 20 EMA", tp.get("pct_above_20_ema", 0)),
        ("% Near 52wH", hp.get("pct_within_20pct_52wh", 0)),
    ]
    labels = [m[0] for m in breadth_metrics]
    values = [m[1] for m in breadth_metrics]
    colors = ["#238636" if v >= 50 else "#da3633" for v in values]

    bars = ax1.barh(labels, values, color=colors, height=0.55, edgecolor="#30363d")
    ax1.axvline(50, color="#8b949e", linestyle="--", linewidth=1.2, alpha=0.7)
    ax1.set_xlim(0, 100)
    ax1.set_title("Market Breadth Participation (%)", color="#c9d1d9", fontsize=12, pad=10)
    ax1.tick_params(colors="#8b949e")
    for bar, val in zip(bars, values):
        ax1.text(val + 2, bar.get_y() + bar.get_height() / 2, f"{val:.1f}%", va="center", color="#ffffff", fontweight="bold", fontsize=10)

    # Panel 2: Sector Alpha vs NIFTY 500 (1M)
    ax2 = axes[1]
    ax2.set_facecolor("#161b22")
    sectors = sector_data.get("sectors", [])[:8]
    sec_names = [s["sector"] for s in reversed(sectors)]
    sec_alphas = [s.get("alpha_1m", 0.0) for s in reversed(sectors)]
    sec_colors = ["#2ea043" if a >= 0 else "#f85149" for a in sec_alphas]

    ax2.barh(sec_names, sec_alphas, color=sec_colors, height=0.55, edgecolor="#30363d")
    ax2.axvline(0, color="#ffffff", linestyle="-", linewidth=1.0, alpha=0.8)
    ax2.set_title("Sector Alpha 1M vs NIFTY 500 (%)", color="#c9d1d9", fontsize=12, pad=10)
    ax2.tick_params(colors="#8b949e")
    for s_name, a in zip(sec_names, sec_alphas):
        x_pos = a + (0.3 if a >= 0 else -1.5)
        ax2.text(x_pos, s_name, f"{a:+.1f}%", va="center", color="#ffffff", fontsize=9, fontweight="bold")

    # Panel 3: Relative Rotation Graph (RRG) Quadrants (Top 20 Candidates)
    ax3 = axes[2]
    ax3.set_facecolor("#161b22")
    ax3.axhline(100, color="#8b949e", linestyle="--", linewidth=1.2)
    ax3.axvline(100, color="#8b949e", linestyle="--", linewidth=1.2)

    # Quadrant Shading
    ax3.fill_between([100, 125], 100, 125, color="#238636", alpha=0.15)  # Leading
    ax3.fill_between([75, 100], 100, 125, color="#1f6feb", alpha=0.15)   # Improving
    ax3.fill_between([100, 125], 75, 100, color="#d29922", alpha=0.15)  # Weakening
    ax3.fill_between([75, 100], 75, 100, color="#da3633", alpha=0.15)   # Lagging

    ax3.text(115, 115, "LEADING", color="#3fb950", fontweight="bold", fontsize=9, ha="center")
    ax3.text(85, 115, "IMPROVING", color="#58a6ff", fontweight="bold", fontsize=9, ha="center")
    ax3.text(115, 85, "WEAKENING", color="#d29922", fontweight="bold", fontsize=9, ha="center")
    ax3.text(85, 85, "LAGGING", color="#f85149", fontweight="bold", fontsize=9, ha="center")

    if not top_df.empty and "rrg_rs_ratio" in top_df.columns:
        ax3.scatter(
            top_df["rrg_rs_ratio"],
            top_df["rrg_rs_momentum"],
            color="#58a6ff",
            s=60,
            edgecolors="#ffffff",
            linewidth=1.2,
            zorder=5
        )
        for _, r in top_df.head(10).iterrows():
            ax3.annotate(
                r["symbol"],
                (r["rrg_rs_ratio"], r["rrg_rs_momentum"]),
                color="#ffffff",
                fontsize=8,
                xytext=(3, 3),
                textcoords="offset points"
            )

    ax3.set_xlim(90, 115)
    ax3.set_ylim(90, 115)
    ax3.set_xlabel("RS-Ratio (Trend vs Benchmark)", color="#8b949e")
    ax3.set_ylabel("RS-Momentum (Velocity)", color="#8b949e")
    ax3.set_title("Top 20 Candidates RRG Scatter", color="#c9d1d9", fontsize=12, pad=10)
    ax3.tick_params(colors="#8b949e")

    plt.tight_layout()
    plt.savefig(out_path, dpi=200, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"✓ Matplotlib dashboard exported: {out_path}")
    return out_path


def generate_sector_rotation_history_chart(
    sector_data: Dict,
    ind_hist_df: Optional[pd.DataFrame] = None,
    output_png: Optional[Path] = None,
    universe_label: str = "NIFTY 500",
) -> Path:
    """
    Generates a 2-panel Sector Rotation & Trajectory graphic:
      Panel 1: Relative Rotation Graph (RRG) Map across all 12 primary sectors.
      Panel 2: Sector Breadth Trajectory (% > 200 EMA) across the last 30 trading sessions.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base_dir = get_base_dir()
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_png or (reports_dir / "sector_rotation_history.png")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7.5), facecolor="#0e1117")
    fig.suptitle(
        f"PROJECT MIP: SECTOR ROTATION & RRG TRAJECTORY [{universe_label}]",
        fontsize=15,
        fontweight="bold",
        color="#ffffff",
        y=0.98
    )

    # ── Panel 1: Sector RRG Quadrants (All 12 Primary Sectors) ──
    ax1.set_facecolor("#161b22")
    ax1.axhline(100, color="#8b949e", linestyle="--", linewidth=1.2)
    ax1.axvline(100, color="#8b949e", linestyle="--", linewidth=1.2)

    ax1.fill_between([100, 115], 100, 115, color="#238636", alpha=0.15)  # Leading
    ax1.fill_between([85, 100], 100, 115, color="#1f6feb", alpha=0.15)   # Improving
    ax1.fill_between([100, 115], 85, 100, color="#d29922", alpha=0.15)  # Weakening
    ax1.fill_between([85, 100], 85, 100, color="#da3633", alpha=0.15)   # Lagging

    ax1.text(111, 112, "LEADING\n(Overweight)", color="#3fb950", fontweight="bold", fontsize=10, ha="center")
    ax1.text(89, 112, "IMPROVING\n(Accumulate)", color="#58a6ff", fontweight="bold", fontsize=10, ha="center")
    ax1.text(111, 88, "WEAKENING\n(Reduce)", color="#d29922", fontweight="bold", fontsize=10, ha="center")
    ax1.text(89, 88, "LAGGING\n(Avoid)", color="#f85149", fontweight="bold", fontsize=10, ha="center")

    sec_list = sector_data.get("sectors", [])
    quad_colors = {
        "LEADING": "#3fb950",
        "IMPROVING": "#58a6ff",
        "WEAKENING": "#d29922",
        "LAGGING": "#f85149",
    }

    min_x, max_x = 95.0, 105.0
    min_y, max_y = 95.0, 105.0

    for s in sec_list:
        sec = s["sector"]
        rx = float(s.get("rrg_rs_ratio", 100.0))
        ry = float(s.get("rrg_rs_momentum", 100.0))
        q = s.get("rrg_quadrant", "WEAKENING")
        c = quad_colors.get(q, "#58a6ff")
        size = max(120, min(600, s.get("stock_count", 30) * 4))

        min_x = min(min_x, rx - 3)
        max_x = max(max_x, rx + 3)
        min_y = min(min_y, ry - 3)
        max_y = max(max_y, ry + 3)

        ax1.scatter(rx, ry, color=c, s=size, edgecolors="#ffffff", linewidth=1.5, alpha=0.85, zorder=5)
        ax1.annotate(
            sec,
            (rx, ry),
            color="#ffffff",
            fontweight="bold",
            fontsize=8.5,
            xytext=(4, 4),
            textcoords="offset points",
            zorder=6
        )

    ax1.set_xlim(min(88, min_x), max(112, max_x))
    ax1.set_ylim(min(88, min_y), max(112, max_y))
    ax1.set_xlabel("RS-Ratio (Relative Strength vs Benchmark)", color="#8b949e", fontsize=10)
    ax1.set_ylabel("RS-Momentum (Rate of Relative Change)", color="#8b949e", fontsize=10)
    ax1.set_title("NSE Primary Sector RRG Map (Bubble Size = Stock Count)", color="#c9d1d9", fontsize=12, pad=10)
    ax1.tick_params(colors="#8b949e")

    # ── Panel 2: Sector Breadth Trajectory Over 30 Sessions ──
    ax2.set_facecolor("#161b22")
    if ind_hist_df is not None and not ind_hist_df.empty and "Date" in ind_hist_df.columns:
        dates = sorted(ind_hist_df["Date"].unique())
        top_secs = [s["sector"] for s in sec_list[:6]]
        palette = ["#3fb950", "#58a6ff", "#f0883e", "#a371f7", "#56d364", "#ff7b72"]

        for idx, sec in enumerate(top_secs):
            s_data = ind_hist_df[ind_hist_df["Sector"] == sec].sort_values("Date")
            if not s_data.empty:
                col = palette[idx % len(palette)]
                ax2.plot(s_data["Date"], s_data["% > 200 EMA"], label=sec, color=col, linewidth=2.0, marker="o", markersize=3.5)

        ax2.axhline(50, color="#8b949e", linestyle="--", linewidth=1.2, alpha=0.7, label="50% Threshold")
        ax2.set_ylim(0, 100)
        # Show every 5th date on x-axis
        step = max(1, len(dates) // 6)
        tick_dates = dates[::step]
        if dates[-1] not in tick_dates:
            tick_dates.append(dates[-1])
        ax2.set_xticks(tick_dates)
        ax2.set_xticklabels([d[5:] for d in tick_dates], rotation=30, ha="right", color="#8b949e")
        ax2.set_title("Top Sector Breadth Trajectory (% > 200 EMA over 30 Days)", color="#c9d1d9", fontsize=12, pad=10)
        ax2.set_ylabel("Breadth % Above 200 EMA", color="#8b949e", fontsize=10)
        ax2.tick_params(colors="#8b949e")
        ax2.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9", fontsize=9)
    else:
        ax2.text(0.5, 0.5, "Industry History Time-Series Actively Accumulating", color="#8b949e", ha="center", va="center")

    plt.tight_layout()
    plt.savefig(out_path, dpi=200, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"✓ Sector rotation history chart exported: {out_path}")
    return out_path


def generate_market_breadth_history_chart(
    breadth_hist_df: pd.DataFrame,
    output_png: Optional[Path] = None,
    universe_label: str = "NIFTY 500",
) -> Path:
    """
    Generates a 2-panel Market Breadth & Net Highs Historical Trend graphic:
      Panel 1: Trend Participation (% > 200, 50, 20 EMA) over last 60 sessions.
      Panel 2: 52-Week Net Highs/Lows Daily Bars over last 60 sessions.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base_dir = get_base_dir()
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_png or (reports_dir / "market_breadth_history.png")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 9), facecolor="#0e1117", sharex=True)
    fig.suptitle(
        f"PROJECT MIP: MARKET BREADTH & PARTICIPATION DYNAMICS [{universe_label}]",
        fontsize=15,
        fontweight="bold",
        color="#ffffff",
        y=0.98
    )

    if breadth_hist_df is not None and not breadth_hist_df.empty and "Date" in breadth_hist_df.columns:
        b_df = breadth_hist_df.sort_values("Date").reset_index(drop=True)
        dates = b_df["Date"].tolist()
        x_indices = np.arange(len(dates))

        # ── Panel 1: Trend Participation ──
        ax1.set_facecolor("#161b22")
        ax1.plot(x_indices, b_df["% > 200 EMA"], label="> 200 EMA (Primary Trend)", color="#3fb950", linewidth=2.2)
        ax1.plot(x_indices, b_df["% > 50 EMA"], label="> 50 EMA (Medium Trend)", color="#58a6ff", linewidth=1.8)
        ax1.plot(x_indices, b_df["% > 20 EMA"], label="> 20 EMA (Short Velocity)", color="#d29922", linewidth=1.5, linestyle=":")
        ax1.axhline(50, color="#ffffff", linestyle="--", linewidth=1.2, alpha=0.6, label="50% Neutral Gate")
        ax1.axhline(60, color="#238636", linestyle=":", linewidth=1.0, alpha=0.5, label="Expansion Line (60%)")
        ax1.axhline(40, color="#da3633", linestyle=":", linewidth=1.0, alpha=0.5, label="Defensive Line (40%)")

        ax1.set_ylim(0, 100)
        ax1.set_ylabel("Breadth Participation %", color="#8b949e", fontsize=10)
        ax1.set_title("60-Session Market Breadth Participation (% > 200/50/20 EMA)", color="#c9d1d9", fontsize=12, pad=8)
        ax1.tick_params(colors="#8b949e")
        ax1.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9", fontsize=9, ncol=3)

        # ── Panel 2: Net 52-Week Highs / Lows ──
        ax2.set_facecolor("#161b22")
        net_highs = b_df["Net Highs"].values
        bar_colors = ["#2ea043" if v >= 0 else "#f85149" for v in net_highs]
        ax2.bar(x_indices, net_highs, color=bar_colors, width=0.65, edgecolor="#30363d")
        ax2.axhline(0, color="#ffffff", linestyle="-", linewidth=1.0, alpha=0.8)

        # 5-day rolling average of Net Highs
        if len(net_highs) >= 5:
            roll_net = pd.Series(net_highs).rolling(5, min_periods=1).mean()
            ax2.plot(x_indices, roll_net, color="#58a6ff", linewidth=1.8, label="5-Session Rolling Net")
            ax2.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9", fontsize=9)

        ax2.set_ylabel("Net 52w Highs - Lows", color="#8b949e", fontsize=10)
        ax2.set_title("52-Week Net Highs vs New Lows (Market Expansion Pressure)", color="#c9d1d9", fontsize=12, pad=8)
        ax2.tick_params(colors="#8b949e")

        # Format X-axis
        step = max(1, len(dates) // 8)
        tick_indices = list(range(0, len(dates), step))
        if (len(dates) - 1) not in tick_indices:
            tick_indices.append(len(dates) - 1)
        ax2.set_xticks(tick_indices)
        ax2.set_xticklabels([dates[i][5:] for i in tick_indices], rotation=30, ha="right", color="#8b949e")
    else:
        ax1.text(0.5, 0.5, "Breadth History Time-Series Actively Accumulating", color="#8b949e", ha="center")
        ax2.text(0.5, 0.5, "Breadth History Time-Series Actively Accumulating", color="#8b949e", ha="center")

    plt.tight_layout()
    plt.savefig(out_path, dpi=200, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"✓ Market breadth history chart exported: {out_path}")
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
                marker_color=["#238636" if v >= 50 else "#da3633" for v in b_vals],
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
                marker_color=["#2ea043" if a >= 0 else "#f85149" for a in sec_alphas],
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
                    marker=dict(size=10, color="#58a6ff"),
                    name="Top Candidates"
                ),
                row=2, col=1
            )

        # 4. Sector Breadth Bar Chart
        sec_breadths = [s.get("breadth_200_pct", 0.0) for s in sectors]
        fig.add_trace(
            go.Bar(
                x=sec_names, y=sec_breadths,
                marker_color="#8957e5",
                name="Sector % > 200 EMA"
            ),
            row=2, col=2
        )

        fig.update_layout(
            template="plotly_dark",
            title=f"Project MIP - Mobile Quantitative Tearsheet ({breadth_data.get('as_of_date', 'LIVE')}) [{universe_label}]",
            height=850,
            showlegend=False
        )

        fig.write_html(str(out_path))
        print(f"✓ Plotly interactive HTML tearsheet exported: {out_path}")
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
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; margin: 15px; }}
h1 {{ color: #58a6ff; font-size: 20px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; margin-bottom: 15px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #21262d; }}
th {{ background: #21262d; color: #8b949e; }}
.green {{ color: #3fb950; font-weight: bold; }}
.red {{ color: #f85149; font-weight: bold; }}
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
