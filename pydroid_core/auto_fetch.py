import os
import sys
import io
import zipfile
import sqlite3
import datetime
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import pandas as pd
import numpy as np

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None
    import requests

import pydroid_core.data_engine as _de

class PydroidAutoFetch:
    def __init__(self, base_dir: Path = None):
        self.base_dir = Path(base_dir) if base_dir else _de.get_base_dir()
        self.session = None

    def log(self, msg: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] PydroidAutoFetch: {msg}")

    def _get_session(self):
        if self.session is None:
            if cffi_requests:
                self.session = cffi_requests.Session(impersonate="chrome")
            else:
                self.session = requests.Session()
                self.session.headers.update({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
                })
        return self.session

    def get_missing_trading_dates(self, as_of_date: str = None) -> List[str]:
        target = as_of_date if as_of_date else datetime.datetime.now().strftime("%Y-%m-%d")
        conn = _de.get_connection(read_only=True, reuse=True)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(date) FROM prices;")
        res = cursor.fetchone()
        max_date = res[0] if res and res[0] else None

        if not max_date:
            self.log("No data in DB. Fetching last 30 days as fallback.")
            max_date = (datetime.datetime.strptime(target, "%Y-%m-%d") - datetime.timedelta(days=30)).strftime("%Y-%m-%d")

        try:
            calendar = _de.load_trading_calendar()
            missing = [d for d in calendar if max_date < d <= target]
            if not missing:
                if calendar and target > calendar[-1]:
                    start = datetime.datetime.strptime(max(max_date, calendar[-1]), "%Y-%m-%d") + datetime.timedelta(days=1)
                    end = datetime.datetime.strptime(target, "%Y-%m-%d")
                    curr = start
                    while curr <= end:
                        if curr.weekday() < 5:
                            missing.append(curr.strftime("%Y-%m-%d"))
                        curr += datetime.timedelta(days=1)
            return sorted(missing)
        except Exception as e:
            self.log(f"Error loading calendar: {e}. Falling back to weekdays.")
            start = datetime.datetime.strptime(max_date, "%Y-%m-%d") + datetime.timedelta(days=1)
            end = datetime.datetime.strptime(target, "%Y-%m-%d")
            missing = []
            curr = start
            while curr <= end:
                if curr.weekday() < 5:
                    missing.append(curr.strftime("%Y-%m-%d"))
                curr += datetime.timedelta(days=1)
            return missing

    def fetch_bhavcopy_for_date(self, date_str: str) -> Optional[pd.DataFrame]:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        session = self._get_session()
        
        url1 = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{dt.strftime('%Y%m%d')}_F_0000.csv.zip"
        url2 = f"https://archives.nseindia.com/content/historical/EQUITIES/{dt.strftime('%Y')}/{dt.strftime('%b').upper()}/cm{dt.strftime('%d%b%Y').upper()}bhav.csv.zip"
        
        for url in [url1, url2]:
            self.log(f"Fetching {url}")
            try:
                resp = session.get(url, timeout=10)
                if resp.status_code == 200:
                    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                        csv_name = [n for n in z.namelist() if n.endswith('.csv')][0]
                        with z.open(csv_name) as f:
                            raw = pd.read_csv(f)
                            return self._standardize_bhavcopy(raw, date_str)
                else:
                    self.log(f"Status {resp.status_code} for {url}")
            except Exception as e:
                self.log(f"Error fetching {url}: {e}")
        return None

    def _standardize_bhavcopy(self, raw: pd.DataFrame, fallback_date: str) -> pd.DataFrame:
        raw.columns = [c.strip().upper() for c in raw.columns]
        
        if 'TCKRSYMB' in raw.columns:
            sym_col, series_col = 'TCKRSYMB', 'SCTYSRS'
            opn_col, hgh_col, low_col, cls_col, vol_col = 'OPNPRIC', 'HGHPRIC', 'LWPRIC', 'CLSPRIC', 'TTLTRADGVOL'
            dt_col = 'TRADDT'
        elif 'SYMBOL' in raw.columns:
            sym_col, series_col = 'SYMBOL', 'SERIES'
            opn_col, hgh_col, low_col, cls_col, vol_col = 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'TOTTRDQTY'
            dt_col = 'TIMESTAMP'
        else:
            self.log(f"Unknown bhavcopy format. Columns: {raw.columns}")
            return pd.DataFrame()
            
        raw = raw[raw[series_col].isin(['EQ', 'BE', 'BZ'])].copy()
        
        if dt_col in raw.columns:
            try:
                raw['date'] = pd.to_datetime(raw[dt_col]).dt.strftime("%Y-%m-%d")
            except:
                raw['date'] = fallback_date
        else:
            raw['date'] = fallback_date
            
        res = pd.DataFrame({
            'date': raw['date'],
            'symbol': raw[sym_col].astype(str).str.strip(),
            'open': pd.to_numeric(raw[opn_col], errors='coerce'),
            'high': pd.to_numeric(raw[hgh_col], errors='coerce'),
            'low': pd.to_numeric(raw[low_col], errors='coerce'),
            'close': pd.to_numeric(raw[cls_col], errors='coerce'),
            'volume': pd.to_numeric(raw[vol_col], errors='coerce')
        })
        
        res = res.dropna()
        res = res[(res['open'] > 0) & (res['high'] > 0) & (res['low'] > 0) & (res['close'] > 0)]
        return res

    def fetch_corporate_actions(self, start_date: str, end_date: str) -> List[Dict]:
        session = self._get_session()
        try:
            self.log("Visiting nseindia.com for cookies")
            session.get("https://www.nseindia.com", timeout=10)
            
            url = "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
            self.log(f"Fetching corporate actions from {url}")
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            else:
                self.log(f"Failed to fetch corporate actions, status: {resp.status_code}")
                return []
        except Exception as e:
            self.log(f"Error fetching corporate actions: {e}")
            return []

    def parse_corporate_actions(self, raw_actions: List[Dict], start_date: str, end_date: str) -> List[Dict]:
        parsed = []
        for action in raw_actions:
            ex_date_str = action.get('exDate', '')
            if not ex_date_str or ex_date_str == '-':
                continue
            
            try:
                ex_date = datetime.datetime.strptime(ex_date_str, "%d-%b-%Y").strftime("%Y-%m-%d")
            except:
                continue
                
            if not (start_date <= ex_date <= end_date):
                continue
                
            symbol = str(action.get('symbol', '')).strip()
            subject = str(action.get('subject', '')).lower()
            
            m_split = re.search(r'split|sub-division.*rs\.?\s*(\d+).*to.*rs\.?\s*(\d+)', subject)
            if m_split:
                old_fv, new_fv = float(m_split.group(1)), float(m_split.group(2))
                if old_fv > 0 and new_fv > 0:
                    parsed.append({'symbol': symbol, 'ex_date': ex_date, 'type': 'split', 'factor': new_fv / old_fv})
                continue
                
            m_bonus = re.search(r'bonus.*(\d+):(\d+)', subject)
            if m_bonus:
                new_shares, old_shares = float(m_bonus.group(1)), float(m_bonus.group(2))
                if old_shares > 0:
                    parsed.append({'symbol': symbol, 'ex_date': ex_date, 'type': 'bonus', 'factor': old_shares / (old_shares + new_shares)})
                continue
                
            m_div = re.search(r'dividend.*(?:rs|inr)\.?\s*(\d+\.?\d*)', subject)
            if m_div:
                div_amt = float(m_div.group(1))
                parsed.append({'symbol': symbol, 'ex_date': ex_date, 'type': 'dividend', 'amount': div_amt})
        return parsed

    def apply_backward_adjustments(self, conn: sqlite3.Connection, parsed_actions: List[Dict]):
        cursor = conn.cursor()
        for act in parsed_actions:
            sym = act['symbol']
            ex_date = act['ex_date']
            
            if act['type'] in ['split', 'bonus']:
                factor = act['factor']
                vol_factor = 1.0 / factor
                self.log(f"Applying {act['type']} for {sym} before {ex_date}, factor {factor}")
                cursor.execute(
                    "UPDATE prices SET open=open*?, high=high*?, low=low*?, close=close*?, volume=volume*? WHERE symbol=? AND date<?",
                    (factor, factor, factor, factor, vol_factor, sym, ex_date)
                )
            elif act['type'] == 'dividend':
                cursor.execute("SELECT close FROM prices WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1", (sym, ex_date))
                res = cursor.fetchone()
                if res and res[0] and res[0] > 0:
                    last_close = res[0]
                    div_amt = act['amount']
                    if div_amt < last_close:
                        factor = 1.0 - (div_amt / last_close)
                        self.log(f"Applying dividend for {sym} before {ex_date}, amt {div_amt}, factor {factor}")
                        cursor.execute(
                            "UPDATE prices SET open=open*?, high=high*?, low=low*?, close=close*? WHERE symbol=? AND date<?",
                            (factor, factor, factor, factor, sym, ex_date)
                        )

    def validate_database(self, conn: sqlite3.Connection) -> Tuple[bool, str]:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prices WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL")
        null_count = cursor.fetchone()[0]
        if null_count > 0:
            return False, f"Found {null_count} rows with null prices"
            
        cursor.execute("SELECT COUNT(*) FROM prices WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0")
        neg_count = cursor.fetchone()[0]
        if neg_count > 0:
            return False, f"Found {neg_count} rows with non-positive prices"
            
        cursor.execute("SELECT symbol, date, COUNT(*) FROM prices GROUP BY symbol, date HAVING COUNT(*) > 1")
        dupes = cursor.fetchone()
        if dupes:
            return False, f"Found duplicates, e.g., symbol {dupes[0]} on {dupes[1]}"
            
        return True, "Database valid"

    def sync_universe(self, target_date: str = None, dry_run: bool = False) -> Dict:
        self.log(f"Starting sync_universe, target_date={target_date}, dry_run={dry_run}")
        
        missing_dates = self.get_missing_trading_dates(target_date)
        if not missing_dates:
            self.log("No missing dates to fetch.")
            return {"status": "success", "dates_fetched": 0, "actions_applied": 0}
            
        self.log(f"Missing dates: {missing_dates}")
        
        conn = _de.get_connection(read_only=True, reuse=True)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM prices")
        valid_symbols = set(row[0] for row in cursor.fetchall())
        
        new_data_frames = []
        for d in missing_dates:
            df = self.fetch_bhavcopy_for_date(d)
            if df is not None and not df.empty:
                if valid_symbols:
                    df = df[df['symbol'].isin(valid_symbols)]
                df['is_delisted'] = 0
                new_data_frames.append(df)
                self.log(f"Fetched {len(df)} records for {d}")
            else:
                self.log(f"No data for {d}")
                
        actions_applied = 0
        if not dry_run and new_data_frames:
            write_conn = _de.get_connection(read_only=False, reuse=False)
            try:
                upsert_query = """
                    INSERT OR REPLACE INTO prices 
                    (date, symbol, open, high, low, close, volume, is_delisted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """
                for df in new_data_frames:
                    rows_to_insert = [
                        (
                            str(row['date']),
                            str(row['symbol']),
                            float(row['open']),
                            float(row['high']),
                            float(row['low']),
                            float(row['close']),
                            float(row['volume']),
                            int(row.get('is_delisted', 0))
                        )
                        for _, row in df.iterrows()
                    ]
                    write_conn.executemany(upsert_query, rows_to_insert)
                
                start_ca, end_ca = missing_dates[0], missing_dates[-1]
                raw_ca = self.fetch_corporate_actions(start_ca, end_ca)
                parsed_ca = self.parse_corporate_actions(raw_ca, start_ca, end_ca)
                if parsed_ca:
                    self.apply_backward_adjustments(write_conn, parsed_ca)
                    actions_applied = len(parsed_ca)
                
                is_valid, msg = self.validate_database(write_conn)
                if not is_valid:
                    write_conn.rollback()
                    self.log(f"Database validation failed: {msg}. Rolled back transaction.")
                    return {"status": "error", "message": f"Validation failed: {msg}"}

                write_conn.commit()
                self.log(f"Successfully committed {sum(len(df) for df in new_data_frames):,} bars and {actions_applied} corporate actions.")
                _de._CACHED_CONN = None
                
            except Exception as e:
                write_conn.rollback()
                self.log(f"Error during db update: {e}")
                return {"status": "error", "message": str(e)}
            finally:
                write_conn.close()
                
        return {
            "status": "success",
            "dates_fetched": len(new_data_frames),
            "actions_applied": actions_applied
        }
