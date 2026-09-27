# Project MIP: Standalone Pydroid 3 Quantitative Workstation
**Directive**: `DIR-PROD-PYDROID3-PORT-01` | **Standing Gate**: `HALT-16`  
**Target Environment**: Android Standalone Application — Pydroid 3 (Python 3.13 ARM64)  
**Location**: `/storage/emulated/0/Documents/Project_MIP_Pydroid3` (Shared Storage)

---

## 1. Executive Summary

This edition of Project MIP is engineered specifically for **native mobile execution inside Pydroid 3** on Samsung Galaxy S23 without requiring Termux, PRoot Linux, root permissions, or C++ build tools.

### Core Architectural Highlights:
1. **Zero-Compiler Invariant**: 100% pure Python + standard library `sqlite3`. Strictly eliminates `pyarrow` and `fastparquet` dependencies.
2. **Indexed SQLite Master Database (`universe.db`)**: 
   - 2,155,428+ historical equity bars across 1,039 NIFTY 500 symbols (2007–2026), Latest EOD: 2026-09-25.
   - Compound indices (`idx_prices_sym_date`, `idx_prices_date`, `idx_prices_sym`).
   - Ultra-fast indexed queries (<15ms per 250-bar series).
3. **Native Mobile Visualizations**:
   - `matplotlib`: 3-panel publication-quality PNG overview chart.
   - `plotly`: Standalone interactive mobile HTML tearsheets.
4. **Pure-Python Telegram Communication**:
   - Direct Telegram Bot API integration using `curl_cffi` (Chrome TLS impersonation) and `requests`.
   - Automatically dispatches alerts, photos, and HTML deliverables.

---

## 2. Verified Pydroid 3 Environment Inventory

The workstation runs natively on the following packages already installed in Pydroid 3:
- **Python**: 3.13 (`linux_aarch64`)
- **Data & Math**: `pandas 3.0.3`, `numpy 2.4.4`, `sqlite3` (built-in standard library)
- **Web & Anti-Bot**: `curl_cffi 0.16.2` (Chrome TLS/JA4 impersonation), `requests 2.34.2`, `beautifulsoup4 4.15.0`
- **Visuals & Tearsheets**: `matplotlib 3.10.9`, `plotly 7.0.0`, `openpyxl 3.1.5`, `pillow 12.2.0`
- **External Feeds**: `yfinance 1.7.0`

---

## 3. Directory Layout

```text
Project_MIP_Pydroid3/
├── data/
│   ├── universe.db                # 270.8 MB Indexed SQLite database (2.15M bars)
│   ├── benchmark_nifty500.csv     # Continuous NIFTY 500 benchmark proxy
│   ├── symbol_sector_map.json     # Official 12-sector taxonomy (1,039 scrips)
│   └── trading_calendar.txt       # Official NSE trading days calendar
├── pydroid_core/
│   ├── __init__.py
│   ├── data_engine.py             # Sub-millisecond SQLite query engine
│   ├── breadth.py                 # Market Breadth engine (% > 200 EMA, Highs/Lows)
│   ├── rrg.py                     # Julius de Kempenaer Relative Rotation Graph
│   ├── sector_rotation.py         # 12 Primary sectors relative strength & alpha
│   ├── scanner.py                 # Institutional 5-tier weekly momentum screener
│   ├── backtest.py                # Lightweight vector backtest simulator
│   ├── visuals.py                 # Matplotlib PNG & Plotly HTML tearsheet generator
│   └── telegram_sender.py         # Pure-Python Telegram Bot API dispatcher
├── tests/
│   ├── 01_test_environment.py     # TDD Step 1: Environment & package audit
│   ├── 02_test_data_engine.py     # TDD Step 2: SQLite database & query benchmarks
│   ├── 03_test_scanner.py         # TDD Step 3: End-to-end screener & Telegram preview
│   └── 04_test_visuals.py         # TDD Step 4: Visuals & backtester audit
├── reports/                       # Mobile-generated charts, CSVs, and tearsheets
├── .env                           # Live Telegram credentials
├── .env.example                   # Template configuration file
├── main_pydroid.py                # 1-Tap interactive mobile terminal workstation
└── PYDROID_SETUP.md               # Operator runbook & quick-start guide
```

---

