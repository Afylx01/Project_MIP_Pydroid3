#!/usr/bin/env python3
"""
Project MIP: Standalone Pydroid 3 Quantitative Workstation
Directives: DIR-PROD-PYDROID3-PORT-01 (HALT-16), DIR-PROD-PYDROID3-PARITY-01 (HALT-17)

Unified 12-option interactive mobile trading desk engineered for Pydroid 3.
Zero-compiler, pure Python + SQLite standard library architecture.
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pydroid_core.data_engine import (
    get_db_path,
    get_latest_date,
    get_universe_statistics,
    get_date_range,
    get_symbols,
    load_symbol_sector_map,
    load_trading_calendar,
    get_connection,
)
from pydroid_core.scanner import PydroidScanner, format_screener_tearsheet
from pydroid_core.breadth import MarketBreadthEngine
from pydroid_core.sector_rotation import SectorRotationEngine
from pydroid_core.visuals import generate_matplotlib_dashboard, generate_plotly_tearsheet
from pydroid_core.telegram_sender import PydroidTelegramSender, format_telegram_alert
from pydroid_core.backtest import LightweightBacktester

# ANSI Styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_MAGENTA = "\033[95m"
C_GRAY = "\033[90m"
C_WHITE = "\033[97m"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner(latest_date: str):
    print(f"{C_BOLD}{C_CYAN}╔══════════════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║           PROJECT MIP — PYDROID 3 MOBILE TRADING DESK                ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║    Standalone Zero-Compiler Edition • Python 3.13 ARM64 • v2.0.0     ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}╚══════════════════════════════════════════════════════════════════════╝{C_RESET}")
    print(f" {C_GRAY}Database: universe.db (Indexed SQLite) | Latest EOD: {C_BOLD}{latest_date}{C_RESET}")
    print(f"{C_GRAY}{'─' * 72}{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [1]: Weekly Momentum Scanner (Full Suite)
# ═══════════════════════════════════════════════════════════════════════
def run_scanner_flow(interactive: bool = True):
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_YELLOW}⚡ RUNNING WEEKLY MOMENTUM SCANNER (FULL SUITE)...{C_RESET}\n")

    scanner = PydroidScanner(BASE_DIR)
    top_df, breadth, sectors, regime = scanner.run_scan(
        as_of_date=latest_date,
        top_n=20,
        export_csv=True
    )

    tearsheet = format_screener_tearsheet(top_df, breadth, sectors, regime, latest_date)
    print(tearsheet)

    print(f"\n{C_GREEN}✓ Scan completed successfully!{C_RESET}")
    print(f"  • Screener CSV: {BASE_DIR / 'reports' / 'screener_output_live.csv'}")
    print(f"  • Market Breadth: {BASE_DIR / 'reports' / 'market_breadth_live.json'}")
    print(f"  • Sector Rotation: {BASE_DIR / 'reports' / 'sector_rotation_live.json'}")

    if interactive:
        input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [2]: Preview Telegram Alert
# ═══════════════════════════════════════════════════════════════════════
def run_telegram_preview():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_BLUE}📱 PREVIEWING LIVE TELEGRAM ALERT PAYLOAD...{C_RESET}\n")

    reports_dir = BASE_DIR / "reports"
    screener_file = reports_dir / "screener_output_live.csv"
    breadth_file = reports_dir / "market_breadth_live.json"
    sector_file = reports_dir / "sector_rotation_live.json"

    if not (screener_file.exists() and breadth_file.exists() and sector_file.exists()):
        print(f"{C_YELLOW}⚠ Live data not cached. Running scanner first...{C_RESET}")
        scanner = PydroidScanner(BASE_DIR)
        top_df, breadth, sectors, regime = scanner.run_scan(as_of_date=latest_date, top_n=20)
    else:
        import pandas as pd
        top_df = pd.read_csv(screener_file)
        with open(breadth_file, "r", encoding="utf-8") as f:
            breadth = json.load(f)
        with open(sector_file, "r", encoding="utf-8") as f:
            sectors = json.load(f)
        scanner = PydroidScanner(BASE_DIR)
        regime = scanner.evaluate_regime(latest_date)

    msg = format_telegram_alert(top_df, breadth, sectors, regime, latest_date)
    sender = PydroidTelegramSender()
    sender.send_message(msg, dry_run=True)

    print(f"\n{C_GRAY}Message Length: {len(msg):,} characters (Telegram Limit: 4,096){C_RESET}")
    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [3]: Dispatch Live Telegram Alert
# ═══════════════════════════════════════════════════════════════════════
def run_telegram_dispatch():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_MAGENTA}⚡ DISPATCHING LIVE TELEGRAM ALERT & DELIVERABLES...{C_RESET}\n")

    sender = PydroidTelegramSender()
    if not sender.is_configured():
        print(f"{C_RED}✗ Telegram credentials not configured in {BASE_DIR / '.env'}!{C_RESET}")
        print("Please edit .env and provide TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
        input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")
        return

    reports_dir = BASE_DIR / "reports"
    screener_file = reports_dir / "screener_output_live.csv"
    if not screener_file.exists():
        print(f"{C_YELLOW}Running scanner to generate latest deliverables...{C_RESET}")
        scanner = PydroidScanner(BASE_DIR)
        top_df, breadth, sectors, regime = scanner.run_scan(as_of_date=latest_date, top_n=20)
    else:
        import pandas as pd
        top_df = pd.read_csv(screener_file)
        with open(reports_dir / "market_breadth_live.json", "r", encoding="utf-8") as f:
            breadth = json.load(f)
        with open(reports_dir / "sector_rotation_live.json", "r", encoding="utf-8") as f:
            sectors = json.load(f)
        scanner = PydroidScanner(BASE_DIR)
        regime = scanner.evaluate_regime(latest_date)

    msg = format_telegram_alert(top_df, breadth, sectors, regime, latest_date)
    print("Dispatching executive alert message...")
    ok_msg = sender.send_message(msg)

    chart_png = reports_dir / "market_overview_chart.png"
    if chart_png.exists():
        print("Dispatching market overview chart PNG...")
        sender.send_photo(chart_png, caption=f"📊 Market Overview Chart — {latest_date}")

    if screener_file.exists():
        print("Dispatching screener candidate CSV...")
        sender.send_document(screener_file, caption=f"📁 Screener Candidates — {latest_date}")

    if ok_msg:
        print(f"\n{C_GREEN}✓ Live Telegram notification dispatched successfully!{C_RESET}")
    else:
        print(f"\n{C_RED}✗ Failed to dispatch message to Telegram.{C_RESET}")

    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [4]: Generate Visual Charts & Tearsheets
# ═══════════════════════════════════════════════════════════════════════
def run_visuals_generator():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_GREEN}📊 GENERATING VISUAL CHARTS & TEARSHEETS...{C_RESET}\n")

    reports_dir = BASE_DIR / "reports"
    screener_file = reports_dir / "screener_output_live.csv"
    if not screener_file.exists():
        print(f"{C_YELLOW}Running scanner to generate latest metrics...{C_RESET}")
        scanner = PydroidScanner(BASE_DIR)
        top_df, breadth, sectors, regime = scanner.run_scan(as_of_date=latest_date, top_n=20)
    else:
        import pandas as pd
        top_df = pd.read_csv(screener_file)
        with open(reports_dir / "market_breadth_live.json", "r", encoding="utf-8") as f:
            breadth = json.load(f)
        with open(reports_dir / "sector_rotation_live.json", "r", encoding="utf-8") as f:
            sectors = json.load(f)

    print("Generating Matplotlib 3-panel graphic...")
    png_path = generate_matplotlib_dashboard(breadth, sectors, top_df)
    print(f"  ✓ Exported: {png_path} ({png_path.stat().st_size:,} bytes)")

    print("\nGenerating interactive HTML tearsheet...")
    html_path = generate_plotly_tearsheet(breadth, sectors, top_df)
    print(f"  ✓ Exported: {html_path} ({html_path.stat().st_size:,} bytes)")

    print(f"\n{C_GREEN}✓ All visual deliverables exported to reports/{C_RESET}")
    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [5]: Lightweight Custom Backtester
# ═══════════════════════════════════════════════════════════════════════
def run_custom_backtest_flow():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_CYAN}💼 LIGHTWEIGHT VECTOR BACKTESTER{C_RESET}\n")

    print(f"Configure Backtest Parameters (Press Enter to accept defaults):")
    start_in = input("  1. Start Date [Default: 2020-01-01]: ").strip() or "2020-01-01"
    end_in = input(f"  2. End Date [Default: {latest_date}]: ").strip() or latest_date
    top_n_in = input("  3. Portfolio Top N [Default: 20]: ").strip() or "20"
    capital_in = input("  4. Initial Capital (₹) [Default: 1000000]: ").strip() or "1000000"

    try:
        top_n = int(top_n_in)
        capital = float(capital_in)
    except ValueError:
        print(f"{C_RED}Invalid inputs! Using defaults.{C_RESET}")
        top_n = 20
        capital = 1_000_000.0

    print(f"\n{C_YELLOW}Running simulation from {start_in} to {end_in}...{C_RESET}")
    bt = LightweightBacktester(BASE_DIR)
    t0 = time.time()
    results = bt.run(
        start_date=start_in,
        end_date=end_in,
        top_n=top_n,
        initial_capital=capital
    )
    elapsed = time.time() - t0

    print(f"\n{C_BOLD}{'=' * 68}{C_RESET}")
    print(f"{C_BOLD} BACKTEST PERFORMANCE SUMMARY ({start_in} to {end_in}){C_RESET}")
    print(f"{C_BOLD}{'=' * 68}{C_RESET}")
    print(f"  Strategy CAGR:       {C_GREEN}{results['cagr_pct']:+.2f}%{C_RESET}")
    print(f"  Benchmark CAGR:      {results['benchmark_cagr_pct']:+.2f}%")
    print(f"  Excess CAGR:         {C_BOLD}{results['excess_cagr_pct']:+.2f}%{C_RESET}")
    print(f"  Sharpe Ratio:        {results['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio:       {results['sortino_ratio']:.2f}")
    print(f"  Calmar Ratio:        {results['calmar_ratio']:.2f}")
    print(f"  Max Drawdown:        {C_RED}{results['max_drawdown_pct']:.2f}%{C_RESET}")
    print(f"  Total Trades:        {results['total_trades']}")
    print(f"  Trade Win Rate:      {results['win_rate_pct']:.1f}%")
    print(f"  Final Equity:        ₹{results['final_equity']:,.2f}")
    print(f"  Computation Time:    {elapsed:.2f}s")
    print(f"{C_BOLD}{'=' * 68}{C_RESET}")
    print(f"✓ Results saved to reports/backtest_results.json")

    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [6]: TDD Diagnostics & Integrity Suite
# ═══════════════════════════════════════════════════════════════════════
def run_tdd_suite():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_YELLOW}🛡️ RUNNING TDD TEST & INTEGRITY SUITE (TESTS 01 - 04)...{C_RESET}\n")

    test_scripts = [
        "01_test_environment.py",
        "02_test_data_engine.py",
        "03_test_scanner.py",
        "04_test_visuals.py",
    ]

    all_passed = True
    for ts in test_scripts:
        script_path = BASE_DIR / "tests" / ts
        print(f"\n{C_BOLD}▶ Running {ts}...{C_RESET}")
        ret = os.system(f'"{sys.executable}" "{script_path}"')
        if ret != 0:
            all_passed = False
            print(f"{C_RED}✗ Test {ts} returned exit code {ret}{C_RESET}")
            break

    print(f"\n{C_BOLD}{'=' * 68}{C_RESET}")
    if all_passed:
        print(f"{C_BOLD}{C_GREEN} 🎉 ALL TDD INTEGRITY TESTS PASSED SUCCESSFULLY! (100% CERTIFIED){C_RESET}")
    else:
        print(f"{C_BOLD}{C_RED} ❌ TDD TEST SUITE ENCOUNTERED FAILURES.{C_RESET}")
    print(f"{C_BOLD}{'=' * 68}{C_RESET}")

    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [7]: Portfolio Rebalancing & Order Generation
# ═══════════════════════════════════════════════════════════════════════
def run_portfolio_orders():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_GREEN}💰 PORTFOLIO REBALANCING & ORDER GENERATION{C_RESET}\n")

    from pydroid_core.portfolio import PortfolioManager

    capital_in = input("  Initial Capital (₹) [Default: 1000000]: ").strip() or "1000000"
    top_n_in = input("  Portfolio Size Top N [Default: 20]: ").strip() or "20"

    try:
        capital = float(capital_in)
        top_n = int(top_n_in)
    except ValueError:
        print(f"{C_RED}Invalid inputs! Using defaults.{C_RESET}")
        capital = 1_000_000.0
        top_n = 20

    # Check if screener output exists
    screener_file = BASE_DIR / "reports" / "screener_output_live.csv"
    if not screener_file.exists():
        print(f"{C_YELLOW}Running scanner first to generate candidates...{C_RESET}")
        scanner = PydroidScanner(BASE_DIR)
        scanner.run_scan(as_of_date=latest_date, top_n=top_n, export_csv=True)

    pm = PortfolioManager(BASE_DIR)
    print(f"\n{C_YELLOW}Computing equal-weight allocation with statutory frictions...{C_RESET}")

    orders_df = pm.generate_rebalance_orders(capital=capital, top_n=top_n)
    csv_path = pm.export_orders(orders_df)

    # Display orders
    detail_rows = orders_df[orders_df['action'] != 'SUMMARY']
    summary_rows = orders_df[orders_df['action'] == 'SUMMARY']

    print(f"\n{C_BOLD}{'=' * 72}{C_RESET}")
    print(f"{C_BOLD} REBALANCE ORDER LEDGER — {latest_date} (₹{capital:,.0f} / Top {top_n}){C_RESET}")
    print(f"{C_BOLD}{'=' * 72}{C_RESET}")
    print(f"{'#':>3} {'Action':<6} {'Symbol':<14} {'Sector':<12} {'Price':>10} {'Shares':>8} {'Value':>12} {'Friction':>10}")
    print(f"{'─' * 72}")

    for i, (_, row) in enumerate(detail_rows.iterrows(), 1):
        action_color = C_GREEN if row['action'] == 'BUY' else (C_RED if row['action'] == 'SELL' else C_YELLOW)
        price_str = f"₹{row['close_price']:,.2f}" if not (row.get('close_price') is None or (isinstance(row['close_price'], float) and row['close_price'] != row['close_price'])) else "N/A"
        print(f"{i:>3} {action_color}{row['action']:<6}{C_RESET} {str(row['symbol']):<14} {str(row['sector']):<12} {price_str:>10} {int(row['target_shares']):>8} ₹{row['target_value']:>10,.0f} ₹{row['total_friction']:>8,.0f}")

    if not summary_rows.empty:
        s = summary_rows.iloc[0]
        print(f"{'─' * 72}")
        print(f"{C_BOLD}    TOTAL{' ' * 30}{' ' * 10} {int(s['target_shares']):>8} ₹{s['target_value']:>10,.0f} ₹{s['total_friction']:>8,.0f}{C_RESET}")
        print(f"    {C_CYAN}Total Cost (incl. frictions): ₹{s['total_cost']:,.0f}{C_RESET}")

    print(f"{C_BOLD}{'=' * 72}{C_RESET}")
    print(f"\n{C_GREEN}✓ Orders exported to:{C_RESET}")
    print(f"  • CSV: {csv_path}")
    print(f"  • TXT: {csv_path.with_suffix('.txt')}")

    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [8]: Auto-Fetch Market Data (NSE Bhavcopy Sync)
# ═══════════════════════════════════════════════════════════════════════
def run_auto_fetch():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_MAGENTA}📡 AUTOMATED MARKET DATA FETCHER (NSE BHAVCOPY SYNC){C_RESET}\n")

    from pydroid_core.auto_fetch import PydroidAutoFetch

    fetcher = PydroidAutoFetch(BASE_DIR)
    missing = fetcher.get_missing_trading_dates()

    print(f"  Current Max Date:   {latest_date}")
    print(f"  Missing Sessions:   {len(missing)}")
    if missing:
        print(f"  Date Range:         {missing[0]} → {missing[-1]}")

    if not missing:
        print(f"\n{C_GREEN}✓ Universe database is already up to date!{C_RESET}")
        input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")
        return

    print(f"\n{C_YELLOW}Options:{C_RESET}")
    print(f"  [1] Dry-Run (simulate without modifying database)")
    print(f"  [2] Live Sync (download & update database)")
    print(f"  [0] Cancel")

    choice = input(f"\n{C_BOLD}Select [0-2]: {C_RESET}").strip()

    if choice == "1":
        print(f"\n{C_YELLOW}Running dry-run simulation...{C_RESET}")
        result = fetcher.sync_universe(dry_run=True)
        print(f"\n{C_GREEN}✓ Dry-run complete. Status: {result.get('status', 'N/A')}{C_RESET}")
    elif choice == "2":
        print(f"\n{C_YELLOW}Starting live data synchronization...{C_RESET}")
        try:
            result = fetcher.sync_universe(dry_run=False)
            status = result.get('status', 'UNKNOWN')
            if status == 'SUCCESS':
                bars = result.get('bars_added', 0)
                new_max = result.get('end_date', 'N/A')
                print(f"\n{C_GREEN}✓ Synchronization COMPLETE!{C_RESET}")
                print(f"  Bars Added:     {bars:,}")
                print(f"  New Max Date:   {new_max}")
            else:
                print(f"\n{C_YELLOW}Sync result: {status}{C_RESET}")
        except Exception as e:
            print(f"\n{C_RED}✗ Sync failed: {e}{C_RESET}")
    else:
        print("Cancelled.")

    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [9]: Sync NSE Sector Taxonomy
# ═══════════════════════════════════════════════════════════════════════
def run_sector_sync():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_BLUE}🏭 SYNCHRONIZING OFFICIAL NSE SECTOR TAXONOMY{C_RESET}\n")

    from pydroid_core.sync_sectors import sync_nse_sectors

    print(f"{C_YELLOW}Downloading official NIFTY Total Market constituent list...{C_RESET}")
    try:
        mapping = sync_nse_sectors(BASE_DIR)
        print(f"\n{C_GREEN}✓ Sector taxonomy synchronized successfully!{C_RESET}")
        print(f"  Symbols Mapped:   {len(mapping):,}")

        # Show sector distribution
        import pandas as pd
        dist = pd.Series(list(mapping.values())).value_counts()
        print(f"\n{C_BOLD}  SECTOR DISTRIBUTION:{C_RESET}")
        for sector, count in dist.items():
            pct = (count / len(mapping)) * 100
            print(f"    {sector:<14} : {count:>4d} ({pct:>5.1f}%)")

        print(f"\n  Exported to: {BASE_DIR / 'data' / 'symbol_sector_map.json'}")
    except Exception as e:
        print(f"\n{C_RED}✗ Sector sync failed: {e}{C_RESET}")

    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [10]: Standalone Market Breadth Report
# ═══════════════════════════════════════════════════════════════════════
def run_standalone_breadth():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_CYAN}📈 STANDALONE MARKET BREADTH ANALYSIS{C_RESET}\n")

    engine = MarketBreadthEngine(BASE_DIR)
    print(f"{C_YELLOW}Computing breadth metrics for {latest_date}...{C_RESET}")

    breadth = engine.compute_breadth(as_of_date=latest_date)

    print(f"\n{C_BOLD}{'=' * 60}{C_RESET}")
    print(f"{C_BOLD} NIFTY 500 MARKET BREADTH — {latest_date}{C_RESET}")
    print(f"{C_BOLD}{'=' * 60}{C_RESET}")

    regime = breadth.get('regime', 'Unknown')
    regime_emoji = {'Bullish Expansion': '🟢', 'Selective/Neutral': '🟡', 'Contraction/Defensive': '🔴'}.get(regime, '⚪')

    print(f"  Regime:             {regime_emoji} {regime}")
    print(f"  % > 200 EMA:        {breadth.get('pct_above_ema200', 0):.1f}%")
    print(f"  % > 50 EMA:         {breadth.get('pct_above_ema50', 0):.1f}%")
    print(f"  % > 20 EMA:         {breadth.get('pct_above_ema20', 0):.1f}%")
    print(f"  % Near 52w High:    {breadth.get('pct_near_52w_high_20', 0):.1f}% (within 20%)")
    print(f"  % Near 52w High:    {breadth.get('pct_near_52w_high_5', 0):.1f}% (within 5%)")
    print(f"  New 52w Highs:      {breadth.get('new_52w_highs', 0)}")
    print(f"  New 52w Lows:       {breadth.get('new_52w_lows', 0)}")
    print(f"  Net Highs-Lows:     {breadth.get('net_highs_lows', 0)}")
    print(f"  Active Scrips:      {breadth.get('active_scrips', 0)}")
    print(f"{C_BOLD}{'=' * 60}{C_RESET}")

    # Save standalone report
    report_path = BASE_DIR / "reports" / "market_breadth_live.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(breadth, f, indent=2)
    print(f"\n{C_GREEN}✓ Breadth report saved to {report_path}{C_RESET}")

    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [11]: Standalone RRG & Sector Rotation Report
# ═══════════════════════════════════════════════════════════════════════
def run_standalone_sector_rrg():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_MAGENTA}🔄 STANDALONE SECTOR ROTATION & RRG ANALYSIS{C_RESET}\n")

    engine = SectorRotationEngine(BASE_DIR)
    print(f"{C_YELLOW}Computing sector rotation metrics for {latest_date}...{C_RESET}")

    sector_results = engine.compute_sector_rotation(as_of_date=latest_date)

    if isinstance(sector_results, dict) and 'sectors' in sector_results:
        sectors_list = sector_results['sectors']
    elif isinstance(sector_results, list):
        sectors_list = sector_results
    else:
        sectors_list = []

    print(f"\n{C_BOLD}{'=' * 75}{C_RESET}")
    print(f"{C_BOLD} SECTOR ROTATION TABLE — {latest_date}{C_RESET}")
    print(f"{C_BOLD}{'=' * 75}{C_RESET}")
    print(f"{'Sector':<14} {'1M Ret':>8} {'3M Ret':>8} {'Alpha1M':>8} {'Alpha3M':>8} {'Breadth':>8} {'RRG':>12}")
    print(f"{'─' * 75}")

    for sec in sectors_list:
        if isinstance(sec, dict):
            name = sec.get('sector', sec.get('name', 'N/A'))
            ret_1m = sec.get('return_1m', sec.get('ret_1m', 0))
            ret_3m = sec.get('return_3m', sec.get('ret_3m', 0))
            alpha_1m = sec.get('alpha_1m', 0)
            alpha_3m = sec.get('alpha_3m', 0)
            breadth = sec.get('breadth_pct', sec.get('pct_above_200ema', 0))
            rrg_quad = sec.get('rrg_quadrant', sec.get('quadrant', 'N/A'))
            color = C_GREEN if ret_1m > 0 else C_RED
            print(f"{name:<14} {color}{ret_1m:>7.1f}%{C_RESET} {ret_3m:>7.1f}% {alpha_1m:>7.1f}% {alpha_3m:>7.1f}% {breadth:>7.1f}% {rrg_quad:>12}")

    print(f"{C_BOLD}{'=' * 75}{C_RESET}")

    # Save standalone report
    report_path = BASE_DIR / "reports" / "sector_rotation_live.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(sector_results, f, indent=2, default=str)
    print(f"\n{C_GREEN}✓ Sector rotation report saved to {report_path}{C_RESET}")

    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Option [12]: Full Database Integrity Audit
# ═══════════════════════════════════════════════════════════════════════
def run_database_audit():
    clear_screen()
    latest_date = get_latest_date()
    print_banner(latest_date)
    print(f"\n{C_BOLD}{C_YELLOW}🔍 FULL DATABASE INTEGRITY AUDIT{C_RESET}\n")

    import time as _time
    t0 = _time.time()

    stats = get_universe_statistics()
    min_date, max_date = get_date_range()
    symbols = get_symbols()
    calendar = load_trading_calendar()
    sector_map = load_symbol_sector_map()

    print(f"{C_BOLD}{'=' * 65}{C_RESET}")
    print(f"{C_BOLD} DATABASE STATISTICS{C_RESET}")
    print(f"{C_BOLD}{'=' * 65}{C_RESET}")
    print(f"  DB Path:            {stats['db_path']}")
    print(f"  DB Size:            {stats['file_size_mb']:.2f} MB")
    print(f"  Total Rows:         {stats['total_rows']:,}")
    print(f"  Unique Symbols:     {stats['unique_symbols']:,}")
    print(f"  Date Range:         {min_date} → {max_date}")
    print(f"  Delisted Rows:      {stats['delisted_rows']:,}")
    print(f"  Trading Calendar:   {len(calendar):,} dates")
    print(f"  Sector Map:         {len(sector_map):,} symbols mapped")

    # Invariant checks
    print(f"\n{C_BOLD} INVARIANT VERIFICATION{C_RESET}")
    print(f"{'─' * 65}")

    conn = get_connection()
    cursor = conn.cursor()
    all_pass = True

    # 1. Zero null prices
    for col in ['open', 'high', 'low', 'close', 'volume']:
        cursor.execute(f"SELECT COUNT(*) FROM prices WHERE {col} IS NULL;")
        null_count = cursor.fetchone()[0]
        status = f"{C_GREEN}✓ PASS{C_RESET}" if null_count == 0 else f"{C_RED}✗ FAIL ({null_count}){C_RESET}"
        if null_count > 0:
            all_pass = False
        print(f"  Zero NULL {col:<8}: {status}")

    # 2. Positive prices
    for col in ['open', 'high', 'low', 'close']:
        cursor.execute(f"SELECT COUNT(*) FROM prices WHERE {col} <= 0;")
        neg_count = cursor.fetchone()[0]
        status = f"{C_GREEN}✓ PASS{C_RESET}" if neg_count == 0 else f"{C_RED}✗ FAIL ({neg_count}){C_RESET}"
        if neg_count > 0:
            all_pass = False
        print(f"  Positive {col:<8}:  {status}")

    # 3. Zero duplicate (symbol, date) keys
    cursor.execute("SELECT COUNT(*) FROM (SELECT date, symbol FROM prices GROUP BY date, symbol HAVING COUNT(*) > 1);")
    dup_count = cursor.fetchone()[0]
    status = f"{C_GREEN}✓ PASS{C_RESET}" if dup_count == 0 else f"{C_RED}✗ FAIL ({dup_count}){C_RESET}"
    if dup_count > 0:
        all_pass = False
    print(f"  Zero Duplicates:    {status}")

    # 4. Date range sanity
    cursor.execute("SELECT COUNT(DISTINCT date) FROM prices;")
    unique_dates = cursor.fetchone()[0]
    print(f"  Unique Trading Days:{C_GREEN} {unique_dates:,}{C_RESET}")

    # 5. Index presence
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prices';")
    indices = [r[0] for r in cursor.fetchall()]
    print(f"  Indices Present:    {', '.join(indices)}")

    elapsed = _time.time() - t0
    print(f"\n{C_BOLD}{'=' * 65}{C_RESET}")
    if all_pass:
        print(f"{C_BOLD}{C_GREEN}  🎉 ALL INVARIANTS VERIFIED — DATABASE IS 100% CERTIFIED{C_RESET}")
    else:
        print(f"{C_BOLD}{C_RED}  ❌ INVARIANT FAILURES DETECTED — REVIEW REQUIRED{C_RESET}")
    print(f"  Audit completed in {elapsed:.2f}s")
    print(f"{C_BOLD}{'=' * 65}{C_RESET}")

    input(f"\n{C_GRAY}Press Enter to return to menu...{C_RESET}")


# ═══════════════════════════════════════════════════════════════════════
# MAIN MENU (12 Options)
# ═══════════════════════════════════════════════════════════════════════
def main_menu():
    while True:
        clear_screen()
        latest_date = get_latest_date()
        print_banner(latest_date)

        print(f"\n{C_BOLD} ── SCANNER & ANALYSIS ──{C_RESET}")
        print(f"  {C_GREEN}[ 1]{C_RESET} 🚀  Run Weekly Momentum Scanner (Full Suite)")
        print(f"  {C_CYAN}[10]{C_RESET} 📈  Standalone Market Breadth Report")
        print(f"  {C_MAGENTA}[11]{C_RESET} 🔄  Standalone Sector Rotation & RRG Analysis")

        print(f"\n{C_BOLD} ── TELEGRAM ──{C_RESET}")
        print(f"  {C_BLUE}[ 2]{C_RESET} 📱  Preview Telegram Alert (Terminal Preview)")
        print(f"  {C_MAGENTA}[ 3]{C_RESET} ⚡  Dispatch Live Telegram Alert (Text + Charts)")

        print(f"\n{C_BOLD} ── PORTFOLIO & BACKTEST ──{C_RESET}")
        print(f"  {C_GREEN}[ 4]{C_RESET} 📊  Generate Visual Charts & Tearsheets")
        print(f"  {C_CYAN}[ 5]{C_RESET} 💼  Run Lightweight Custom Backtester")
        print(f"  {C_GREEN}[ 7]{C_RESET} 💰  Portfolio Rebalancing & Order Generation")

        print(f"\n{C_BOLD} ── DATA & MAINTENANCE ──{C_RESET}")
        print(f"  {C_MAGENTA}[ 8]{C_RESET} 📡  Auto-Fetch Market Data (NSE Bhavcopy Sync)")
        print(f"  {C_BLUE}[ 9]{C_RESET} 🏭  Sync NSE Sector Taxonomy")
        print(f"  {C_YELLOW}[12]{C_RESET} 🔍  Full Database Integrity Audit")
        print(f"  {C_YELLOW}[ 6]{C_RESET} 🛡️   Run TDD Diagnostics & Integrity Suite")

        print(f"\n  {C_RED}[ 0]{C_RESET} 🚪  Exit Workstation\n")

        try:
            choice = input(f"{C_BOLD}Select Option [0-12]: {C_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        handlers = {
            "1": run_scanner_flow,
            "2": run_telegram_preview,
            "3": run_telegram_dispatch,
            "4": run_visuals_generator,
            "5": run_custom_backtest_flow,
            "6": run_tdd_suite,
            "7": run_portfolio_orders,
            "8": run_auto_fetch,
            "9": run_sector_sync,
            "10": run_standalone_breadth,
            "11": run_standalone_sector_rrg,
            "12": run_database_audit,
        }

        if choice == "0":
            print(f"\n{C_CYAN}Goodbye! Project MIP Pydroid 3 session ended.{C_RESET}\n")
            break
        elif choice in handlers:
            handlers[choice]()
        else:
            print(f"{C_RED}Invalid option!{C_RESET}")
            time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project MIP Pydroid 3 Mobile Trading Desk")
    parser.add_argument("--option", type=int, choices=range(1, 13),
                        help="Run option directly without menu (1-12)")
    args = parser.parse_args()

    option_map = {
        1: lambda: run_scanner_flow(interactive=False),
        2: run_telegram_preview,
        3: run_telegram_dispatch,
        4: run_visuals_generator,
        5: run_custom_backtest_flow,
        6: run_tdd_suite,
        7: run_portfolio_orders,
        8: run_auto_fetch,
        9: run_sector_sync,
        10: run_standalone_breadth,
        11: run_standalone_sector_rrg,
        12: run_database_audit,
    }

    if args.option and args.option in option_map:
        option_map[args.option]()
    else:
        main_menu()
