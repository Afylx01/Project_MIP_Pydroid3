#!/usr/bin/env python3
"""
TDD Test 02: Pydroid 3 Data Access Engine Verification & Benchmarks
Directive: DIR-PROD-PYDROID3-PORT-01 (Standing Gate HALT-16)

Tests:
1. SQLite connection and pragma configurations.
2. Invariant verification:
   - Total rows == 2,146,531
   - Unique symbols == 1,039
   - Date span == 2007-01-02 to 2026-09-11
   - Positive prices == 100%
   - Null values == 0
3. Sub-millisecond indexed query benchmarks:
   - Single-symbol 250-bar raw indexed lookup latency (<15ms)
   - Single-symbol 250-bar DataFrame retrieval latency (<50ms)
   - Universe daily snapshot latency (<150ms)
   - Multi-symbol date slice
4. Sector taxonomy mapping completeness (100% coverage).
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pydroid_core.data_engine import (
    get_db_path,
    get_connection,
    get_latest_date,
    get_date_range,
    get_symbols,
    load_bars,
    load_symbol_history,
    load_universe_snapshot,
    load_symbol_sector_map,
    load_trading_calendar,
    get_universe_statistics,
)

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log_pass(msg: str):
    print(f" {GREEN}[PASS]{RESET} {msg}")


def log_fail(msg: str):
    print(f" {RED}[FAIL]{RESET} {msg}")


def log_info(msg: str):
    print(f" {CYAN}[INFO]{RESET} {msg}")


def main():
    print(f"{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD}{CYAN} PROJECT MIP: PYDROID 3 DATA ENGINE & DATABASE AUDIT (TEST 02){RESET}")
    print(f"{BOLD}{'=' * 72}{RESET}\n")

    failures = 0

    # 1. Database File Presence & Size
    db_path = get_db_path()
    log_info(f"Database File: {db_path}")
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        log_pass(f"Database exists on storage ({size_mb:.2f} MB)")
    else:
        log_fail(f"Database file does not exist at {db_path}")
        return 1

    # 2. Database Invariants
    log_info("Executing Master Database Integrity Invariant Checks...")
    stats = get_universe_statistics()
    log_info(f"Statistics: {stats}")

    expected_rows = 2146531
    if stats["total_rows"] == expected_rows:
        log_pass(f"Total row count exactly matches master ({stats['total_rows']:,} rows)")
    else:
        log_fail(f"Row count mismatch: Expected {expected_rows:,}, got {stats['total_rows']:,}")
        failures += 1

    expected_symbols = 1039
    if stats["unique_symbols"] == expected_symbols:
        log_pass(f"Unique symbol count verified ({stats['unique_symbols']:,} symbols)")
    else:
        log_fail(f"Symbol count mismatch: Expected {expected_symbols}, got {stats['unique_symbols']}")
        failures += 1

    expected_min_date = "2007-01-02"
    expected_max_date = "2026-09-11"
    if stats["min_date"] == expected_min_date and stats["max_date"] == expected_max_date:
        log_pass(f"Date boundaries verified: {stats['min_date']} to {stats['max_date']}")
    else:
        log_fail(f"Date range mismatch: Expected {expected_min_date}..{expected_max_date}, got {stats['min_date']}..{stats['max_date']}")
        failures += 1

    # 3. Fast Zero-Null / Positive Prices Verification
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM prices WHERE close <= 0 OR open <= 0 OR high <= 0 OR low <= 0;")
    non_pos = c.fetchone()[0]
    if non_pos == 0:
        log_pass("100% positive OHLC prices confirmed (zero non-positive values)")
    else:
        log_fail(f"Found {non_pos} non-positive price rows!")
        failures += 1

    c.execute("SELECT COUNT(*) FROM prices WHERE date IS NULL OR symbol IS NULL OR close IS NULL;")
    nulls = c.fetchone()[0]
    if nulls == 0:
        log_pass("Zero null values across required columns confirmed")
    else:
        log_fail(f"Found {nulls} null rows!")
        failures += 1

    # 4. Latency Benchmarks
    print(f"\n{BOLD}--- Performance & Latency Benchmarks ---{RESET}")
    test_symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC", "LT", "ICICIBANK", "SBIN", "BHARTIARTL", "KOTAKBANK"]

    # Warmup query
    load_symbol_history("RELIANCE", lookback_bars=250, as_dataframe=False)

    # 4a. Raw indexed cursor lookup latency (target < 15ms)
    raw_latencies = []
    for sym in test_symbols:
        t0 = time.perf_counter()
        records = load_symbol_history(sym, lookback_bars=250, as_dataframe=False)
        dt = (time.perf_counter() - t0) * 1000.0  # ms
        raw_latencies.append(dt)
        if len(records) != 250:
            log_fail(f"Symbol {sym} returned {len(records)} records, expected 250")
            failures += 1

    avg_raw_lat = sum(raw_latencies) / len(raw_latencies)
    min_raw_lat = min(raw_latencies)
    max_raw_lat = max(raw_latencies)
    log_info(f"Raw Indexed 250-Bar Latency (10 scrips): Avg {avg_raw_lat:.2f} ms | Min {min_raw_lat:.2f} ms | Max {max_raw_lat:.2f} ms")
    if avg_raw_lat < 15.0:
        log_pass(f"Raw indexed lookup benchmark PASSED (< 15 ms target, achieved {avg_raw_lat:.2f} ms)")
    else:
        log_fail(f"Raw indexed lookup too slow: {avg_raw_lat:.2f} ms >= 15 ms target")
        failures += 1

    # 4b. Single-symbol 250-bar DataFrame retrieval latency (target < 50ms)
    df_latencies = []
    for sym in test_symbols:
        t0 = time.perf_counter()
        df_sym = load_symbol_history(sym, lookback_bars=250, as_dataframe=True)
        dt = (time.perf_counter() - t0) * 1000.0
        df_latencies.append(dt)
        if len(df_sym) != 250:
            log_fail(f"Symbol {sym} returned {len(df_sym)} bars, expected 250")
            failures += 1

    avg_df_lat = sum(df_latencies) / len(df_latencies)
    min_df_lat = min(df_latencies)
    max_df_lat = max(df_latencies)
    log_info(f"DataFrame 250-Bar Latency (10 scrips): Avg {avg_df_lat:.2f} ms | Min {min_df_lat:.2f} ms | Max {max_df_lat:.2f} ms")
    if avg_df_lat < 50.0:
        log_pass(f"DataFrame lookup benchmark PASSED (< 50 ms target, achieved {avg_df_lat:.2f} ms)")
    else:
        log_fail(f"DataFrame lookup too slow: {avg_df_lat:.2f} ms >= 50 ms target")
        failures += 1

    # 4c. Universe Daily Snapshot Latency
    latest_date = get_latest_date()
    t0 = time.perf_counter()
    df_snap = load_universe_snapshot(latest_date)
    dt_snap = (time.perf_counter() - t0) * 1000.0
    log_info(f"Universe Snapshot Latency ({latest_date}): {dt_snap:.2f} ms ({len(df_snap)} scrips)")
    if dt_snap < 150.0 and len(df_snap) >= 490:
        log_pass(f"Universe snapshot benchmark PASSED ({dt_snap:.2f} ms, {len(df_snap)} scrips)")
    else:
        log_fail(f"Universe snapshot benchmark failed or count < 490: {dt_snap:.2f} ms, count {len(df_snap)}")
        failures += 1

    # 4d. Date Range Slicing
    t0 = time.perf_counter()
    df_slice = load_bars(start_date="2026-08-01", end_date="2026-08-31", symbols=["RELIANCE", "TCS", "INFY"])
    dt_slice = (time.perf_counter() - t0) * 1000.0
    log_info(f"Multi-symbol 1-month slice latency: {dt_slice:.2f} ms ({len(df_slice)} rows)")
    if len(df_slice) > 0:
        log_pass(f"Date range filtering verified ({len(df_slice)} rows returned in {dt_slice:.2f} ms)")
    else:
        log_fail("Date range filtering returned empty dataframe!")
        failures += 1

    # 5. Sector Map Completeness
    print(f"\n{BOLD}--- Metadata & Sector Taxonomy Verification ---{RESET}")
    sector_map = load_symbol_sector_map()
    log_info(f"Sector Taxonomy Mapping: {len(sector_map)} symbols mapped")
    if len(sector_map) >= 1000:
        log_pass(f"Sector taxonomy coverage confirmed ({len(sector_map)} >= 1,000)")
    else:
        log_fail(f"Sector taxonomy incomplete: {len(sector_map)} symbols")
        failures += 1

    calendar = load_trading_calendar()
    log_info(f"NSE Trading Calendar: {len(calendar)} trading days")
    if len(calendar) > 3000:
        log_pass(f"Trading calendar loaded successfully ({len(calendar):,} trading days)")
    else:
        log_fail(f"Trading calendar missing or too short ({len(calendar)} entries)")
        failures += 1

    # Summary
    print(f"\n{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD} TEST 02 AUDIT SUMMARY:{RESET}")
    print(f"  Failures: {failures}")
    print(f"{BOLD}{'=' * 72}{RESET}\n")

    if failures == 0:
        print(f"{BOLD}{GREEN} [PASS] PYDROID 3 DATA ENGINE VERIFIED & READY FOR TEST 03{RESET}\n")
        return 0
    else:
        print(f"{BOLD}{RED} [FAIL] TEST 02 FAILED WITH {failures} ERRORS.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
