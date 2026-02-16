#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from invest.backtest import run_long_only_backtest
from invest.config import load_settings, read_watchlist


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run simple long-only backtest on signal files")
    p.add_argument("--symbols", help="Comma-separated symbols; overrides watchlist")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = read_watchlist() or settings.default_symbols

    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, float | str]] = []

    for symbol in symbols:
        in_path = Path("data/processed") / f"{symbol}_signals.csv"
        if not in_path.exists():
            print(f"skip {symbol}: missing {in_path}")
            continue

        df = pd.read_csv(in_path)
        bt, summary = run_long_only_backtest(df)

        curve_path = report_dir / f"{symbol}_equity_curve.csv"
        bt.to_csv(curve_path, index=False)

        row = {"symbol": symbol, **summary}
        rows.append(row)
        print(f"backtested {symbol}: {curve_path}")

    if rows:
        summary_df = pd.DataFrame(rows)
        summary_path = report_dir / "summary.csv"
        summary_df.to_csv(summary_path, index=False)
        print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
