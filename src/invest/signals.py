from __future__ import annotations

import numpy as np
import pandas as pd


def add_sma_signals(df: pd.DataFrame, fast_window: int, slow_window: int) -> pd.DataFrame:
    out = df.copy()
    if "close" not in out.columns:
        raise ValueError("Input data must include a 'close' column")

    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["close"]).reset_index(drop=True)

    if out.empty:
        raise ValueError("No valid numeric close prices found in input data")

    out["fast_sma"] = out["close"].rolling(fast_window).mean()
    out["slow_sma"] = out["close"].rolling(slow_window).mean()

    out["signal"] = np.where(out["fast_sma"] > out["slow_sma"], 1, 0)
    out["position_change"] = out["signal"].diff().fillna(0)
    return out
