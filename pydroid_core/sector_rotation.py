"""
Project MIP Pydroid 3: Sector Rotation Engine
Directive: DIR-PROD-PYDROID3-PORT-01

Computes comprehensive Sector Rotation analytics across the 12 primary NSE sectors:
  1. Equal-weighted 1M (21d), 3M (63d), 1Y (252d) sector returns.
  2. Relative Strength Alpha vs NIFTY 500 (Alpha_1M and Alpha_3M).
  3. Sector Internal Breadth (% > 200 EMA and % within 20% of 52w High).
  4. Sector RRG Quadrant (Mean RS-Ratio and RS-Momentum).
  5. Top 20 Momentum Candidate Density.
  6. Composite Sector Rank Score:
       Score = 0.5 * Alpha_1M + 0.5 * Alpha_3M + 0.2 * (Sector_Breadth_200 - 50.0)
"""

import json
import datetime
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from .data_engine import (
    get_base_dir,
    get_latest_date,
    load_bars,
    load_symbol_sector_map,
)
from .rrg import classify_quadrant

PRIMARY_SECTORS = [
    "AUTO",
    "FINSERV",
    "CAPGOODS",
    "CHEMICALS",
    "REALTY",
    "CONSDUR",
    "FMCG",
    "PHARMA",
    "IT",
    "METALS",
    "ENERGY",
    "INFRA_MEDIA",
]

SECTOR_NAMES = {
    "AUTO": "Automobile & Auto Ancil",
    "FINSERV": "Financial Services & Banks",
    "CAPGOODS": "Capital Goods & Industrials",
    "CHEMICALS": "Chemicals & Petrochemicals",
    "REALTY": "Realty & Construction",
    "CONSDUR": "Consumer Durables",
    "FMCG": "Fast Moving Consumer Goods",
    "PHARMA": "Healthcare & Pharma",
    "IT": "Information Technology",
    "METALS": "Metals & Mining",
    "ENERGY": "Oil, Gas & Power Utilities",
    "INFRA_MEDIA": "Infra, Telecom & Media",
}


