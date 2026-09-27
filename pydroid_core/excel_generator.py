"""
Project MIP Pydroid 3: Institutional 12-Sheet Excel Workbook Generator
Directive: DIR-PROD-PYDROID3-PARITY-01 (MIP-1 v5.5.1 Parity)

Generates the complete 12-sheet institutional Excel workbook:
  1. Dashboard
  2. Strategy Rationale (Dark Navy #0D47A1 tab, ELI5 quant rationale, 5-yr backtest proof)
  3. Sector Rotation
  4. Industry Ranking
  5. Industry History 30d
  6. Stock Ranking (Volar, Delivery %, ATR, TradingView links)
  7. Top Candidates (ATR Risk Parity, Stop Loss, 2-per-sector cap)
  8. Highest Delivery (Institutional accumulation spikes >= 5Cr)
  9. ETF Momentum Ranking (Definedge Momentify ALL-ONE Top 7)
 10. Pick Performance (Vintage performance tracker)
 11. Breadth History
 12. Configuration
"""

import os
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .data_engine import get_base_dir, load_bars, load_symbol_sector_map

# Institutional Color Palette
PRIMARY_BLUE = "1F4E79"
DARK_NAVY    = "0D47A1"
GREEN_COLOR  = "2E7D32"
RED_COLOR    = "C62828"
AMBER_COLOR  = "F9A825"
BG_LIGHT     = "FAFAFA"
BG_WHITE     = "FFFFFF"
FILL_GREEN   = "E8F5E9"
FILL_RED     = "FFEBEE"
FILL_AMBER   = "FFF8E1"
BORDER_GREY  = "D0D7DE"


