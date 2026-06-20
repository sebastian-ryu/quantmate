# Open Questions

Answering these will determine the first MVP. Resolved answers are kept here so design decisions remain traceable.

## Resolved Answers

- First MVP includes stock recommendations, backtesting, and optional paper trading.
- Paper trading means simulated trading and must be user-selectable, not mandatory.
- The product should eventually support intraday, swing, medium-term, and long-term quant styles.
- The first implementation should ship several built-in strategies before adding a custom web strategy builder.
- A web UI condition builder is desirable later, even if it starts with limited freedom.
- The repository exists at https://github.com/sebastian-ryu/quantmate.
- User-facing summaries should be concise.
- Ask one question at a time when possible.
- Python backend is preferred for reconsideration because the project already uses Python for strategy/data/backtesting.
- MySQL will run through Docker Compose.

## Trading Scope

1. Resolved: first usable version includes recommendations, backtesting, and optional paper trading.
2. Is live trading a long-term goal only, or should the architecture prepare for it from day one?
3. Should live trading support only cash stock orders, or also ETFs, margin, credit, or derivatives?

## Investment Style

4. Resolved: support multiple styles over time: intraday, 1-10 day swing, several weeks/months, and long-term factor investing.
5. Should the first algorithms favor quant/factor screening, trader-style supply/demand analysis, or a mix?
6. Is the user more interested in finding candidates before market open, during market hours, or after market close?

## Data

7. Partially resolved: choose initial data based on strategy needs. Practical order is daily OHLCV first, then fundamentals/supply-demand data, then minute/intraday data.
8. Are minute bars required early?
9. Should tick/order-book data be stored, or only used temporarily for signals?
10. Which fundamentals matter first: PER/PBR/ROE, financial statements, dividends, earnings growth, analyst estimates, or disclosures?

## Strategy Authoring

11. Resolved for MVP: provide several built-in strategies first.
12. Resolved for later: add a limited web UI condition builder after built-in strategies and backtesting are stable.

## Local Environment

13. Resolved: use Docker Compose for MySQL and local services.
14. Should the app run through one command later, such as `./dev` or `make dev`?
15. Which OS will be the main development and runtime machine?

## Broker And Account

16. Is a Korea Investment & Securities account already available for API application?
17. Should the first broker integration use mock credentials and sandbox/paper mode only?
18. What default trading limits should be hardcoded before any live order feature exists?

## GitHub

19. Repository exists. Visibility still needs to be recorded.
20. Should authentication use GitHub CLI, HTTPS token, or SSH?

## UI Direction

21. Should the UI feel closer to a research dashboard, trading terminal, or simple step-by-step wizard?
22. Which screen is most important on first launch?
    - market/data status
    - recommended stocks
    - strategy builder
    - backtest results
    - portfolio/account status
