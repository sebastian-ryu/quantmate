# Working Rules

These rules are part of the project process and should be updated when the process changes.

## Documentation Rules

- Keep project decisions in repository documents.
- Update TODO before or during each implementation step.
- When design changes, check whether these files need updates:
  - `docs/00-project-brief.md`
  - `docs/01-initial-decisions.md`
  - `docs/02-todo.md`
  - `docs/03-open-questions.md`
  - `docs/04-working-rules.md`
- Add architecture decision records when a decision has meaningful long-term impact.
- Keep explanations clear enough for the user to revisit later.

## Development Rules

- Prefer small, reviewable phases.
- Do not implement live trading before data, screening, backtesting, and paper trading are reviewed.
- Keep broker credentials out of source control.
- Use `.env.example` for required environment variable names.
- Add tests around strategy calculations, data imports, and trading safety logic.
- Record assumptions in strategy documentation and backtest results.

## Trading Safety Rules

- Default mode is research-only.
- Live trading must be disabled by default.
- Every generated signal must be auditable.
- Every order request must be logged before and after broker submission.
- A kill switch must be available before live trading.
- Hard risk limits must be enforced server-side.
- The UI must clearly distinguish research, paper, read-only live, and live-trading modes.

## Data Rules

- Store source/provider information with imported data.
- Do not mix adjusted and unadjusted prices without explicit metadata.
- Track import time and data period.
- Treat free/public data as potentially inconsistent until validated.
- Backtests must document transaction cost, slippage, and rebalancing assumptions.

## Review Rules

- Review documents before scaffolding the actual app.
- Review UI alternatives before building the main screens.
- Review broker integration plan before creating real API credentials.
- Review live trading safety controls before implementing order placement.

