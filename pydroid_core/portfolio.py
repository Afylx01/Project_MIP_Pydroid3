import datetime
import math
import json
from pathlib import Path
from typing import Dict, Optional
import pandas as pd

from .data_engine import get_base_dir, get_connection, get_latest_date

FRICTIONS = {
    'stt_rate': 0.001,           # STT @ 0.1% (buy side)
    'exchange_turnover': 0.0000345,  # Exchange turnover @ 0.00345%
    'gst_rate': 0.18,            # GST @ 18% on brokerage + exchange turnover
    'stamp_duty': 0.00015,       # Stamp duty @ 0.015%
    'brokerage_rate': 0.0003,    # Assumed discount broker @ 0.03%
}

class PortfolioManager:
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or get_base_dir()
        self.reports_dir = self.base_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
    def log(self, msg: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] PORTFOLIO: {msg}")
        
    def load_screener_output(self) -> pd.DataFrame:
        """
        Reads reports/screener_output_live.csv and returns DataFrame sorted by volar_score descending.
        """
        screener_path = self.reports_dir / "screener_output_live.csv"
        if not screener_path.exists():
            raise FileNotFoundError(f"Screener output not found at {screener_path}")
            
        df = pd.read_csv(screener_path)
        if 'volar_score' in df.columns:
            df = df.sort_values(by='volar_score', ascending=False).reset_index(drop=True)
        return df

    def compute_frictions(self, trade_value: float) -> dict:
        """
        Computes statutory frictions for the Indian market on the given trade value.
        """
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
            'total_friction': total_friction
        }

    def generate_rebalance_orders(self, capital: float = 1_000_000.0, top_n: int = 20, current_holdings: dict = None) -> pd.DataFrame:
        """
        Generates rebalance orders for a given capital, distributing it equally among the top N candidates.
        """
        self.log(f"Generating rebalance orders for capital: {capital}, top_n: {top_n}")
        screener_df = self.load_screener_output()
        top_candidates = screener_df.head(top_n)
        
        per_stock_capital = capital / top_n
        orders = []
        
        current_holdings = current_holdings or {}
        new_portfolio_symbols = set(top_candidates['symbol'].tolist())
        
        # Get latest prices from DB
        conn = get_connection(read_only=True, reuse=True)
        latest_date = get_latest_date()
        
        prices = {}
        for sym in list(new_portfolio_symbols) + list(current_holdings.keys()):
            query = "SELECT close FROM prices WHERE symbol = ? AND date = ?"
            df_price = pd.read_sql_query(query, conn, params=(sym, latest_date))
            if not df_price.empty:
                prices[sym] = df_price.iloc[0]['close']
            else:
                prices[sym] = 0.0 # Fallback

        # 1. Process new/held targets
        for _, row in top_candidates.iterrows():
            sym = row['symbol']
            sector = row.get('sector', 'Unknown')
            
            close_price = prices.get(sym)
            if close_price is None or close_price <= 0:
                close_price = row.get('close') or row.get('close_price')
                
            if not close_price or pd.isna(close_price):
                self.log(f"Warning: Could not find valid close price for {sym}, skipping.")
                continue
                
            target_shares = math.floor(per_stock_capital / close_price)
            current_shares = current_holdings.get(sym, 0)
            
            action = "BUY" if current_shares == 0 else "HOLD"
            
            target_value = target_shares * close_price
            frictions = self.compute_frictions(target_value)
            
            orders.append({
                'action': action,
                'symbol': sym,
                'sector': sector,
                'close_price': close_price,
                'target_shares': target_shares,
                'target_value': target_value,
                'stt': frictions['stt'],
                'exchange_turnover': frictions['exchange_turnover'],
                'brokerage': frictions['brokerage'],
                'gst': frictions['gst'],
                'stamp_duty': frictions['stamp_duty'],
                'total_friction': frictions['total_friction'],
                'total_cost': target_value + frictions['total_friction']
            })
            
        # 2. Process sells
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
                    'target_shares': 0,
                    'target_value': target_value,
                    'stt': frictions['stt'],
                    'exchange_turnover': frictions['exchange_turnover'],
                    'brokerage': frictions['brokerage'],
                    'gst': frictions['gst'],
                    'stamp_duty': frictions['stamp_duty'],
                    'total_friction': frictions['total_friction'],
                    'total_cost': target_value - frictions['total_friction']
                })

        orders_df = pd.DataFrame(orders)
        
        if not orders_df.empty:
            summary_row = pd.DataFrame([{
                'action': 'SUMMARY',
                'symbol': 'TOTAL',
                'sector': '',
                'close_price': 0.0,
                'target_shares': orders_df['target_shares'].sum(),
                'target_value': orders_df['target_value'].sum(),
                'stt': orders_df['stt'].sum(),
                'exchange_turnover': orders_df['exchange_turnover'].sum(),
                'brokerage': orders_df['brokerage'].sum(),
                'gst': orders_df['gst'].sum(),
                'stamp_duty': orders_df['stamp_duty'].sum(),
                'total_friction': orders_df['total_friction'].sum(),
                'total_cost': orders_df['total_cost'].sum()
            }])
            orders_df = pd.concat([orders_df, summary_row], ignore_index=True)
            
        return orders_df

    def export_orders(self, orders_df: pd.DataFrame) -> Path:
        """
        Saves orders DataFrame to a CSV and a human-readable text file.
        """
        csv_path = self.reports_dir / "rebalance_orders.csv"
        txt_path = self.reports_dir / "rebalance_orders.txt"
        
        orders_df.to_csv(csv_path, index=False)
        self.log(f"Exported orders to CSV: {csv_path}")
        
        with open(txt_path, 'w') as f:
            f.write("=== REBALANCE ORDERS LEDGER ===\n")
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
