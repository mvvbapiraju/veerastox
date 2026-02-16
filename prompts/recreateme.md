You are a senior Python engineer. Recreate the full `veerastox` repository from scratch so behavior matches exactly, including quirks and edge cases.

Project goal:
Build a stock-research toolkit with:
1. CLI pipeline for downloading OHLCV data, generating SMA crossover signals, and running a long-only backtest.
2. CLI cleanup utility for generated artifacts.
3. CLI beta screener for S&P 500 / NASDAQ-100 / DJI using Slickcharts + Yahoo Finance beta values.
4. Streamlit web app with two tabs: Live Dashboard and Strategy Lab.
5. Packaging via `pyproject.toml` with console script entrypoints.

Non-negotiable constraints:
1. Python >= 3.10.
2. Use this package structure and module names exactly.
3. Keep CLI names and argument contracts exactly.
4. Preserve exact default values and fallback behavior.
5. Preserve specific printed log message formats.
6. Preserve API/data source choices (`yfinance`, `pandas.read_html` on Slickcharts).
7. Preserve web app logic including Streamlit caching TTLs, session_state keys, and table/chart rendering behavior.
8. Preserve known inconsistencies/quirks from original code (for compatibility).
9. Do not “improve” behavior unless required to match current implementation.

Create this file tree:
.
├── .env.example
├── .gitignore
├── README.md
├── init_project.sh
├── pyproject.toml
├── requirements.txt
├── config/
│   └── watchlist.txt
├── data/
│   ├── raw/
│   └── processed/
├── reports/
├── scripts/
│   ├── __init__.py
│   ├── get_data.py
│   ├── generate_signals.py
│   ├── run_backtest.py
│   └── beta_top_indexes.py
└── src/
└── invest/
├── __init__.py
├── config.py
├── data_provider.py
├── signals.py
├── backtest.py
├── cli/
│   ├── __init__.py
│   ├── get_data.py
│   ├── generate_signals.py
│   ├── run_backtest.py
│   ├── cleanup.py
│   ├── beta_top20_sp500.py
│   ├── beta_top20_nasdaq.py
│   ├── beta_top20_dji.py
│   ├── beta_top_50_all.py
│   └── webapp.py
└── webapp/
├── __init__.py
└── app.py

File-by-file requirements:

1. `.env.example`
   DEFAULT_SYMBOLS=AAPL,MSFT,GOOGL
   START_DATE=2020-01-01
   END_DATE=
   FAST_SMA=20
   SLOW_SMA=50
   Include the same comments explaining each variable category.

2. `config/watchlist.txt`
   Default lines:
   AAPL
   MSFT
   GOOGL
   AMZN
   NVDA

