from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from invest.config import load_settings, read_watchlist
from invest.signals import add_sma_signals


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate SMA crossover signals from raw data")
    p.add_argument("--fast", type=int, help="Fast SMA window")
    p.add_argument("--slow", type=int, help="Slow SMA window")
    p.add_argument("--symbols", help="Comma-separated symbols; overrides watchlist")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()

    fast = args.fast or settings.fast_sma
    slow = args.slow or settings.slow_sma

    if fast >= slow:
        raise ValueError("FAST_SMA must be lower than SLOW_SMA")

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = read_watchlist() or settings.default_symbols

    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)

    for symbol in symbols:
        in_path = Path("data/raw") / f"{symbol}.csv"
        if not in_path.exists():
            print(f"skip {symbol}: missing {in_path}")
            continue

        df = pd.read_csv(in_path)
        signaled = add_sma_signals(df, fast_window=fast, slow_window=slow)

        out_path = out_dir / f"{symbol}_signals.csv"
        signaled.to_csv(out_path, index=False)
        print(f"saved {symbol}: {out_path}")


if __name__ == "__main__":
    main()
