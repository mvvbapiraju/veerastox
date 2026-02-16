from __future__ import annotations

import base64
import urllib.request
from datetime import date, datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yfinance as yf
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
try:
    import plotly.graph_objects as go
except Exception:  # pragma: no cover - runtime fallback when plotly isn't installed
    go = None

from invest.backtest import run_long_only_backtest, save_equity_curve_plot, save_summary_plot
from invest.config import load_settings, read_watchlist
from invest.data_provider import download_symbol_history, save_history
from invest.signals import add_sma_signals

INDEX_CONFIG = {
    "sp500": {"url": "https://www.slickcharts.com/sp500", "size": 50},
    "nasdaq": {"url": "https://www.slickcharts.com/nasdaq100", "size": 50},
    "dji": {"url": "https://www.slickcharts.com/dowjones", "size": 30},
}

RETURN_WINDOWS = {"1D": 1, "1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252}


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


def _dedupe_ranked(df: pd.DataFrame, final_top: int) -> pd.DataFrame:
    ranked = df.copy()
    ranked["Ticker"] = ranked["Ticker"].astype(str).str.upper().str.strip()
    ranked = ranked.sort_values("Beta", ascending=False).reset_index(drop=True)
    return (
        ranked.groupby(["Ticker"], as_index=False)
        .agg(
            Company=("Company", "first"),
            Beta=("Beta", "max"),
            Indexes=("Index", lambda s: ", ".join(sorted({str(x).upper() for x in s}))),
        )
        .sort_values("Beta", ascending=False)
        .head(final_top)
        .reset_index(drop=True)
    )


@st.cache_data(ttl=3600, show_spinner=False)
def build_final_list(individual_count: int = 20, final_count: int = 50) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    install_browser_user_agent()
    per_index: dict[str, pd.DataFrame] = {}
    full_rows: list[pd.DataFrame] = []

    for idx, conf in INDEX_CONFIG.items():
        table = pd.read_html(conf["url"])[0].head(conf["size"]).copy()
        table["Symbol"] = table["Symbol"].astype(str).str.upper().str.strip()

        rows: list[dict[str, str | float]] = []
        for _, row in table.iterrows():
            ticker = str(row["Symbol"])
            company = str(row["Company"])
            try:
                beta = yf.Ticker(ticker).info.get("beta")
            except Exception:
                beta = None
            rows.append({"Ticker": ticker, "Company": company, "Beta": beta, "Index": idx})

        betas = pd.DataFrame(rows)
        betas["Beta"] = pd.to_numeric(betas["Beta"], errors="coerce")
        betas = betas.dropna(subset=["Beta"]).sort_values("Beta", ascending=False).reset_index(drop=True)
        per_index[idx] = betas.head(individual_count).copy()
        full_rows.append(betas)

    final_df = _dedupe_ranked(pd.concat(full_rows, ignore_index=True), final_count)
    return per_index, final_df


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_market_data(tickers: list[str]) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
    downloaded = yf.download(
        tickers=tickers,
        period="1y",
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    if downloaded.empty:
        return pd.DataFrame()

    close_map: dict[str, pd.Series] = {}
    if isinstance(downloaded.columns, pd.MultiIndex):
        for ticker in tickers:
            if (ticker, "Close") in downloaded.columns:
                close_map[ticker] = downloaded[(ticker, "Close")]
            elif "Close" in downloaded.columns.get_level_values(0):
                close_map[ticker] = downloaded["Close"]
    elif "Close" in downloaded.columns:
        close_map[tickers[0]] = downloaded["Close"]

    close_df = pd.DataFrame(close_map).dropna(how="all")
    return close_df


def compute_returns(close_df: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for ticker in tickers:
        if ticker not in close_df.columns:
            rows.append({"Ticker": ticker, **{k: float("nan") for k in RETURN_WINDOWS}})
            continue

        series = close_df[ticker].dropna()
        result: dict[str, float | str] = {"Ticker": ticker}
        for label, window in RETURN_WINDOWS.items():
            if len(series) < 2:
                result[label] = float("nan")
                continue
            n = min(window, len(series) - 1)
            result[label] = (series.iloc[-1] / series.iloc[-(n + 1)]) - 1
        rows.append(result)

    return pd.DataFrame(rows).set_index("Ticker")


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_latest_volume(tickers: list[str]) -> pd.Series:
    if not tickers:
        return pd.Series(dtype="float64")

    downloaded = yf.download(
        tickers=tickers,
        period="10d",
        interval="1d",
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    if downloaded.empty:
        return pd.Series(index=tickers, dtype="float64")

    vol_map: dict[str, float] = {}
    if isinstance(downloaded.columns, pd.MultiIndex):
        for ticker in tickers:
            if (ticker, "Volume") in downloaded.columns:
                series = downloaded[(ticker, "Volume")].dropna()
                vol_map[ticker] = float(series.iloc[-1]) if not series.empty else float("nan")
            elif "Volume" in downloaded.columns.get_level_values(0):
                series = downloaded["Volume"].dropna()
                vol_map[ticker] = float(series.iloc[-1]) if not series.empty else float("nan")
            else:
                vol_map[ticker] = float("nan")
    else:
        series = downloaded["Volume"].dropna() if "Volume" in downloaded.columns else pd.Series(dtype="float64")
        vol_map[tickers[0]] = float(series.iloc[-1]) if not series.empty else float("nan")

    return pd.Series(vol_map, dtype="float64")


def build_index_table(df: pd.DataFrame, returns_df: pd.DataFrame, volume_series: pd.Series) -> pd.DataFrame:
    table = df[["Ticker", "Company", "Beta"]].copy().reset_index(drop=True)
    table.insert(0, "S.No", range(1, len(table) + 1))
    r = returns_df.reindex(table["Ticker"]).reset_index(drop=True)
    table["Volume"] = table["Ticker"].map(volume_series).astype("float64")
    for col in RETURN_WINDOWS:
        table[col] = r[col]

    table.columns = ["S.No", "Ticker", "Company", "Beta", "Volume", "1D", "1W", "1M", "3M", "6M", "1Y"]
    return table


def format_compact_number(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    n = float(value)
    v = abs(n)
    if v >= 1e9:
        return f"{n / 1e9:.2f}B".replace(".00", "")
    if v >= 1e6:
        return f"{n / 1e6:.2f}M".replace(".00", "")
    if v >= 1e3:
        return f"{n / 1e3:.2f}K".replace(".00", "")
    return f"{n:.0f}"


def _filter_to_regular_market_hours(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    idx = pd.to_datetime(df.index, errors="coerce")
    if getattr(idx, "tz", None) is None:
        idx = idx.tz_localize("America/New_York")
    else:
        idx = idx.tz_convert("America/New_York")
    out = df.copy()
    out.index = idx
    return out.between_time("09:30", "16:00")


def _is_market_open_now() -> bool:
    now_ny = pd.Timestamp.now(tz="America/New_York")
    if now_ny.weekday() >= 5:
        return False
    now_t = now_ny.time()
    return now_t >= pd.Timestamp("09:30").time() and now_t <= pd.Timestamp("16:00").time()


@st.cache_data(ttl=5, show_spinner=False)
def fetch_realtime_quote(ticker: str) -> dict[str, object]:
    try:
        yf_ticker = yf.Ticker(ticker)
        data = yf_ticker.history(period="1d", interval="1m", auto_adjust=False)
    except Exception:
        return {"price": None, "change_pct": None, "volume": None, "asof": None}
    if data.empty or "Close" not in data.columns:
        return {"price": None, "change_pct": None, "volume": None, "asof": None}
    data = _filter_to_regular_market_hours(data)
    if data.empty:
        return {"price": None, "change_pct": None, "volume": None, "asof": None}

    close = data["Close"].dropna()
    if close.empty:
        return {"price": None, "change_pct": None, "volume": None, "asof": None}

    price = None
    volume = None
    prev_close = None

    try:
        fi = yf_ticker.fast_info
        price = fi.get("last_price")
        volume = fi.get("last_volume")
        prev_close = fi.get("previous_close")
    except Exception:
        pass

    if price in (None, 0):
        price = float(close.iloc[-1])
    if prev_close not in (None, 0):
        change_pct = (float(price) / float(prev_close)) - 1
    else:
        first_close = float(close.iloc[0]) if len(close) > 0 else None
        change_pct = ((float(price) / first_close) - 1) if first_close not in (None, 0) else None

    if volume in (None, 0) and "Volume" in data.columns:
        vol = data["Volume"].dropna()
        volume = float(vol.sum()) if not vol.empty else None

    asof = close.index[-1]
    return {"price": float(price), "change_pct": change_pct, "volume": volume, "asof": asof}


@st.cache_data(ttl=900, show_spinner=False)
def fetch_offhours_snapshot(ticker: str) -> dict[str, object]:
    try:
        downloaded = yf.download(
            tickers=ticker,
            period="7d",
            interval="1m",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception:
        return {"price": None, "change_pct": None, "volume": None, "volume_change_pct": None, "asof": None}

    if downloaded.empty or "Close" not in downloaded.columns:
        return {"price": None, "change_pct": None, "volume": None, "volume_change_pct": None, "asof": None}

    downloaded = _filter_to_regular_market_hours(downloaded)
    if downloaded.empty:
        return {"price": None, "change_pct": None, "volume": None, "volume_change_pct": None, "asof": None}

    close = downloaded["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = pd.to_numeric(close, errors="coerce").dropna()
    if close.empty:
        return {"price": None, "change_pct": None, "volume": None, "volume_change_pct": None, "asof": None}

    volume_col = downloaded["Volume"] if "Volume" in downloaded.columns else pd.Series(index=close.index, dtype="float64")
    if isinstance(volume_col, pd.DataFrame):
        volume_col = volume_col.iloc[:, 0]
    volume_col = pd.to_numeric(volume_col, errors="coerce").fillna(0.0)

    session_close = close.groupby(close.index.date).last()
    session_volume = volume_col.groupby(volume_col.index.date).sum()
    if session_close.empty:
        return {"price": None, "change_pct": None, "volume": None, "volume_change_pct": None, "asof": None}

    last_close = float(session_close.iloc[-1])
    last_volume = float(session_volume.iloc[-1]) if not session_volume.empty else None
    prev_close = float(session_close.iloc[-2]) if len(session_close) >= 2 else None
    prev_volume = float(session_volume.iloc[-2]) if len(session_volume) >= 2 else None

    change_pct = (last_close / prev_close - 1) if prev_close not in (None, 0) else None
    volume_change_pct = (last_volume / prev_volume - 1) if prev_volume not in (None, 0) else None
    asof = close.index[-1]
    return {
        "price": last_close,
        "change_pct": change_pct,
        "volume": last_volume,
        "volume_change_pct": volume_change_pct,
        "asof": asof,
    }


@st.cache_data(ttl=30, show_spinner=False)
def fetch_single_ticker_close(ticker: str) -> pd.Series:
    downloaded = yf.download(
        tickers=ticker,
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if downloaded.empty:
        return pd.Series(dtype="float64")

    if "Close" in downloaded.columns:
        close = downloaded["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close.dropna()
    return pd.Series(dtype="float64")


@st.cache_data(ttl=900, show_spinner=False)
def fetch_inception_close(ticker: str) -> pd.Series:
    downloaded = yf.download(
        tickers=ticker,
        period="max",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if downloaded.empty:
        return pd.Series(dtype="float64")

    if "Close" in downloaded.columns:
        close = downloaded["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close.dropna()
    return pd.Series(dtype="float64")


@st.cache_data(ttl=900, show_spinner=False)
def fetch_inception_ohlc(ticker: str) -> pd.DataFrame:
    downloaded = yf.download(
        tickers=ticker,
        period="max",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if downloaded.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close"])

    if isinstance(downloaded.columns, pd.MultiIndex):
        downloaded.columns = downloaded.columns.get_level_values(0)

    required = ["Open", "High", "Low", "Close"]
    if not all(c in downloaded.columns for c in required):
        return pd.DataFrame(columns=["open", "high", "low", "close"])

    ohlc = downloaded[required].copy().dropna()
    ohlc.columns = ["open", "high", "low", "close"]
    idx = pd.to_datetime(ohlc.index, errors="coerce")
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    ohlc.index = idx.normalize() + pd.Timedelta(hours=16)
    return ohlc.dropna()


@st.cache_data(ttl=5, show_spinner=False)
def fetch_intraday_close(ticker: str) -> pd.Series:
    downloaded = yf.download(
        tickers=ticker,
        period="1d",
        interval="1m",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if downloaded.empty:
        return pd.Series(dtype="float64")
    downloaded = _filter_to_regular_market_hours(downloaded)
    if downloaded.empty:
        return pd.Series(dtype="float64")
    if "Close" in downloaded.columns:
        close = downloaded["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close.dropna()
    return pd.Series(dtype="float64")


@st.cache_data(ttl=5, show_spinner=False)
def fetch_intraday_ohlc(ticker: str, interval: str = "5m") -> pd.DataFrame:
    period_by_interval = {
        "1m": "7d",
        "2m": "60d",
        "5m": "60d",
        "15m": "60d",
        "30m": "60d",
        "60m": "730d",
        "90m": "60d",
    }
    downloaded = yf.download(
        tickers=ticker,
        period=period_by_interval.get(interval, "60d"),
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if downloaded.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close"])

    downloaded = _filter_to_regular_market_hours(downloaded)
    if downloaded.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close"])

    if isinstance(downloaded.columns, pd.MultiIndex):
        downloaded.columns = downloaded.columns.get_level_values(0)

    required = ["Open", "High", "Low", "Close"]
    if not all(c in downloaded.columns for c in required):
        return pd.DataFrame(columns=["open", "high", "low", "close"])

    ohlc = downloaded[required].copy().dropna()
    ohlc.columns = ["open", "high", "low", "close"]
    idx = pd.to_datetime(ohlc.index, errors="coerce")
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    ohlc.index = idx
    return ohlc.dropna()


def _resolve_symbols(symbols_raw: str, fallback: list[str]) -> list[str]:
    parsed = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
    if not parsed:
        parsed = fallback
    # Preserve order and drop duplicates.
    return list(dict.fromkeys(parsed))


def _run_get_data(symbols: list[str], start: str, end: str | None) -> list[str]:
    logs: list[str] = []
    for symbol in symbols:
        try:
            df = download_symbol_history(symbol, start=start, end=end)
            out_path = save_history(df, symbol)
            logs.append(f"saved {symbol}: {out_path}")
        except Exception as exc:
            logs.append(f"error {symbol}: {exc}")
    return logs


def _run_generate_signals(symbols: list[str], fast: int, slow: int) -> list[str]:
    logs: list[str] = []
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        in_path = Path("data/raw") / f"{symbol}.csv"
        if not in_path.exists():
            logs.append(f"skip {symbol}: missing {in_path}")
            continue
        try:
            df = pd.read_csv(in_path)
            signaled = add_sma_signals(df, fast_window=fast, slow_window=slow)
            out_path = out_dir / f"{symbol}_signals.csv"
            signaled.to_csv(out_path, index=False)
            logs.append(f"saved {symbol}: {out_path}")
        except Exception as exc:
            logs.append(f"error {symbol}: {exc}")
    return logs


def _run_backtests(symbols: list[str], visual_only: bool) -> tuple[list[str], pd.DataFrame]:
    logs: list[str] = []
    rows: list[dict[str, float | str]] = []
    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    for symbol in symbols:
        in_path = Path("data/processed") / f"{symbol}_signals.csv"
        if not in_path.exists():
            logs.append(f"skip {symbol}: missing {in_path}")
            continue

        try:
            df = pd.read_csv(in_path)
            bt, summary = run_long_only_backtest(df)

            curve_path = report_dir / f"{symbol}_equity_curve.csv"
            if not visual_only:
                bt.to_csv(curve_path, index=False)

            curve_plot_path = report_dir / f"{symbol}_equity_curve.png"
            save_equity_curve_plot(bt, symbol, curve_plot_path)

            rows.append({"symbol": symbol, **summary})
            if visual_only:
                logs.append(f"backtested {symbol}: {curve_plot_path}")
            else:
                logs.append(f"backtested {symbol}: {curve_path}, {curve_plot_path}")
        except Exception as exc:
            logs.append(f"error {symbol}: {exc}")

    summary_df = pd.DataFrame(rows)
    if not summary_df.empty:
        summary_path = report_dir / "summary.csv"
        if not visual_only:
            summary_df.to_csv(summary_path, index=False)
        summary_plot_path = report_dir / "summary.png"
        save_summary_plot(summary_df, summary_plot_path)
        if visual_only:
            logs.append(f"summary: {summary_plot_path}")
        else:
            logs.append(f"summary: {summary_path}, {summary_plot_path}")

    return logs, summary_df


def _cleanup_previous_reports() -> list[str]:
    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    removed: list[str] = []
    for pattern in ("*.csv", "*.png"):
        for path in report_dir.glob(pattern):
            try:
                path.unlink()
                removed.append(path.name)
            except Exception:
                continue
    return removed


def _render_strategy_reports(show_csv_tables: bool) -> None:
    report_dir = Path("reports")
    if not report_dir.exists():
        return

    png_files = sorted(report_dir.glob("*.png"))
    csv_files = sorted(report_dir.glob("*.csv"))
    if not png_files and not csv_files:
        return

    st.subheader("Generated Reports")

    if png_files:
        summary_img = next((p for p in png_files if p.name == "summary.png"), None)
        if summary_img is not None:
            summary_count = 0
            summary_csv = report_dir / "summary.csv"
            if summary_csv.exists():
                try:
                    summary_count = len(pd.read_csv(summary_csv))
                except Exception:
                    summary_count = 0

            if summary_count <= 5:
                layout = [1, 2, 1]
            elif summary_count <= 10:
                layout = [1.8, 2.2, 1.8]
            elif summary_count <= 20:
                layout = [1.2, 2.8, 1.2]
            else:
                layout = [0.8, 3.4, 0.8]

            _, c_mid, _ = st.columns(layout)
            with c_mid:
                encoded = base64.b64encode(summary_img.read_bytes()).decode("ascii")
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:center;">
                      <img src="data:image/png;base64,{encoded}" alt="{summary_img.name}"
                           style="width:100%;height:420px;object-fit:contain;" />
                    </div>
                    <div style="text-align:center;color:rgba(49,51,63,0.7);font-size:0.85rem;margin-top:0.2rem;">
                      {summary_img.name}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        remaining = [p for p in png_files if p != summary_img]
        for i in range(0, len(remaining), 3):
            cols = st.columns(3)
            with cols[0]:
                st.image(str(remaining[i]), caption=remaining[i].name, width="stretch")
            if i + 1 < len(remaining):
                with cols[1]:
                    st.image(str(remaining[i + 1]), caption=remaining[i + 1].name, width="stretch")
            if i + 2 < len(remaining):
                with cols[2]:
                    st.image(str(remaining[i + 2]), caption=remaining[i + 2].name, width="stretch")

    if show_csv_tables and csv_files:
        st.markdown("<div class='tight-section-title'>CSV Tables</div>", unsafe_allow_html=True)
        for csv_path in csv_files:
            try:
                df = pd.read_csv(csv_path)
            except Exception as exc:
                st.warning(f"Could not read {csv_path.name}: {exc}")
                continue

            st.markdown(f"`{csv_path.name}`")
            if df.empty:
                st.info("No rows in file.")
                continue

            show = df.copy()
            if csv_path.name == "summary.csv":
                for col in ["market_return", "strategy_return", "alpha_vs_market", "max_drawdown"]:
                    if col in show.columns:
                        show[col] = pd.to_numeric(show[col], errors="coerce")
                st.dataframe(
                    show.style.format(
                        {
                            "market_return": "{:.2%}",
                            "strategy_return": "{:.2%}",
                            "alpha_vs_market": "{:.2%}",
                            "max_drawdown": "{:.2%}",
                        }
                    ),
                    width="stretch",
                )
            else:
                st.dataframe(show, width="stretch")


def render_aggrid_table(
    df: pd.DataFrame,
    include_indexes: bool = False,
    render: bool = True,
    page_size: int = 25,
) -> pd.DataFrame:
    work = df.copy()
    for c in ["S.No", "Beta", "Volume", "1D", "1W", "1M", "3M", "6M", "1Y"]:
        if c in work.columns:
            work[c] = pd.to_numeric(work[c], errors="coerce")

    gb = GridOptionsBuilder.from_dataframe(work)
    gb.configure_default_column(sortable=True, filter=True, resizable=True)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=page_size)

    center = {"textAlign": "center"}
    beta_formatter = JsCode("function(p){return p.value==null?'-':Number(p.value).toFixed(3)}")
    volume_formatter = JsCode(
        """
        function(p){
            if (p.value == null || isNaN(Number(p.value))) return '-';
            const v = Math.abs(Number(p.value));
            const n = Number(p.value);
            if (v >= 1e9) return (n / 1e9).toFixed(2).replace(/\\.00$/, '') + 'B';
            if (v >= 1e6) return (n / 1e6).toFixed(2).replace(/\\.00$/, '') + 'M';
            if (v >= 1e3) return (n / 1e3).toFixed(2).replace(/\\.00$/, '') + 'K';
            return n.toFixed(0);
        }
        """
    )
    ret_formatter = JsCode("function(p){return p.value==null?'-':(Number(p.value)*100).toFixed(2)+'%'}")

    base_cols = ["S.No", "Ticker", "Company"]
    if include_indexes:
        base_cols.append("Indexes")
    base_cols.extend(["Beta", "Volume"])

    for col in base_cols:
        if col == "S.No":
            gb.configure_column(col, width=72, pinned="left", cellStyle=center, type=["numericColumn"])
        elif col == "Beta":
            gb.configure_column(col, valueFormatter=beta_formatter, cellStyle=center, type=["numericColumn"])
        elif col == "Volume":
            gb.configure_column(col, valueFormatter=volume_formatter, cellStyle=center, type=["numericColumn"])
        else:
            gb.configure_column(col, cellStyle=center)

    col_defs = []
    for c in base_cols:
        col_def: dict[str, object] = {"field": c, "headerName": c, "headerClass": "header-center", "cellStyle": center}
        if c == "S.No":
            col_def["type"] = ["numericColumn"]
            col_def["width"] = 72
            col_def["pinned"] = "left"
        elif c == "Beta":
            col_def["type"] = ["numericColumn"]
            col_def["valueFormatter"] = beta_formatter
        elif c == "Volume":
            col_def["type"] = ["numericColumn"]
            col_def["valueFormatter"] = volume_formatter
        col_defs.append(col_def)

    returns_children = []
    for c in ["1D", "1W", "1M", "3M", "6M", "1Y"]:
        returns_children.append(
            {
                "field": c,
                "headerName": c,
                "headerClass": "header-center",
                "cellStyle": center,
                "valueFormatter": ret_formatter,
                "type": ["numericColumn"],
            }
        )
    col_defs.append(
        {
            "headerName": "Returns",
            "headerClass": "header-center",
            "marryChildren": True,
            "suppressStickyLabel": True,
            "children": returns_children,
        }
    )

    grid_options = gb.build()
    grid_options["columnDefs"] = col_defs

    rows = len(work)
    visible_rows = min(rows, max(page_size, 1))
    height = min(max(240, 90 + visible_rows * 29), 800)
    custom_css = {
        ".ag-header-cell-label": {"justify-content": "center"},
        ".ag-header-cell-text": {"font-weight": "700", "text-align": "center"},
        ".ag-header-group-cell-label": {"justify-content": "center"},
        ".ag-header-group-cell .ag-header-group-cell-label": {"justify-content": "center"},
        ".ag-header-group-text": {"font-weight": "700", "text-align": "center", "width": "100%"},
    }
    if render:
        response = AgGrid(
            work,
            gridOptions=grid_options,
            allow_unsafe_jscode=True,
            update_on=["sortChanged", "filterChanged"],
            fit_columns_on_grid_load=False,
            custom_css=custom_css,
            height=height,
            theme="streamlit",
        )
        out = pd.DataFrame(response.get("data", []))
        return out if not out.empty else work

    # When not rendering, return the current data order as-is.
    return work


def render_backtest_summary_table(df: pd.DataFrame) -> None:
    work = df.copy()
    expected = ["Symbol", "Market Return", "Strategy Return", "Alpha Vs Market", "Max Drawdown"]
    cols = [c for c in expected if c in work.columns]
    work = work[cols]

    for c in ["Market Return", "Strategy Return", "Alpha Vs Market", "Max Drawdown"]:
        if c in work.columns:
            work[c] = pd.to_numeric(work[c], errors="coerce")

    gb = GridOptionsBuilder.from_dataframe(work)
    gb.configure_default_column(sortable=True, filter=True, resizable=True)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)

    left = {"textAlign": "left"}
    ret_formatter = JsCode("function(p){return p.value==null?'-':(Number(p.value)*100).toFixed(2)+'%'}")

    col_defs: list[dict[str, object]] = []
    for c in cols:
        col_def: dict[str, object] = {"field": c, "headerName": c, "headerClass": "header-center", "cellStyle": left}
        if c in {"Market Return", "Strategy Return", "Alpha Vs Market", "Max Drawdown"}:
            col_def["type"] = ["numericColumn"]
            col_def["valueFormatter"] = ret_formatter
        col_defs.append(col_def)

    grid_options = gb.build()
    grid_options["columnDefs"] = col_defs

    rows = len(work)
    visible_rows = min(rows, 20)
    height = max(110, 62 + visible_rows * 29)
    custom_css = {
        ".ag-header-cell-label": {"justify-content": "center"},
        ".ag-header-cell-text": {"font-weight": "700", "text-align": "center"},
    }

    AgGrid(
        work,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        update_on=["sortChanged", "filterChanged"],
        fit_columns_on_grid_load=False,
        custom_css=custom_css,
        height=height,
        theme="streamlit",
    )


def apply_standard_line_chart_layout(fig: go.Figure, title_y: str) -> None:
    fig.update_layout(
        height=380,
        xaxis_title="Date",
        yaxis_title=title_y,
        hovermode="x unified",
        dragmode="pan",
        margin={"l": 18, "r": 12, "t": 10, "b": 12},
        font={"size": 13},
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")


def _to_naive_ny(ts: pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        return t.tz_convert("America/New_York").tz_localize(None)
    return t


def _read_visible_x_range(fig: go.Figure, fallback_start: pd.Timestamp, fallback_end: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    xr = getattr(getattr(fig.layout, "xaxis", None), "range", None)
    if xr and len(xr) == 2:
        start = pd.to_datetime(xr[0], errors="coerce")
        end = pd.to_datetime(xr[1], errors="coerce")
        if pd.notna(start) and pd.notna(end):
            return _to_naive_ny(start), _to_naive_ny(end)
    return _to_naive_ny(fallback_start), _to_naive_ny(fallback_end)


def _build_day_boundary_overlays(plot_dates: pd.Series, range_start: pd.Timestamp, range_end: pd.Timestamp) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    start_ts = pd.Timestamp(range_start)
    end_ts = pd.Timestamp(range_end)
    if end_ts < start_ts:
        start_ts, end_ts = end_ts, start_ts
    day_list = pd.date_range(start=start_ts.normalize(), end=end_ts.normalize(), freq="D")
    if day_list.empty:
        return [], []

    boundary_positions: set[pd.Timestamp] = set()
    shapes: list[dict[str, object]] = []
    annotations: list[dict[str, object]] = []
    for day in day_list:
        if pd.Timestamp(day).weekday() >= 5:
            continue
        nominal = pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30)
        if pd.Timestamp(day).normalize() == start_ts.normalize() and nominal < start_ts:
            x_pos = start_ts
        else:
            x_pos = nominal
        if x_pos > end_ts:
            continue
        boundary_positions.add(pd.Timestamp(x_pos))
        shapes.append(
            {
                "type": "line",
                "xref": "x",
                "yref": "paper",
                "x0": x_pos,
                "x1": x_pos,
                "y0": 0,
                "y1": 1,
                "line": {"color": "rgba(0,0,0,0.40)", "width": 2.6},
                "layer": "below",
            }
        )
        annotations.append(
            {
                "xref": "x",
                "yref": "paper",
                "x": x_pos,
                "y": 0,
                "yshift": 8,
                "text": pd.Timestamp(day).strftime("%b %d"),
                "showarrow": False,
                "font": {"size": 11, "color": "rgba(49,51,63,0.78)"},
                "xanchor": "left",
                "yanchor": "bottom",
            }
        )

    return shapes, annotations


def _build_session_ticks(range_start: pd.Timestamp, range_end: pd.Timestamp) -> tuple[list[pd.Timestamp], list[str]]:
    start_ts = pd.Timestamp(range_start)
    end_ts = pd.Timestamp(range_end)
    if end_ts < start_ts:
        start_ts, end_ts = end_ts, start_ts
    days = pd.date_range(start=start_ts.normalize(), end=end_ts.normalize(), freq="D")
    tickvals: list[pd.Timestamp] = []
    ticktext: list[str] = []
    for day in days:
        if pd.Timestamp(day).weekday() >= 5:
            continue
        session_start = pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30)
        session_end = pd.Timestamp(day) + pd.Timedelta(hours=16)
        if session_end < start_ts or session_start > end_ts:
            continue

        # Start-of-session marker is date label (not 9:30 AM time).
        if start_ts <= session_start <= end_ts:
            tickvals.append(session_start)
            ticktext.append(pd.Timestamp(day).strftime("%b %d"))

        # Hourly markers only at top of each hour.
        for hour in range(10, 17):
            h = pd.Timestamp(day) + pd.Timedelta(hours=hour)
            if start_ts <= h <= end_ts:
                tickvals.append(h)
                ticktext.append(pd.Timestamp(h).strftime("%I%p").lstrip("0"))
    return tickvals, ticktext


def _select_fetch_interval(span: pd.Timedelta) -> str:
    if span <= pd.Timedelta(hours=2):
        return "1m"
    if span <= pd.Timedelta(hours=10):
        return "5m"
    if span <= pd.Timedelta(days=2):
        return "15m"
    if span <= pd.Timedelta(days=7):
        return "30m"
    return "60m"


def apply_stock_intraday_axis_format(
    fig: go.Figure,
    plot_dates: pd.Series,
    range_start: pd.Timestamp,
    range_end: pd.Timestamp,
) -> None:
    shapes, annotations = _build_day_boundary_overlays(plot_dates, range_start, range_end)
    tickvals, ticktext = _build_session_ticks(range_start, range_end)
    fig.update_layout(shapes=shapes, annotations=annotations)
    fig.update_xaxes(
        type="date",
        ticklabelmode="instant",
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
        # Hide midnight hour labels; day boundaries are annotated with dates.
        labelalias={
            "12 AM": "",
            "12AM": "",
            "12:00 AM": "",
            "12:00AM": "",
            "12:00\u202fAM": "",
            "00:00": "",
            "00:00 AM": "",
        },
        rangebreaks=[
            dict(bounds=["sat", "mon"]),
            dict(bounds=[16, 9.5], pattern="hour"),
        ],
        griddash="dot",
        showgrid=True,
        gridcolor="rgba(0,0,0,0.18)",
        gridwidth=1.0,
        showticklabels=True,
        automargin=True,
    )


def main() -> None:
    st.set_page_config(page_title="Veerastox", layout="wide")
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.9rem;
        }
        div[data-testid="stNumberInput"] { margin-bottom: -0.45rem; }
        div[data-testid="stNumberInput"][aria-label="Final list count"],
        div[data-testid="stNumberInput"][aria-label="Individual list count"] {
            min-width: 150px;
        }
        .tight-section-title {
            font-size: 1.75rem;
            font-weight: 600;
            line-height: 1.1;
            margin: 0;
            padding: 0;
        }
        .section-separator {
            border-top: 2px solid #3aa86b;
            margin: 1.25rem 0 0.75rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Veerastox")
    app_tab_live, app_tab_strategy = st.tabs(["β Screener Dashboard", "Strategy Lab"])

    with app_tab_live:
        st.caption(
            "Use the counters beside each section title to control list sizes. "
            "The all-index list is deduplicated and sorted by beta, table sorting drives chart order, "
            "and Stock Details auto-refreshes live intraday data every 5 seconds."
        )

        individual_count = int(st.session_state.get("individual_count", 20))
        final_count = int(st.session_state.get("final_count", 50))

        per_index, final_df = build_final_list(individual_count=int(individual_count), final_count=int(final_count))
        tickers = final_df["Ticker"].tolist()
        index_tickers = sorted({t for idx_df in per_index.values() for t in idx_df["Ticker"].tolist()})
        all_tickers = sorted(set(tickers).union(index_tickers))
        all_close_df = fetch_market_data(all_tickers)
        if not all_close_df.empty:
            returns_df = compute_returns(all_close_df, all_tickers)
        else:
            returns_df = pd.DataFrame(index=all_tickers, columns=list(RETURN_WINDOWS.keys()), dtype=float)

        final_rank_df = final_df.copy().reset_index(drop=True)
        final_rank_df.insert(0, "S.No", range(1, len(final_rank_df) + 1))
        volume_series = fetch_latest_volume(all_tickers)
        final_returns = returns_df.reindex(final_rank_df["Ticker"]).reset_index(drop=True)
        final_rank_df["Indexes"] = final_rank_df["Indexes"].astype(str).apply(
            lambda s: ", ".join(part.strip().upper() for part in s.split(",") if part.strip())
        )
        final_rank_df["Volume"] = final_rank_df["Ticker"].map(volume_series).astype("float64")
        for col in RETURN_WINDOWS:
            final_rank_df[col] = final_returns[col]
        final_rank_df = final_rank_df[
            ["S.No", "Ticker", "Company", "Indexes", "Beta", "Volume", "1D", "1W", "1M", "3M", "6M", "1Y"]
        ]

        st.subheader("Stock Stats")
        current_ticker_value = str(st.session_state.get("detail_ticker", tickers[0] if tickers else "")).strip()
        detail_width = max(160, min(420, 80 + len(current_ticker_value) * 16))
        selected = st.selectbox(
            "Ticker",
            tickers,
            index=0 if tickers else None,
            accept_new_options=True,
            placeholder="Select or type ticker",
            key="detail_ticker",
            width=detail_width,
        )
        detail_ticker = str(selected).strip().upper() if selected else None
        market_open_now = _is_market_open_now()
        live_refresh_every = "5s" if market_open_now else None

        @st.fragment(run_every=live_refresh_every)
        def render_realtime_quote(ticker: str | None) -> None:
            if not ticker:
                return
            market_open = _is_market_open_now()
            quote = fetch_realtime_quote(ticker) if market_open else fetch_offhours_snapshot(ticker)
            q1, q2, q3 = st.columns(3)

            prev_map = st.session_state.get("live_quote_prev", {})
            prev = prev_map.get(ticker, {})
            trend_map = st.session_state.get("live_quote_trend", {})
            trend_prev = trend_map.get(ticker, {})

            def _trend_color(curr: float | None, last: float | None, prev_trend: str | None) -> tuple[str, str | None]:
                if curr is None:
                    return "rgba(49,51,63,0.85)", prev_trend
                if last is None:
                    return "rgba(49,51,63,0.85)", prev_trend
                if curr > last:
                    return "#129B3A", "up"
                if curr < last:
                    return "#C5332B", "down"
                if prev_trend == "up":
                    return "#129B3A", "up"
                if prev_trend == "down":
                    return "#C5332B", "down"
                return "rgba(49,51,63,0.85)", prev_trend

            if market_open:
                price_color, price_trend = _trend_color(quote.get("price"), prev.get("price"), trend_prev.get("price"))
                change_color, change_trend = _trend_color(quote.get("change_pct"), prev.get("change_pct"), trend_prev.get("change_pct"))
                volume_color, volume_trend = _trend_color(quote.get("volume"), prev.get("volume"), trend_prev.get("volume"))
            else:
                change_pct = quote.get("change_pct")
                vol_change_pct = quote.get("volume_change_pct")
                if change_pct is None:
                    price_color = "rgba(49,51,63,0.85)"
                    change_color = "rgba(49,51,63,0.85)"
                elif change_pct > 0:
                    price_color = "#129B3A"
                    change_color = "#129B3A"
                elif change_pct < 0:
                    price_color = "#C5332B"
                    change_color = "#C5332B"
                else:
                    price_color = "rgba(49,51,63,0.85)"
                    change_color = "rgba(49,51,63,0.85)"

                if vol_change_pct is None:
                    volume_color = "rgba(49,51,63,0.85)"
                elif vol_change_pct > 0:
                    volume_color = "#129B3A"
                elif vol_change_pct < 0:
                    volume_color = "#C5332B"
                else:
                    volume_color = "rgba(49,51,63,0.85)"
                price_trend = trend_prev.get("price")
                change_trend = trend_prev.get("change_pct")
                volume_trend = trend_prev.get("volume")
            price_text = f"${quote['price']:.2f}" if quote["price"] is not None else "N/A"
            change_text = f"{quote['change_pct']:.2%}" if quote["change_pct"] is not None else "N/A"
            volume_text = format_compact_number(quote["volume"])

            q1.markdown(
                "<div style='font-size:1.15rem;color:rgba(49,51,63,0.9);'>Live Price</div>"
                f"<div style='font-size:2.2rem;font-weight:600;color:{price_color};'>"
                f"{price_text}</div>",
                unsafe_allow_html=True,
            )
            q2.markdown(
                "<div style='font-size:1.15rem;color:rgba(49,51,63,0.9);'>Live Change</div>"
                f"<div style='font-size:2.2rem;font-weight:600;color:{change_color};'>"
                f"{change_text}</div>",
                unsafe_allow_html=True,
            )
            q3.markdown(
                "<div style='font-size:1.15rem;color:rgba(49,51,63,0.9);'>Live Intraday Volume</div>"
                f"<div style='font-size:2.2rem;font-weight:600;color:{volume_color};'>"
                f"{volume_text}</div>",
                unsafe_allow_html=True,
            )

            if market_open:
                prev_map[ticker] = {
                    "price": quote.get("price"),
                    "change_pct": quote.get("change_pct"),
                    "volume": quote.get("volume"),
                }
                st.session_state["live_quote_prev"] = prev_map
                trend_map[ticker] = {
                    "price": price_trend,
                    "change_pct": change_trend,
                    "volume": volume_trend,
                }
                st.session_state["live_quote_trend"] = trend_map
            if market_open:
                refreshed_ny = pd.Timestamp.now(tz="America/New_York")
                refresh_text = "Auto-refresh: 5s."
            else:
                asof = quote.get("asof")
                if asof is not None:
                    asof_ts = pd.to_datetime(asof, errors="coerce")
                    if pd.notna(asof_ts):
                        if getattr(asof_ts, "tzinfo", None) is None:
                            refreshed_ny = asof_ts.tz_localize("America/New_York")
                        else:
                            refreshed_ny = asof_ts.tz_convert("America/New_York")
                    else:
                        refreshed_ny = pd.Timestamp.now(tz="America/New_York")
                else:
                    refreshed_ny = pd.Timestamp.now(tz="America/New_York")
                refresh_text = "Auto-refresh: Off (market closed)."
            refreshed_at = refreshed_ny.strftime("%Y-%m-%d %H:%M:%S %Z")
            status_text = "Open (live 5s refresh)" if market_open else "Closed (using latest session vs previous session)"
            st.markdown(
                "<div style='margin-top:0.1rem; margin-bottom:0.2rem; color:rgba(49,51,63,0.55); "
                "font-size:0.82rem; line-height:1.15;'>"
                f"Market data source: Yahoo Finance intraday feed (may be delayed). {refresh_text} "
                f"Market status: {status_text}. "
                f"Refreshed at: {refreshed_at}"
                "</div>",
                unsafe_allow_html=True,
            )

        render_realtime_quote(detail_ticker)

        @st.fragment(run_every=live_refresh_every)
        def render_stock_details_chart(ticker: str | None, hist_series: pd.Series) -> None:
            if not ticker:
                return
            live = fetch_realtime_quote(ticker) if _is_market_open_now() else {"price": None}
            existing_fig = st.session_state.get("stock_details_fig")
            existing_ticker = st.session_state.get("stock_details_fig_ticker")
            now_ny = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
            fallback_start = now_ny - pd.Timedelta(hours=7)
            fallback_end = now_ny
            if existing_fig is not None and existing_ticker == ticker:
                vis_start_probe, vis_end_probe = _read_visible_x_range(existing_fig, fallback_start, fallback_end)
            else:
                vis_start_probe, vis_end_probe = fallback_start, fallback_end
            if vis_end_probe < vis_start_probe:
                vis_start_probe, vis_end_probe = vis_end_probe, vis_start_probe
            fetch_interval = _select_fetch_interval(vis_end_probe - vis_start_probe)
            daily_ohlc = fetch_inception_ohlc(ticker)

            # Always preload at least ~1 month of session intraday bars so zoom/pan
            # to recent history is populated immediately, even before next refresh.
            preload_intraday_ohlc = fetch_intraday_ohlc(ticker, interval="5m")
            if not preload_intraday_ohlc.empty:
                preload_cutoff = pd.Timestamp.now(tz="America/New_York").tz_localize(None) - pd.Timedelta(days=31)
                preload_intraday_ohlc = preload_intraday_ohlc[preload_intraday_ohlc.index >= preload_cutoff]

            if fetch_interval == "5m":
                intraday_ohlc = preload_intraday_ohlc
            else:
                intraday_ohlc = fetch_intraday_ohlc(ticker, interval=fetch_interval)
                if intraday_ohlc.empty:
                    intraday_ohlc = preload_intraday_ohlc
                elif not preload_intraday_ohlc.empty:
                    intraday_ohlc = pd.concat([preload_intraday_ohlc, intraday_ohlc], axis=0)
                    intraday_ohlc = intraday_ohlc.sort_index()
                    intraday_ohlc = intraday_ohlc[~intraday_ohlc.index.duplicated(keep="last")]

            # Fallback if OHLC download is unavailable but close series exists.
            if daily_ohlc.empty and not hist_series.empty:
                fallback = hist_series.copy().dropna()
                fallback_idx = pd.to_datetime(fallback.index, errors="coerce")
                daily_ohlc = pd.DataFrame(
                    {
                        "open": fallback.values,
                        "high": fallback.values,
                        "low": fallback.values,
                        "close": fallback.values,
                    },
                    index=fallback_idx.normalize() + pd.Timedelta(hours=16),
                )

            if daily_ohlc.empty and intraday_ohlc.empty:
                return

            plot_ohlc = daily_ohlc.copy()
            if not intraday_ohlc.empty:
                intraday_dates = set(pd.to_datetime(intraday_ohlc.index, errors="coerce").date)
                if not plot_ohlc.empty:
                    plot_dates = pd.Index(pd.to_datetime(plot_ohlc.index, errors="coerce").date)
                    plot_ohlc = plot_ohlc[~plot_dates.isin(intraday_dates)]
                plot_ohlc = pd.concat([plot_ohlc, intraday_ohlc], axis=0)

            plot_ohlc = plot_ohlc.sort_index()
            plot_ohlc = plot_ohlc[~plot_ohlc.index.duplicated(keep="last")]
            if plot_ohlc.empty:
                return

            # Keep the latest bar in sync between source updates.
            if live.get("price") is not None:
                last_idx = plot_ohlc.index[-1]
                px = float(live["price"])
                plot_ohlc.loc[last_idx, "close"] = px
                plot_ohlc.loc[last_idx, "high"] = max(float(plot_ohlc.loc[last_idx, "high"]), px)
                plot_ohlc.loc[last_idx, "low"] = min(float(plot_ohlc.loc[last_idx, "low"]), px)

            if go is not None:
                plot_df = (
                    plot_ohlc.reset_index()
                    .rename(columns={"index": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close"})
                )
                if "Date" not in plot_df.columns:
                    plot_df = plot_df.rename(columns={plot_df.columns[0]: "Date"})

                for c in ["Open", "High", "Low", "Close"]:
                    plot_df[c] = pd.to_numeric(plot_df[c], errors="coerce")
                plot_df = plot_df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
                if plot_df.empty:
                    return

                fig = st.session_state.get("stock_details_fig")
                fig_ticker = st.session_state.get("stock_details_fig_ticker")
                must_rebuild = fig is None or fig_ticker != ticker

                session_dates = sorted(pd.Index(pd.to_datetime(plot_df["Date"], errors="coerce").dt.date).unique())
                if session_dates:
                    last_session_date = session_dates[-1]
                    prev_session_date = session_dates[-2] if len(session_dates) >= 2 else session_dates[-1]
                else:
                    last_session_date = pd.Timestamp.now().date()
                    prev_session_date = last_session_date
                range_start = pd.Timestamp(prev_session_date) + pd.Timedelta(hours=9, minutes=30)
                range_end = pd.Timestamp(last_session_date) + pd.Timedelta(hours=16)

                visible = plot_df[(plot_df["Date"] >= range_start) & (plot_df["Date"] <= range_end)]
                if visible.empty:
                    visible = plot_df.tail(min(len(plot_df), 390))
                    range_start = pd.Timestamp(visible["Date"].iloc[0])
                    range_end = pd.Timestamp(visible["Date"].iloc[-1])
                ymin = float(visible["Low"].min())
                ymax = float(visible["High"].max())
                ypad = max((ymax - ymin) * 0.08, max(abs(ymin), abs(ymax)) * 0.002, 0.25)
                yrange = [ymin - ypad, ymax + ypad]

                if must_rebuild:
                    fig = go.Figure()
                    fig.add_trace(
                        go.Candlestick(
                            x=plot_df["Date"],
                            open=plot_df["Open"],
                            high=plot_df["High"],
                            low=plot_df["Low"],
                            close=plot_df["Close"],
                            name=ticker,
                            uid=f"{ticker}_candles",
                            increasing_line_color="#158a4a",
                            decreasing_line_color="#c03a2b",
                            increasing_fillcolor="rgba(21,138,74,0.26)",
                            decreasing_fillcolor="rgba(192,58,43,0.26)",
                            whiskerwidth=0.45,
                        )
                    )
                    apply_standard_line_chart_layout(fig, "Price (USD)")
                    fig.update_layout(showlegend=False, uirevision=f"stock_details_{ticker}")
                    fig.update_layout(height=460, margin={"l": 18, "r": 12, "t": 10, "b": 48})
                    fig.update_xaxes(rangeslider_visible=False)
                    fig.update_yaxes(tickprefix="$", tickformat=",.2f")
                    fig.update_xaxes(range=[range_start, range_end], autorange=False)
                    fig.update_yaxes(range=yrange, autorange=False)
                    vis_start, vis_end = _read_visible_x_range(fig, range_start, range_end)
                    apply_stock_intraday_axis_format(fig, plot_df["Date"], vis_start, vis_end)
                    st.session_state["stock_details_fig"] = fig
                    st.session_state["stock_details_fig_ticker"] = ticker
                else:
                    # Replace trace data so stale/off-hours x-points are dropped.
                    # uirevision keeps user's zoom/pan across refreshes.
                    fig.data[0].x = plot_df["Date"].tolist()
                    fig.data[0].open = plot_df["Open"].tolist()
                    fig.data[0].high = plot_df["High"].tolist()
                    fig.data[0].low = plot_df["Low"].tolist()
                    fig.data[0].close = plot_df["Close"].tolist()
                    fig.data[0].name = ticker
                    fig.data[0].uid = f"{ticker}_candles"
                    # Re-apply label rules without changing zoom range.
                    vis_start, vis_end = _read_visible_x_range(fig, range_start, range_end)
                    apply_stock_intraday_axis_format(fig, plot_df["Date"], vis_start, vis_end)

                st.plotly_chart(
                    fig,
                    width="stretch",
                    key="stock_details_chart",
                    config={"scrollZoom": True, "displaylogo": False, "doubleClick": "reset"},
                )
            else:
                st.line_chart(plot_ohlc["close"].rename(ticker))

        close_df = all_close_df.reindex(columns=tickers)
        if detail_ticker:
            series = fetch_inception_close(detail_ticker)
            render_stock_details_chart(detail_ticker, series)
            if not series.empty:
                if len(series) > 1:
                    ret_1d = (series.iloc[-1] / series.iloc[-2]) - 1
                else:
                    ret_1d = float("nan")
            if len(series) > 30:
                ret_1m = (series.iloc[-1] / series.iloc[-22]) - 1
            else:
                ret_1m = float("nan")
            if len(series) > 90:
                ret_3m = (series.iloc[-1] / series.iloc[-64]) - 1
            else:
                ret_3m = float("nan")
            if len(series) > 180:
                ret_6m = (series.iloc[-1] / series.iloc[-127]) - 1
            else:
                ret_6m = float("nan")
            if not series.empty:
                ret_1y = (series.iloc[-1] / series.iloc[0]) - 1
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("1D Return", f"{ret_1d:.2%}" if pd.notna(ret_1d) else "N/A")
                m2.metric("1M Return", f"{ret_1m:.2%}" if pd.notna(ret_1m) else "N/A")
                m3.metric("3M Return", f"{ret_3m:.2%}" if pd.notna(ret_3m) else "N/A")
                m4.metric("6M Return", f"{ret_6m:.2%}" if pd.notna(ret_6m) else "N/A")
                m5.metric("1Y Return", f"{ret_1y:.2%}")
            elif detail_ticker:
                st.warning(f"No historical data available for {detail_ticker}.")

        st.markdown("<div class='section-separator'></div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        table_hdr_col, table_count_col, _ = st.columns([2.45, 0.95, 6.60], vertical_alignment="center")
        with table_hdr_col:
            st.markdown("<div class='tight-section-title'>Beta Screener Top List: All-Index</div>", unsafe_allow_html=True)
        with table_count_col:
            st.number_input(
                "Final list count",
                min_value=1,
                max_value=200,
                value=final_count,
                step=1,
                key="final_count",
                label_visibility="collapsed",
                width=150,
            )
        ranking_placeholder = st.empty()
        ordered_final = render_aggrid_table(final_rank_df, include_indexes=True, render=True, page_size=20)
        with ranking_placeholder.container():
            if {"Ticker", "Beta"}.issubset(ordered_final.columns):
                chart_df = ordered_final[["Ticker", "Beta"]].copy()
                chart_df["Beta"] = pd.to_numeric(chart_df["Beta"], errors="coerce")
                chart_df = chart_df.dropna(subset=["Beta"])
                if not chart_df.empty:
                    chart_df["Order"] = range(len(chart_df))
                    ordered_tickers = chart_df["Ticker"].tolist()
                    chart = (
                        alt.Chart(chart_df)
                        .mark_bar()
                        .encode(
                            x=alt.X("Ticker:N", sort=ordered_tickers, title="Ticker"),
                            y=alt.Y("Beta:Q", title="Beta"),
                            color=alt.Color(
                                "Order:Q",
                                scale=alt.Scale(domain=[0, max(len(chart_df) - 1, 1)], range=["#0b6e3e", "#b8e6c8"]),
                                legend=None,
                            ),
                            tooltip=[alt.Tooltip("Ticker:N"), alt.Tooltip("Beta:Q", format=".3f")],
                        )
                        .properties(height=360)
                    )
                    st.altair_chart(chart, width="stretch")

        per_idx_hdr_col, per_idx_count_col, _ = st.columns([2.45, 0.95, 6.60], vertical_alignment="center")
        with per_idx_hdr_col:
            st.markdown("<div class='tight-section-title'>Beta Screener Top List: Per-Index</div>", unsafe_allow_html=True)
        with per_idx_count_col:
            st.number_input(
                "Individual list count",
                min_value=1,
                max_value=100,
                value=individual_count,
                step=1,
                key="individual_count",
                label_visibility="collapsed",
                width=150,
            )
        tabs = st.tabs(["S&P 500", "NASDAQ-100", "DJI"])
        sp500_df = build_index_table(per_index["sp500"], returns_df, volume_series)
        nasdaq_df = build_index_table(per_index["nasdaq"], returns_df, volume_series)
        dji_df = build_index_table(per_index["dji"], returns_df, volume_series)
        with tabs[0]:
            render_aggrid_table(sp500_df, include_indexes=False, page_size=10)
        with tabs[1]:
            render_aggrid_table(nasdaq_df, include_indexes=False, page_size=10)
        with tabs[2]:
            render_aggrid_table(dji_df, include_indexes=False, page_size=10)

    with app_tab_strategy:
        settings = load_settings()
        default_symbols = read_watchlist() or settings.default_symbols
        default_symbols_text = ",".join(default_symbols)

        st.caption(
            "Run the original 3-step workflow from the app: download data, generate SMA signals, and run backtests."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            symbols_raw = st.text_input("Symbols (comma-separated)", value=default_symbols_text, key="lab_symbols")
        with c2:
            default_start = datetime.strptime(settings.start_date, "%Y-%m-%d").date()
            start_date = st.date_input("Start date", value=default_start, key="lab_start_date")
        with c3:
            use_end = st.checkbox("Use end date", value=bool(settings.end_date), key="lab_use_end")
            default_end = datetime.strptime(settings.end_date, "%Y-%m-%d").date() if settings.end_date else date.today()
            end_date = st.date_input("End date", value=default_end, disabled=not use_end, key="lab_end_date")

        c4, c5 = st.columns(2)
        with c4:
            fast = st.number_input("Fast SMA", min_value=1, max_value=500, value=settings.fast_sma, step=1, key="lab_fast")
        with c5:
            slow = st.number_input("Slow SMA", min_value=2, max_value=1000, value=settings.slow_sma, step=1, key="lab_slow")
        visual_only = st.checkbox("Visual backtest reports only (skip CSV tables)", value=True, key="lab_visual_only")

        run_c1, run_c2 = st.columns(2)
        run_pipeline = run_c1.button("Run Backtest", type="primary", use_container_width=True)
        run_clear_reports = run_c2.button("Clear Reports", type="secondary", use_container_width=True)

        symbols = _resolve_symbols(symbols_raw, default_symbols)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d") if use_end else None

        if fast >= slow:
            st.error("Fast SMA must be lower than Slow SMA.")
        else:
            logs: list[str] = []
            summary_df = pd.DataFrame()

            if run_pipeline:
                with st.spinner("Downloading raw price history..."):
                    logs.extend(_run_get_data(symbols, start=start_str, end=end_str))

            if run_pipeline:
                with st.spinner("Generating SMA signals..."):
                    logs.extend(_run_generate_signals(symbols, fast=int(fast), slow=int(slow)))

            if run_pipeline:
                removed = _cleanup_previous_reports()
                if removed:
                    logs.append(f"cleanup reports: removed {len(removed)} file(s)")
                with st.spinner("Running backtests..."):
                    bt_logs, summary_df = _run_backtests(symbols, visual_only=visual_only)
                    logs.extend(bt_logs)
                    st.session_state["lab_summary_df"] = summary_df
            if run_clear_reports:
                removed = _cleanup_previous_reports()
                if removed:
                    logs.append(f"cleanup reports: removed {len(removed)} file(s)")
                else:
                    logs.append("cleanup reports: no files to remove")
                st.session_state["lab_summary_df"] = pd.DataFrame()

            persisted_summary = st.session_state.get("lab_summary_df")
            if isinstance(persisted_summary, pd.DataFrame) and not persisted_summary.empty:
                show = persisted_summary.copy()
                for col in ["market_return", "strategy_return", "alpha_vs_market", "max_drawdown"]:
                    if col in show.columns:
                        show[col] = pd.to_numeric(show[col], errors="coerce")
                display_cols = {
                    "symbol": "Symbol",
                    "market_return": "Market Return",
                    "strategy_return": "Strategy Return",
                    "alpha_vs_market": "Alpha Vs Market",
                    "max_drawdown": "Max Drawdown",
                }
                show = show.rename(columns=display_cols)
                st.subheader("Backtest Summary")
                for col in ["Market Return", "Strategy Return", "Alpha Vs Market", "Max Drawdown"]:
                    if col in show.columns:
                        show[col] = pd.to_numeric(show[col], errors="coerce")
                render_backtest_summary_table(show)
            _render_strategy_reports(show_csv_tables=not visual_only)
            if logs:
                st.subheader("Pipeline Logs")
                st.code("\n".join(logs), language="text")


if __name__ == "__main__":
    main()
