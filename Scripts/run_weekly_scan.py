"""
scripts/run_weekly_scan.py
===========================
Runs every Saturday via GitHub Actions.
Scans all stocks and saves results to Supabase.
No Streamlit dependency — pure Python.
"""

import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client

# ── Config ────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SMA_WEEKS    = 50
YEARS        = 4
BENCHMARK    = "SPY"

# ── Universe ──────────────────────────────────────────────────
from utils_standalone import SECTORS, SECTOR_STOCKS, evaluate, fetch_weekly_raw

def main():
    print(f"[{datetime.now()}] Starting weekly scan...")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set as environment variables")
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Fetch SPY as benchmark
    print("Fetching SPY benchmark...")
    spx_df = fetch_weekly_raw(BENCHMARK)
    if spx_df.empty:
        print("ERROR: Could not fetch SPY data")
        sys.exit(1)
    spx_close = spx_df["Close"]

    # 2. Scan all sector ETFs
    print("Scanning sector ETFs...")
    sector_results = []
    for tk, name in SECTORS.items():
        df = fetch_weekly_raw(tk)
        if df.empty: continue
        ev = evaluate(df, spx_close)
        ev["ticker"] = tk; ev["name"] = name
        sector_results.append(ev)
        print(f"  {tk}: {ev['stage']} score={ev['score']}")
        time.sleep(0.5)

    # 3. Scan all sector stocks
    print("Scanning sector stocks...")
    stock_results = {}
    for sec_tk, stocks in SECTOR_STOCKS.items():
        results = []
        for tk in stocks:
            df = fetch_weekly_raw(tk)
            if df.empty: continue
            ev = evaluate(df, spx_close)
            ev["ticker"] = tk
            results.append(ev)
            time.sleep(0.3)
        stock_results[sec_tk] = results
        print(f"  {sec_tk}: {len(results)} stocks scanned")

    # 4. Save to Supabase
    scan_date = datetime.now().strftime("%Y-%m-%d")
    print(f"Saving results to Supabase (scan date: {scan_date})...")

    # Save sector results
    sb.table("scan_cache").upsert({
        "id": f"sectors_{scan_date}",
        "scan_type": "sectors",
        "data": json.dumps(sector_results, default=str),
        "scan_date": scan_date,
    }).execute()

    # Save stock results per sector
    for sec_tk, results in stock_results.items():
        sb.table("scan_cache").upsert({
            "id": f"stocks_{sec_tk}_{scan_date}",
            "scan_type": f"stocks_{sec_tk}",
            "data": json.dumps(results, default=str),
            "scan_date": scan_date,
        }).execute()

    # Save combined signals (PREMIUM + EARLY)
    all_signals = []
    for sec_tk, results in stock_results.items():
        for r in results:
            if r.get("premium") or r.get("early_sig") or r.get("score", 0) >= 4:
                r["sector"] = SECTORS.get(sec_tk, sec_tk)
                all_signals.append(r)

    all_signals.sort(key=lambda x: (
        -int(x.get("premium", False)),
        -int(x.get("early_sig", False)),
        -x.get("score", 0),
        -(x.get("rs") or -99)
    ))

    sb.table("scan_cache").upsert({
        "id": f"signals_{scan_date}",
        "scan_type": "signals",
        "data": json.dumps(all_signals, default=str),
        "scan_date": scan_date,
    }).execute()

    # Also save as "latest" for easy retrieval
    sb.table("scan_cache").upsert({
        "id": "sectors_latest",
        "scan_type": "sectors_latest",
        "data": json.dumps(sector_results, default=str),
        "scan_date": scan_date,
    }).execute()

    sb.table("scan_cache").upsert({
        "id": "signals_latest",
        "scan_type": "signals_latest",
        "data": json.dumps(all_signals, default=str),
        "scan_date": scan_date,
    }).execute()

    print(f"[{datetime.now()}] Scan complete!")
    print(f"  Sectors: {len(sector_results)}")
    print(f"  Total stocks scanned: {sum(len(v) for v in stock_results.values())}")
    print(f"  Signals: {len(all_signals)}")


if __name__ == "__main__":
    main()