## 4. Quick Start: Running in Pydroid 3 (Step-by-Step)

### Step 1: Open Pydroid 3
Launch the **Pydroid 3** app from your Samsung Galaxy S23 app drawer.

### Step 2: Open Test 01
1. Tap the **Folder icon (📁)** in the top app bar -> Tap **Open**.
2. Navigate to:  
   `Internal storage` → `Documents` → `Project_MIP_Pydroid3` → `tests` → `01_test_environment.py`.
3. Tap the yellow **Play (▶)** button in the bottom-right corner.
4. Verify the console output concludes with:
   ```text
   [PASS] PYDROID 3 ENVIRONMENT VERIFIED & READY FOR TEST 02
   ```

### Step 3: Run Remaining TDD Integrity Tests
Open and run each test file in order by tapping the yellow Play button:
- `tests/02_test_data_engine.py`: Validates dynamic monotonic bounds (>= 2,146,531 rows, detected: 2,155,428+), 0 nulls, sub-15ms lookups.
- `tests/03_test_scanner.py`: Runs full momentum scan, outputs Top 20 table.
- `tests/04_test_visuals.py`: Generates Matplotlib PNG, Plotly HTML, and runs backtest.

### Step 4: Launch Master Interactive Workstation (`main_pydroid.py`)
1. Open `Project_MIP_Pydroid3/main_pydroid.py` in Pydroid 3.
2. Tap the yellow **Play (▶)** button.
3. The interactive mobile dashboard will display:
   ```text
   ╔══════════════════════════════════════════════════════════════════════╗
   ║           PROJECT MIP — PYDROID 3 MOBILE TRADING DESK                ║
   ║    Standalone Zero-Compiler Edition • Python 3.13 ARM64 • v2.0.0     ║
   ╚══════════════════════════════════════════════════════════════════════╝
    Database: universe.db (Indexed SQLite) | Latest EOD: 2026-09-25
   ────────────────────────────────────────────────────────────────────────

    ── SCANNER & ANALYSIS ──
     [ 1] 🚀  Run Weekly Momentum Scanner (Full Suite)
     [10] 📈  Standalone Market Breadth Report
     [11] 🔄  Standalone Sector Rotation & RRG Analysis

    ── TELEGRAM ──
     [ 2] 📱  Preview Telegram Alert (Terminal Preview)
     [ 3] ⚡  Dispatch Live Telegram Alert (Text + Charts)

    ── PORTFOLIO & BACKTEST ──
     [ 4] 📊  Generate Visual Charts & Tearsheets
     [ 5] 💼  Run Lightweight Custom Backtester
     [ 7] 💰  Portfolio Rebalancing & Order Generation

    ── DATA & MAINTENANCE ──
     [ 8] 📡  Auto-Fetch Market Data (NSE Bhavcopy Sync)
     [ 9] 🏭  Sync NSE Sector Taxonomy
     [12] 🔍  Full Database Integrity Audit
     [ 6] 🛡️   Run TDD Diagnostics & Integrity Suite

     [ 0] 🚪  Exit Workstation
   ```

---

## 5. Configuration & Telegram Notifications

Credentials are read from `/storage/emulated/0/Documents/Project_MIP_Pydroid3/.env`:
```bash
TELEGRAM_BOT_TOKEN="your_bot_token"
TELEGRAM_CHAT_ID="687480641"
```

To test live Telegram alert dispatch:
- Select Option `[3]` in `main_pydroid.py`.
- It will transmit:
  1. Executive HTML Momentum Summary (Regime, Breadth, Sector Rotation, Top Allocations).
  2. High-resolution Matplotlib 3-panel overview chart (`reports/market_overview_chart.png`).
  3. Screener CSV data ticket (`reports/screener_output_live.csv`).

---

## 6. Zero-Compiler Invariant Certification

- **PRoot / Termux Dependency**: **0%** (Runs 100% inside standalone Pydroid 3 Android app).
- **PyArrow / Fastparquet Dependency**: **0%** (All data queries run via standard library `sqlite3`).
- **External Binaries**: **0%** (Replaced `/usr/local/bin/telegram-notify` with native HTTP REST calls).
- **Data Parity**: **100%** (2,155,428+ bars and 1,039 scrips verified with 0 nulls and 100% positive prices).
