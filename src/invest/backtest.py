from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def run_long_only_backtest(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    bt = df.copy()
    bt = bt.sort_values("date")

    bt["daily_return"] = bt["close"].pct_change().fillna(0)
    bt["strategy_return"] = bt["daily_return"] * bt["signal"].shift(1).fillna(0)

    bt["equity_market"] = (1 + bt["daily_return"]).cumprod()
    bt["equity_strategy"] = (1 + bt["strategy_return"]).cumprod()

    total_market = float(bt["equity_market"].iloc[-1] - 1)
    total_strategy = float(bt["equity_strategy"].iloc[-1] - 1)

    max_dd = _max_drawdown(bt["equity_strategy"])

    summary = {
        "market_return": total_market,
        "strategy_return": total_strategy,
        "alpha_vs_market": total_strategy - total_market,
        "max_drawdown": max_dd,
    }
    return bt, summary


def _max_drawdown(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdown = (equity_curve / running_max) - 1
    return float(drawdown.min())


def save_equity_curve_plot(bt: pd.DataFrame, symbol: str, out_path: Path) -> Path:
    plot_df = bt.copy()
    plot_df["date"] = pd.to_datetime(plot_df["date"], errors="coerce")
    plot_df = plot_df.sort_values("date")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(plot_df["date"], plot_df["equity_market"], label="Market", linewidth=1.8)
    ax.plot(plot_df["date"], plot_df["equity_strategy"], label="Strategy", linewidth=1.8)
    ax.set_title(f"{symbol} Backtest Equity Curve")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity (Start = 1.0)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def save_summary_plot(summary_df: pd.DataFrame, out_path: Path) -> Path:
    ordered = summary_df.sort_values("alpha_vs_market", ascending=False)
    symbols = ordered["symbol"].astype(str).tolist()
    market = ordered["market_return"].tolist()
    strategy = ordered["strategy_return"].tolist()

    x = list(range(len(symbols)))
    width = 0.38

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar([i - width / 2 for i in x], market, width=width, label="Market Return")
    ax.bar([i + width / 2 for i in x], strategy, width=width, label="Strategy Return")
    ax.set_title("Backtest Summary by Symbol")
    ax.set_xlabel("Symbol")
    ax.set_ylabel("Total Return")
    ax.set_xticks(x)
    ax.set_xticklabels(symbols)
    ax.axhline(0, color="black", linewidth=1)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path
