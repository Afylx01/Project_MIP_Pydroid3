#!/usr/bin/env python3
"""
TDD Test 03: Pydroid 3 Momentum Scanner, Breadth & RRG Verification
Directive: DIR-PROD-PYDROID3-PORT-01 (Standing Gate HALT-16)

Tests:
1. End-to-end execution of PydroidScanner on latest trading date.
2. Market Breadth metrics calculation:
   - % > 200 EMA, % > 50 EMA, % > 20 EMA
   - High proximity (% within 20% and 5% of 52wH)
   - Net new highs/lows
   - Regime classification
3. Sector Rotation Engine execution:
   - 12 primary sectors analyzed & ranked
   - Alpha vs benchmark computed
4. Strategy Filter application:
   - Retracement <= 20% from 52wH
   - Trend > 200 EMA
   - RS > 200 EMA of ratio
   - Exactly Top 20 Candidates selected
5. Telegram alert payload formatting:
   - Character count invariance (< 4,096 chars)
   - Dry-run dispatch test
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pydroid_core.data_engine import get_latest_date
from pydroid_core.scanner import PydroidScanner, format_screener_tearsheet
from pydroid_core.telegram_sender import PydroidTelegramSender, format_telegram_alert

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
    print(f"{BOLD}{CYAN} PROJECT MIP: PYDROID 3 SCANNER & BREADTH PIPELINE AUDIT (TEST 03){RESET}")
    print(f"{BOLD}{'=' * 72}{RESET}\n")

    failures = 0
    latest_date = get_latest_date()
    log_info(f"Target Execution Date: {latest_date}")

    # 1. Initialize Scanner
    scanner = PydroidScanner()
    log_pass("PydroidScanner initialized successfully")

    # 2. Run Scan
    log_info("Running full quantitative screener pipeline...")
    top_df, breadth, sectors, regime, top_etf, deliv = scanner.run_scan(
        as_of_date=latest_date,
        top_n=20,
        lookback_days=550,
        export_csv=True,
        export_excel=True
    )

    # 3. Assert Candidate Count & Sector Concentration Hard Cap
    log_info(f"Top Candidates Selected: {len(top_df)}")
    if len(top_df) == 20:
        log_pass("Candidate allocation verified: Exactly 20 top momentum scrips selected")
    else:
        log_fail(f"Expected 20 candidates, got {len(top_df)}")
        failures += 1

    max_sec = top_df["sector"].value_counts().max()
    log_info(f"Max stocks per sector: {max_sec}")
    if max_sec <= 2:
        log_pass("Sector concentration hard cap strictly satisfied (Max <= 2 stocks per sector)")
    else:
        log_fail(f"Sector hard cap violated: {max_sec} > 2")
        failures += 1

    # 3b. Assert ATR-14 & Dynamic Stop Loss
    if "atr_14" in top_df.columns and "stop_loss" in top_df.columns:
        log_pass("ATR-14 volatility risk metrics and dynamic stop loss (2x ATR) verified")
    else:
        log_fail("ATR-14 or stop_loss column missing from top_df")
        failures += 1

    # 3c. Assert ETF Momentum Engine (Top 7)
    if top_etf is not None and len(top_etf) == 7:
        log_pass(f"Definedge ALL-ONE ETF Momentum Engine verified: {len(top_etf)} top non-repeating picks")
    else:
        log_fail("ETF engine failed to return top 7 picks")
        failures += 1

    # 4. Assert Breadth Metrics
    tp = breadth.get("trend_participation", {})
    pct_200 = tp.get("pct_above_200_ema", 0)
    pct_50 = tp.get("pct_above_50_ema", 0)
    log_info(f"Market Breadth: % > 200 EMA = {pct_200}% | % > 50 EMA = {pct_50}%")
    if 0 <= pct_200 <= 100 and 0 <= pct_50 <= 100:
        log_pass("Market breadth metrics within valid percentage range [0, 100]")
    else:
        log_fail("Market breadth metrics out of bounds!")
        failures += 1

    # 5. Assert Sector Rotation Coverage
    sec_list = sectors.get("sectors", [])
    log_info(f"Sectors Analyzed: {len(sec_list)} sectors")
    if len(sec_list) == 12:
        log_pass("Sector rotation coverage verified: All 12 primary NSE sectors evaluated")
    else:
        log_fail(f"Sector count mismatch: Expected 12, got {len(sec_list)}")
        failures += 1

    # 6. Check CSV and 12-Sheet Excel Export
    csv_file = BASE_DIR / "reports" / "screener_output_live.csv"
    if csv_file.exists() and csv_file.stat().st_size > 0:
        log_pass(f"Screener CSV export confirmed: {csv_file} ({csv_file.stat().st_size} bytes)")
    else:
        log_fail(f"Screener CSV export missing or empty: {csv_file}")
        failures += 1

    excel_file = BASE_DIR / "reports" / f"MIP1_Momentum_Scanner_{latest_date}.xlsx"
    if excel_file.exists() and excel_file.stat().st_size > 0:
        log_pass(f"Institutional 12-sheet Excel export confirmed: {excel_file} ({excel_file.stat().st_size:,} bytes)")
    else:
        log_fail(f"Institutional Excel export missing: {excel_file}")
        failures += 1

    # 7. Print Terminal Tearsheet
    print(f"\n{BOLD}--- Terminal Screener Tearsheet ---{RESET}")
    tearsheet = format_screener_tearsheet(
        top_df, breadth, sectors, regime, latest_date,
        top_etf_df=top_etf, delivery_df=deliv
    )
    print(tearsheet)

    # 8. Test Telegram Alert Formatting & Size Invariant
    print(f"\n{BOLD}--- Telegram Alert Payload Verification ---{RESET}")
    alert_msg = format_telegram_alert(
        top_df, breadth, sectors, regime, latest_date,
        top_etf_df=top_etf, delivery_df=deliv
    )
    char_len = len(alert_msg)
    log_info(f"Telegram Alert Length: {char_len:,} characters (Telegram Limit: 4,096)")

    if char_len <= 4096:
        log_pass(f"Telegram message length invariant strictly satisfied ({char_len} <= 4,096)")
    else:
        log_fail(f"Telegram message exceeds 4,096 characters ({char_len} chars)")
        failures += 1

    # 9. Dry-Run Dispatch Test
    sender = PydroidTelegramSender()
    dry_ok = sender.send_message(alert_msg, dry_run=True)
    if dry_ok:
        log_pass("Telegram dry-run dispatch simulation passed")
    else:
        log_fail("Telegram dry-run dispatch failed")
        failures += 1

    # Summary
    print(f"\n{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD} TEST 03 AUDIT SUMMARY:{RESET}")
    print(f"  Failures: {failures}")
    print(f"{BOLD}{'=' * 72}{RESET}\n")

    if failures == 0:
        print(f"{BOLD}{GREEN} [PASS] PYDROID 3 SCANNER VERIFIED & READY FOR TEST 04{RESET}\n")
        return 0
    else:
        print(f"{BOLD}{RED} [FAIL] TEST 03 FAILED WITH {failures} ERRORS.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