3. `.gitignore`
   Include:
   __pycache__/
   *.py[cod]
   *.egg-info/
   .venv/
   .env
   .DS_Store
   .idea/
   data/raw/*.csv
   data/processed/*.csv
   reports/*.csv
   Do not ignore report PNG files.

4. `requirements.txt`
   Exactly:
   pandas>=2.2.0
   numpy>=1.26.0
   yfinance>=0.2.50
   python-dotenv>=1.0.1
   matplotlib>=3.8.0
   lxml>=5.0.0
   streamlit>=1.38.0
   streamlit-aggrid>=1.0.5
   plotly>=5.24.0

5. `pyproject.toml`
   Use setuptools build backend.
   Project name/version/description:
   name = veerastox
   version = 0.1.0
   requires-python >=3.10
   Include dependencies matching requirements.
   Add console_scripts exactly:
   veerastox-get-data = invest.cli.get_data:main
   veerastox-generate-signals = invest.cli.generate_signals:main
   veerastox-run-backtest = invest.cli.run_backtest:main
   veerastox-cleanup = invest.cli.cleanup:main
   veerastox-beta-sp500 = invest.cli.beta_top20_sp500:main
   veerastox-beta-nasdaq = invest.cli.beta_top20_nasdaq:main
   veerastox-beta-dji = invest.cli.beta_top20_dji:main
   veerastox-beta-all = invest.cli.beta_top_50_all:main
   veerastox-webapp = invest.cli.webapp:main
   Setuptools package-dir should be src.

6. `init_project.sh`
   Bash script with `set -euo pipefail`.
   Supported command whitelist exactly:
   veerastox-get-data
   veerastox-generate-signals
   veerastox-run-backtest
   veerastox-cleanup
   veerastox-beta-sp500
   veerastox-beta-nasdaq
   veerastox-beta-dji
   veerastox-beta-all
   veerastox-webapp
   Behavior:
1. `-h`/`--help` prints usage and exits 0.
2. Optional first argument may be one supported command, validated.
3. Initialization steps in order:
   python3 -m pip install -r requirements.txt
   python3 -m pip install --no-deps -e .
   python3 -m compileall src scripts
4. If supported command provided, run it with remaining args.
5. On unsupported command, print error + usage and exit 1.

7. `src/invest/__init__.py`, `src/invest/cli/__init__.py`, `src/invest/webapp/__init__.py`, `scripts/__init__.py`
   Keep minimal module docstrings.

8. `src/invest/config.py`
   Implement:
1. `Settings` dataclass with:
   default_symbols: list[str]
   start_date: str
   end_date: str | None
   fast_sma: int
   slow_sma: int
2. `_parse_symbols(raw: str) -> list[str]`: split comma, strip, uppercase, drop empties.
3. `load_settings()`:
   call `load_dotenv()`.
   default env fallbacks:
   DEFAULT_SYMBOLS fallback string "AAPL,MSFT" (note: two symbols fallback, keep this exact quirk).
   START_DATE fallback "2020-01-01"
   END_DATE fallback empty -> None
   FAST_SMA fallback "20"
   SLOW_SMA fallback "50"
4. `read_watchlist(path="config/watchlist.txt")`:
   return [] if file missing.
   read lines, strip, uppercase.
   skip blank and lines starting with `#`.

9. `src/invest/data_provider.py`
   Implement:
1. `download_symbol_history(symbol, start, end)`:
   use `yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)`.
   raise `ValueError(f"No data returned for symbol={symbol}")` if empty.
   if columns are MultiIndex, flatten to first level.
   `reset_index()`.
   lowercase all column names.
   append `symbol` column with original symbol string.
2. `save_history(df, symbol, out_dir="data/raw")`:
   mkdir parents exist_ok.
   write CSV to `data/raw/<SYMBOL>.csv`, index=False.
   return Path.

10. `src/invest/signals.py`
    Implement `add_sma_signals(df, fast_window, slow_window)`:
1. Validate `close` column exists, else raise ValueError.
2. Convert close to numeric (coerce), drop rows where close NaN, reset index.
3. If empty after cleaning, raise ValueError("No valid numeric close prices found in input data").
4. Compute:
   fast_sma = rolling mean(fast_window)
   slow_sma = rolling mean(slow_window)
   signal = 1 if fast_sma > slow_sma else 0
   position_change = signal.diff().fillna(0)

11. `src/invest/backtest.py`
    Implement:
1. `run_long_only_backtest(df)`:
   sort by date.
   daily_return = close.pct_change().fillna(0)
   strategy_return = daily_return * signal.shift(1).fillna(0)
   equity_market = (1+daily_return).cumprod()
   equity_strategy = (1+strategy_return).cumprod()
   summary dict keys:
   market_return
   strategy_return
   alpha_vs_market
   max_drawdown
   max_drawdown uses helper:
   running_max = equity_curve.cummax()
   drawdown = equity_curve / running_max - 1
   return min drawdown float.
2. `save_equity_curve_plot(bt, symbol, out_path)`:
   parse `date` as datetime errors coerce, sort by date.
   plot equity_market + equity_strategy with matplotlib.
   title: `<SYMBOL> Backtest Equity Curve`
   xlabel Date, ylabel Equity (Start = 1.0), grid alpha 0.3, legend.
   figsize (10,5), dpi 140.
   save and close.
3. `save_summary_plot(summary_df, out_path)`:
   sort by alpha_vs_market descending.
   bar chart for market vs strategy returns side-by-side.
   title `Backtest Summary by Symbol`.
   xlabel Symbol, ylabel Total Return.
   x tick labels symbols.
   horizontal zero line.
   grid on y.
   figsize (10,5), dpi 140.

12. `src/invest/cli/get_data.py`
    Args:
    --start
    --end
    --symbols comma-separated override.
    Behavior:
1. Load settings.
2. Symbols = parsed --symbols OR watchlist OR settings.default_symbols.
3. Start/end from args or settings.
4. For each symbol call download/save.
5. Print `saved {symbol}: {out_path}`.

13. `src/invest/cli/generate_signals.py`
    Args:
    --fast int
    --slow int
    --symbols
    Behavior:
1. Load settings and use env defaults when args missing.
2. Validate fast < slow else `ValueError("FAST_SMA must be lower than SLOW_SMA")`.
3. Symbols same fallback rules.
4. Ensure `data/processed` exists.
5. For each symbol:
   input `data/raw/<SYMBOL>.csv`.
   if missing: print `skip {symbol}: missing {in_path}` and continue.
   read CSV, add signals, write `data/processed/<SYMBOL>_signals.csv`, print saved message.

14. `src/invest/cli/run_backtest.py`
    Args:
    --symbols
    --visual-only (store_true)
    Behavior:
1. Symbols fallback same logic.
2. Ensure `reports` dir exists.
3. For each symbol from processed signals:
   if missing print skip message.
   run backtest.
   if not visual_only write curve CSV.
   always write curve PNG.
   append summary row.
   print:
   visual_only false -> `backtested {symbol}: {curve_csv}, {curve_png}`
   visual_only true -> `backtested {symbol}: {curve_png}`
4. After loop, if rows exist:
   summary DataFrame.
   if not visual_only write `reports/summary.csv`.
   always write `reports/summary.png`.
   print summary message similarly with one or two files.

15. `src/invest/cli/cleanup.py`
    Args:
    --raw
    --processed
    --reports
    --dry-run
    Behavior:
1. If no explicit raw/processed/reports flags: clean all three dirs.
2. Ensure each target dir exists before cleaning.
3. For each child path in target:
   if dry-run: print `would remove: {child}`
   else remove file or rmtree dir and print `removed: {child}`
4. Final print:
   dry-run -> `dry run complete: {N} path(s) would be removed`
   else -> `cleanup complete: removed {N} path(s)`

16. `scripts/get_data.py` and `scripts/generate_signals.py`
    Standalone shebang scripts mirroring the corresponding CLI module behavior exactly.

17. `scripts/run_backtest.py`
    Standalone shebang version without visual-only option and without PNG generation.
    It writes only:
    reports/<SYMBOL>_equity_curve.csv
    reports/summary.csv
    Uses same backtest core function and skip behavior.

18. `scripts/beta_top_indexes.py`
    Implement full beta screener script.
    Constants:
    INDEX_CONFIG with keys sp500/nasdaq/dji.
    URLs:
    https://www.slickcharts.com/sp500
    https://www.slickcharts.com/nasdaq100
    https://www.slickcharts.com/dowjones
    Sizes: 50/50/30.
    Labels:
    S&P 500 Top 50
    NASDAQ-100 Top 50
    DJI Top 30
    Arguments:
    --index choices all|sp500|nasdaq|dji default all
    positional optional individual_count
    positional optional final_count
    --top-per-index default 20
    --final-top default 50
    --no-fill flag
    Behavior:
1. Install browser-like User-Agent via urllib opener.
2. For each index:
   read first table with `pd.read_html(url)`, head(size), normalize Symbol uppercase.
3. Fetch beta:
   for each ticker use `yf.Ticker(ticker).info.get("beta")`; on exception beta None.
   build DataFrame columns Ticker, Company, Beta, Index.
   numeric Beta, dropna, sort descending.
4. `run_single_index` prints table title and top rows.
5. Print format:
   `\n=== <TITLE> ===`
   then `df.to_string(index=False)` or `No rows available.`
6. Dedup final ranking by ticker:
   Beta=max
   Company=first
   Indexes is sorted unique index list joined by comma (no spaces in this script).
   sort by Beta desc and head(final_top).
7. `--no-fill` uses union of displayed top lists only.
   default fill behavior uses concatenated full index universes.
8. Validation:
   top_per_index and final_top must be > 0 else ValueError.
   if `--index` != all and positional final_count provided: ValueError.
   if index != all print only single index table and exit.
   if index == all print three index tables + final combined table title:
   `Final Combined Top {len(final)} by Beta (from individual index lists)`.

19. CLI wrappers for beta scripts:
    `src/invest/cli/beta_top20_sp500.py`
    `src/invest/cli/beta_top20_nasdaq.py`
    `src/invest/cli/beta_top20_dji.py`
    `src/invest/cli/beta_top_50_all.py`
    Behavior in each:
1. Install same User-Agent opener.
2. Resolve project root via `Path(__file__).resolve().parents[3]`.
3. Locate `scripts/beta_top_indexes.py`, raise FileNotFoundError if missing.
4. Replace `sys.argv` with `[script_path, "--index", "<target>", *sys.argv[1:]]`.
5. Execute via `runpy.run_path(..., run_name="__main__")`.
   Targets: sp500 / nasdaq / dji / all.

20. `src/invest/cli/webapp.py`
    Behavior:
1. Resolve app path `src/invest/webapp/app.py`.
2. Launch streamlit in subprocess:
   `[sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]]`
3. exit code from subprocess should be propagated via SystemExit.

21. `src/invest/webapp/app.py`
    Implement all these functions with same signatures and behavior:
    install_browser_user_agent
    _dedupe_ranked
    build_final_list (cache ttl=3600)
    fetch_market_data (cache ttl=1800)
    compute_returns
    fetch_latest_volume (cache ttl=1800)
    build_index_table
    format_compact_number
    _filter_to_regular_market_hours
    _is_market_open_now
    fetch_realtime_quote (cache ttl=5)
    fetch_offhours_snapshot (cache ttl=900)
    fetch_single_ticker_close (cache ttl=30; keep even if currently unused)
    fetch_inception_close (cache ttl=900)
    fetch_intraday_close (cache ttl=5)
    _resolve_symbols
    _run_get_data
    _run_generate_signals
    _run_backtests
    _cleanup_previous_reports
    _render_strategy_reports
    render_aggrid_table
    render_backtest_summary_table
    apply_standard_line_chart_layout
    _to_naive_ny
    _read_visible_x_range
    _build_day_boundary_overlays
    apply_stock_intraday_axis_format
    main

Critical web app details to match:
1. Imports:
   base64, urllib.request, datetime/date, Path, altair, pandas, streamlit, yfinance, st_aggrid.
   Plotly import must be wrapped in try/except and set `go = None` on failure.
2. `INDEX_CONFIG` in web app only stores url+size (no labels).
3. `RETURN_WINDOWS` exactly:
   1D:1, 1W:5, 1M:21, 3M:63, 6M:126, 1Y:252.
4. `_dedupe_ranked` in web app joins index names as uppercase sorted unique with `", "` separator (with space), unlike script behavior.
5. `build_final_list`:
   for each index fetch top universe, fetch betas one by one via `yf.Ticker(...).info`.
   per-index output is head(individual_count).
   final list is deduped from concatenated full lists (not from per-index top subset).
6. `fetch_market_data` and `fetch_latest_volume` must handle yfinance MultiIndex and single-symbol shape cases exactly.
7. `_is_market_open_now` uses weekday + 09:00 to 16:00 America/New_York inclusive.
8. Real-time quote:
   prefers `fast_info` keys `last_price`, `last_volume`, `previous_close`.
   falls back to intraday history close/volume.
   returns dict with keys `price`, `change_pct`, `volume`, `asof`.
9. Off-hours snapshot:
   uses 7d/1m download.
   filters to regular market hours.
   groups by date for session close/session volume.
   returns `volume_change_pct` in addition to price/change/volume/asof.
10. Streamlit page config:
    title Veerastox, layout wide.
    inject custom CSS for block-container padding, number input spacing, section title style, green separator.
11. Two tabs:
    Live Dashboard
    Strategy Lab
12. Live Dashboard:
    caption describing count controls, deduped all-index list, chart order driven by table sorting, and 5-second auto-refresh.
    session defaults:
    individual_count from session_state default 20
    final_count from session_state default 50
    build final/per-index data + returns + volumes.
    prepare final rank table columns:
    S.No, Ticker, Company, Indexes, Beta, Volume, 1D, 1W, 1M, 3M, 6M, 1Y
13. Stock Stats section:
    selectbox label `Ticker`, options from final tickers, `accept_new_options=True`, placeholder `Select or type ticker`, key `detail_ticker`.
    width computed as `max(160, min(420, 80 + len(current_ticker_value) * 16))`.
14. Real-time metrics fragment:
    `@st.fragment(run_every="5s" if market open else None)`.
    shows Live Price / Live Change / Live Intraday Volume in colored large text.
    market-open colors use trend-vs-previous values from `st.session_state["live_quote_prev"]` and `st.session_state["live_quote_trend"]`.
    off-hours colors derive from sign of change and volume_change_pct.
    status footer includes source, refresh mode, market status text, refreshed timestamp.
15. Stock Details chart fragment:
    uses inception history, overlays 1m intraday for current day, syncs last price with live quote.
    if plotly available:
    persist figure in session_state with keys stock_details_fig / stock_details_fig_ticker.
    keep `uirevision` so zoom/pan persists.
    apply custom intraday axis formatting with day-boundary lines and date labels when span <= 3 days.
    hide midnight labels using labelalias variants including `12:00 AM` variant.
    plot config: scrollZoom true, displaylogo false, doubleClick reset.
    if plotly unavailable, fallback to `st.line_chart`.
16. Stock Details return metrics:
    show 1D/1M/3M/6M/1Y metrics using index offsets:
    1D from last/prev if len>1
    1M from last vs -22 if len>30
    3M from last vs -64 if len>90
    6M from last vs -127 if len>180
    1Y from last vs first when non-empty
17. All-index beta screener section:
    title `Beta Screener Top List: All-Index`.
    number_input for final count:
    min 1 max 200 key final_count width 150 label hidden.
    render AgGrid table.
    bar chart via Altair uses current table order, color gradient from #0b6e3e to #b8e6c8, height 360.
18. Per-index section:
    title `Beta Screener Top List: Per-Index`.
    number_input min 1 max 100 key individual_count width 150 label hidden.
    tabs S&P 500 / NASDAQ-100 / DJI with AgGrid page_size 10.
19. Strategy Lab tab:
    defaults from settings + watchlist.
    inputs:
    Symbols text
    Start date
    Use end date checkbox
    End date input (disabled unless checkbox true)
    Fast SMA number input
    Slow SMA number input
    Visual-only checkbox default True
    Buttons:
    Run Backtest (primary, full width)
    Clear Reports (secondary, full width)
    Validation: fast < slow else show error.
    Run Backtest action does:
    _run_get_data
    _run_generate_signals
    _cleanup_previous_reports
    _run_backtests
    store summary in `st.session_state["lab_summary_df"]`.
    Clear Reports removes report csv/png and resets stored summary.
20. Strategy summary/report display:
    if summary exists, rename columns to:
    Symbol, Market Return, Strategy Return, Alpha Vs Market, Max Drawdown
    render via `render_backtest_summary_table` using AgGrid.
    call `_render_strategy_reports(show_csv_tables=not visual_only)`.
    show logs in `st.code`.
21. `_render_strategy_reports` behavior:
    read reports directory.
    display PNGs and CSVs if present.
    summary.png centered using base64 HTML image block.
    summary image layout columns depend on summary row count:
    <=5 -> [1,2,1]
    <=10 -> [1.8,2.2,1.8]
    <=20 -> [1.2,2.8,1.2]
    else -> [0.8,3.4,0.8]
    remaining PNGs in 3-column grid.
    if CSV tables enabled:
    summary.csv percent-format market_return/strategy_return/alpha_vs_market/max_drawdown.
    other CSVs shown raw.

22. AgGrid formatting details:
    `render_aggrid_table`:
    sortable/filterable/resizable, pagination.
    center-align key columns.
    Beta formatted to 3 decimals.
    Volume compact formatting K/M/B.
    Returns formatted as percent.
    Grouped header `Returns` with children 1D/1W/1M/3M/6M/1Y.
    height rule: min(max(240, 90 + visible_rows*29), 800).
    return currently visible/sorted data from AgGrid response; if empty response, return original.
    `render_backtest_summary_table`:
    left-align cells.
    percent formatter for return/drawdown columns.
    pagination size 20.
    height max(110, 62 + visible_rows*29).

23. `README.md`
    Document quick start, command list, outputs, cleanup, beta commands, webapp command, setup workflow, investing caveats, and notes.
    Keep command examples:
    veerastox-cleanup
    veerastox-get-data
    veerastox-generate-signals
    veerastox-run-backtest
    veerastox-run-backtest --visual-only
    veerastox-beta-sp500 [individual_count]
    veerastox-beta-nasdaq [individual_count]
    veerastox-beta-dji [individual_count]
    veerastox-beta-all [individual_count] [final_count]
    veerastox-webapp
    Include optional initializer examples and project tree block.

Implementation quirks to preserve:
1. `config.load_settings()` fallback default symbols are only AAPL,MSFT while `.env.example` has AAPL,MSFT,GOOGL.
2. Web app imports `altair` directly but pyproject doesn’t list altair explicitly.
3. README mentions a SPY snapshot concept but current webapp implementation does not build a dedicated SPY comparison section.
4. Script and webapp final-index dedupe `Indexes` delimiter differs:
   script uses comma without spaces.
   webapp uses comma+space uppercase.
5. `fetch_single_ticker_close` exists but is not central to rendered flow; still include.

Acceptance checks:
1. `python3 -m compileall src scripts` succeeds.
2. CLI help works:
   `PYTHONPATH=src python3 -m invest.cli.get_data --help`
   `PYTHONPATH=src python3 -m invest.cli.generate_signals --help`
   `PYTHONPATH=src python3 -m invest.cli.run_backtest --help`
   `PYTHONPATH=src python3 -m invest.cli.cleanup --help`
   `PYTHONPATH=src python3 -m invest.cli.beta_top20_sp500 --help`
   `PYTHONPATH=src python3 -m invest.cli.beta_top20_nasdaq --help`
   `PYTHONPATH=src python3 -m invest.cli.beta_top20_dji --help`
   `PYTHONPATH=src python3 -m invest.cli.beta_top_50_all --help`
3. End-to-end local pipeline:
   `PYTHONPATH=src python3 -m invest.cli.get_data --symbols AAPL`
   `PYTHONPATH=src python3 -m invest.cli.generate_signals --symbols AAPL`
   `PYTHONPATH=src python3 -m invest.cli.run_backtest --symbols AAPL --visual-only`
   should generate `reports/AAPL_equity_curve.png` and `reports/summary.png`.
4. `PYTHONPATH=src python3 -m invest.cli.cleanup --dry-run` shows dry-run output.
5. `PYTHONPATH=src python3 -m invest.cli.webapp` launches Streamlit app.

Output requirements for your answer:
1. Print each created file with path and full content.
2. Ensure imports resolve and command entry points work.
3. Keep code type-hinted and equivalent to specified behavior.
4. Do not omit any file listed above.