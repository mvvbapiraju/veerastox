from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Settings:
    default_symbols: list[str]
    start_date: str
    end_date: str | None
    fast_sma: int
    slow_sma: int


def _parse_symbols(raw: str) -> list[str]:
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def load_settings() -> Settings:
    load_dotenv()

    default_symbols = _parse_symbols(os.getenv("DEFAULT_SYMBOLS", "AAPL,MSFT"))
    start_date = os.getenv("START_DATE", "2020-01-01")
    end_date = os.getenv("END_DATE", "") or None
    fast_sma = int(os.getenv("FAST_SMA", "20"))
    slow_sma = int(os.getenv("SLOW_SMA", "50"))

    return Settings(
        default_symbols=default_symbols,
        start_date=start_date,
        end_date=end_date,
        fast_sma=fast_sma,
        slow_sma=slow_sma,
    )


def read_watchlist(path: str = "config/watchlist.txt") -> list[str]:
    watchlist_file = Path(path)
    if not watchlist_file.exists():
        return []

    symbols: list[str] = []
    for line in watchlist_file.read_text().splitlines():
        item = line.strip().upper()
        if not item or item.startswith("#"):
            continue
        symbols.append(item)
    return symbols
