from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf


def download_symbol_history(symbol: str, start: str, end: str | None) -> pd.DataFrame:
    df = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for symbol={symbol}")

    # yfinance may return MultiIndex columns (e.g., price field + ticker).
    # Keep only the price-field level so saved CSVs have a single header row.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()
    df.columns = [str(col).lower() for col in df.columns]
    df["symbol"] = symbol
    return df


def save_history(df: pd.DataFrame, symbol: str, out_dir: str = "data/raw") -> Path:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(out_dir) / f"{symbol}.csv"
    df.to_csv(out_path, index=False)
    return out_path