class InstitutionalExcelGenerator:
    """Compiles the complete 12-sheet MIP-1 Excel workbook using openpyxl."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else get_base_dir()
        self.reports_dir = self.base_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_workbook(
        self,
        as_of_date: str,
        screener_df: pd.DataFrame,
        top_candidates_df: pd.DataFrame,
        breadth_data: dict,
        sector_data: dict,
        delivery_df: Optional[pd.DataFrame] = None,
        etf_ranking_df: Optional[pd.DataFrame] = None,
        top_etf_df: Optional[pd.DataFrame] = None,
        market_bullish: bool = True,
        universe_label: str = "NIFTY 500",
        bars_df: Optional[pd.DataFrame] = None,
    ) -> Path:
        """Assembles and formats all 12 sheets into the destination Excel file."""
        excel_path = self.reports_dir / f"MIP1_Momentum_Scanner_{as_of_date}.xlsx"

        # Ensure bars_df is available for 30d/60d history tabs
        if bars_df is None or bars_df.empty:
            try:
                target_dt = datetime.datetime.strptime(as_of_date, "%Y-%m-%d")
                start_str = (target_dt - datetime.timedelta(days=400)).strftime("%Y-%m-%d")
                bars_df = load_bars(start_date=start_str, end_date=as_of_date, include_delisted=False)
                smap = load_symbol_sector_map()
                bars_df["sector"] = bars_df["symbol"].map(smap).fillna("INFRA_MEDIA")
                bars_df = bars_df.sort_values(by=["symbol", "date"]).reset_index(drop=True)
                bars_df["ema_200"] = bars_df.groupby("symbol")["close"].transform(lambda s: s.ewm(span=200, adjust=True, min_periods=min(50, len(s))).mean())
                bars_df["ema_50"] = bars_df.groupby("symbol")["close"].transform(lambda s: s.ewm(span=50, adjust=True, min_periods=min(20, len(s))).mean())
                bars_df["ema_20"] = bars_df.groupby("symbol")["close"].transform(lambda s: s.ewm(span=20, adjust=True, min_periods=min(10, len(s))).mean())
                bars_df["high_252"] = bars_df.groupby("symbol")["high"].transform(lambda s: s.rolling(252, min_periods=min(50, len(s))).max())
                bars_df["low_252"] = bars_df.groupby("symbol")["low"].transform(lambda s: s.rolling(252, min_periods=min(50, len(s))).min())
                bars_df["ret_1m"] = bars_df.groupby("symbol")["close"].transform(lambda s: s / s.shift(21) - 1.0) * 100.0
            except Exception:
                bars_df = None

        # 1. Build DataFrame tabs
        dash_meta, dash_rot, dash_rrg, dash_stk, dash_etf, layout = self._build_dashboard_frames(
            as_of_date, screener_df, top_candidates_df, breadth_data, sector_data, top_etf_df, market_bullish, universe_label
        )
        rat_df = self._build_strategy_rationale_df(screener_df)
        sec_df = self._build_sector_rotation_df(sector_data, screener_df)
        ind_df = self._build_industry_ranking_df(sector_data, screener_df)
        hist_df = self._build_industry_history_df(as_of_date, bars_df)
        stock_df = self._build_stock_ranking_df(screener_df, delivery_df)
        cand_df = self._build_candidates_df(top_candidates_df, delivery_df, market_bullish)
        deliv_sheet_df = self._build_highest_delivery_df(delivery_df, screener_df)
        etf_sheet_df = self._build_etf_ranking_df(etf_ranking_df)
        perf_sum, perf_det = self._build_picks_performance_df()
        breadth_hist_df = self._build_breadth_history_df(as_of_date, bars_df, universe_label)
        config_df = self._build_config_df(as_of_date, excel_path, universe_label)

        # 2. Write raw sheets using pd.ExcelWriter
        with pd.ExcelWriter(str(excel_path), engine="openpyxl") as writer:
            # Dashboard
            dash_meta.to_excel(writer, sheet_name="Dashboard", index=False, startrow=3)
            dash_rot.to_excel(writer, sheet_name="Dashboard", index=False, startrow=layout["rot"])
            dash_rrg.to_excel(writer, sheet_name="Dashboard", index=False, startrow=layout["rrg"])
            dash_stk.to_excel(writer, sheet_name="Dashboard", index=False, startrow=layout["stk"])
            dash_etf.to_excel(writer, sheet_name="Dashboard", index=False, startrow=layout["etf"])

            # Main Strategy Tabs
            rat_df.to_excel(writer, sheet_name="Strategy Rationale", index=False)
            sec_df.to_excel(writer, sheet_name="Sector Rotation", index=False)
            ind_df.to_excel(writer, sheet_name="Industry Ranking", index=False)
            hist_df.to_excel(writer, sheet_name="Industry History 30d", index=False)
            stock_df.to_excel(writer, sheet_name="Stock Ranking", index=False)
            cand_df.to_excel(writer, sheet_name="Top Candidates", index=False)
            deliv_sheet_df.to_excel(writer, sheet_name="Highest Delivery", index=False)
            etf_sheet_df.to_excel(writer, sheet_name="ETF Momentum Ranking", index=False)

            if not perf_sum.empty:
                perf_sum.to_excel(writer, sheet_name="Pick Performance", index=False, startrow=1)
                perf_det.to_excel(writer, sheet_name="Pick Performance", index=False, startrow=len(perf_sum) + 4)
            else:
                pd.DataFrame([{"Note": "Pick tracking active — accumulating vintages."}]).to_excel(writer, sheet_name="Pick Performance", index=False)

            breadth_hist_df.to_excel(writer, sheet_name="Breadth History", index=False)
            config_df.to_excel(writer, sheet_name="Configuration", index=False)

        # 3. Apply Professional openpyxl Styling
        self._apply_workbook_styles(excel_path, as_of_date, layout, market_bullish)

        return excel_path

    def _build_dashboard_frames(self, as_of_date, screener_df, top_candidates_df, breadth_data, sector_data, top_etf_df, market_bullish, universe_label="NIFTY 500"):
        tp = breadth_data.get("trend_participation", {})
        hp = breadth_data.get("high_proximity", {})
        nhl = breadth_data.get("net_highs_lows", {})

        regime_label = "BULL (Trend Aligned: Entries Active)" if market_bullish else "BEAR (Defensive Cash Protection Active)"
        meta_items = [
            ("Scan Date", as_of_date),
            ("Market Regime", regime_label),
            ("Target Universe", f"{universe_label} Survivorship-Free PIT Universe"),
            ("Ranking Metric", "Volar Score (Smooth Return / Realized Annualized Volatility)"),
            ("Target Holdings", "Top 20 Scrips (Empirical Institutional Sweet Spot)"),
            ("Sector Hard Cap", "Max 2 Stocks per Sector (Strict Anti-Clustering Rule)"),
            ("Position Sizing Mode", "ATR-14 Volatility Risk Parity (1% Risk Budget per Trade)"),
            ("Market Breadth (>200 EMA)", f"{tp.get('pct_above_200_ema', 0.0):.1f}% ({tp.get('count_above_200_ema', 0)} scrips)"),
            ("Market Breadth (>50 EMA)", f"{tp.get('pct_above_50_ema', 0.0):.1f}%"),
            ("Near 52w High (Within 20%)", f"{hp.get('pct_within_20pct_52wh', 0.0):.1f}%"),
            ("52w Net Highs", f"+{nhl.get('new_52w_highs', 0)} / -{nhl.get('new_52w_lows', 0)} (Net: {nhl.get('net_highs_lows', 0):+d})"),
            ("Strategy Rationale", "See 'Strategy Rationale' tab for empirical 5-year factorial proofs"),
        ]
        dash_meta = pd.DataFrame(meta_items, columns=["System Dimension", "Parameter / Value"])

        # Sectors
        sec_list = sector_data.get("sectors", [])[:10]
        rot_rows = []
        for idx, s in enumerate(sec_list, 1):
            rot_rows.append({
                "Rank": idx,
                "Sector": s.get("sector", ""),
                "N Scrips": s.get("total_symbols", 0),
                "Breadth %": s.get("pct_above_200ema", 0.0),
                "1M Ret %": s.get("ret_1m", 0.0),
                "3M Ret %": s.get("ret_3m", 0.0),
                "Alpha 1M %": s.get("alpha_1m", 0.0),
                "Alpha 3M %": s.get("alpha_3m", 0.0),
                "RRG Quadrant": s.get("rrg_quadrant", "UNKNOWN"),
                "Action": "ACCUMULATE" if s.get("rrg_quadrant") in ["LEADING", "IMPROVING"] else ("REDUCE" if s.get("rrg_quadrant") == "WEAKENING" else "AVOID"),
            })
        dash_rot = pd.DataFrame(rot_rows) if rot_rows else pd.DataFrame(columns=["Rank", "Sector", "N Scrips", "Breadth %", "1M Ret %", "3M Ret %", "Alpha 1M %", "Alpha 3M %", "RRG Quadrant", "Action"])

        # RRG Summary
        rrg_counts = {"LEADING": 0, "IMPROVING": 0, "WEAKENING": 0, "LAGGING": 0}
        rrg_sectors = {"LEADING": [], "IMPROVING": [], "WEAKENING": [], "LAGGING": []}
        for s in sector_data.get("sectors", []):
            q = s.get("rrg_quadrant", "LAGGING")
            if q in rrg_counts:
                rrg_counts[q] += 1
                rrg_sectors[q].append(s.get("sector", ""))
        dash_rrg = pd.DataFrame([
            {"Quadrant": q, "Count": rrg_counts[q], "Sectors": ", ".join(rrg_sectors[q][:6])}
            for q in ["LEADING", "IMPROVING", "WEAKENING", "LAGGING"]
        ])

        # Top 20 Stocks
        stk_rows = []
        cands = top_candidates_df.head(20) if not top_candidates_df.empty else screener_df.head(20)
        for idx, (_, r) in enumerate(cands.iterrows(), 1):
            sym = r["symbol"]
            stk_rows.append({
                "Rank": idx,
                "Symbol": sym,
                "Sector": r.get("sector", "OTHER"),
                "Close Price": round(float(r.get("close", 0.0)), 2),
                "Volar Score": round(float(r.get("volar_score", 0.0)), 3),
                "1Y Ret %": round(float(r.get("ret_1y", 0.0) if abs(float(r.get("ret_1y", 0.0))) > 5.0 or float(r.get("ret_1y", 0.0)) == 0.0 else float(r.get("ret_1y", 0.0)) * 100), 1),
                "RRG": r.get("rrg_quadrant", "WEAKENING"),
                "TradingView": f"https://in.tradingview.com/chart/?symbol=NSE:{sym}",
            })
        dash_stk = pd.DataFrame(stk_rows) if stk_rows else pd.DataFrame(columns=["Rank", "Symbol", "Sector", "Close Price", "Volar Score", "1Y Ret %", "RRG", "TradingView"])

        # Top 7 ETFs
        etf_rows = []
        if top_etf_df is not None and not top_etf_df.empty:
            for idx, (_, r) in enumerate(top_etf_df.head(7).iterrows(), 1):
                sym = r["symbol"]
                etf_rows.append({
                    "Rank": idx,
                    "ETF Symbol": sym,
                    "Underlying": r.get("underlying", ""),
                    "Price": round(float(r.get("price", 0.0)), 2),
                    "Volar Score": round(float(r.get("volar_score", 0.0)), 3),
                    "Target Qty": int(r.get("target_qty", 0)),
                    "Target Val (₹)": round(float(r.get("target_val", 0.0)), 2),
                    "Status": r.get("status", "TOP PICK"),
                    "TradingView": f"https://in.tradingview.com/chart/?symbol=NSE:{sym}",
                })
        dash_etf = pd.DataFrame(etf_rows) if etf_rows else pd.DataFrame(columns=["Rank", "ETF Symbol", "Underlying", "Price", "Volar Score", "Target Qty", "Target Val (₹)", "Status", "TradingView"])

        # Calculate row layouts
        rot_title = 4 + len(dash_meta) + 2
        rot_start = rot_title
        rrg_title = rot_start + 1 + len(dash_rot) + 2
        rrg_start = rrg_title
        stk_title = rrg_start + 1 + len(dash_rrg) + 2
        stk_start = stk_title
        etf_title = stk_start + 1 + len(dash_stk) + 2
        etf_start = etf_title

        layout = {
            "rot": rot_start, "rrg": rrg_start, "stk": stk_start, "etf": etf_start,
            "rot_title": rot_title, "rrg_title": rrg_title, "stk_title": stk_title, "etf_title": etf_title,
        }

        return dash_meta, dash_rot, dash_rrg, dash_stk, dash_etf, layout

    def _build_strategy_rationale_df(self, screener_df):
        rows = [
            ("=== 1. ACTIVE STRATEGY SETTINGS (Empirical Calibrations) ===", "", "", ""),
            ("Dimension / Setting", "Calibrated Value", "Quant Rationale (ELI5)", "Backtest Impact (Why it Works)"),
            ("Target Universe", "NIFTY 500 PIT Sphere", "Top 500 liquid Indian equities with zero survivorship bias", "Eliminates circuit traps and illiquid execution slippage while ensuring genuine market breadth."),
            ("Ranking Metric", "Volar Score (Slope x R²)", "Multiplies return slope by R² to penalize erratic volatility spikes", "Delivered 23.35% Net CAGR vs 11.38% for 52W Proximity. Highest alpha with lowest turnover."),
            ("Portfolio Size (N)", "Top 20 Stocks", "Optimal institutional diversification sweet spot", "Peaks Sharpe at 1.42-1.59 and cuts max drawdowns. Avoids single-stock blowup risk."),
            ("Rebalance Frequency", "Monthly (M)", "Monthly portfolio re-weighting", "Matches the empirical 40-60 session momentum half-life without holding decaying laggards."),
            ("Market Trend Gate", "ACTIVE (NIFTY 500 >= 20 EMA)", "Defensive Cash Shield during Bear Regimes", "Reduces Max Drawdown from -34.7% to -22.3% and elevates Profit Factor to 2.35."),
            ("Sector Concentration Cap", "Max 2 per Sector", "Strict anti-clustering constraint", "Prevents catastrophic sector blowups (e.g. over-allocation to tech in 2021). Guarantees 10+ distinct sectors."),
            ("Retracement Cutoff", "20% from 52W High", "Falling knife & broken chart filter", "Strictly rejects severely damaged charts while allowing natural volatility pullbacks."),
            ("Long-Term Trend Gate", "Price > 200 EMA", "Structural bull confirmation", "Guarantees institutional sponsorship behind every entered position."),
            ("Dynamic Position Sizing", "ATR-14 Risk Parity", "14-Day ATR Inverse-Volatility Risk Budgeting", "Equalizes risk across positions by allocating smaller capital to volatile names and larger capital to steady compounders."),
            ("", "", "", ""),
            ("=== 2. EMPIRICAL 5-YEAR FACTORIAL BACKTEST PROOF (2021-2026) ===", "", "", ""),
            ("Factor Tested", "Winning Configuration", "Losing / Disqualified Configuration", "Key Empirical Quantitative Proof"),
            ("Ranking Method", "Volar: 23.35% Net CAGR | 1.08 Sharpe", "52W Proximity: 11.38% Net CAGR | 0.63 Sharpe", "52W Proximity suffers 568% annual turnover on whipsaws; Volar delivers 285% turnover."),
            ("Rebalance Cadence", "Monthly: 25.40% Net CAGR | 1.23 Sharpe", "Quarterly: 13.04% Net CAGR | 0.60 Sharpe", "Quarterly rebalancing decays momentum; Monthly rebalancing nearly doubles net return."),
            ("Portfolio Breadth", "N=20: 22.41% Net CAGR | -27.50% Max DD", "N=5: 12.51% Net CAGR | -39.44% Max DD", "5 stocks represents reckless single-stock risk; 20 stocks hits the optimal efficient frontier."),
            ("Market Gate", "Gate ON: -22.32% Max DD | 2.35 Profit Factor", "Gate OFF: -34.70% Max DD | 1.58 Profit Factor", "Holding cash when the index is below 20 EMA preserves capital in market crashes."),
            ("", "", "", ""),
            ("=== 3. DISQUALIFIED TRASH IDEAS (EMPIRICAL WARNINGS) ===", "", "", ""),
            ("Disqualified Setting", "Why People Try It", "Fatal Flaw Identified in Backtesting", "Verdict"),
            ("5-Stock Portfolio", "Greed for hyper-concentration", "High idiosyncratic risk: a single bad stock crushes the portfolio. Max drawdown hits -41.52%.", "TRASH (Reckless Concentration)"),
            ("Quarterly Rebalancing", "Desire to minimize brokerage", "Momentum in India decays after 40-60 days. Holds declining stocks for 3 months, halving CAGR.", "TRASH (Decaying Momentum)"),
            ("52-Week High Proximity", "Classic retail breakout indicator", "Triggers 568% annual turnover on false breakouts; underperforms buy-and-hold index.", "TRASH (High Churn / Low Alpha)")
        ]
        return pd.DataFrame(rows, columns=["Parameter / Factor", "Setting / Evidence", "Quant Rationale (ELI5)", "Empirical Proof / Verdict"])

    def _build_sector_rotation_df(self, sector_data, screener_df=None):
        sec_list = sector_data.get("sectors", [])

        leaders_map = {}
        if screener_df is not None and not screener_df.empty and "sector" in screener_df.columns:
            for sec, grp in screener_df.groupby("sector"):
                top3 = grp.sort_values(by="volar_score", ascending=False)["symbol"].head(3).tolist()
                leaders_map[str(sec)] = ", ".join(top3)

        rows = []
        for idx, s in enumerate(sec_list, 1):
            sec = s.get("sector", "")
            q = s.get("rrg_quadrant", "UNKNOWN")
            act = "OVERWEIGHT" if q == "LEADING" else ("ACCUMULATE" if q == "IMPROVING" else ("REDUCE" if q == "WEAKENING" else "AVOID"))
            rows.append({
                "Rank": idx,
                "Sector": sec,
                "Industry Name": s.get("name", sec),
                "Total Scrips": s.get("stock_count", s.get("total_symbols", 0)),
                "Top 3 Leaders": leaders_map.get(sec, ""),
                "Breadth % (>200EMA)": s.get("breadth_200_pct", s.get("pct_above_200ema", 0.0)),
                "1M Return %": s.get("ret_1m", 0.0),
                "3M Return %": s.get("ret_3m", 0.0),
                "1Y Return %": s.get("ret_1y", 0.0),
                "Alpha 1M %": s.get("alpha_1m", 0.0),
                "Alpha 3M %": s.get("alpha_3m", 0.0),
                "RRG Quadrant": q,
                "Action": act,
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Rank", "Sector", "Industry Name", "Total Scrips", "Top 3 Leaders", "Breadth % (>200EMA)", "1M Return %", "3M Return %", "1Y Return %", "Alpha 1M %", "Alpha 3M %", "RRG Quadrant", "Action"])

    def _build_industry_ranking_df(self, sector_data, screener_df=None):
        sec_list = sector_data.get("sectors", [])

        leaders_map = {}
        if screener_df is not None and not screener_df.empty and "sector" in screener_df.columns:
            for sec, grp in screener_df.groupby("sector"):
                top3 = grp.sort_values(by="volar_score", ascending=False)["symbol"].head(3).tolist()
                leaders_map[str(sec)] = ", ".join(top3)

        rows = []
        for idx, s in enumerate(sec_list, 1):
            sec = s.get("sector", "")
            q = s.get("rrg_quadrant", "UNKNOWN")
            act = "OVERWEIGHT" if q == "LEADING" else ("ACCUMULATE" if q == "IMPROVING" else ("REDUCE" if q == "WEAKENING" else "AVOID"))
            rows.append({
                "Rank": idx,
                "Sector": sec,
                "Industry Name": s.get("name", sec),
                "Total Scrips": s.get("stock_count", s.get("total_symbols", 0)),
                "Composite Score": s.get("composite_score", 0.0),
                "1M Return %": s.get("ret_1m", 0.0),
                "3M Return %": s.get("ret_3m", 0.0),
                "1Y Return %": s.get("ret_1y", 0.0),
                "Alpha 1M %": s.get("alpha_1m", 0.0),
                "Alpha 3M %": s.get("alpha_3m", 0.0),
                "Breadth % (>200EMA)": s.get("breadth_200_pct", s.get("pct_above_200ema", 0.0)),
                "Near 52w High %": s.get("near_high_pct", 0.0),
                "RS-Ratio (RRG)": s.get("rrg_rs_ratio", 100.0),
                "RS-Mom (RRG)": s.get("rrg_rs_momentum", 100.0),
                "RRG Quadrant": q,
                "Top 3 Leaders": leaders_map.get(sec, ""),
                "Action": act,
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Rank", "Sector", "Industry Name", "Total Scrips", "Composite Score", "1M Return %", "3M Return %", "1Y Return %", "Alpha 1M %", "Alpha 3M %", "Breadth % (>200EMA)", "Near 52w High %", "RS-Ratio (RRG)", "RS-Mom (RRG)", "RRG Quadrant", "Top 3 Leaders", "Action"])

    def _build_industry_history_df(self, as_of_date, bars_df=None):
        """Computes daily 30-day sector breadth and return history time-series."""
        if bars_df is None or bars_df.empty:
            return pd.DataFrame(columns=["Date", "Sector", "Scrips", "% > 200 EMA", "1M Ret %", "52w Highs"])

        all_dates = sorted(bars_df["date"].unique())
        sub_dates = [d for d in all_dates if d <= as_of_date][-30:]
        if not sub_dates:
            return pd.DataFrame(columns=["Date", "Sector", "Scrips", "% > 200 EMA", "1M Ret %", "52w Highs"])

        sub = bars_df[bars_df["date"].isin(sub_dates)].copy()
        if "sector" not in sub.columns:
            smap = load_symbol_sector_map()
            sub["sector"] = sub["symbol"].map(smap).fillna("INFRA_MEDIA")

        req = {"close", "ema_200", "high_252"}
        if not req.issubset(set(sub.columns)):
            return pd.DataFrame(columns=["Date", "Sector", "Scrips", "% > 200 EMA", "1M Ret %", "52w Highs"])

        ret_col = "ret_1m" if "ret_1m" in sub.columns else ("ret_21" if "ret_21" in sub.columns else None)

        def _calc_sec_hist(g):
            n = len(g)
            above_200 = (g["close"] > g["ema_200"]).mean() * 100.0 if "ema_200" in g.columns else 0.0
            r1m = g[ret_col].mean() if ret_col else 0.0
            if ret_col == "ret_21" and abs(r1m) < 0.5:
                r1m *= 100.0
            new_highs = (g["close"] >= 0.99 * g["high_252"]).sum() if "high_252" in g.columns else 0
            return pd.Series({
                "Scrips": n,
                "% > 200 EMA": round(above_200, 1),
                "1M Ret %": round(r1m, 2),
                "52w Highs": int(new_highs),
            })

        hist = sub.groupby(["date", "sector"]).apply(_calc_sec_hist, include_groups=False).reset_index()
        hist = hist.rename(columns={"date": "Date", "sector": "Sector"})
        return hist.sort_values(by=["Date", "Sector"], ascending=[False, True]).reset_index(drop=True)

    def _build_stock_ranking_df(self, screener_df, delivery_df):
        dmap = {}
        if delivery_df is not None and not delivery_df.empty:
            dmap = delivery_df.set_index("symbol").to_dict(orient="index")

        rows = []
        for idx, (_, r) in enumerate(screener_df.iterrows(), 1):
            sym = r["symbol"]
            d_info = dmap.get(sym, {})
            rows.append({
                "Rank": idx,
                "Symbol": sym,
                "Sector": r.get("sector", "OTHER"),
                "Close Price": round(float(r.get("close", 0.0)), 2),
                "Volar Score": round(float(r.get("volar_score", 0.0)), 3),
                "1Y Ret %": round(float(r.get("ret_1y", 0.0) if abs(float(r.get("ret_1y", 0.0))) > 5.0 or float(r.get("ret_1y", 0.0)) == 0.0 else float(r.get("ret_1y", 0.0)) * 100), 1),
                "From 52w High %": round(float(r.get("drawdown_from_high", 0.0) or (1.0 - r.get("close", 0.0) / max(0.01, r.get("high_252", 1.0))) * 100), 1),
                "Vs EMA-200 %": round(float((r.get("close", 0.0) / max(0.01, r.get("ema_200", 1.0)) - 1.0) * 100), 1),
                "Delivery %": d_info.get("deliv_per", np.nan),
                "Delivery Times (5D)": d_info.get("deliv_times", np.nan),
                "Delivery Value (₹Cr)": d_info.get("delivery_value_cr", np.nan),
                "Delivery Action": d_info.get("deliv_action", "⚪ NEUTRAL"),
                "RRG": r.get("rrg_quadrant", "WEAKENING"),
                "TradingView": f"https://in.tradingview.com/chart/?symbol=NSE:{sym}",
            })
        return pd.DataFrame(rows)

    def _build_candidates_df(self, top_candidates_df, delivery_df, market_bullish):
        dmap = {}
        if delivery_df is not None and not delivery_df.empty:
            dmap = delivery_df.set_index("symbol").to_dict(orient="index")

        rows = []
        is_bear = not market_bullish
        for idx, (_, r) in enumerate(top_candidates_df.iterrows(), 1):
            sym = r["symbol"]
            px = float(r.get("close", r.get("close_price", 0.0)))
            atr = float(r.get("atr_14", px * 0.03))
            sl = float(r.get("stop_loss", max(0.01, px - 2.0 * atr)))
            qty = int(r.get("target_shares", 0))
            d_info = dmap.get(sym, {})

            rows.append({
                "Rank": idx,
                "Symbol": sym,
                "Sector": r.get("sector", "OTHER"),
                "Close Price": round(px, 2),
                "MIP-1 Status": "HOLD (BEAR - 100% CASH)" if is_bear else "NEW BUY",
                "ATR (14D)": round(atr, 2),
                "Stop Loss (2x ATR)": round(sl, 2),
                "Risk Budget (₹)": round(qty * (px - sl), 2) if qty > 0 else 0.0,
                "Target Qty (₹10L)": qty,
                "Target Value (₹)": round(qty * px, 2),
                "Delivery %": d_info.get("deliv_per", np.nan),
                "Delivery Times (5D)": d_info.get("deliv_times", np.nan),
                "Delivery Action": d_info.get("deliv_action", "⚪ NEUTRAL"),
                "Volar Score": round(float(r.get("volar_score", 0.0)), 3),
                "RRG": r.get("rrg_quadrant", "WEAKENING"),
                "TradingView": f"https://in.tradingview.com/chart/?symbol=NSE:{sym}",
            })
        return pd.DataFrame(rows)

    def _build_highest_delivery_df(self, delivery_df, screener_df):
        if delivery_df is None or delivery_df.empty:
            return pd.DataFrame([{"Note": "NSE Delivery Bhavcopy not available for this session."}])

        active_syms = set(screener_df["symbol"].tolist()) if not screener_df.empty else set(delivery_df["symbol"])
        sub = delivery_df[delivery_df["symbol"].isin(active_syms)].copy()
        if sub.empty:
            sub = delivery_df.copy()

        # Filter spikes >= 5 Cr turnover
        spikes = sub[sub["delivery_value_cr"].fillna(0) >= 5.0].sort_values("deliv_per", ascending=False).reset_index(drop=True)
        if len(spikes) < 10:
            spikes = sub[sub["delivery_value_cr"].fillna(0) >= 1.0].sort_values("deliv_per", ascending=False).reset_index(drop=True)

        rows = []
        for idx, (_, r) in enumerate(spikes.iterrows(), 1):
            sym = r["symbol"]
            rows.append({
                "Rank": idx,
                "Symbol": sym,
                "Series": r.get("series", "EQ"),
                "Delivery Action": r.get("deliv_action", "⚪ NEUTRAL"),
                "Close Price": round(float(r.get("close_price", 0.0)), 2),
                "1D Return %": round(float(r.get("deliv_ret_pct", 0.0)), 2),
                "Delivery %": round(float(r.get("deliv_per", 0.0)), 2),
                "Delivery Qty": int(r.get("deliv_qty", 0)) if pd.notna(r.get("deliv_qty")) else 0,
                "Delivery Times (5D)": round(float(r.get("deliv_times", 0.0)), 1) if pd.notna(r.get("deliv_times")) else np.nan,
                "Delivery Value (₹Cr)": round(float(r.get("delivery_value_cr", 0.0)), 2),
                "TradingView": f"https://in.tradingview.com/chart/?symbol=NSE:{sym}",
            })
        return pd.DataFrame(rows)

    def _build_etf_ranking_df(self, etf_ranking_df):
        if etf_ranking_df is None or etf_ranking_df.empty:
            return pd.DataFrame([{"Note": "ETF scanning disabled or no data available."}])

        rows = []
        for idx, (_, r) in enumerate(etf_ranking_df.iterrows(), 1):
            sym = r["symbol"]
            rows.append({
                "Rank": idx,
                "Symbol": sym,
                "Underlying Asset": r.get("underlying", ""),
                "Price": round(float(r.get("price", 0.0)), 2),
                "Volar Score": round(float(r.get("volar_score", 0.0)), 3),
                "1Y Return %": round(float(r.get("return_1y", 0.0)), 1),
                "From 52w High %": round(float(r.get("retrace_pct", 0.0)), 1),
                "Vs EMA-100 %": round(float(r.get("vs_ema100", 0.0)), 1),
                "Vs EMA-200 %": round(float(r.get("vs_ema200", 0.0)), 1),
                "Turnover (₹Cr)": round(float(r.get("turnover_cr", 0.0)), 2),
                "Status": r.get("status", "QUALIFIED"),
                "TradingView": f"https://in.tradingview.com/chart/?symbol=NSE:{sym}",
            })
        return pd.DataFrame(rows)

    def _build_picks_performance_df(self):
        picks_path = self.reports_dir / "picks_history.parquet"
        if not picks_path.exists():
            return pd.DataFrame(), pd.DataFrame()
        try:
            picks = pd.read_parquet(picks_path)
            return picks.head(10), picks.tail(50)
        except Exception:
            return pd.DataFrame(), pd.DataFrame()

    def _build_breadth_history_df(self, as_of_date: str, bars_df: Optional[pd.DataFrame] = None, universe_label: str = "NIFTY 500") -> pd.DataFrame:
        """Computes daily market-wide breadth history across the last 60 sessions."""
        if bars_df is None or bars_df.empty:
            return pd.DataFrame(columns=["Date", "Universe", "Active Scrips", "% > 200 EMA", "% > 50 EMA", "% > 20 EMA", "% Near 52wH", "52w Highs", "52w Lows", "Net Highs", "Breadth Regime"])

        all_dates = sorted(bars_df["date"].unique())
        sub_dates = [d for d in all_dates if d <= as_of_date][-60:]
        if not sub_dates:
            return pd.DataFrame(columns=["Date", "Universe", "Active Scrips", "% > 200 EMA", "% > 50 EMA", "% > 20 EMA", "% Near 52wH", "52w Highs", "52w Lows", "Net Highs", "Breadth Regime"])

        sub = bars_df[bars_df["date"].isin(sub_dates)].copy()

        def _calc_breadth_row(g):
            n = len(g)
            p200 = round((g["close"] > g["ema_200"]).mean() * 100.0, 1) if "ema_200" in g.columns else 0.0
            p50 = round((g["close"] > g["ema_50"]).mean() * 100.0, 1) if "ema_50" in g.columns else 0.0
            p20 = round((g["close"] > g["ema_20"]).mean() * 100.0, 1) if "ema_20" in g.columns else 0.0
            pnear = round((g["close"] >= 0.80 * g["high_252"]).mean() * 100.0, 1) if "high_252" in g.columns else 0.0
            nh = int((g["close"] >= 0.99 * g["high_252"]).sum()) if "high_252" in g.columns else 0
            nl = int((g["close"] <= 1.01 * g["low_252"]).sum()) if "low_252" in g.columns else 0
            net = nh - nl

            if p200 >= 60.0 and p50 >= 55.0:
                regime = "🟢 STRONG EXPANSION"
            elif p200 < 40.0 or (p200 < 50.0 and net < 0):
                regime = "🔴 CONTRACTION / DEFENSIVE"
            else:
                regime = "🟡 SELECTIVE / NEUTRAL"

            return pd.Series({
                "Universe": universe_label,
                "Active Scrips": n,
                "% > 200 EMA": p200,
                "% > 50 EMA": p50,
                "% > 20 EMA": p20,
                "% Near 52wH": pnear,
                "52w Highs": nh,
                "52w Lows": nl,
                "Net Highs": net,
                "Breadth Regime": regime,
            })

        b_hist = sub.groupby("date").apply(_calc_breadth_row, include_groups=False).reset_index()
        b_hist = b_hist.rename(columns={"date": "Date"})
        return b_hist.sort_values(by="Date", ascending=False).reset_index(drop=True)

    def _build_config_df(self, as_of_date, excel_path, universe_label="NIFTY 500"):
        rows = [
            ("MIP Version", "v5.5.1 (Standalone Pydroid 3 Edition — Empirical Optimal Settings)"),
            ("Scan Date", as_of_date),
            ("Target Universe", universe_label),
            ("Output File", str(excel_path.name)),
            ("Database Engine", "Zero-Compiler SQLite3 (universe.db)"),
            ("Ranking Metric", "Volar Score (Slope * 252 * R²)"),
            ("Portfolio Sizing", "ATR-14 Volatility Risk Parity (1% Risk Budget)"),
            ("Sector Hard Cap", "Max 2 Stocks per Sector"),
            ("ETF Engine", "Definedge Momentify ALL-ONE Liquid Sector/Asset Rotation"),
            ("Delivery Engine", "NSE 5-Day Delivery Spikes & Accumulation/Distribution Classifier"),
        ]
        return pd.DataFrame(rows, columns=["Parameter", "Value"])

    def _apply_workbook_styles(self, excel_path: Path, as_of_date: str, layout: dict, market_bullish: bool):
        """Applies headers, tab colors, number formatting, borders, and hyperlinks."""
        wb = openpyxl.load_workbook(str(excel_path))

        hf = PatternFill("solid", fgColor=PRIMARY_BLUE)
        hfont = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        thin_side = Side(style="thin", color=BORDER_GREY)
        thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        def style_generic_sheet(ws, hdr_rows, freeze="A2", linkify=True):
            max_r = ws.max_row
            max_c = ws.max_column

            for hr in hdr_rows:
                ws.row_dimensions[hr].height = 24
                for c in range(1, max_c + 1):
                    cell = ws.cell(hr, c)
                    if cell.value is not None:
                        cell.font = hfont
                        cell.fill = hf
                        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            start_r = max(hdr_rows) + 1 if hdr_rows else 2
            for r in range(start_r, max_r + 1):
                row_bg = BG_LIGHT if (r % 2 == 0) else BG_WHITE
                for c in range(1, max_c + 1):
                    cell = ws.cell(r, c)
                    h_val = str(ws.cell(hdr_rows[0] if hdr_rows else 1, c).value or "").lower()
                    cell.fill = PatternFill("solid", fgColor=row_bg)
                    cell.border = thin_border
                    val = cell.value

                    if isinstance(val, (int, float)):
                        if "%" in h_val or "return" in h_val or "alpha" in h_val or "excess" in h_val:
                            cell.alignment = Alignment(horizontal="right", vertical="center")
                            cell.number_format = '+#,##0.0"%";-#,##0.0"%";"0.0%"'
                            cell.font = Font(name="Arial", size=9.5, color="006100" if val >= 0 else "9C0006")
                        elif "price" in h_val or "stop loss" in h_val or "target val" in h_val or "budget" in h_val:
                            cell.alignment = Alignment(horizontal="right", vertical="center")
                            cell.number_format = "₹#,##0.00"
                            cell.font = Font(name="Arial", size=9.5, color="212121")
                        elif "qty" in h_val:
                            cell.alignment = Alignment(horizontal="right", vertical="center")
                            cell.number_format = "#,##0"
                        elif "times" in h_val:
                            cell.alignment = Alignment(horizontal="right", vertical="center")
                            cell.number_format = '0.0"x"'
                            if val >= 1.5:
                                cell.font = Font(name="Arial", size=9.5, color="006100", bold=True)
                        else:
                            cell.alignment = Alignment(horizontal="right", vertical="center")
                            cell.font = Font(name="Arial", size=9.5, color="212121")
                    else:
                        if c in (1, 2) or "sector" in h_val or "symbol" in h_val:
                            cell.alignment = Alignment(horizontal="left", vertical="center")
                        else:
                            cell.alignment = Alignment(horizontal="center", vertical="center")
                        cell.font = Font(name="Arial", size=9.5, color="212121")

            for c in range(1, max_c + 1):
                col_letter = get_column_letter(c)
                ml = max((len(str(ws.cell(r, c).value or "")) for r in range(1, max_r + 1)), default=10)
                ws.column_dimensions[col_letter].width = min(max(ml + 4, 11), 40)

            if freeze:
                ws.freeze_panes = freeze

            if linkify:
                for hr in hdr_rows:
                    for c in range(1, max_c + 1):
                        h_title = str(ws.cell(hr, c).value or "").lower()
                        if "tradingview" in h_title:
                            ws.column_dimensions[get_column_letter(c)].width = 15
                            for r in range(hr + 1, max_r + 1):
                                cell = ws.cell(r, c)
                                if cell.value and str(cell.value).startswith("http"):
                                    url = str(cell.value)
                                    cell.value = "📈 View Chart"
                                    cell.hyperlink = url
                                    cell.font = Font(name="Arial", size=9.5, color="0563C1", underline="single", bold=True)
                                    cell.alignment = Alignment(horizontal="center", vertical="center")

        # Format Dashboard
        ws_dash = wb["Dashboard"]
        ws_dash.merge_cells("A1:D1")
        ws_dash["A1"] = "PROJECT MIP — QUANTITATIVE MOMENTUM DESK"
        ws_dash["A1"].font = Font(name="Arial", size=14, bold=True, color="FFFFFF")
        ws_dash["A1"].fill = PatternFill("solid", fgColor=PRIMARY_BLUE)
        ws_dash["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws_dash.row_dimensions[1].height = 28

        regime_txt = "BULL (Trend Aligned: Entries Active)" if market_bullish else "BEAR (Defensive Cash Protection Active)"
        regime_col = GREEN_COLOR if market_bullish else RED_COLOR
        ws_dash.merge_cells("A2:D2")
        ws_dash["A2"] = f"Scan Date: {as_of_date}  |  Market Regime: {regime_txt}"
        ws_dash["A2"].font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        ws_dash["A2"].fill = PatternFill("solid", fgColor=regime_col)
        ws_dash["A2"].alignment = Alignment(horizontal="left", vertical="center")
        ws_dash.row_dimensions[2].height = 22

        sec_headers = [
            (3, "SYSTEM & MARKET REGIME OVERVIEW"),
            (layout["rot_title"], "TOP SECTOR ROTATION LEADERS (1M/3M Alpha & Breadth)"),
            (layout["rrg_title"], "RELATIVE ROTATION GRAPH (RRG) QUADRANTS"),
            (layout["stk_title"], "TOP 20 MOMENTUM CANDIDATES (Sector Hard Cap Enforced)"),
            (layout["etf_title"], "DEFINEDGE MOMENTIFY ETF MOMENTUM (TOP 7 ALL-ONE)"),
        ]
        for s_row, s_title in sec_headers:
            ws_dash.cell(s_row, 1, s_title)
            ws_dash.cell(s_row, 1).font = Font(name="Arial", size=11, bold=True, color=PRIMARY_BLUE)

        style_generic_sheet(ws_dash, [4, layout["rot"] + 1, layout["rrg"] + 1, layout["stk"] + 1, layout["etf"] + 1], freeze=None)

        # Tab Styling
        if "Strategy Rationale" in wb.sheetnames:
            ws_sr = wb["Strategy Rationale"]
            ws_sr.sheet_properties.tabColor = DARK_NAVY
            style_generic_sheet(ws_sr, [1], freeze="A2")
            ws_sr.column_dimensions["A"].width = 28
            ws_sr.column_dimensions["B"].width = 38
            ws_sr.column_dimensions["C"].width = 52
            ws_sr.column_dimensions["D"].width = 65

            for r in range(1, ws_sr.max_row + 1):
                val = str(ws_sr.cell(r, 1).value or "")
                if val.startswith("==="):
                    ws_sr.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
                    c = ws_sr.cell(r, 1)
                    c.font = Font(name="Arial", size=10.5, bold=True, color="FFFFFF")
                    c.fill = PatternFill("solid", fgColor=PRIMARY_BLUE)
                    c.alignment = Alignment(horizontal="left", vertical="center")
                    ws_sr.row_dimensions[r].height = 24

        if "Highest Delivery" in wb.sheetnames:
            wb["Highest Delivery"].sheet_properties.tabColor = GREEN_COLOR
            style_generic_sheet(wb["Highest Delivery"], [1], freeze="A2")

        if "ETF Momentum Ranking" in wb.sheetnames:
            wb["ETF Momentum Ranking"].sheet_properties.tabColor = "6A1B9A"
            style_generic_sheet(wb["ETF Momentum Ranking"], [1], freeze="A2")

        for sname in ["Sector Rotation", "Industry Ranking", "Industry History 30d", "Stock Ranking", "Top Candidates", "Pick Performance", "Breadth History", "Configuration"]:
            if sname in wb.sheetnames:
                style_generic_sheet(wb[sname], [1], freeze="A2")

        wb.save(str(excel_path))
