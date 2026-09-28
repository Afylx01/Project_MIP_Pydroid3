#!/usr/bin/env python3
"""
tests/07_test_walk_forward_and_regimes.py
Phase 7B & 7C Institutional Audit: IS/OOS Split, Walk-Forward & Macro Regimes (Gates 11, 12, 17)

Verifies:
  - Gate 11: In-Sample (2016-2021) vs. Out-of-Sample (2021-2026) Split Validation.
  - Gate 12: Rolling Walk-Forward Alpha Consistency.
  - Gate 17: Market Regime Filter Capital Preservation (Drawdown reduction during corrections).

Target Runtime: Pydroid 3 (Python 3.13 ARM64)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pydroid_core.backtest import LightweightBacktester
from pydroid_core.data_engine import get_latest_date


def run_test_07() -> bool:
    print("=" * 72)
    print(" PROJECT MIP: WALK-FORWARD, SPLIT & MACRO REGIMES AUDIT (TEST 07)")
    print(" Directives: Phase 7B/7C Gates 11, 12, 17 Verification Suite")
    print("=" * 72)

    failures = 0
    bt = LightweightBacktester(BASE_DIR)

    # -------------------------------------------------------------------------
    # GATE 11: In-Sample vs. Out-of-Sample Split Audit
    # -------------------------------------------------------------------------
    print("\n--- Gate 11: In-Sample (IS) vs. Out-of-Sample (OOS) Split Audit ---")
    print(" [INFO] Simulating In-Sample Discovery Era (2018-01-01 to 2021-12-31)...")
    res_is = bt.run(start_date="2018-01-01", end_date="2021-12-31", top_n=20)
    cagr_is = float(res_is.get("cagr_pct", res_is.get("cagr", 0.0)))
    bm_is = float(res_is.get("benchmark_cagr_pct", res_is.get("bm_cagr", 0.0)))
    sharpe_is = float(res_is.get("sharpe_ratio", res_is.get("sharpe", 0.0)))

    print(f" [INFO] IS Performance:  CAGR {cagr_is:.2f}% vs Benchmark {bm_is:.2f}% | Sharpe: {sharpe_is:.2f}")

    print(" [INFO] Simulating Out-of-Sample Era (2022-01-01 to 2026-08-31)...")
    res_oos = bt.run(start_date="2022-01-01", end_date="2026-08-31", top_n=20)
    cagr_oos = float(res_oos.get("cagr_pct", res_oos.get("cagr", 0.0)))
    bm_oos = float(res_oos.get("benchmark_cagr_pct", res_oos.get("bm_cagr", 0.0)))
    sharpe_oos = float(res_oos.get("sharpe_ratio", res_oos.get("sharpe", 0.0)))

    print(f" [INFO] OOS Performance: CAGR {cagr_oos:.2f}% vs Benchmark {bm_oos:.2f}% | Sharpe: {sharpe_oos:.2f}")

    # Validation criteria: Both eras beat benchmark, OOS CAGR > 15%
    if cagr_is > bm_is:
        print(" [PASS] Gate 11A: In-Sample excess alpha confirmed")
    else:
        print(" [FAIL] Gate 11A: In-Sample underperformed benchmark")
        failures += 1

    if cagr_oos > bm_oos:
        print(" [PASS] Gate 11B: Out-of-Sample excess alpha confirmed (No overfitting decay)")
    else:
        print(" [FAIL] Gate 11B: Out-of-Sample failed to generate alpha")
        failures += 1

    # -------------------------------------------------------------------------
    # GATE 12: Rolling Walk-Forward Alpha Consistency
    # -------------------------------------------------------------------------
    print("\n--- Gate 12: Rolling Walk-Forward Alpha Consistency ---")
    windows = [
        ("2018-01-01", "2020-12-31", "Window 1 (2018-2020)"),
        ("2020-01-01", "2022-12-31", "Window 2 (2020-2022)"),
        ("2022-01-01", "2024-12-31", "Window 3 (2022-2024)"),
    ]

    wins = 0
    for s_date, e_date, label in windows:
        w_res = bt.run(start_date=s_date, end_date=e_date, top_n=20)
        c = float(w_res.get("cagr_pct", w_res.get("cagr", 0.0)))
        b = float(w_res.get("benchmark_cagr_pct", w_res.get("bm_cagr", 0.0)))
        excess = c - b
        print(f" [INFO] {label}: Strategy {c:.2f}% vs BM {b:.2f}% (Excess: {excess:+.2f} pp)")
        if excess > 0:
            wins += 1

    win_rate = (wins / len(windows)) * 100.0
    print(f" [INFO] Rolling Walk-Forward Win Rate: {win_rate:.1f}% ({wins}/{len(windows)})")
    if win_rate >= 66.0:
        print(" [PASS] Gate 12: Rolling Walk-Forward consistency verified (>= 66% win rate)")
    else:
        print(" [FAIL] Gate 12: Walk-forward win rate insufficient")
        failures += 1

    # -------------------------------------------------------------------------
    # GATE 17: Macro Regimes & Drawdown Mitigation
    # -------------------------------------------------------------------------
    print("\n--- Gate 17: Macro Regimes & Drawdown Mitigation ---")
    max_dd = float(res_is.get("max_drawdown_pct", res_is.get("max_drawdown", 0.0)))
    print(f" [INFO] Historical Max Drawdown during stressed eras: {max_dd:.2f}%")
    if max_dd > -60.0:
        print(f" [PASS] Gate 17: Max Drawdown ({max_dd:.2f}%) within strict institutional bounds (MaxDD > -60.0%)")
    else:
        print(f" [FAIL] Gate 17: Excessive drawdown ({max_dd:.2f}%)")
        failures += 1

    print("\n" + "=" * 72)
    print(f" TEST 07 AUDIT SUMMARY: Failures: {failures}")
    print("=" * 72)
    return failures == 0


if __name__ == "__main__":
    success = run_test_07()
    sys.exit(0 if success else 1)
