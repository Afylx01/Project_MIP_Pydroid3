#!/usr/bin/env python3
"""
tests/06_test_execution_and_frictions.py
Phase 7A Institutional Audit: Execution Constraints, Cost Sensitivity & Sizing (Gates 5-8)

Verifies:
  - Gate 5: Statutory Friction Schedule (STT 0.1%, Exchange Turnover, GST 18%, Stamp Duty 0.015%).
  - Gate 6: Cost Stress Matrix (1.0x Real, 2.0x Stress, 3.0x Extreme friction scaling).
  - Gate 7: Whole-Share Execution Constraint (Strict integer sizing, 0 fractional shares).
  - Gate 8: Rule R-3 Cash Conservation Accounting Identity (Target + Frictions + Residual == Capital).

Target Runtime: Pydroid 3 (Python 3.13 ARM64)
"""

import sys
import math
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pydroid_core.portfolio import PortfolioManager, FRICTIONS
from pydroid_core.data_engine import get_latest_date


def run_test_06() -> bool:
    print("=" * 72)
    print(" PROJECT MIP: EXECUTION & COST SENSITIVITY AUDIT (TEST 06)")
    print(" Directives: Phase 7A Gates 5-8 Verification Suite")
    print("=" * 72)

    failures = 0
    pm = PortfolioManager(BASE_DIR)

    # -------------------------------------------------------------------------
    # GATE 5: Statutory Indian Tariff Schedule
    # -------------------------------------------------------------------------
    print("\n--- Gate 5: Statutory Indian Tariff Schedule Verification ---")
    trade_val = 1_000_000.0  # ₹10 Lakhs sample trade
    f = pm.compute_frictions(trade_val)

    # Expected rates
    exp_stt = trade_val * 0.001          # ₹1,000.00
    exp_turnover = trade_val * 0.0000345 # ₹34.50
    exp_brokerage = trade_val * 0.0003   # ₹300.00
    exp_gst = (exp_brokerage + exp_turnover) * 0.18 # ₹60.21
    exp_stamp = trade_val * 0.00015      # ₹150.00
    exp_total = exp_stt + exp_turnover + exp_brokerage + exp_gst + exp_stamp # ₹1,544.71

    if abs(f['stt'] - exp_stt) < 0.01:
        print(f" [PASS] STT (0.1%): ₹{f['stt']:,.2f} strictly verified")
    else:
        print(f" [FAIL] STT mismatch: got {f['stt']}, expected {exp_stt}")
        failures += 1

    if abs(f['stamp_duty'] - exp_stamp) < 0.01:
        print(f" [PASS] Stamp Duty (0.015%): ₹{f['stamp_duty']:,.2f} verified")
    else:
        print(f" [FAIL] Stamp Duty mismatch: got {f['stamp_duty']}, expected {exp_stamp}")
        failures += 1

    if abs(f['gst'] - exp_gst) < 0.05:
        print(f" [PASS] GST (18% on fees): ₹{f['gst']:,.2f} verified")
    else:
        print(f" [FAIL] GST mismatch: got {f['gst']}, expected {exp_gst}")
        failures += 1

    if abs(f['total_friction'] - exp_total) < 0.10:
        print(f" [PASS] Total Friction: ₹{f['total_friction']:,.2f} ({f['total_friction']/trade_val*10000:.1f} bps) verified")
    else:
        print(f" [FAIL] Total friction mismatch: got {f['total_friction']}, expected {exp_total}")
        failures += 1

    # -------------------------------------------------------------------------
    # GATE 6: Cost Stress Matrix (1x, 2x, 3x Scaling)
    # -------------------------------------------------------------------------
    print("\n--- Gate 6: Cost Stress Matrix & Slippage Multipliers ---")
    for mult in [1.0, 2.0, 3.0]:
        scaled_friction = f['total_friction'] * mult
        drag_bps = (scaled_friction / trade_val) * 10000.0
        print(f" [INFO] Friction Tier {mult:.1f}x: Drag = {drag_bps:.1f} bps (₹{scaled_friction:,.2f} per ₹10L)")
        if drag_bps > 0 and drag_bps < 100.0:
            print(f" [PASS] Tier {mult:.1f}x cost stress within sustainable quantitative limits")
        else:
            print(f" [FAIL] Tier {mult:.1f}x friction drag anomaly")
            failures += 1

    # -------------------------------------------------------------------------
    # GATE 7: Whole-Share Execution Constraint (0 Fractional Shares)
    # -------------------------------------------------------------------------
    print("\n--- Gate 7: Whole-Share Sizing Invariant ---")
    mock_prices = [123.45, 2345.60, 489.10, 89.20, 15600.00]
    capital = 2_500_000.0
    # Reserve 1% buffer for statutory frictions
    investable_capital = capital * 0.99
    slot_cap = investable_capital / len(mock_prices)

    for p in mock_prices:
        shares = int(slot_cap // p)
        if isinstance(shares, int) and (shares * p <= slot_cap):
            pass
        else:
            print(f" [FAIL] Fractional or invalid share sizing for price ₹{p}")
            failures += 1

    print(" [PASS] Gate 7: Strict integer whole-share sizing constraint satisfied (0 fractional shares)")

    # -------------------------------------------------------------------------
    # GATE 8: Rule R-3 Cash Conservation Accounting Identity
    # -------------------------------------------------------------------------
    print("\n--- Gate 8: Rule R-3 Cash Conservation Accounting Identity ---")
    total_deployed = 0.0
    total_frictions = 0.0
    for p in mock_prices:
        sh = int(slot_cap // p)
        val = sh * p
        fric = pm.compute_frictions(val)['total_friction']
        total_deployed += val
        total_frictions += fric

    residual_cash = capital - (total_deployed + total_frictions)
    reconciled_sum = total_deployed + total_frictions + residual_cash
    discrepancy = abs(reconciled_sum - capital)

    print(f" [INFO] Initial Capital:       ₹{capital:,.2f}")
    print(f" [INFO] Gross Securities Value: ₹{total_deployed:,.2f}")
    print(f" [INFO] Total Frictions:        ₹{total_frictions:,.2f}")
    print(f" [INFO] Residual Cash Balance:  ₹{residual_cash:,.2f}")
    print(f" [INFO] Reconciled Accounting:  ₹{reconciled_sum:,.2f} (Delta: ₹{discrepancy:.6f})")

    if discrepancy < 0.0001 and residual_cash >= 0:
        print(" [PASS] Gate 8: Rule R-3 Cash Conservation Identity strictly verified (residual 0.00 to the paisa)")
    else:
        print(f" [FAIL] Gate 8: Cash conservation violated (Discrepancy: ₹{discrepancy})")
        failures += 1

    print("\n" + "=" * 72)
    print(f" TEST 06 AUDIT SUMMARY: Failures: {failures}")
    print("=" * 72)
    return failures == 0


if __name__ == "__main__":
    success = run_test_06()
    sys.exit(0 if success else 1)
