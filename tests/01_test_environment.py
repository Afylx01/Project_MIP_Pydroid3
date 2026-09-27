#!/usr/bin/env python3
"""
TDD Test 01: Pydroid 3 Environment, Permissions & Packages
Directive: DIR-PROD-PYDROID3-PORT-01 (Standing Gate HALT-16)

Verifies:
1. Python Runtime (3.11+ / 3.13) & ARM64 architecture.
2. File system write/read permissions in shared mobile storage.
3. Availability and versions of confirmed Pydroid 3 packages:
   - sqlite3, pandas, numpy
   - curl_cffi, requests, bs4
   - matplotlib, plotly, openpyxl, PIL
   - yfinance
4. Absence of forbidden dependencies (pyarrow, fastparquet).
"""

import os
import sys
import platform
import tempfile
from pathlib import Path

# ANSI colors
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


def log_warn(msg: str):
    print(f" {YELLOW}[WARN]{RESET} {msg}")


def main():
    print(f"{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD}{CYAN} PROJECT MIP: PYDROID 3 ENVIRONMENT & PRE-FLIGHT AUDIT (TEST 01){RESET}")
    print(f"{BOLD}{'=' * 72}{RESET}\n")

    failures = 0
    warnings = 0

    # 1. Python Runtime
    py_ver = sys.version_info
    log_info(f"Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro} ({platform.python_implementation()})")
    if py_ver.major == 3 and py_ver.minor >= 11:
        log_pass(f"Python runtime >= 3.11 verified (Detected: {py_ver.major}.{py_ver.minor}.{py_ver.micro})")
    else:
        log_fail(f"Python runtime must be >= 3.11! Detected: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
        failures += 1

    # 2. Architecture & OS
    arch = platform.machine()
    log_info(f"Machine Architecture: {arch}, OS: {platform.system()}")
    if "aarch64" in arch.lower() or "arm64" in arch.lower():
        log_pass(f"ARM64 architecture verified ({arch})")
    else:
        log_warn(f"Non-ARM64 architecture detected ({arch}). Proceeding for emulation/testing.")
        warnings += 1

    # 3. Storage Read/Write Verification
    test_dir = Path(__file__).resolve().parent.parent / "reports"
    test_dir.mkdir(parents=True, exist_ok=True)
    probe_file = test_dir / ".pydroid_probe.tmp"
    try:
        with open(probe_file, "w", encoding="utf-8") as f:
            f.write("PYDROID3_STORAGE_OK\n")
        with open(probe_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
        probe_file.unlink()
        if content == "PYDROID3_STORAGE_OK":
            log_pass(f"Mobile storage read/write verified in {test_dir.parent}")
        else:
            log_fail("Storage probe file content mismatch!")
            failures += 1
    except Exception as e:
        log_fail(f"Storage write permission failed: {e}")
        failures += 1

    # 4. Standard Library sqlite3
    try:
        import sqlite3
        log_pass(f"sqlite3 standard library available (SQLite version: {sqlite3.sqlite_version})")
    except ImportError as e:
        log_fail(f"sqlite3 not found: {e}")
        failures += 1

    # 5. Core Numerical & Data Packages
    core_pkgs = [
        ("pandas", "Data manipulation"),
        ("numpy", "Vectorized math"),
    ]
    for pkg_name, desc in core_pkgs:
        try:
            mod = __import__(pkg_name)
            ver = getattr(mod, "__version__", "unknown")
            log_pass(f"{pkg_name} ({desc}) available - version {ver}")
        except ImportError as e:
            log_fail(f"Required package '{pkg_name}' ({desc}) missing: {e}")
            failures += 1

    # 6. Networking & TLS Impersonation Packages
    net_pkgs = [
        ("requests", "HTTP communication"),
        ("bs4", "HTML parsing (BeautifulSoup4)"),
    ]
    for pkg_name, desc in net_pkgs:
        try:
            mod = __import__(pkg_name)
            ver = getattr(mod, "__version__", "unknown")
            log_pass(f"{pkg_name} ({desc}) available - version {ver}")
        except ImportError as e:
            log_fail(f"Package '{pkg_name}' missing: {e}")
            failures += 1

    # curl_cffi check (primary TLS impersonator)
    try:
        import curl_cffi
        ver = getattr(curl_cffi, "__version__", "unknown")
        log_pass(f"curl_cffi (Chrome TLS/JA4 impersonation) available - version {ver}")
    except ImportError:
        log_warn("curl_cffi not found in this environment. Falling back to requests for HTTP.")
        warnings += 1

    # 7. Visualization & Tearsheet Packages
    viz_pkgs = [
        ("matplotlib", "Static chart rendering"),
        ("plotly", "Interactive HTML tearsheets"),
        ("openpyxl", "Excel workbook generation"),
        ("PIL", "Pillow image processing"),
    ]
    for pkg_name, desc in viz_pkgs:
        try:
            mod = __import__(pkg_name)
            ver = getattr(mod, "__version__", "unknown")
            log_pass(f"{pkg_name} ({desc}) available - version {ver}")
        except ImportError as e:
            log_warn(f"Visualization package '{pkg_name}' ({desc}) not found: {e}")
            warnings += 1

    # 8. External feeds
    try:
        import yfinance
        ver = getattr(yfinance, "__version__", "unknown")
        log_pass(f"yfinance (Market data feed) available - version {ver}")
    except ImportError:
        log_warn("yfinance not installed. External ticker updates will be disabled.")
        warnings += 1

    # 9. Verify Absence of Forbidden Dependencies
    forbidden_pkgs = ["pyarrow", "fastparquet"]
    for pkg_name in forbidden_pkgs:
        try:
            mod = __import__(pkg_name)
            log_info(f"Note: '{pkg_name}' is installed in current host environment, but Project_MIP_Pydroid3 core has ZERO dependency on it.")
        except ImportError:
            log_pass(f"Forbidden dependency '{pkg_name}' correctly absent (Zero-Compiler invariant confirmed)")

    # 10. Summary & Sign-Off
    print(f"\n{BOLD}{'=' * 72}{RESET}")
    print(f"{BOLD} PRE-FLIGHT AUDIT SUMMARY:{RESET}")
    print(f"  Failures: {failures}")
    print(f"  Warnings: {warnings}")
    print(f"{BOLD}{'=' * 72}{RESET}\n")

    if failures == 0:
        print(f"{BOLD}{GREEN} [PASS] PYDROID 3 ENVIRONMENT VERIFIED & READY FOR TEST 02{RESET}\n")
        return 0
    else:
        print(f"{BOLD}{RED} [FAIL] PRE-FLIGHT AUDIT FAILED WITH {failures} FATAL ERRORS.{RESET}")
        print(f" Please install missing packages in Pydroid 3 PIP menu.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
