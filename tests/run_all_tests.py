#!/usr/bin/env python3
"""
tests/run_all_tests.py
Master Institutional TDD & Invariant Test Orchestrator for Project MIP Pydroid 3.

Runs all 9 test suites sequentially:
  - Test 01: Python 3.13 ARM64 Mobile Wheel & Environment Audit
  - Test 02: SQLite Schema, Compound Indices & Invariant Verification
  - Test 03: Momentum Scanner, Factor Engine & Breadth Verification
  - Test 04: Matplotlib Charts, Plotly Tearsheet & Vector Backtester
  - Test 05: Point-in-Time Universe, Corporate Actions & Lookahead Proof (Gates 1-4)
  - Test 06: Statutory Friction Schedule, Whole-Share Sizing & Rule R-3 (Gates 5-8)
  - Test 07: IS/OOS Split, Rolling Walk-Forward & Macro Regimes (Gates 11, 12, 17)
  - Test 08: Core Risk Ratios (Sharpe/Calmar), Payoff & Monte Carlo Alpha Proof (Gates 18-25)
  - Test 09: Definedge ALL-ONE ETF Non-Repeating Allocation & Delivery Analytics (Gate 32)
"""

import sys
import os
import time
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TESTS_DIR = BASE_DIR / "tests"

TEST_SCRIPTS = [
    ("01_test_environment.py", "Environment & Mobile Package Wheel Audit"),
    ("02_test_data_engine.py", "Data Engine, SQLite Schema & Invariants"),
    ("03_test_scanner.py", "Momentum Screener, Factors & Market Breadth"),
    ("04_test_visuals.py", "Visual Dashboard, Tearsheet & Backtester"),
    ("05_test_data_integrity.py", "PIT Universe, Corporate Actions & Lookahead (Gates 1-4)"),
    ("06_test_execution_and_frictions.py", "Statutory Frictions, Sizing & Rule R-3 (Gates 5-8)"),
    ("07_test_walk_forward_and_regimes.py", "IS/OOS Split, Walk-Forward & Regimes (Gates 11,12,17)"),
    ("08_test_statistical_significance.py", "Risk Ratios, Expectancy & Monte Carlo (Gates 18-25)"),
    ("09_test_etf_and_delivery.py", "ALL-ONE ETF Allocation & Delivery Analytics (Gate 32)"),
]

# ANSI Colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_WHITE = "\033[97m"


def main():
    print(f"\n{C_BOLD}{C_CYAN}╔══════════════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║     PROJECT MIP — MASTER INSTITUTIONAL TEST & AUDIT ORCHESTRATOR     ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║             Complete 9-Test Suite • Zero-Compiler Architecture       ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}╚══════════════════════════════════════════════════════════════════════╝{C_RESET}\n")

    results = []
    t_start = time.time()

    for fname, desc in TEST_SCRIPTS:
        fpath = TESTS_DIR / fname
        if not fpath.exists():
            print(f"{C_RED}❌ Test script not found: {fname}{C_RESET}")
            results.append((fname, desc, "MISSING", 0.0))
            continue

        print(f"\n{C_BOLD}{C_YELLOW}▶ EXECUTING: {fname} — {desc}{C_RESET}")
        t0 = time.time()
        ret = subprocess.run([sys.executable, str(fpath)], cwd=str(BASE_DIR))
        dur = time.time() - t0
        status = "PASS" if ret.returncode == 0 else "FAIL"
        results.append((fname, desc, status, dur))

    total_time = time.time() - t_start

    # Print Summary Table
    print(f"\n\n{C_BOLD}{'=' * 75}{C_RESET}")
    print(f"{C_BOLD}{C_WHITE}MASTER AUDIT SUITE EXECUTION SUMMARY{C_RESET}")
    print(f"{C_BOLD}{'=' * 75}{C_RESET}")
    print(f"{'#':<3} {'Test Suite':<35} {'Status':<10} {'Duration':<10}")
    print(f"{'─' * 75}")

    all_passed = True
    for idx, (fname, desc, st, dur) in enumerate(results, 1):
        color = C_GREEN if st == "PASS" else C_RED
        print(f"{idx:<3} {fname:<35} {color}{st:<10}{C_RESET} {dur:>6.2f}s")
        if st != "PASS":
            all_passed = False

    print(f"{'─' * 75}")
    print(f"Total Execution Time: {total_time:.2f}s")

    if all_passed:
        print(f"\n{C_BOLD}{C_GREEN}🏆 ALL 9 INSTITUTIONAL TEST SUITES PASSED FLAWLESSLY!{C_RESET}")
        print(f"{C_GREEN}Zero-Compiler Invariant Confirmed • System Ready for Production Trading.{C_RESET}\n")
        return 0
    else:
        print(f"\n{C_BOLD}{C_RED}❌ AUDIT SUITE FAILED — INVESTIGATE DEFECTS BEFORE DEPLOYMENT.{C_RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
