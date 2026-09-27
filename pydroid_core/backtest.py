"""
Project MIP Pydroid 3: Lightweight Vector Backtest Engine
Directive: DIR-PROD-PYDROID3-PORT-01

Fast historical backtest simulator running directly on SQLite universe data:
  - Monthly rebalancing simulation.
  - Multi-factor momentum ranking (Volar score: Return / Volatility).
  - Exit buffer and cash filter.
  - Generates comprehensive tearsheet: CAGR, Sharpe, Sortino, Calmar, MaxDD, Win Rate.
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
    load_bars,
    load_trading_calendar,
)


class LightweightBacktester:
    """Zero-compiler vectorized portfolio backtester for Pydroid 3."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or get_base_dir()
        self.benchmark_csv = self.base_dir / "data" / "benchmark_nifty500.csv"

    def log(self, msg: str):
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [Backtest] {msg}")

    def load_benchmark(self) -> pd.DataFrame:
        if not self.benchmark_csv.exists():
            return pd.DataFrame(columns=["date", "close"])
        df = pd.read_csv(self.benchmark_csv)
        df["date"] = df["date"].astype(str)
        return df

    def run(
        self,
        start_date: str = "2016-01-01",
        end_date: str = "2026-08-31",
        top_n: int = 20,
        initial_capital: float = 1_000_000.0,
        friction_bps: float = 15.0,  # 15 bps statutory fees
    ) -> Dict:
        """Runs the historical monthly rebalance strategy backtest."""
        self.log(f"Running backtest from {start_date} to {end_date} (Top {top_n})...")
        
        # Determine lookback start (1.5 years prior for indicators)
        start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        warmup_dt = start_dt - datetime.timedelta(days=550)
        warmup_str = warmup_dt.strftime("%Y-%m-%d")

        self.log(f"Loading bars from SQLite ({warmup_str} to {end_date})...")
        bars = load_bars(start_date=warmup_str, end_date=end_date)
        bars["date"] = bars["date"].astype(str)
        bars = bars.sort_values(by=["symbol", "date"]).reset_index(drop=True)

        self.log("Computing momentum factors across universe...")
        bars["close_252d"] = bars.groupby("symbol")["close"].shift(252)
        bars["ret_1y"] = (bars["close"] / bars["close_252d"] - 1.0)
        bars["daily_ret"] = bars.groupby("symbol")["close"].pct_change()
        bars["vol_252"] = bars.groupby("symbol")["daily_ret"].transform(
            lambda s: s.rolling(252, min_periods=min(50, len(s))).std() * np.sqrt(252)
        )
        bars["volar"] = bars["ret_1y"] / bars["vol_252"].clip(lower=0.05)
        bars["ema_200"] = bars.groupby("symbol")["close"].transform(
            lambda s: s.ewm(span=200, adjust=True, min_periods=min(50, len(s))).mean()
        )
        bars["high_252"] = bars.groupby("symbol")["high"].transform(
            lambda s: s.rolling(252, min_periods=min(50, len(s))).max()
        )

        # Filters
        bars["pass_retrace"] = bars["close"] >= 0.80 * bars["high_252"]
        bars["pass_trend"] = bars["close"] > bars["ema_200"]
        bars["pass_all"] = bars["pass_retrace"] & bars["pass_trend"] & (bars["volar"] > 0)

        # Identify monthly rebalance dates (last trading day of each month)
        all_dates = sorted(bars["date"].unique())
        test_dates = [d for d in all_dates if d >= start_date]

        # Group by YYYY-MM and take last date
        df_dates = pd.DataFrame({"date": test_dates})
        df_dates["month"] = df_dates["date"].str[:7]
        rebalance_dates = df_dates.groupby("month")["date"].last().tolist()

        self.log(f"Simulating across {len(rebalance_dates)} monthly rebalance periods...")

        # Benchmark reference
        b_df = self.load_benchmark()
        bm_map = dict(zip(b_df["date"], b_df["close"])) if not b_df.empty else {}

        capital = initial_capital
        portfolio_equity = [(rebalance_dates[0], capital)]
        trades_count = 0
        winning_trades = 0
        total_closed_trades = 0

        current_holdings = {}  # {symbol: shares}

        # Pre-index only needed rebalance dates for instant O(1) lookups
        self.log(f"Pre-indexing {len(rebalance_dates)} rebalance snapshots...")
        reb_date_set = set(rebalance_dates)
        reb_bars = bars[bars["date"].isin(reb_date_set)]
        bars_by_date = {d: g for d, g in reb_bars.groupby("date")}

        for i in range(len(rebalance_dates) - 1):
            reb_date = rebalance_dates[i]
            next_reb_date = rebalance_dates[i + 1]

            # Price lookup for current date (O(1) instant hash lookup)
            reb_slice = bars_by_date.get(reb_date, pd.DataFrame())
            if reb_slice.empty:
                continue
            close_map_reb = dict(zip(reb_slice["symbol"], reb_slice["close"]))

            # Evaluate strategy selection
            candidates = reb_slice[reb_slice["pass_all"]].sort_values(by="volar", ascending=False)
            selected_symbols = candidates["symbol"].head(top_n).tolist()

            # Mark to market prior holdings & calculate closed trades
            if current_holdings:
                reb_val = 0.0
                for sym, shares in current_holdings.items():
                    px = close_map_reb.get(sym, 0.0)
                    reb_val += shares * px
                capital = reb_val

            # Reallocate equally
            if selected_symbols and capital > 0:
                target_alloc = capital / len(selected_symbols)
                new_holdings = {}
                for sym in selected_symbols:
                    px = close_map_reb.get(sym, 0.0)
                    if px > 0:
                        shares = (target_alloc * (1.0 - friction_bps / 10000.0)) / px
                        new_holdings[sym] = (shares, px)
                        trades_count += 1
                
                # Next period close lookup (O(1) hash lookup)
                next_slice = bars_by_date.get(next_reb_date, pd.DataFrame())
                close_map_next = dict(zip(next_slice["symbol"], next_slice["close"])) if not next_slice.empty else {}

                next_val = 0.0
                for sym, (shares, buy_px) in new_holdings.items():
                    exit_px = close_map_next.get(sym, buy_px)
                    next_val += shares * exit_px
                    total_closed_trades += 1
                    if exit_px > buy_px:
                        winning_trades += 1
                
                capital = next_val
                current_holdings = {sym: info[0] for sym, info in new_holdings.items()}
            else:
                # 100% Cash preservation
                current_holdings = {}

            portfolio_equity.append((next_reb_date, capital))

        # Metrics calculation
        eq_df = pd.DataFrame(portfolio_equity, columns=["date", "equity"])
        eq_df["ret"] = eq_df["equity"].pct_change().fillna(0.0)

        total_return = (eq_df["equity"].iloc[-1] / initial_capital) - 1.0
        n_years = max(1.0, (datetime.datetime.strptime(end_date, "%Y-%m-%d") - start_dt).days / 365.25)
        cagr = ((eq_df["equity"].iloc[-1] / initial_capital) ** (1.0 / n_years) - 1.0) * 100.0

        # Drawdown
        eq_df["peak"] = eq_df["equity"].cummax()
        eq_df["drawdown"] = (eq_df["equity"] - eq_df["peak"]) / eq_df["peak"]
        max_dd = float(eq_df["drawdown"].min()) * 100.0

        # Ratios (annualized from monthly)
        ann_mean = float(eq_df["ret"].mean()) * 12.0
        ann_std = float(eq_df["ret"].std()) * np.sqrt(12.0)
        sharpe = round(ann_mean / ann_std, 2) if ann_std > 0 else 0.0

        downside_std = float(eq_df[eq_df["ret"] < 0]["ret"].std()) * np.sqrt(12.0)
        sortino = round(ann_mean / downside_std, 2) if downside_std > 0 else 0.0
        calmar = round(cagr / abs(max_dd), 2) if abs(max_dd) > 0 else 0.0

        win_rate = round((winning_trades / max(1, total_closed_trades)) * 100.0, 1)

        # Benchmark comparison (Robust nearest-date interpolation & fallback)
        if not b_df.empty:
            b_start_rows = b_df[b_df["date"] >= start_date]
            b_start_px = float(b_start_rows.iloc[0]["close"]) if not b_start_rows.empty else float(b_df.iloc[0]["close"])

            b_end_rows = b_df[b_df["date"] <= end_date]
            b_end_px = float(b_end_rows.iloc[-1]["close"]) if not b_end_rows.empty else float(b_df.iloc[-1]["close"])

            if b_start_px > 0 and b_end_px > 0:
                bm_cagr = ((b_end_px / b_start_px) ** (1.0 / n_years) - 1.0) * 100.0
            else:
                bm_cagr = 0.0
        else:
            bm_cagr = 0.0

        results = {
            "start_date": start_date,
            "end_date": end_date,
            "years": round(n_years, 2),
            "initial_capital": initial_capital,
            "final_equity": round(capital, 2),
            "total_return_pct": round(total_return * 100.0, 2),
            "cagr_pct": round(cagr, 2),
            "benchmark_cagr_pct": round(bm_cagr, 2),
            "excess_cagr_pct": round(cagr - bm_cagr, 2),
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "max_drawdown_pct": round(max_dd, 2),
            "total_trades": total_closed_trades,
            "win_rate_pct": win_rate,
        }

        # Export to reports/
        reports_dir = self.base_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        with open(reports_dir / "backtest_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results
