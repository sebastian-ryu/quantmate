# TODO

This file is the source-controlled project task list. Update it whenever scope, order, or design changes.

## Phase 0: Project Definition

- [x] Capture initial project idea in repository documents.
- [x] Record initial architecture recommendation.
- [x] Record initial safety rules.
- [x] Review first batch of open questions with the user.
- [x] Confirm first MVP scope.
- [ ] Record GitHub repository visibility.
- [x] Decide Docker-based local setup vs native installs.

## Phase 1: Repository Bootstrap

- [x] Initialize Git repository locally.
- [x] Add `.gitignore`.
- [x] Add `.env.example`.
- [x] Add Docker Compose for local MySQL.
- [x] Add basic developer setup guide.
- [ ] Add root application project structure.
- [ ] Add initial architecture decision record.
- [ ] Add license decision if repository will be public.

## Phase 2: Local Development Environment

- [ ] Choose exact Python version.
- [ ] Choose exact FastAPI version.
- [ ] Choose Node.js version for SvelteKit.
- [ ] Add local database migration tool.
- [ ] Add formatting and linting rules.

## Phase 3: Data Model And Storage

- [ ] Define market, exchange, symbol, instrument tables.
- [ ] Define daily OHLCV table.
- [ ] Define intraday/real-time data storage policy.
- [ ] Define fundamentals/disclosures storage policy.
- [ ] Define provider metadata and import audit tables.
- [ ] Define corporate action handling policy.

## Phase 4: Data Ingestion MVP

- [ ] Import Korean stock symbol list.
- [ ] Import daily OHLCV for selected stocks.
- [ ] Save imported data to MySQL.
- [ ] Add import job history.
- [ ] Add retry and rate-limit handling.
- [ ] Add basic data quality checks.

## Phase 5: Screening Engine MVP

- [ ] Define strategy interface.
- [ ] Implement built-in momentum screener.
- [ ] Implement built-in swing trading screener.
- [ ] Implement built-in long-term factor screener.
- [ ] Implement liquidity filter.
- [ ] Implement risk exclusion filter.
- [ ] Store screening runs and results.
- [ ] Return explanations for selected stocks.

## Phase 6: Backtesting MVP

- [ ] Define backtest input contract.
- [ ] Implement daily-bar backtest.
- [ ] Include transaction cost assumptions.
- [ ] Include slippage assumptions.
- [ ] Report CAGR, MDD, volatility, win rate, turnover.
- [ ] Save backtest runs and result summaries.

## Phase 7: Web UI MVP

- [ ] Review reference products and choose layout direction.
- [ ] Create dashboard view.
- [ ] Create stock universe/data status view.
- [ ] Create strategy list/detail view.
- [ ] Create screening result view.
- [ ] Create backtest result view.
- [ ] Add settings page for local configuration.

## Phase 8: KIS Read-Only Integration

- [ ] Add KIS credential configuration without committing secrets.
- [ ] Implement token issue/refresh flow.
- [ ] Add current quote API.
- [ ] Add WebSocket real-time quote connection.
- [ ] Add account read-only checks.
- [ ] Add broker API audit log.

## Phase 9: Paper Trading

- [ ] Add UI setting to enable or disable paper trading.
- [ ] Implement simulated account.
- [ ] Implement simulated order placement.
- [ ] Implement fill model.
- [ ] Record generated signals and simulated orders.
- [ ] Compare strategy intent vs simulated execution.

## Phase 10: Guarded Live Trading

- [ ] Add explicit live-trading enable switch.
- [ ] Add maximum order amount per stock.
- [ ] Add maximum daily order count.
- [ ] Add maximum daily loss stop.
- [ ] Add kill switch.
- [ ] Add manual confirmation option.
- [ ] Add live order API only after review.

## Phase 11: US Market Extension

- [ ] Decide US market data source.
- [ ] Add US symbol normalization.
- [ ] Add currency handling.
- [ ] Add US market calendar.
- [ ] Add US broker/trading plan only if needed.
