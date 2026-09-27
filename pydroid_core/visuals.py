"""
Project MIP Pydroid 3: Mobile Visualization & Tearsheet Engine
Directive: DIR-PROD-PYDROID3-PORT-01

Leverages Pydroid 3 native visualization libraries:
  - Matplotlib: Generates high-resolution publication-quality PNG charts
  - Plotly: Generates standalone interactive HTML tearsheets
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from .data_engine import get_base_dir


def generate_matplotlib_dashboard(
    breadth_data: Dict,
    sector_data: Dict,
    top_df: pd.DataFrame,
    output_png: Optional[Path] = None
) -> Path:
    """
    Generates a 3-panel quantitative market overview graphic using Matplotlib.
    Saves to reports/market_overview_chart.png.
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
        f"PROJECT MIP: QUANTITATIVE DESK OVERVIEW ({breadth_data.get('as_of_date', 'LIVE')})",
        fontsize=16,
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
    sec_alphas = [s["alpha_1m"] for s in reversed(sectors)]
    sec_colors = ["#2ea043" if a >= 0 else "#f85149" for a in sec_alphas]

    ax2.barh(sec_names, sec_alphas, color=sec_colors, height=0.55, edgecolor="#30363d")
    ax2.axvline(0, color="#ffffff", linestyle="-", linewidth=1.0, alpha=0.8)
    ax2.set_title("Sector Alpha 1M vs NIFTY 500 (%)", color="#c9d1d9", fontsize=12, pad=10)
    ax2.tick_params(colors="#8b949e")
    for s_name, a in zip(sec_names, sec_alphas):
        x_pos = a + (0.3 if a >= 0 else -1.5)
        ax2.text(x_pos, s_name, f"{a:+.1f}%", va="center", color="#ffffff", fontsize=9, fontweight="bold")

    # Panel 3: Relative Rotation Graph (RRG) Quadrants
    ax3 = axes[2]
    ax3.set_facecolor("#161b22")
    ax3.axhline(100, color="#8b949e", linestyle="--", linewidth=1.2)
    ax3.axvline(100, color="#8b949e", linestyle="--", linewidth=1.2)

    # Quadrant Shading
    ax3.fill_between([100, 120], 100, 120, color="#238636", alpha=0.15)  # Leading
    ax3.fill_between([80, 100], 100, 120, color="#1f6feb", alpha=0.15)   # Improving
    ax3.fill_between([100, 120], 80, 100, color="#d29922", alpha=0.15)  # Weakening
    ax3.fill_between([80, 100], 80, 100, color="#da3633", alpha=0.15)   # Lagging

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


def generate_plotly_tearsheet(
    breadth_data: Dict,
    sector_data: Dict,
    top_df: pd.DataFrame,
    output_html: Optional[Path] = None
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
        sec_alphas = [s["alpha_1m"] for s in sectors]
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
        sec_breadths = [s["breadth_200_pct"] for s in sectors]
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
            title=f"Project MIP - Mobile Quantitative Tearsheet ({breadth_data.get('as_of_date', 'LIVE')})",
            height=850,
            showlegend=False
        )

        fig.write_html(str(out_path))
        print(f"✓ Plotly interactive HTML tearsheet exported: {out_path}")
        return out_path

    except ImportError:
        # Fallback pure-HTML generator if plotly is absent
        return generate_pure_html_fallback(breadth_data, sector_data, top_df, out_path)


def generate_pure_html_fallback(
    breadth_data: Dict,
    sector_data: Dict,
    top_df: pd.DataFrame,
    out_path: Path
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
<title>Project MIP Mobile Tearsheet - {as_of}</title>
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
<p>As of Date: <b>{as_of}</b> | Regime: <b>{regime.get('label', 'N/A')}</b></p>

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
