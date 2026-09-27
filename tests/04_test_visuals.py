#!/usr/bin/env python3
"""
TDD Test 04: Pydroid 3 Visuals, Tearsheets & Backtester Verification
Directive: DIR-PROD-PYDROID3-PORT-01 (Standing Gate HALT-16)

Tests:
1. Static high-resolution PNG chart generation via Matplotlib.
2. Interactive HTML tearsheet generation via Plotly.
3. Vector backtest simulation engine execution.
4. Output verification in reports/ directory.
"""

import sys
import json
from pathlib import Path
import pandas as pd

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pydroid_core.visuals import generate_matplotlib_dashboard, generate_plotly_tearsheet
from pydroid_core.backtest import LightweightBacktester

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
    print(f"{BOLD}{CYAN} PROJECT MIP: PYDROID 3 VISUALS & BACKTEST AUDIT (TEST 04){RESET}")
    print(f"{BOLD}{'=' * 72}{RESET}\n")

    failures = 0
    reports_dir = BASE_DIR / "reports"

    # 1. Load Pre-Computed Data from Test 03
    breadth_file = reports_dir / "market_breadth_live.json"
    sector_file = reports_dir / "sector_rotation_live.json"
    screener_file = reports_dir / "screener_output_live.csv"

    if not (breadth_file.exists() and sector_file.exists() and screener_file.exists()):
        log_fail("Prerequisite report files missing from reports/. Please run Test 03 first.")
        return 1

    with open(breadth_file, "r", encoding="utf-8") as f:
        breadth_data = json.load(f)
    with open(sector_file, "r", encoding="utf-8") as f:
        sector_data = json.load(f)
    top_df = pd.read_csv(screener_file)

    log_pass(f"Ingested live report data: {len(top_df)} scrips, {len(sector_data.get('sectors', []))} sectors")

    # 2. Test Matplotlib High-Resolution Graphic
    print(f"\n{BOLD}--- Matplotlib Mobile Chart Export Test ---{RESET}")
    chart_png = reports_dir / "market_overview_chart.png"
    try:
        generate_matplotlib_dashboard(breadth_data, sector_data, top_df, output_png=chart_png)
        if chart_png.exists() and chart_png.stat().st_size > 20000:
            log_pass(f"Matplotlib dashboard generated successfully ({chart_png.stat().st_size:,} bytes)")
        else:
            log_fail(f"Matplotlib dashboard missing or too small: {chart_png}")
            failures += 1
    except Exception as e:
        log_fail(f"Matplotlib rendering failed: {e}")
        failures += 1

    # 3. Test Plotly Interactive HTML Tearsheet
    print(f"\n{BOLD}--- Plotly Mobile Tearsheet Export Test ---{RESET}")
    tearsheet_html = reports_dir / "mip_mobile_tearsheet.html"
    try:
        generate_plotly_tearsheet(breadth_data, sector_data, top_df, output_html=tearsheet_html)
        if tearsheet_html.exists() and tearsheet_html.stat().st_size > 5000:
            log_pass(f"Interactive HTML tearsheet generated successfully ({tearsheet_html.stat().st_size:,} bytes)")
        else:
            log_fail(f"Interactive HTML tearsheet missing or too small: {tearsheet_html}")
            failures += 1
    except Exception as e:
        log_fail(f"Plotly tearsheet generation failed: {e}")
        failures += 1

    # 4. Test Lightweight Vector Backtester
    print(f"\n{BOLD}--- Lightweight Vector Backtester Test ---{RESET}")
    try:
        backtester = LightweightBacktester()
        log_info("Executing 6-year backtest simulation (2020-01-01 to 2026-08-31)...")
        bt_results = backtester.run(
            start_date="2020-01-01",
            end_date="2026-08-31",
            top_n=20,
            initial_capital=1_000_000.0
        )
        log_info(f"Backtest Output: CAGR {bt_results['cagr_pct']}% vs BM {bt_results['benchmark_cagr_pct']}% | Sharpe {bt_results['sharpe_ratio']} | MaxDD {bt_results['max_drawdown_pct']}%")

        if bt_results["cagr_pct"] > bt_results["benchmark_cagr_pct"]:
            log_pass(f"Strategy excess return confirmed (+{bt_results['excess_cagr_pct']}% excess CAGR)")
        else:
            log_fail(f"Strategy underperformed benchmark: {bt_results['cagr_pct']}% <= {bt_results['benchmark_cagr_pct']}%")
            failures += 1

        bt_file = reports_dir / "backtest_results.json"
        if bt_file.exists() and bt_file.stat().st_size > 0:
            log_pass(f"Backtest results exported to {bt_file}")
        else:
            log_fail(f"Backtest JSON missing: {bt_file}")
            failures += 1

    except Exception as e:
        log_fail(f"Backtester execution failed: {e}")
        failures += 1

    # Summary
    print(f"\n{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD} TEST 04 AUDIT SUMMARY:{RESET}")
    print(f"  Failures: {failures}")
    print(f"{BOLD}{'=' * 72}{RESET}\n")

    if failures == 0:
        print(f"{BOLD}{GREEN} [PASS] PYDROID 3 VISUALS & TEARSHEET PIPELINE VERIFIED{RESET}\n")
        return 0
    else:
        print(f"{BOLD}{RED} [FAIL] TEST 04 FAILED WITH {failures} ERRORS.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
