"""
Project MIP Pydroid 3: Production Momentum Scanner
Directive: DIR-PROD-PYDROID3-PARITY-01 (MIP-1 v5.5.1 Full Parity)

Evaluates verified institutional 5-tier momentum strategy rules on SQLite universe:
  1. Filter 1 (Retracement): Close >= 0.80 * 252d High.
  2. Filter 2 (Trend): Close > 200 EMA.
  3. Filter 3 (Relative Strength): Stock / NIFTY 500 ratio > 200 EMA of ratio.
  4. Ranking Metric: Volar Score = Return_252 / max(vol_252, 0.05).
  5. Market Regime: NIFTY 500 Close vs 20 EMA (Normal vs Defensive).
  6. Sector Concentration Hard Cap: Max 2 stocks per industry/sector (anti-clustering).
  7. ATR-14 Volatility Risk Parity Sizing & 2x ATR dynamic stop loss.
  8. Integrated Definedge Momentify ALL-ONE ETF Engine & NSE Delivery Manager.
  9. Automatic 12-Sheet Institutional Excel Workbook Generation (openpyxl).
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
    load_universe_constituents,
    get_universe_label,
)
from .rrg import compute_rrg_metrics
from .breadth import MarketBreadthEngine
from .sector_rotation import SectorRotationEngine
from .delivery import NSEDeliveryManager
from .etf_engine import ETFMomentumEngine
from .excel_generator import InstitutionalExcelGenerator


class PydroidScanner:
    """Institutional momentum screener with full MIP-1 v5.5.1 parity."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else get_base_dir()
        self.benchmark_csv = self.base_dir / "data" / "benchmark_nifty500.csv"
        self.sector_map = load_symbol_sector_map()
        self.breadth_engine = MarketBreadthEngine(self.base_dir)
        self.sector_engine = SectorRotationEngine(self.base_dir)
        self.delivery_manager = NSEDeliveryManager(self.base_dir / "data" / "bhavcopy_delivery")
        self.etf_engine = ETFMomentumEngine(self.base_dir)
        self.excel_generator = InstitutionalExcelGenerator(self.base_dir)

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

    def _record_picks_history(self, target_date: str, top_df: pd.DataFrame, market_bullish: bool):
        """Records weekly picks into SQLite picks_history table for Pick Performance tracking."""
        try:
            from .data_engine import get_connection
            conn = get_connection(read_only=False, reuse=False)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS picks_history (
                    pick_date TEXT,
                    symbol TEXT,
                    rank INTEGER,
                    industry TEXT,
                    regime TEXT,
                    signal_type TEXT,
                    status TEXT,
                    entry_price REAL,
                    ret_1w REAL,
                    ret_1m REAL,
                    ret_since REAL,
                    last_px_date TEXT,
                    volar_score REAL,
                    PRIMARY KEY (pick_date, symbol)
                )
            """)
            regime_str = "BULL" if market_bullish else "BEAR"
            sig_str = "BUY" if market_bullish else "BEAR_HOLD"
            for _, r in top_df.iterrows():
                sym = str(r["symbol"]).strip().upper()
                rnk = int(r.get("rank", 0))
                ind = str(r.get("industry", r.get("sector", "SERVICES"))).strip().upper()
                px = float(r.get("close", 0.0))
                volar = float(r.get("volar_score", 0.0))
                cursor.execute("""
                    INSERT OR REPLACE INTO picks_history
                    (pick_date, symbol, rank, industry, regime, signal_type, status, entry_price, ret_1w, ret_1m, ret_since, last_px_date, volar_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (target_date, sym, rnk, ind, regime_str, sig_str, "ACTIVE", px, None, None, 0.0, target_date, volar))

            # Update returns for past active picks using current close prices
            px_map = dict(zip(top_df["symbol"], top_df["close"]))
            cursor.execute("SELECT pick_date, symbol, entry_price FROM picks_history WHERE status='ACTIVE' AND pick_date != ?", (target_date,))
            active_picks = cursor.fetchall()
            for pdate, sym, entry in active_picks:
                if sym in px_map and entry > 0:
                    curr_px = float(px_map[sym])
                    ret_s = round((curr_px / entry - 1.0) * 100.0, 2)
                    cursor.execute("""
                        UPDATE picks_history
                        SET ret_since=?, last_px_date=?
                        WHERE pick_date=? AND symbol=?
                    """, (ret_s, target_date, pdate, sym))

            conn.commit()
            conn.close()
        except Exception as e:
            self.log(f"Warning: Failed to record picks history ({e})")

    def run_scan(
        self,
        as_of_date: Optional[str] = None,
        universe_mode: Optional[str] = None,
        top_n: Optional[int] = None,
        lookback_days: int = 550,
        max_per_sector: Optional[int] = None,
        export_csv: bool = True,
        export_excel: bool = True,
        auto_update_universe: bool = True,
    ) -> Tuple[pd.DataFrame, Dict, Dict, Dict, Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        Executes end-to-end screener pipeline on SQLite universe.
        If auto_update_universe=True and as_of_date is None, automatically syncs universe
        with the latest market date before running the scan.
        Filters universe by universe_mode ('NIFTY500', 'NIFTY750', 'ALL').
        Consumes active investing settings from data/investing_settings.json.
        Returns: (top_df, breadth_results, sector_results, regime_info, top_etf_df, delivery_df)
        """
        from .settings import load_investing_settings
        st = load_investing_settings(self.base_dir)
        universe_mode = universe_mode or str(st.get("universe_mode", "NIFTY500"))
        top_n = int(top_n if top_n is not None else st.get("top_n", 20))
        max_per_sector = int(max_per_sector if max_per_sector is not None else st.get("max_per_sector", 2))
        self.atr_stop_multiplier = float(st.get("atr_stop_multiplier", 2.0))

        # 0. Dynamic Market Data Auto-Sync
        if auto_update_universe and as_of_date is None:
            self.log("Auto-Sync Active: Checking NSE archives for latest market data...")
            try:
                from .auto_fetch import PydroidAutoFetch
                fetcher = PydroidAutoFetch(self.base_dir)
                sync_res = fetcher.sync_universe(dry_run=False)
                dates_fetched = sync_res.get("dates_fetched", 0)
                if dates_fetched > 0:
                    self.log(f"✓ Successfully fetched and saved {dates_fetched} new market session(s) to SQLite universe!")
                else:
                    self.log("✓ Universe is already up to date with latest market session.")
            except Exception as e:
                self.log(f"Warning: Auto-update universe check skipped ({e}). Proceeding with current data.")

        target_date = as_of_date or get_latest_date()
        u_label = get_universe_label(universe_mode)
        self.log(f"Starting Production Momentum Scan as of {target_date} [{u_label}]...")

        target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d")
        start_str = (target_dt - datetime.timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        self.log(f"Loading bars from SQLite ({start_str} to {target_date})...")
        bars = load_bars(start_date=start_str, end_date=target_date, include_delisted=False)

        active_today = set(bars[bars["date"] == target_date]["symbol"].unique())
        
        # Universe constituent filtering (Nifty 500 / Nifty 750 / All Active)
        u_constituents = load_universe_constituents(universe_mode)
        if u_constituents:
            initial_count = len(active_today)
            active_today = active_today.intersection(u_constituents)
            self.log(f"Universe Filter [{u_label}]: {len(active_today):,} / {initial_count:,} active symbols matched.")
        else:
            self.log(f"Universe Filter [{u_label}]: Evaluating all {len(active_today):,} active symbols.")

        bars = bars[bars["symbol"].isin(active_today)].copy()
        bars = bars.sort_values(by=["symbol", "date"]).reset_index(drop=True)

        self.log("Computing EMAs, rolling highs/lows, ATR-14, volatility, and returns...")
        bars["high_252"] = bars.groupby("symbol")["high"].transform(
            lambda s: s.rolling(252, min_periods=min(50, len(s))).max()
        )
        bars["low_252"] = bars.groupby("symbol")["low"].transform(
            lambda s: s.rolling(252, min_periods=min(50, len(s))).min()
        )
        bars["ema_200"] = bars.groupby("symbol")["close"].transform(
            lambda s: s.ewm(span=200, adjust=True, min_periods=min(50, len(s))).mean()
        )
        bars["ema_50"] = bars.groupby("symbol")["close"].transform(
            lambda s: s.ewm(span=50, adjust=True, min_periods=min(20, len(s))).mean()
        )
        bars["ema_20"] = bars.groupby("symbol")["close"].transform(
            lambda s: s.ewm(span=20, adjust=True, min_periods=min(10, len(s))).mean()
        )
        bars["ret_252"] = bars.groupby("symbol")["close"].transform(
            lambda s: s / s.shift(252) - 1.0
        )
        bars["ret_1y"] = bars["ret_252"] * 100.0
        bars["ret_21"] = bars.groupby("symbol")["close"].transform(
            lambda s: s / s.shift(21) - 1.0
        )
        bars["ret_63"] = bars.groupby("symbol")["close"].transform(
            lambda s: s / s.shift(63) - 1.0
        )
        bars["ret_1m"] = bars["ret_21"] * 100.0
        bars["ret_3m"] = bars["ret_63"] * 100.0
        bars["sector"] = bars["symbol"].map(lambda sym: self.sector_map.get(sym, "OTHER"))

        # Volatility & Volar Score
        bars["ret_1d"] = bars.groupby("symbol")["close"].pct_change().fillna(0.0)
        bars["vol_252"] = bars.groupby("symbol")["ret_1d"].transform(
            lambda s: s.rolling(252, min_periods=min(20, len(s))).std() * np.sqrt(252)
        ).fillna(0.30).replace(0.0, 0.30)
        bars["volar_score"] = bars["ret_252"] / bars["vol_252"].clip(lower=0.05)

        # ATR-14 Calculation
        prev_close = bars.groupby("symbol")["close"].shift(1)
        tr1 = bars["high"] - bars["low"]
        tr2 = (bars["high"] - prev_close).abs()
        tr3 = (bars["low"] - prev_close).abs()
        bars["tr"] = np.maximum(tr1, np.maximum(tr2, tr3))
        bars["atr_14"] = bars.groupby("symbol")["tr"].transform(
            lambda s: s.rolling(14, min_periods=min(5, len(s))).mean()
        ).fillna(bars["close"] * 0.03)

        # 30-day Turnover & RSI-14
        bars["turnover"] = bars["close"] * bars["volume"]
        bars["turnover_30d"] = bars.groupby("symbol")["turnover"].transform(
            lambda s: s.rolling(30, min_periods=min(10, len(s))).mean()
        ).fillna(0.0)
        bars["turnover_30d_cr"] = (bars["turnover_30d"] / 1e7).round(2)

        def _calc_rsi(s, period=14):
            d = s.diff()
            g = d.clip(lower=0)
            l = -d.clip(upper=0)
            ag = g.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()
            al = l.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()
            rs = ag / al.replace(0, np.nan)
            return (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

        bars["rsi_14"] = bars.groupby("symbol")["close"].transform(_calc_rsi).round(2)
        bars["max_move_60"] = bars.groupby("symbol")["ret_1d"].transform(
            lambda s: s.abs().rolling(60, min_periods=min(10, len(s))).max()
        ).fillna(0.0)
        bars["pct_above_ema200"] = ((bars["close"] / bars["ema_200"] - 1.0) * 100.0).round(2)

        # Benchmark mapping
        b_df = self.load_benchmark()
        bm_map = dict(zip(b_df["date"], b_df["close"])) if not b_df.empty else {}
        bars["benchmark_close"] = bars["date"].map(bm_map)
        bars["benchmark_close"] = bars.groupby("symbol")["benchmark_close"].ffill().bfill().fillna(1.0)

        # RS Ratio
        bars["rs_ratio_raw"] = bars["close"] / bars["benchmark_close"]
        bars["rs_ema_200"] = bars.groupby("symbol")["rs_ratio_raw"].transform(
            lambda s: s.ewm(span=200, adjust=True, min_periods=min(50, len(s))).mean()
        )

        # RRG calculation
        bars = compute_rrg_metrics(bars)

        # Target date cross-section snapshot
        snap = bars[bars["date"] == target_date].copy()
        if snap.empty:
            raise ValueError(f"No bars available for target date {target_date}")

        # Diagnostic flags on snapshot
        snap["extension_flag"] = np.where(
            snap["pct_above_ema200"] > 40.0, "⚠ EXT >40%",
            np.where(snap["pct_above_ema200"] > 25.0, "EXT >25%", "")
        )
        snap["liquidity_flag"] = np.where(
            snap["turnover_30d"] < 1e7, "⚠ LOW LIQ (<₹1Cr)", ""
        )
        snap["sanity_flag"] = np.where(
            snap["max_move_60"] > 0.35, "⚠ SANITY (>±35% 60d)", ""
        )
        snap["industry"] = snap["sector"]
        snap["above_sma50"] = snap["close"] > snap["ema_50"]
        snap["above_sma100"] = snap["close"] > snap["close"].rolling(100, min_periods=20).mean().fillna(snap["close"])
        snap["above_sma200"] = snap["close"] > snap["ema_200"]
        snap["rs_positive"] = snap["rs_ratio_raw"] > 1.0
        snap["trend_aligned"] = snap["close"] > snap["ema_200"]
        snap["elite"] = (snap["close"] > snap["ema_200"]) & (snap["close"] >= 0.85 * snap["high_252"])
        snap["at_52w_high"] = snap["close"] >= 0.99 * snap["high_252"]

        # 1. Market Breadth Engine
        self.log("Evaluating Market Breadth...")
        breadth_results = self.breadth_engine.compute_breadth(as_of_date=target_date, snapshot_df=snap)

        # Strategy Filters
        snap["pass_f1_retrace"] = snap["close"] >= (0.80 * snap["high_252"])
        snap["pass_f2_trend"] = snap["close"] > snap["ema_200"]
        snap["pass_f3_rs"] = snap["rs_ratio_raw"] > snap["rs_ema_200"]
        snap["pass_all_filters"] = (
            snap["pass_f1_retrace"] & snap["pass_f2_trend"] & snap["pass_f3_rs"] & (snap["volar_score"] > 0)
        )

        passed_df = snap[snap["pass_all_filters"]].copy()
        # STRICT CONSTRAINT: Candidates ranked strictly by Volar score descending!
        passed_df = passed_df.sort_values(by="volar_score", ascending=False).reset_index(drop=True)

        # Enforce Sector Concentration Hard Cap (Max 2 stocks per industry/sector)
        sec_counts = {}
        top_rows = []
        for _, r in passed_df.iterrows():
            sec = str(r.get("sector", "OTHER")).strip().upper()
            if sec_counts.get(sec, 0) < max_per_sector:
                top_rows.append(r)
                sec_counts[sec] = sec_counts.get(sec, 0) + 1
            if len(top_rows) >= top_n:
                break

        top_df = pd.DataFrame(top_rows).reset_index(drop=True) if top_rows else passed_df.head(top_n).copy()
        top_df["rank"] = range(1, len(top_df) + 1)

        # Dynamic Stop Loss
        mult = getattr(self, "atr_stop_multiplier", 2.0)
        top_df["stop_loss"] = (top_df["close"] - mult * top_df["atr_14"]).clip(lower=0.01).round(2)

        # 2. Sector Rotation Engine
        self.log("Evaluating Sector Rotation...")
        top_symbols = top_df["symbol"].tolist()
        sector_results = self.sector_engine.compute_sector_rotation(
            as_of_date=target_date,
            snapshot_df=snap,
            top_20_symbols=top_symbols,
        )

        # 3. Market Regime
        regime_info = self.evaluate_regime(target_date)
        market_bullish = regime_info.get("is_normal_regime", True)

        # 4. Delivery Volume & Accumulation/Distribution
        self.log("Fetching NSE Delivery Accumulation/Distribution metrics...")
        try:
            delivery_df = self.delivery_manager.get_delivery_data(target_dt.date())
        except Exception:
            delivery_df = pd.DataFrame()

        # Map delivery data to top_df and snap
        if delivery_df is not None and not delivery_df.empty:
            dmap = delivery_df.set_index("symbol").to_dict(orient="index")
            top_df["deliv_per"] = top_df["symbol"].map(lambda s: dmap.get(s, {}).get("delivery_pct", np.nan))
            top_df["deliv_qty"] = top_df["symbol"].map(lambda s: dmap.get(s, {}).get("delivery_qty", np.nan))
            top_df["deliv_times"] = top_df["symbol"].map(lambda s: dmap.get(s, {}).get("delivery_multiple_5d", np.nan))
            top_df["deliv_val_cr"] = top_df["symbol"].map(lambda s: dmap.get(s, {}).get("delivery_value_cr", np.nan))
            top_df["delivery_action"] = top_df["symbol"].map(lambda s: dmap.get(s, {}).get("action", "⚪ NEUTRAL"))
            snap["deliv_per"] = snap["symbol"].map(lambda s: dmap.get(s, {}).get("delivery_pct", np.nan))
            snap["deliv_qty"] = snap["symbol"].map(lambda s: dmap.get(s, {}).get("delivery_qty", np.nan))
            snap["deliv_times"] = snap["symbol"].map(lambda s: dmap.get(s, {}).get("delivery_multiple_5d", np.nan))
            snap["deliv_val_cr"] = snap["symbol"].map(lambda s: dmap.get(s, {}).get("delivery_value_cr", np.nan))

        # Position Sizing (ATR Risk-Parity for ₹1L Portfolio)
        total_cap = 100000.0
        risk_budget = total_cap * 0.01  # 1% risk budget
        qtys, vals = [], []
        for _, r in top_df.iterrows():
            p = float(r["close"])
            a = float(r["atr_14"])
            rps = max(2.0 * a, p * 0.02)
            q = int(risk_budget // rps) if (rps > 0 and p > 0) else 0
            q = max(0, min(q, int((total_cap * 0.25) // p))) if p > 0 else 0
            qtys.append(q if market_bullish else 0)
            vals.append(round(q * p, 2) if market_bullish else 0.0)
        top_df["target_qty"] = qtys
        top_df["target_val"] = vals

        # Map industry rank and rotation state
        ind_rank_map = {s["sector"]: s["rank"] for s in sector_results.get("sectors", [])}
        ind_rot_map = {s["sector"]: s.get("rotation_state", "NEUTRAL") for s in sector_results.get("sectors", [])}
        top_df["industry_rank"] = top_df["sector"].map(ind_rank_map).fillna(99).astype(int)
        top_df["rotation_state"] = top_df["sector"].map(ind_rot_map).fillna("NEUTRAL")

        # Informational Selection Tier (order is STRICTLY by Volar!)
        def _assign_tier(row):
            q = str(row.get("rrg_quadrant", "UNKNOWN")).upper()
            rot = str(row.get("rotation_state", "NEUTRAL")).upper()
            if (q == "LEADING" and "UPTREND" in rot) or (q == "IMPROVING" and "RECOVERY" in rot):
                t = "TIER-1 (Leading + Uptrend)"
            elif q in ["LEADING", "IMPROVING"]:
                t = "TIER-2 (RRG right side)"
            else:
                t = "TIER-3 (All)"
            return f"HOLD (BEAR - {t})" if not market_bullish else t

        top_df["selection_tier"] = top_df.apply(_assign_tier, axis=1)
        top_df["tradingview"] = top_df["symbol"].map(lambda s: f"https://in.tradingview.com/chart/?symbol=NSE:{s}")

        # Record picks into persistent SQLite table
        self._record_picks_history(target_date, top_df, market_bullish)

        # 5. Definedge Momentify ALL-ONE ETF Momentum Engine
        self.log("Scanning Definedge Momentify ALL-ONE ETFs...")
        top_etf_df = None
        etf_ranking_df = None
        try:
            all_one = self.etf_engine.get_all_one_universe()
            if not all_one.empty:
                etf_ranking_df, top_etf_df = self.etf_engine.run_etf_scan(all_one, market_bullish=market_bullish, as_of_date=target_date)
                self.log(f"Ranked {len(etf_ranking_df)} ALL-ONE ETFs | Top {len(top_etf_df)} Picks Selected")
        except Exception as e:
            self.log(f"Warning: ETF scan encountered an issue: {e}")

        # 6. Export Reports (CSV & 12-Sheet Excel)
        reports_dir = self.base_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        if export_csv:
            out_csv = reports_dir / "screener_output_live.csv"
            export_cols = [
                "rank", "symbol", "close", "sector", "volar_score", "ret_1y", "vol_252",
                "high_252", "ema_200", "atr_14", "stop_loss", "rrg_quadrant", "rrg_rs_ratio",
                "rrg_rs_momentum", "pass_f1_retrace", "pass_f2_trend", "pass_f3_rs"
            ]
            avail_cols = [c for c in export_cols if c in top_df.columns]
            top_df[avail_cols].to_csv(out_csv, index=False)
            self.log(f"Exported screener candidates to {out_csv}")

        # 6. Generate Complete Visual Artifacts Suite (Charts & Tearsheets)
        chart_paths = {}
        try:
            from .visuals import generate_all_visuals
            self.log(f"Generating publication-quality charts & tearsheets [{u_label}]...")
            ind_hist_df = self.excel_generator._build_industry_history_df(target_date, bars)
            b_hist_df = self.excel_generator._build_breadth_history_df(target_date, bars, u_label)
            chart_paths = generate_all_visuals(
                as_of_date=target_date,
                breadth_data=breadth_results,
                sector_data=sector_results,
                top_df=top_df,
                ind_hist_df=ind_hist_df,
                breadth_hist_df=b_hist_df,
                universe_label=u_label,
                bars_df=bars,
            )
            top_df.attrs["chart_paths"] = chart_paths
        except Exception as e:
            self.log(f"Warning: Visuals generation skipped ({e})")

        excel_file = None
        if export_excel:
            try:
                self.log("Compiling institutional 14-sheet Excel workbook (with embedded charts & raw metrics)...")
                excel_file = self.excel_generator.generate_workbook(
                    as_of_date=target_date,
                    screener_df=snap[snap["pass_all_filters"]].sort_values("volar_score", ascending=False) if not snap[snap["pass_all_filters"]].empty else top_df,
                    top_candidates_df=top_df,
                    breadth_data=breadth_results,
                    sector_data=sector_results,
                    delivery_df=delivery_df,
                    etf_ranking_df=etf_ranking_df,
                    top_etf_df=top_etf_df,
                    market_bullish=market_bullish,
                    universe_label=u_label,
                    bars_df=bars,
                    chart_paths=chart_paths,
                    snap_df=snap,
                )
                self.log(f"Generated 14-sheet Excel workbook: {excel_file}")
                top_df.attrs["excel_path"] = excel_file
            except Exception as e:
                self.log(f"Warning: Excel workbook compilation failed: {e}")

        top_df.attrs["universe_label"] = u_label
        top_df.attrs["universe_mode"] = universe_mode
        return top_df, breadth_results, sector_results, regime_info, top_etf_df, delivery_df


def format_screener_tearsheet(
    top_df: pd.DataFrame,
    breadth: Dict,
    sectors: Dict,
    regime: Dict,
    as_of_date: str,
    top_etf_df: Optional[pd.DataFrame] = None,
    delivery_df: Optional[pd.DataFrame] = None,
    universe_label: Optional[str] = None,
) -> str:
    """Formats plain-text / ANSI terminal summary tearsheet with full v5.5.1 sections."""
    u_str = universe_label or top_df.attrs.get("universe_label", "NIFTY 500")
    lines = []
    lines.append("=" * 76)
    lines.append(f" PROJECT MIP: WEEKLY MOMENTUM SCANNER TEARSHEET ({as_of_date})")
    lines.append("=" * 76)

    # 1. Market Regime & Breadth
    lines.append(f"\n[1] MARKET REGIME & BREADTH")
    lines.append(f"  Target Universe:   {u_str}")
    lines.append(f"  Benchmark Regime:  {regime.get('label', 'N/A')}")
    b_tp = breadth.get("trend_participation", {})
    b_hp = breadth.get("high_proximity", {})
    b_nhl = breadth.get("net_highs_lows", {})
    b_reg = breadth.get("regime", {})
    lines.append(f"  Breadth State:     {b_reg.get('label', 'N/A')}")
    lines.append(f"  Trend Breadth:     >200 EMA: {b_tp.get('pct_above_200_ema', 0.0):.1f}% | >50 EMA: {b_tp.get('pct_above_50_ema', 0.0):.1f}% | >20 EMA: {b_tp.get('pct_above_20_ema', 0.0):.1f}%")
    lines.append(f"  High Proximity:    Within 20% of 52wH: {b_hp.get('pct_within_20pct_52wh', 0.0):.1f}% | Within 5%: {b_hp.get('pct_within_5pct_52wh', 0.0):.1f}%")
    lines.append(f"  52-Week Net Highs: +{b_nhl.get('new_52w_highs', 0)} / -{b_nhl.get('new_52w_lows', 0)} (Net: {b_nhl.get('net_highs_lows', 0):+d})")

    # 2. Sector Rotation Summary
    lines.append(f"\n[2] SECTOR ROTATION RANKINGS")
    lines.append(f"  {'Rank':<5}{'Sector':<14}{'1M Ret':<10}{'Alpha 1M':<11}{'>200EMA':<10}{'RRG Quad':<12}{'Top20'}")
    lines.append("  " + "-" * 70)
    for s in sectors.get("sectors", [])[:6]:
        lines.append(
            f"  {s['rank']:<5}{s['sector']:<14}{s['ret_1m']:+6.2f}%   {s['alpha_1m']:+6.2f}%    "
            f"{s['breadth_200_pct']:5.1f}%    {s['rrg_quadrant']:<12}{s['top_20_count']}"
        )

    # 3. Top Candidates (Sector Hard Cap & ATR Stop Loss)
    lines.append(f"\n[3] TOP 20 MOMENTUM CANDIDATES (SECTOR HARD CAP: MAX 2/SECTOR)")
    lines.append(f"  {'Rank':<5}{'Symbol':<13}{'Close (₹)':<11}{'Stop Loss':<11}{'Sector':<12}{'Volar':<7}{'1Y Ret':<9}{'RRG Quad'}")
    lines.append("  " + "-" * 76)
    for _, row in top_df.iterrows():
        val = float(row.get('ret_1y', 0.0))
        ret_1y_pct = val if abs(val) > 5.0 or val == 0.0 else val * 100.0
        sl_val = row.get('stop_loss', row['close'] * 0.94)
        lines.append(
            f"  {int(row['rank']):<5}{row['symbol']:<13}{row['close']:<11.2f}{sl_val:<11.2f}{row['sector']:<12}"
            f"{row['volar_score']:<7.2f}{ret_1y_pct:+6.1f}%   {row['rrg_quadrant']}"
        )

    # 4. Top 7 ALL-ONE Momentify ETFs
    if top_etf_df is not None and not top_etf_df.empty:
        lines.append(f"\n[4] DEFINEDGE MOMENTIFY ALL-ONE ETF PICKS (TOP 7)")
        lines.append(f"  {'Rank':<5}{'Symbol':<13}{'Price (₹)':<11}{'Volar':<8}{'Target Qty':<12}{'Underlying Asset'}")
        lines.append("  " + "-" * 70)
        for idx, (_, r) in enumerate(top_etf_df.head(7).iterrows(), 1):
            lines.append(
                f"  {idx:<5}{r['symbol']:<13}{r['price']:<11.2f}{r['volar_score']:<8.2f}{int(r['target_qty']):<12}{r['underlying']}"
            )

    # 5. Institutional Delivery Accumulation Spikes
    if delivery_df is not None and not delivery_df.empty:
        spikes = delivery_df[delivery_df["delivery_value_cr"].fillna(0) >= 5.0].sort_values("deliv_per", ascending=False).head(4)
        if not spikes.empty:
            lines.append(f"\n[5] TOP INSTITUTIONAL DELIVERY SPIKES (₹5Cr+)")
            lines.append(f"  {'Symbol':<14}{'Deliv %':<10}{'Deliv Times':<13}{'Deliv Value':<14}{'Action'}")
            lines.append("  " + "-" * 64)
            for _, r in spikes.iterrows():
                dt_str = f"{r['deliv_times']:.1f}x" if pd.notna(r.get('deliv_times')) else "-"
                lines.append(
                    f"  {r['symbol']:<14}{r['deliv_per']:>6.1f}%    {dt_str:<13}₹{r['delivery_value_cr']:>6.1f} Cr     {r['deliv_action']}"
                )

    lines.append("=" * 76)
    return "\n".join(lines)
