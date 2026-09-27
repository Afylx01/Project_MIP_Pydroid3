"""
Project MIP Pydroid 3: Portfolio Manager & Dynamic Position Sizing
Directive: DIR-PROD-PYDROID3-PARITY-01 (MIP-1 v5.5.1 Parity)

Implements:
  - Sector Concentration Hard Cap (Max 2 stocks per sector/industry to prevent clustering).
  - ATR-14 Volatility Risk Parity Position Sizing (Risk Budget = 1% per position, Stop Loss = 2x ATR).
  - Equal-Weight Fallback Position Sizing.
  - Statutory frictions (STT, Exchange Turnover, GST, Stamp Duty, Brokerage).
  - Rebalance orders ledger generation (CSV & TXT).
"""

import math
import datetime
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from .data_engine import get_base_dir, get_connection, get_latest_date

FRICTIONS = {
    'stt_rate': 0.001,               # STT @ 0.1% (buy side delivery)
    'exchange_turnover': 0.0000345,  # Exchange turnover @ 0.00345%
    'gst_rate': 0.18,                # GST @ 18% on brokerage + turnover
    'stamp_duty': 0.00015,           # Stamp duty @ 0.015%
    'brokerage_rate': 0.0003,        # Discount broker @ 0.03%
}


class PortfolioManager:
    """Manages portfolio rebalance tickets, ATR risk parity sizing, and sector caps."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else get_base_dir()
        self.reports_dir = self.base_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def log(self, msg: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] PORTFOLIO: {msg}")

    def load_screener_output(self) -> pd.DataFrame:
        """Reads reports/screener_output_live.csv sorted by volar_score descending."""
        screener_path = self.reports_dir / "screener_output_live.csv"
        if not screener_path.exists():
            raise FileNotFoundError(f"Screener output not found at {screener_path}")

        df = pd.read_csv(screener_path)
        if 'volar_score' in df.columns:
            df = df.sort_values(by='volar_score', ascending=False).reset_index(drop=True)
        return df

    def compute_frictions(self, trade_value: float) -> dict:
        """Computes Indian statutory market frictions for the given trade value."""
        stt = trade_value * FRICTIONS['stt_rate']
        exchange_turnover = trade_value * FRICTIONS['exchange_turnover']
        brokerage = trade_value * FRICTIONS['brokerage_rate']
        gst = (brokerage + exchange_turnover) * FRICTIONS['gst_rate']
        stamp_duty = trade_value * FRICTIONS['stamp_duty']
        total_friction = stt + exchange_turnover + brokerage + gst + stamp_duty

        return {
            'stt': stt,
            'exchange_turnover': exchange_turnover,
            'brokerage': brokerage,
            'gst': gst,
            'stamp_duty': stamp_duty,
            'total_friction': total_friction,
        }

    def compute_atr_14(self, symbols: List[str], as_of_date: str) -> Dict[str, float]:
        """Calculates 14-day Average True Range (ATR_14) from SQLite prices."""
        conn = get_connection(read_only=True, reuse=True)
        atr_dict = {}

        # Lookback 40 trading days prior to as_of_date
        query = """
            SELECT symbol, date, high, low, close
            FROM prices
            WHERE symbol IN ({seq}) AND date <= ?
            ORDER BY symbol, date DESC
        """.format(seq=','.join(['?'] * len(symbols)))

        params = list(symbols) + [as_of_date]
        df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return {s: 0.0 for s in symbols}

        for sym, grp in df.groupby("symbol"):
            grp = grp.sort_values("date").tail(25)
            if len(grp) < 15:
                atr_dict[sym] = float(grp["close"].iloc[-1] * 0.03) if not grp.empty else 0.0
                continue

            h = grp["high"].values
            l = grp["low"].values
            c = grp["close"].values
            prev_c = np.roll(c, 1)
            prev_c[0] = c[0]

            tr1 = h - l
            tr2 = np.abs(h - prev_c)
            tr3 = np.abs(l - prev_c)
            tr = np.maximum(tr1, np.maximum(tr2, tr3))

            atr_14 = float(np.mean(tr[-14:]))
            atr_dict[sym] = round(atr_14, 2)

        return atr_dict

    def generate_rebalance_orders(
        self,
        capital: float = 1_000_000.0,
        top_n: int = 20,
        max_per_sector: int = 2,
        sizing_mode: str = "atr_risk_parity",
        risk_per_trade_pct: float = 1.0,
        current_holdings: Optional[dict] = None,
    ) -> pd.DataFrame:
        """
        Generates rebalance orders applying:
          1. Sector Concentration Hard Cap (Max 2 per sector).
          2. ATR-14 Volatility Risk Parity (or Equal Weight) Position Sizing.
          3. Statutory friction deductions.
        """
        self.log(f"Generating rebalance tickets: Capital=₹{capital:,.0f} | Top N={top_n} | Max/Sector={max_per_sector} | Sizing={sizing_mode}")
        screener_df = self.load_screener_output()

        # Enforce Sector Concentration Hard Cap: Max N stocks per industry/sector
        sector_counts = {}
        filtered_candidates = []

        for _, row in screener_df.iterrows():
            sec = str(row.get('sector', 'OTHER')).strip().upper()
            if sector_counts.get(sec, 0) < max_per_sector:
                filtered_candidates.append(row)
                sector_counts[sec] = sector_counts.get(sec, 0) + 1

            if len(filtered_candidates) >= top_n:
                break

        top_candidates = pd.DataFrame(filtered_candidates)
        if top_candidates.empty:
            self.log("No qualifying screener candidates found.")
            return pd.DataFrame()

        current_holdings = current_holdings or {}
        new_portfolio_symbols = set(top_candidates['symbol'].tolist())
        latest_date = get_latest_date()

        # Compute ATR-14 for risk parity sizing
        atr_map = self.compute_atr_14(top_candidates['symbol'].tolist(), latest_date)

        # Retrieve latest prices from DB
        conn = get_connection(read_only=True, reuse=True)
        prices = {}
        for sym in list(new_portfolio_symbols) + list(current_holdings.keys()):
            query = "SELECT close FROM prices WHERE symbol = ? AND date = ?"
            df_price = pd.read_sql_query(query, conn, params=(sym, latest_date))
            if not df_price.empty:
                prices[sym] = float(df_price.iloc[0]['close'])
            else:
                prices[sym] = 0.0

        orders = []
        per_stock_equal = capital / max(len(top_candidates), 1)
        risk_budget = capital * (risk_per_trade_pct / 100.0)

        # 1. Process Buys / Target Allocations
        for _, row in top_candidates.iterrows():
            sym = row['symbol']
            sector = row.get('sector', 'Unknown')
            close_price = prices.get(sym) or float(row.get('close', 0.0))

            if not close_price or close_price <= 0:
                continue

            atr = atr_map.get(sym, close_price * 0.03)
            stop_loss = round(max(0.01, close_price - 2.0 * atr), 2)

            if sizing_mode == "atr_risk_parity" and atr > 0:
                risk_per_share = max(2.0 * atr, close_price * 0.02)
                q_risk = int(risk_budget // risk_per_share)
                q_cap = int((capital * 0.25) // close_price)  # Max 25% single-stock ceiling
                target_shares = max(0, min(q_risk, q_cap))
            else:
                target_shares = math.floor(per_stock_equal / close_price)

            current_shares = current_holdings.get(sym, 0)
            action = "BUY" if current_shares == 0 else "HOLD"

            target_value = target_shares * close_price
            frictions = self.compute_frictions(target_value)

            orders.append({
                'action': action,
                'symbol': sym,
                'sector': sector,
                'close_price': close_price,
                'atr_14': atr,
                'stop_loss': stop_loss,
                'target_shares': target_shares,
                'target_value': target_value,
                'risk_allocated': round(target_shares * (close_price - stop_loss), 2),
                'stt': frictions['stt'],
                'exchange_turnover': frictions['exchange_turnover'],
                'brokerage': frictions['brokerage'],
                'gst': frictions['gst'],
                'stamp_duty': frictions['stamp_duty'],
                'total_friction': frictions['total_friction'],
                'total_cost': target_value + frictions['total_friction'],
            })

        # 2. Process Sells for removed holdings
        for sym, shares in current_holdings.items():
            if sym not in new_portfolio_symbols:
                close_price = prices.get(sym, 0.0)
                target_value = shares * close_price
                frictions = self.compute_frictions(target_value)

                orders.append({
                    'action': 'SELL',
                    'symbol': sym,
                    'sector': 'Unknown',
                    'close_price': close_price,
                    'atr_14': 0.0,
                    'stop_loss': 0.0,
                    'target_shares': 0,
                    'target_value': target_value,
                    'risk_allocated': 0.0,
                    'stt': frictions['stt'],
                    'exchange_turnover': frictions['exchange_turnover'],
                    'brokerage': frictions['brokerage'],
                    'gst': frictions['gst'],
                    'stamp_duty': frictions['stamp_duty'],
                    'total_friction': frictions['total_friction'],
                    'total_cost': target_value - frictions['total_friction'],
                })

        orders_df = pd.DataFrame(orders)

        if not orders_df.empty:
            summary_row = pd.DataFrame([{
                'action': 'SUMMARY',
                'symbol': 'TOTAL',
                'sector': f'{len(top_candidates)} Positions ({len(sector_counts)} Sectors)',
                'close_price': 0.0,
                'atr_14': 0.0,
                'stop_loss': 0.0,
                'target_shares': orders_df['target_shares'].sum(),
                'target_value': orders_df['target_value'].sum(),
                'risk_allocated': orders_df['risk_allocated'].sum(),
                'stt': orders_df['stt'].sum(),
                'exchange_turnover': orders_df['exchange_turnover'].sum(),
                'brokerage': orders_df['brokerage'].sum(),
                'gst': orders_df['gst'].sum(),
                'stamp_duty': orders_df['stamp_duty'].sum(),
                'total_friction': orders_df['total_friction'].sum(),
                'total_cost': orders_df['total_cost'].sum(),
            }])
            orders_df = pd.concat([orders_df, summary_row], ignore_index=True)

        return orders_df

    def export_orders(self, orders_df: pd.DataFrame) -> Path:
        """Saves orders DataFrame to a CSV and a human-readable text file."""
        csv_path = self.reports_dir / "rebalance_orders.csv"
        txt_path = self.reports_dir / "rebalance_orders.txt"

        orders_df.to_csv(csv_path, index=False)
        self.log(f"Exported orders to CSV: {csv_path}")

        with open(txt_path, 'w', encoding="utf-8") as f:
            f.write("=== REBALANCE ORDERS LEDGER (MIP-1 ATR RISK PARITY) ===\n")
            f.write(f"Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            if not orders_df.empty:
                summary_df = orders_df[orders_df['action'] == 'SUMMARY']
                details_df = orders_df[orders_df['action'] != 'SUMMARY']

                f.write(details_df.to_string(index=False))
                f.write("\n\n=== SUMMARY ===\n")
                f.write(summary_df.to_string(index=False))
            else:
                f.write("No orders generated.\n")

        self.log(f"Exported orders to TXT: {txt_path}")
        return csv_path
