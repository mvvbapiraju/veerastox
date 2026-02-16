#!/usr/bin/env python3
from __future__ import annotations

import argparse
import urllib.request

import pandas as pd
import yfinance as yf

INDEX_CONFIG = {
    "sp500": {"url": "https://www.slickcharts.com/sp500", "size": 50, "label": "S&P 500 Top 50"},
    "nasdaq": {"url": "https://www.slickcharts.com/nasdaq100", "size": 50, "label": "NASDAQ-100 Top 50"},
    "dji": {"url": "https://www.slickcharts.com/dowjones", "size": 30, "label": "DJI Top 30"},
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Show top beta stocks for individual indexes and a final combined list "
            "built from individual index top lists."
        )
    )
    p.add_argument(
        "--index",
        choices=["all", "sp500", "nasdaq", "dji"],
        default="all",
        help="Index to run. Use 'all' to print all three plus final combined list.",
    )
    p.add_argument(
        "individual_count",
        nargs="?",
        type=int,
        help="Optional positional override for per-index list size (default: 20).",
    )
    p.add_argument(
        "final_count",
        nargs="?",
        type=int,
        help="Optional positional override for final combined list size (default: 50).",
    )
    p.add_argument(
        "--top-per-index",
        type=int,
        default=20,
        help="How many rows to print for each individual index list (default: 20).",
    )
    p.add_argument(
        "--final-top",
        type=int,
        default=50,
        help="Final combined top size (default: 50).",
    )
    p.add_argument(
        "--no-fill",
        action="store_true",
        help=(
            "Build final list only from the displayed per-index top lists "
            "(strict top-list union, deduped)."
        ),
    )
    return p.parse_args()


def install_browser_user_agent() -> None:
    opener = urllib.request.build_opener()
    opener.addheaders = [
        (
            "User-Agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
    ]
    urllib.request.install_opener(opener)


def get_index_constituents(index_key: str) -> pd.DataFrame:
    conf = INDEX_CONFIG[index_key]
    tables = pd.read_html(conf["url"])
    table = tables[0].head(conf["size"]).copy()
    table["Symbol"] = table["Symbol"].astype(str).str.strip().str.upper()
    return table[["Symbol", "Company"]]


def get_betas(constituents: pd.DataFrame, index_key: str) -> pd.DataFrame:
    rows: list[dict[str, str | float]] = []
    for _, row in constituents.iterrows():
        ticker = str(row["Symbol"])
        company = str(row["Company"])
        try:
            info = yf.Ticker(ticker).info
            beta = info.get("beta")
        except Exception:
            beta = None
        rows.append(
            {
                "Ticker": ticker,
                "Company": company,
                "Beta": beta,
                "Index": index_key,
            }
        )

    df = pd.DataFrame(rows)
    df["Beta"] = pd.to_numeric(df["Beta"], errors="coerce")
    df = df.dropna(subset=["Beta"]).sort_values("Beta", ascending=False).reset_index(drop=True)
    return df


def print_table(title: str, df: pd.DataFrame) -> None:
    print(f"\n=== {title} ===")
    if df.empty:
        print("No rows available.")
        return
    print(df.to_string(index=False))


def _dedupe_ranked(df: pd.DataFrame, final_top: int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Ticker", "Company", "Beta", "Indexes"])

    ranked = df.copy()
    ranked["Ticker"] = ranked["Ticker"].astype(str).str.upper().str.strip()
    ranked = ranked.sort_values("Beta", ascending=False).reset_index(drop=True)

    grouped = (
        ranked.groupby(["Ticker"], as_index=False)
        .agg(
            Company=("Company", "first"),
            Beta=("Beta", "max"),
            Indexes=("Index", lambda s: ",".join(sorted(set(map(str, s))))),
        )
        .sort_values("Beta", ascending=False)
        .head(final_top)
        .reset_index(drop=True)
    )
    return grouped


def build_final_top(
    top_lists: list[pd.DataFrame],
    full_lists: list[pd.DataFrame],
    final_top: int,
    fill: bool,
) -> pd.DataFrame:
    if not top_lists and not full_lists:
        return pd.DataFrame(columns=["Ticker", "Company", "Beta", "Indexes"])

    if not fill:
        return _dedupe_ranked(pd.concat(top_lists, ignore_index=True), final_top=final_top)

    # Default behavior: final ranking from full index universes, deduped by ticker.
    return _dedupe_ranked(pd.concat(full_lists, ignore_index=True), final_top=final_top)


def run_single_index(index_key: str, top_n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    constituents = get_index_constituents(index_key)
    full = get_betas(constituents, index_key)
    top = full.head(top_n).reset_index(drop=True)
    label = INDEX_CONFIG[index_key]["label"]
    print_table(f"{label} - Top {len(top)} by Beta", top[["Ticker", "Company", "Beta"]])
    return top, full


def main() -> None:
    args = parse_args()
    install_browser_user_agent()

    top_per_index = args.individual_count if args.individual_count is not None else args.top_per_index
    final_top = args.final_count if args.final_count is not None else args.final_top

    if top_per_index <= 0 or final_top <= 0:
        raise ValueError("individual_count and final_count must be positive integers")

    if args.index != "all" and args.final_count is not None:
        raise ValueError("final_count is only supported when --index all")

    if args.index != "all":
        run_single_index(args.index, top_per_index)
        return

    top_lists: list[pd.DataFrame] = []
    full_lists: list[pd.DataFrame] = []
    for index_key in ("sp500", "nasdaq", "dji"):
        top, full = run_single_index(index_key, top_per_index)
        top_lists.append(top)
        full_lists.append(full)

    final50 = build_final_top(
        top_lists,
        full_lists,
        final_top=final_top,
        fill=not args.no_fill,
    )
    print_table(
        f"Final Combined Top {len(final50)} by Beta (from individual index lists)",
        final50[["Ticker", "Company", "Beta", "Indexes"]],
    )


if __name__ == "__main__":
    main()
