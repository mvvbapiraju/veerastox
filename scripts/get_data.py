#!/usr/bin/env python3
from __future__ import annotations

import argparse

from invest.config import load_settings, read_watchlist
from invest.data_provider import download_symbol_history, save_history


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download OHLCV data for watchlist symbols")
    p.add_argument("--start", help="Start date YYYY-MM-DD")
    p.add_argument("--end", help="End date YYYY-MM-DD")
    p.add_argument("--symbols", help="Comma-separated symbols; overrides watchlist")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = read_watchlist() or settings.default_symbols

    start = args.start or settings.start_date
    end = args.end or settings.end_date

    for symbol in symbols:
        df = download_symbol_history(symbol, start=start, end=end)
        out_path = save_history(df, symbol)
        print(f"saved {symbol}: {out_path}")


if __name__ == "__main__":
    main()