class SectorRotationEngine:
    """Quantitative Sector Rotation & Relative Strength Engine for Pydroid 3."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or get_base_dir()
        self.sector_map = load_symbol_sector_map()
        self.benchmark_csv = self.base_dir / "data" / "benchmark_nifty500.csv"

    def log(self, msg: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [SectorEngine] {msg}")

    def load_benchmark(self) -> pd.DataFrame:
        if not self.benchmark_csv.exists():
            return pd.DataFrame(columns=["date", "close"])
        df = pd.read_csv(self.benchmark_csv)
        df["date"] = df["date"].astype(str)
        return df

    def get_benchmark_returns(self, as_of_date: str) -> Dict[str, float]:
        """Calculates benchmark 21-day, 63-day, and 252-day returns."""
        b_df = self.load_benchmark()
        if b_df.empty:
            return {"bm_ret_1m": 0.0, "bm_ret_3m": 0.0, "bm_ret_1y": 0.0}

        row = b_df[b_df["date"] == as_of_date]
        if row.empty:
            prior = b_df[b_df["date"] <= as_of_date]
            if prior.empty:
                return {"bm_ret_1m": 0.0, "bm_ret_3m": 0.0, "bm_ret_1y": 0.0}
            idx = prior.index[-1]
        else:
            idx = row.index[0]

        curr_close = b_df.loc[idx, "close"]
        idx_1m = max(0, idx - 21)
        idx_3m = max(0, idx - 63)
        idx_1y = max(0, idx - 252)

        ret_1m = (curr_close / b_df.loc[idx_1m, "close"] - 1.0) * 100.0
        ret_3m = (curr_close / b_df.loc[idx_3m, "close"] - 1.0) * 100.0
        ret_1y = (curr_close / b_df.loc[idx_1y, "close"] - 1.0) * 100.0

        return {
            "bm_ret_1m": round(ret_1m, 2),
            "bm_ret_3m": round(ret_3m, 2),
            "bm_ret_1y": round(ret_1y, 2),
        }

    def compute_sector_rotation(
        self,
        as_of_date: Optional[str] = None,
        snapshot_df: Optional[pd.DataFrame] = None,
        top_20_symbols: Optional[List[str]] = None,
    ) -> Dict:
        """
        Computes all sector rotation metrics, returns, alpha, breadth, and ranking.
        """
        target_date = as_of_date or get_latest_date()
        self.log(f"Computing Sector Rotation as of {target_date}...")

        top_20_set = set(top_20_symbols) if top_20_symbols else set()
        bm_returns = self.get_benchmark_returns(target_date)

        # If snapshot_df contains precomputed columns, use it
        req_cols = {"symbol", "close", "ema_200", "high_252"}
        if snapshot_df is not None and req_cols.issubset(set(snapshot_df.columns)):
            snap = snapshot_df.copy()
            if "date" in snap.columns:
                snap = snap[snap["date"] == target_date].copy()
        else:
            # Slices bars for past 400 days
            target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d")
            start_str = (target_dt - datetime.timedelta(days=400)).strftime("%Y-%m-%d")

            bars = load_bars(start_date=start_str, end_date=target_date, include_delisted=False)
            active_today = set(bars[bars["date"] == target_date]["symbol"].unique())
            bars = bars[bars["symbol"].isin(active_today)].copy()
            bars = bars.sort_values(by=["symbol", "date"]).reset_index(drop=True)

            # Returns and EMAs
            bars["close_21d"] = bars.groupby("symbol")["close"].shift(21)
            bars["close_63d"] = bars.groupby("symbol")["close"].shift(63)
            bars["close_252d"] = bars.groupby("symbol")["close"].shift(252)

            bars["ret_1m"] = (bars["close"] / bars["close_21d"] - 1.0) * 100.0
            bars["ret_3m"] = (bars["close"] / bars["close_63d"] - 1.0) * 100.0
            bars["ret_1y"] = (bars["close"] / bars["close_252d"] - 1.0) * 100.0

            bars["ema_200"] = bars.groupby("symbol")["close"].transform(
                lambda s: s.ewm(span=200, adjust=True, min_periods=min(50, len(s))).mean()
            )
            bars["high_252"] = bars.groupby("symbol")["high"].transform(
                lambda s: s.rolling(252, min_periods=min(50, len(s))).max()
            )
            snap = bars[bars["date"] == target_date].copy()

        # Attach sector
        snap["sector"] = snap["symbol"].map(self.sector_map).fillna("INFRA_MEDIA")

        # Compute Sector Metrics
        sector_results = []
        for sec in PRIMARY_SECTORS:
            sec_df = snap[snap["sector"] == sec]
            n_stocks = len(sec_df)
            if n_stocks == 0:
                continue

            ret_1m = float(sec_df["ret_1m"].mean()) if "ret_1m" in sec_df.columns else 0.0
            ret_3m = float(sec_df["ret_3m"].mean()) if "ret_3m" in sec_df.columns else 0.0
            ret_1y = float(sec_df["ret_1y"].mean()) if "ret_1y" in sec_df.columns else 0.0

            alpha_1m = ret_1m - bm_returns["bm_ret_1m"]
            alpha_3m = ret_3m - bm_returns["bm_ret_3m"]

            # Breadth
            above_200 = int((sec_df["close"] > sec_df["ema_200"]).sum())
            breadth_200_pct = round((above_200 / n_stocks) * 100.0, 1)

            within_20 = int((sec_df["close"] >= 0.80 * sec_df["high_252"]).sum())
            near_high_pct = round((within_20 / n_stocks) * 100.0, 1)

            # RRG
            avg_rs_ratio = float(sec_df["rrg_rs_ratio"].mean()) if "rrg_rs_ratio" in sec_df.columns else 100.0
            avg_rs_mom = float(sec_df["rrg_rs_momentum"].mean()) if "rrg_rs_momentum" in sec_df.columns else 100.0
            rrg_quad = classify_quadrant(avg_rs_ratio, avg_rs_mom)

            # Top 20 Candidates
            top_20_count = int(sec_df["symbol"].isin(top_20_set).sum())
            top_20_share = round((top_20_count / 20.0) * 100.0, 1) if top_20_symbols else 0.0

            # Composite Score
            composite_score = round(0.5 * alpha_1m + 0.5 * alpha_3m + 0.2 * (breadth_200_pct - 50.0), 2)

            sector_results.append({
                "sector": sec,
                "name": SECTOR_NAMES.get(sec, sec),
                "stock_count": n_stocks,
                "ret_1m": round(ret_1m, 2),
                "ret_3m": round(ret_3m, 2),
                "ret_1y": round(ret_1y, 2),
                "alpha_1m": round(alpha_1m, 2),
                "alpha_3m": round(alpha_3m, 2),
                "breadth_200_pct": breadth_200_pct,
                "near_high_pct": near_high_pct,
                "rrg_rs_ratio": round(avg_rs_ratio, 2),
                "rrg_rs_momentum": round(avg_rs_mom, 2),
                "rrg_quadrant": rrg_quad,
                "top_20_count": top_20_count,
                "top_20_share_pct": top_20_share,
                "composite_score": composite_score,
            })

        # Rank by composite score
        sector_results.sort(key=lambda x: x["composite_score"], reverse=True)
        for rank, s in enumerate(sector_results, 1):
            s["rank"] = rank

        output = {
            "as_of_date": target_date,
            "benchmark_returns": bm_returns,
            "sectors": sector_results,
            "top_sector": sector_results[0]["sector"] if sector_results else "",
            "bottom_sector": sector_results[-1]["sector"] if sector_results else "",
        }

        # Export to reports/
        reports_dir = self.base_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_file = reports_dir / "sector_rotation_live.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        return output
