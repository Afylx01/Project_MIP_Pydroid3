"""
Project MIP Pydroid 3: Production Momentum Scanner
Directive: DIR-PROD-PYDROID3-PORT-01

Evaluates verified institutional 5-tier momentum strategy rules on SQLite universe:
  1. Filter 1 (Retracement): Close >= 0.80 * 252d High.
  2. Filter 2 (Trend): Close > 200 EMA.
  3. Filter 3 (Relative Strength): Stock / NIFTY 500 ratio > 200 EMA of ratio.
  4. Ranking Metric: Volar Score = Return_252 / max(vol_252, 0.05).
  5. Market Regime: NIFTY 500 Close vs 20 EMA (Normal vs Defensive).
  6. RRG Analytics: RS-Ratio, RS-Momentum, Quadrant classification.
  7. Integrated Market Breadth & Sector Rotation.
"""

import sys
import json
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from .data_engine import (
    get_base_dir,
    get_latest_date,
    load_bars,
    load_symbol_sector_map,
)
from .rrg import compute_rrg_metrics
from .breadth import MarketBreadthEngine
from .sector_rotation import SectorRotationEngine


class PydroidScanner:
    """Institutional momentum screener optimized for Pydroid 3 mobile execution."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or get_base_dir()
        self.benchmark_csv = self.base_dir / "data" / "benchmark_nifty500.csv"
        self.sector_map = load_symbol_sector_map()
        self.breadth_engine = MarketBreadthEngine(self.base_dir)
        self.sector_engine = SectorRotationEngine(self.base_dir)

    def log(self, msg: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [Scanner] {msg}")

    def load_benchmark(self) -> pd.DataFrame:
        if not self.benchmark_csv.exists():
            return pd.DataFrame(columns=["date", "close", "ema_20"])
        df = pd.read_csv(self.benchmark_csv)
        df["date"] = df["date"].astype(str)
        return df

    def evaluate_regime(self, as_of_date: str) -> Dict:
        """Evaluates benchmark regime against 20 EMA."""
        b_df = self.load_benchmark()
        if b_df.empty:
            return {"is_normal_regime": True, "label": "🟢 NORMAL EXPANSION", "regime": "NORMAL"}

        row = b_df[b_df["date"] == as_of_date]
        if row.empty:
            prior = b_df[b_df["date"] <= as_of_date]
            if prior.empty:
                return {"is_normal_regime": True, "label": "🟢 NORMAL EXPANSION", "regime": "NORMAL"}
            row = prior.iloc[[-1]]

        bm_close = float(row["close"].iloc[0])
        bm_ema20 = float(row["ema_20"].iloc[0]) if "ema_20" in row.columns else bm_close
        is_normal = bm_close >= bm_ema20

        return {
            "bm_close": round(bm_close, 2),
            "bm_ema20": round(bm_ema20, 2),
            "is_normal_regime": is_normal,
            "label": "🟢 NORMAL (AGGRESSIVE)" if is_normal else "🔴 DEFENSIVE (CASH SHIELD)",
            "regime": "NORMAL" if is_normal else "DEFENSIVE",
        }

    def run_scan(
        self,
        as_of_date: Optional[str] = None,
        top_n: int = 20,
        lookback_days: int = 550,
        export_csv: bool = True
    ) -> Tuple[pd.DataFrame, Dict, Dict, Dict]:
        """
        Executes end-to-end screener pipeline on SQLite universe.
        Returns: (top_df, breadth_results, sector_results, regime_info)
        """
        target_date = as_of_date or get_latest_date()
        self.log(f"Starting Production Momentum Scan as of {target_date}...")

        target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d")
        start_str = (target_dt - datetime.timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        self.log(f"Loading bars from SQLite ({start_str} to {target_date})...")
        bars = load_bars(start_date=start_str, end_date=target_date, include_delisted=False)

        active_today = set(bars[bars["date"] == target_date]["symbol"].unique())
        self.log(f"Active symbols on {target_date}: {len(active_today):,}")
        bars = bars[bars["symbol"].isin(active_today)].copy()
        bars = bars.sort_values(by=["symbol", "date"]).reset_index(drop=True)

        # Merge Benchmark Close
        b_df = self.load_benchmark()
        if not b_df.empty:
            bench_map = dict(zip(b_df["date"], b_df["close"]))
            bars["benchmark_close"] = bars["date"].map(bench_map).fillna(1.0)
        else:
            bars["benchmark_close"] = 1.0

        # Technical Indicators
        self.log("Computing EMAs, rolling highs/lows, volatility, and returns...")
        bars["ema_200"] = bars.groupby("symbol")["close"].transform(
            lambda s: s.ewm(span=200, adjust=True, min_periods=min(50, len(s))).mean()
        )
        bars["ema_50"] = bars.groupby("symbol")["close"].transform(
            lambda s: s.ewm(span=50, adjust=True, min_periods=min(20, len(s))).mean()
        )
        bars["ema_20"] = bars.groupby("symbol")["close"].transform(
            lambda s: s.ewm(span=20, adjust=True, min_periods=min(10, len(s))).mean()
        )
        bars["high_252"] = bars.groupby("symbol")["high"].transform(
            lambda s: s.rolling(252, min_periods=min(50, len(s))).max()
        )
        bars["low_252"] = bars.groupby("symbol")["low"].transform(
            lambda s: s.rolling(252, min_periods=min(50, len(s))).min()
        )

        # 1-year return and volatility
        bars["close_252d"] = bars.groupby("symbol")["close"].shift(252)
        bars["close_21d"] = bars.groupby("symbol")["close"].shift(21)
        bars["close_63d"] = bars.groupby("symbol")["close"].shift(63)

        bars["ret_1y"] = (bars["close"] / bars["close_252d"] - 1.0)
        bars["ret_1m"] = (bars["close"] / bars["close_21d"] - 1.0) * 100.0
        bars["ret_3m"] = (bars["close"] / bars["close_63d"] - 1.0) * 100.0

        bars["daily_ret"] = bars.groupby("symbol")["close"].pct_change()
        bars["vol_252"] = bars.groupby("symbol")["daily_ret"].transform(
            lambda s: s.rolling(252, min_periods=min(50, len(s))).std() * np.sqrt(252)
        )
        bars["volar_score"] = bars["ret_1y"] / bars["vol_252"].clip(lower=0.05)

        # Relative Strength vs Benchmark
        bars["rs_ratio_raw"] = bars["close"] / bars["benchmark_close"]
        bars["rs_ema_200"] = bars.groupby("symbol")["rs_ratio_raw"].transform(
            lambda s: s.ewm(span=200, adjust=True, min_periods=min(50, len(s))).mean()
        )

        # RRG calculation
        bars = compute_rrg_metrics(bars)

        # Take snapshot for target date
        snap = bars[bars["date"] == target_date].copy()
        snap["sector"] = snap["symbol"].map(self.sector_map).fillna("INFRA_MEDIA")

        # 1. Market Breadth Engine
        self.log("Evaluating Market Breadth...")
        breadth_results = self.breadth_engine.compute_breadth(as_of_date=target_date, snapshot_df=snap)

        # Filters
        # F1: Retracement <= 20% from 52w High
        snap["pass_f1_retrace"] = snap["close"] >= (0.80 * snap["high_252"])
        # F2: Trend > 200 EMA
        snap["pass_f2_trend"] = snap["close"] > snap["ema_200"]
        # F3: Relative Strength vs Benchmark > RS EMA 200
        snap["pass_f3_rs"] = snap["rs_ratio_raw"] > snap["rs_ema_200"]

        # Combined Strategy Pass
        snap["pass_all_filters"] = (
            snap["pass_f1_retrace"] & snap["pass_f2_trend"] & snap["pass_f3_rs"] & (snap["volar_score"] > 0)
        )

        passed_df = snap[snap["pass_all_filters"]].copy()
        passed_df = passed_df.sort_values(by="volar_score", ascending=False).reset_index(drop=True)
        top_df = passed_df.head(top_n).copy()
        top_df["rank"] = range(1, len(top_df) + 1)

        # 2. Sector Rotation Engine
        self.log("Evaluating Sector Rotation...")
        top_symbols = top_df["symbol"].tolist()
        sector_results = self.sector_engine.compute_sector_rotation(
            as_of_date=target_date,
            snapshot_df=snap,
            top_20_symbols=top_symbols
        )

        # 3. Market Regime
        regime_info = self.evaluate_regime(target_date)

        # Export CSV
        if export_csv:
            reports_dir = self.base_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            out_csv = reports_dir / "screener_output_live.csv"
            
            export_cols = [
                "rank", "symbol", "close", "sector", "volar_score", "ret_1y", "vol_252",
                "high_252", "ema_200", "rrg_quadrant", "rrg_rs_ratio", "rrg_rs_momentum",
                "pass_f1_retrace", "pass_f2_trend", "pass_f3_rs"
            ]
            avail_cols = [c for c in export_cols if c in top_df.columns]
            top_df[avail_cols].to_csv(out_csv, index=False)
            self.log(f"Exported screener candidates to {out_csv}")

        return top_df, breadth_results, sector_results, regime_info


def format_screener_tearsheet(
    top_df: pd.DataFrame,
    breadth: Dict,
    sectors: Dict,
    regime: Dict,
    as_of_date: str
) -> str:
    """Formats plain-text / ANSI terminal summary tearsheet."""
    lines = []
    lines.append("=" * 74)
    lines.append(f" PROJECT MIP: WEEKLY MOMENTUM SCANNER TEARSHEET ({as_of_date})")
    lines.append("=" * 74)

    # 1. Market Regime & Breadth
    lines.append(f"\n[1] MARKET REGIME & BREADTH")
    lines.append(f"  Benchmark Regime:  {regime.get('label', 'N/A')}")
    b_tp = breadth.get("trend_participation", {})
    b_hp = breadth.get("high_proximity", {})
    b_nhl = breadth.get("net_highs_lows", {})
    b_reg = breadth.get("regime", {})
    lines.append(f"  Breadth State:     {b_reg.get('label', 'N/A')}")
    lines.append(f"  Trend Breadth:     >200 EMA: {b_tp.get('pct_above_200_ema', 0)}% | >50 EMA: {b_tp.get('pct_above_50_ema', 0)}% | >20 EMA: {b_tp.get('pct_above_20_ema', 0)}%")
    lines.append(f"  High Proximity:    Within 20% of 52wH: {b_hp.get('pct_within_20pct_52wh', 0)}% | Within 5%: {b_hp.get('pct_within_5pct_52wh', 0)}%")
    lines.append(f"  52-Week Net Highs: +{b_nhl.get('new_52w_highs', 0)} / -{b_nhl.get('new_52w_lows', 0)} (Net: {b_nhl.get('net_highs_lows', 0):+d})")

    # 2. Sector Rotation Summary
    lines.append(f"\n[2] SECTOR ROTATION RANKINGS")
    lines.append(f"  {'Rank':<5}{'Sector':<14}{'1M Ret':<10}{'Alpha 1M':<11}{'>200EMA':<10}{'RRG Quad':<12}{'Top20'}")
    lines.append("  " + "-" * 68)
    for s in sectors.get("sectors", [])[:6]:
        lines.append(
            f"  {s['rank']:<5}{s['sector']:<14}{s['ret_1m']:+6.2f}%   {s['alpha_1m']:+6.2f}%    "
            f"{s['breadth_200_pct']:5.1f}%    {s['rrg_quadrant']:<12}{s['top_20_count']}"
        )

    # 3. Top Candidates
    lines.append(f"\n[3] TOP MOMENTUM CANDIDATES (PORTFOLIO ALLOCATION)")
    lines.append(f"  {'Rank':<5}{'Symbol':<14}{'Close (₹)':<12}{'Sector':<12}{'Volar':<8}{'1Y Ret':<10}{'RRG Quad'}")
    lines.append("  " + "-" * 68)
    for _, row in top_df.iterrows():
        ret_1y_pct = row['ret_1y'] * 100.0 if 'ret_1y' in row else 0.0
        lines.append(
            f"  {int(row['rank']):<5}{row['symbol']:<14}{row['close']:<12.2f}{row['sector']:<12}"
            f"{row['volar_score']:<8.2f}{ret_1y_pct:+6.1f}%    {row['rrg_quadrant']}"
        )

    lines.append("=" * 74)
    return "\n".join(lines)
