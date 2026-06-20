# Initial Decisions

Each item starts as `Proposed` until reviewed.

## Technology Stack

### Backend

Status: Proposed

Use Java + Spring Boot for the main backend.

Reasons:

- The user is already comfortable with Java.
- Spring Boot is well suited for a local API server, scheduled jobs, database access, and external REST/WebSocket integrations.
- Broker API secrets and trading safety controls should live server-side, not in the browser.

### Quant Runtime

Status: Proposed

Use Python for data analysis, strategy calculation, and backtesting modules.

Reasons:

- Python has stronger stock-data, numerical, and backtesting library support.
- User-defined strategies are easier to prototype in Python.
- This keeps strategy logic easier to test separately from the web app.

Initial integration options:

1. Start simple: backend invokes Python jobs through a controlled command interface.
2. Later: move Python into a small internal worker service if needed.

### Web Client

Status: Proposed

Use SvelteKit with TypeScript.

Reasons:

- The user has some prior exposure to Svelte.
- SvelteKit is productive for local dashboards and forms.
- The UI can remain thin: display data, configure strategies, run jobs, and show results.

### Database

Status: Proposed

Use MySQL 8.4 LTS locally, preferably through Docker Compose.

Reasons:

- MySQL matches the user's current preference.
- MySQL 8.4 is an LTS line, better suited than innovation releases for a long-running local project.
- Docker Compose makes setup repeatable and avoids machine-specific install drift.

Possible future additions:

- DuckDB or Parquet files for fast research snapshots.
- PostgreSQL/TimescaleDB only if MySQL becomes a bottleneck for time-series workloads.

### Broker API

Status: Proposed

Use Korea Investment & Securities Open API as the first broker integration.

Initial usage order:

1. OAuth/token and configuration handling.
2. Market data read APIs.
3. WebSocket real-time quote ingestion.
4. Account read-only APIs.
5. Paper-trading executor.
6. Live order APIs.

### Historical Data Sources

Status: Proposed

Use multiple sources depending on data type:

- KIS Open API: broker-aligned current quotes, real-time data, account/trading.
- FinanceDataReader: early historical daily data and symbol lists.
- pykrx: Korean market OHLCV and market data checks.
- OpenDART: financial statements, disclosures, fundamentals.
- yfinance: US market or benchmark research only, with license/terms caution.

The app should store provider metadata with imported data so that later discrepancies can be traced.

## Initial Algorithm Families

Status: Proposed

Built-in algorithms should start with explainable strategies:

- Momentum: recent relative strength, moving average trend, breakout.
- Value: PER/PBR/dividend yield based filters when reliable fundamentals are available.
- Quality: ROE, operating margin, debt ratio, earnings stability.
- Low volatility: lower drawdown or volatility among liquid stocks.
- Liquidity and volume: volume surge, turnover, trading value filters.
- Supply/demand: foreign/institution net buying, program trading, investor flow data if available.
- Risk filters: trading halt, management issue, low liquidity, extreme gap, abnormal volatility.

No strategy should be treated as universally good. Each strategy needs:

- intent
- required data
- signal rules
- risk/failure cases
- default parameters
- backtest assumptions

## Repository And Secrets

Status: Proposed

The GitHub repository should be private at first.

Secrets must never be committed. Use local `.env` files and provide only `.env.example`.

The provided URL should be corrected to:

https://github.com/sebastian-ryu/quantmate

