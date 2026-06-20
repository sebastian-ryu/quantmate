# Open Questions

Answering these will determine the first MVP.

## Trading Scope

1. Should the first usable version stop at stock recommendations and backtesting, or should it include paper trading?
2. Is live trading a long-term goal only, or should the architecture prepare for it from day one?
3. Should live trading support only cash stock orders, or also ETFs, margin, credit, or derivatives?

## Investment Style

4. What holding period matters most at first?
   - intraday
   - 1-10 day swing
   - several weeks/months
   - long-term factor investing
5. Should the first algorithms favor quant/factor screening, trader-style supply/demand analysis, or a mix?
6. Is the user more interested in finding candidates before market open, during market hours, or after market close?

## Data

7. Is daily OHLCV enough for the first version?
8. Are minute bars required early?
9. Should tick/order-book data be stored, or only used temporarily for signals?
10. Which fundamentals matter first: PER/PBR/ROE, financial statements, dividends, earnings growth, analyst estimates, or disclosures?

## Strategy Authoring

11. How should custom strategies be written first?
    - Python code files
    - form-based condition builder
    - block/visual builder
    - simple rule DSL
12. Should strategies be editable from the web UI in the first version, or can they be source files initially?

## Local Environment

13. Is Docker acceptable for MySQL and local services?
14. Should the app run through one command later, such as `./dev` or `make dev`?
15. Which OS will be the main development and runtime machine?

## Broker And Account

16. Is a Korea Investment & Securities account already available for API application?
17. Should the first broker integration use mock credentials and sandbox/paper mode only?
18. What default trading limits should be hardcoded before any live order feature exists?

## GitHub

19. Should the GitHub repository be private at first?
20. Should authentication use GitHub CLI, HTTPS token, or SSH?

## UI Direction

21. Should the UI feel closer to a research dashboard, trading terminal, or simple step-by-step wizard?
22. Which screen is most important on first launch?
    - market/data status
    - recommended stocks
    - strategy builder
    - backtest results
    - portfolio/account status

