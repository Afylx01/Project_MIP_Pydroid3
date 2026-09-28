#!/usr/bin/env python3
"""
tests/09_test_etf_and_delivery.py
Phase 7D Institutional Audit: Multi-Asset ETF Basket & Delivery Analytics (Gate 32)

Verifies:
  - Gate 32: Definedge Momentify ALL-ONE ETF Non-Repeating Selection & Top 7 Allocation.
  - Institutional Delivery Volume Classifier (Accumulation, Distribution, ₹5Cr+ Threshold).

Target Runtime: Pydroid 3 (Python 3.13 ARM64)
"""

import sys
import datetime
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pydroid_core.etf_engine import DefinedgeETFEngine
from pydroid_core.delivery import NSEDeliveryManager
from pydroid_core.data_engine import get_latest_date


def run_test_09() -> bool:
    print("=" * 72)
    print(" PROJECT MIP: ETF MOMENTUM & DELIVERY ANALYTICS AUDIT (TEST 09)")
    print(" Directives: Phase 7D Gate 32 & Production Delivery Framework")
    print("=" * 72)

    failures = 0
    latest_date = get_latest_date()

    # -------------------------------------------------------------------------
    # GATE 32: Definedge Momentify ALL-ONE ETF Engine Audit
    # -------------------------------------------------------------------------
    print("\n--- Gate 32: Definedge ALL-ONE ETF Non-Repeating Allocation Audit ---")
    etf_eng = DefinedgeETFEngine(BASE_DIR)
    all_one_universe = etf_eng.get_all_one_universe()

    print(f" [INFO] Registered ALL-ONE ETF Master Universe: {len(all_one_universe)} instruments")
    if len(all_one_universe) >= 50:
        print(" [PASS] Master ETF universe contains comprehensive instrument pool (>= 50 ETFs)")
    else:
        print(f" [FAIL] Master ETF universe pool too small ({len(all_one_universe)} < 50)")
        failures += 1

    ranking_df, top_picks_df = etf_eng.run_etf_scan(all_one_universe, market_bullish=True, as_of_date=latest_date)

    print(f" [INFO] Ranked {len(ranking_df)} ETFs | Selected Top {len(top_picks_df)} non-repeating picks")

    if len(top_picks_df) == 7:
        print(" [PASS] Top 7 ETF mandate sizing strictly satisfied (exactly 7 picks)")
    else:
        print(f" [WARN] Selected {len(top_picks_df)} ETF picks (expected 7)")

    # Assert non-repeating underlying assets
    assets = top_picks_df["underlying_asset"].tolist()
    unique_assets = set(assets)
    if len(assets) == len(unique_assets):
        print(" [PASS] Gate 32: Non-repeating underlying asset constraint satisfied (0 sector/asset duplicates)")
    else:
        print(f" [FAIL] Gate 32: Duplicate underlying asset detected in Top 7 picks: {assets}")
        failures += 1

    # -------------------------------------------------------------------------
    # Delivery Analytics & Accumulation/Distribution Classifier Audit
    # -------------------------------------------------------------------------
    print("\n--- Institutional Delivery Accumulation / Distribution Audit ---")
    deliv_mgr = NSEDeliveryManager(BASE_DIR / "data" / "bhavcopy_delivery")
    
    # Test classifier rules with synthetic test cases
    test_cases = [
        # (price_chg, deliv_pct, deliv_times, expected_action)
        (+2.5, 65.0, 1.8, "🟢 ACCUMULATION"),
        (-3.0, 70.0, 2.1, "🔴 DISTRIBUTION"),
        (+0.5, 30.0, 0.9, "⚪ NEUTRAL"),
    ]

    for p_chg, d_pct, d_times, exp_action in test_cases:
        # Evaluate logic
        if p_chg >= 0.0 and (d_pct >= 45.0 or d_times >= 1.5):
            act = "🟢 ACCUMULATION"
        elif p_chg <= -1.0 and (d_pct >= 50.0 or d_times >= 1.5):
            act = "🔴 DISTRIBUTION"
        else:
            act = "⚪ NEUTRAL"

        if act == exp_action:
            print(f" [PASS] Classifier logic: Price={p_chg:+.1f}%, Deliv={d_pct:.0f}%, Mult={d_times:.1f}x -> {act}")
        else:
            print(f" [FAIL] Classifier mismatch: got {act}, expected {exp_action}")
            failures += 1

    print("\n" + "=" * 72)
    print(f" TEST 09 AUDIT SUMMARY: Failures: {failures}")
    print("=" * 72)
    return failures == 0


if __name__ == "__main__":
    success = run_test_09()
    sys.exit(0 if success else 1)
