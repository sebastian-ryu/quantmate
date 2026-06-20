# Project Brief

## Goal

Build a local web application for stock investment research, stock screening, strategy backtesting, and optional automated trading.

The first useful product should help select stocks using explainable algorithms. Automated trading is an optional later feature and must be guarded by strong safety controls.

## Product Priorities

1. Collect and normalize stock-related data.
2. Store reusable data locally where practical.
3. Provide built-in stock selection algorithms commonly used in quant investing and trading.
4. Explain each algorithm enough for the user to understand what it looks for and when it can fail.
5. Allow user-defined strategies.
6. Backtest strategies before using them in live or paper trading.
7. Integrate Korea Investment & Securities Open API for real-time data and, later, trading.
8. Support Korean equities first.
9. Keep US stock support possible, but do not build it first.

## Non-Goals For The First Version

- Mobile app support.
- Cloud deployment.
- Multi-user account management.
- Fully automated live trading from day one.
- Advanced portfolio optimization before basic screening and backtesting work.
- Paid data vendor integration unless a free/public route is insufficient.

## Key Risks

- Financial risk from live order automation.
- Data quality differences between providers.
- Survivorship bias in backtests if delisted stocks and corporate actions are ignored.
- API rate limits and broker-side policy changes.
- Secrets leakage if API keys are committed.
- Overfitting strategies to historical data.

## Safety Baseline

Live trading must be the final stage, not the initial stage.

The system should initially support these modes:

1. `research`: data collection, screening, and backtesting only.
2. `paper`: simulated order execution against market data.
3. `live-readonly`: broker account and market data integration without orders.
4. `live-trading`: real orders, disabled by default and protected by hard limits.

## Initial Architecture Direction

Use a modular monolith first:

- Web client: SvelteKit.
- Backend API and orchestration: Java with Spring Boot.
- Quant/data/strategy runtime: Python module or worker.
- Database: local MySQL for app data and normalized market data.
- Broker integration: Korea Investment & Securities Open API.

This keeps the main server in Java, where the user is strongest, while using Python where the quant ecosystem is strongest.

