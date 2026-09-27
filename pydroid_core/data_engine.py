"""
Project MIP Pydroid 3 Data Access Engine
Directive: DIR-PROD-PYDROID3-PORT-01

Pure Python + SQLite3 + Pandas data layer.
Zero PyArrow / Fastparquet dependency.
Optimized for mobile ARM64 storage and sub-millisecond indexed queries.
"""

import json
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

_CACHED_CONN: Optional[sqlite3.Connection] = None


def get_base_dir() -> Path:
    """Returns the base directory of Project_MIP_Pydroid3."""
    p = Path(__file__).resolve().parent.parent
    if (p / "data" / "universe.db").exists():
        return p
    
    candidates = [
        Path("/storage/emulated/0/Documents/Project_MIP_Pydroid3"),
        Path("/sdcard/Documents/Project_MIP_Pydroid3"),
    ]
    for c in candidates:
        if (c / "data" / "universe.db").exists():
            return c
    return p


def get_db_path() -> Path:
    """Returns absolute path to universe.db."""
    return get_base_dir() / "data" / "universe.db"


def get_connection(read_only: bool = True, reuse: bool = True) -> sqlite3.Connection:
    """
    Returns an open SQLite3 connection with performance pragmas.
    Reuses existing connection by default to avoid connection open/close overhead.
    """
    global _CACHED_CONN
    if reuse and _CACHED_CONN is not None:
        try:
            # Quick probe
            _CACHED_CONN.execute("SELECT 1;")
            return _CACHED_CONN
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            _CACHED_CONN = None

    db_path = get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}! Please run scripts/export_universe_to_sqlite.py first.")
    
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    if read_only:
        try:
            conn.execute("PRAGMA query_only = ON;")
        except sqlite3.OperationalError:
            pass
    conn.execute("PRAGMA cache_size = 100000;")
    conn.execute("PRAGMA mmap_size = 300000000;")
    conn.execute("PRAGMA temp_store = MEMORY;")

    if reuse:
        _CACHED_CONN = conn
    return conn


def get_latest_date() -> str:
    """Returns the latest available trading date in universe.db (YYYY-MM-DD)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(date) FROM prices;")
    res = cursor.fetchone()
    return res[0] if res and res[0] else ""


def get_date_range() -> Tuple[str, str]:
    """Returns (min_date, max_date)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MIN(date), MAX(date) FROM prices;")
    res = cursor.fetchone()
    return (res[0], res[1]) if res else ("", "")


def get_symbols() -> List[str]:
    """Returns sorted list of all unique symbols in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT symbol FROM prices ORDER BY symbol ASC;")
    return [row[0] for row in cursor.fetchall()]


def load_bars(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    symbols: Optional[List[str]] = None,
    include_delisted: bool = True
) -> pd.DataFrame:
    """
    Loads OHLCV bars matching criteria.
    Dynamically uses index idx_prices_date or idx_prices_sym_date.
    """
    conditions = []
    params = []

    if start_date:
        conditions.append("date >= ?")
        params.append(str(start_date))
    if end_date:
        conditions.append("date <= ?")
        params.append(str(end_date))
    if symbols:
        placeholders = ",".join("?" for _ in symbols)
        conditions.append(f"symbol IN ({placeholders})")
        params.extend(symbols)
    if not include_delisted:
        conditions.append("is_delisted = 0")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT date, symbol, open, high, low, close, volume, is_delisted
        FROM prices
        {where_clause}
        ORDER BY date ASC, symbol ASC;
    """

    conn = get_connection()
    df = pd.read_sql_query(query, conn, params=params)
    
    if not df.empty:
        df['is_delisted'] = df['is_delisted'].astype(bool)
    return df


def load_symbol_history(
    symbol: str,
    lookback_bars: int = 250,
    end_date: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
    as_dataframe: bool = True
) -> Any:
    """
    Sub-millisecond retrieval of symbol historical bars using idx_prices_sym_date.
    Returns bars sorted in ascending chronological order.
    """
    db_conn = conn or get_connection()
    cursor = db_conn.cursor()

    if end_date:
        query = """
            SELECT date, symbol, open, high, low, close, volume, is_delisted
            FROM prices
            WHERE symbol = ? AND date <= ?
            ORDER BY date DESC
            LIMIT ?;
        """
        params = (symbol, str(end_date), int(lookback_bars))
    else:
        query = """
            SELECT date, symbol, open, high, low, close, volume, is_delisted
            FROM prices
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT ?;
        """
        params = (symbol, int(lookback_bars))

    cursor.execute(query, params)
    rows = cursor.fetchall()

    if not as_dataframe:
        # Return reversed raw tuples: (date, symbol, open, high, low, close, volume, is_delisted)
        return rows[::-1]

    cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'is_delisted']
    if not rows:
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(rows, columns=cols)
    df = df.iloc[::-1].reset_index(drop=True)
    df['is_delisted'] = df['is_delisted'].astype(bool)
    return df


def load_universe_snapshot(date: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> pd.DataFrame:
    """
    Retrieves all scrip bars for a specific date (or latest date).
    Uses idx_prices_date for ultra-fast snapshot retrieval.
    """
    db_conn = conn or get_connection()
    target_date = date or get_latest_date()
    query = """
        SELECT date, symbol, open, high, low, close, volume, is_delisted
        FROM prices
        WHERE date = ?
        ORDER BY symbol ASC;
    """
    df = pd.read_sql_query(query, db_conn, params=[target_date])
    if not df.empty:
        df['is_delisted'] = df['is_delisted'].astype(bool)
    return df


def load_symbol_sector_map() -> Dict[str, str]:
    """Loads official sector taxonomy mapping dictionary {SYMBOL: SECTOR}."""
    map_path = get_base_dir() / "data" / "symbol_sector_map.json"
    if not map_path.exists():
        return {}
    with open(map_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("symbol_to_sector", data)


def load_trading_calendar() -> List[str]:
    """Loads list of valid NSE trading dates."""
    cal_path = get_base_dir() / "data" / "trading_calendar.txt"
    if not cal_path.exists():
        return []
    with open(cal_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return sorted(lines)


def get_universe_statistics() -> Dict[str, Any]:
    """Returns database summary statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM prices;")
    total_rows = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT symbol) FROM prices;")
    unique_symbols = cursor.fetchone()[0]

    cursor.execute("SELECT MIN(date), MAX(date) FROM prices;")
    min_date, max_date = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM prices WHERE is_delisted = 1;")
    delisted_count = cursor.fetchone()[0]

    db_path = get_db_path()
    file_size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0.0

    return {
        "db_path": str(db_path),
        "file_size_mb": round(file_size_mb, 2),
        "total_rows": total_rows,
        "unique_symbols": unique_symbols,
        "min_date": min_date,
        "max_date": max_date,
        "delisted_rows": delisted_count,
    }
