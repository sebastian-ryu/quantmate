# QuantMate

QuantMate is a local-first web application for stock screening, strategy research, backtesting, and optional automated trading.

The first target market is Korean equities. The architecture should keep future US market support in mind, but the initial implementation must stay focused on Korean stock data, algorithmic screening, and safe broker integration.

## Current Status

This repository is in the planning phase.

Start with these documents:

- [Project Brief](docs/00-project-brief.md)
- [Initial Decisions](docs/01-initial-decisions.md)
- [TODO](docs/02-todo.md)
- [Open Questions](docs/03-open-questions.md)
- [Working Rules](docs/04-working-rules.md)
- [References](docs/05-references.md)
- [Local Setup](docs/06-local-setup.md)

## Safety Position

This project is software for research and automation. It is not investment advice.

Live trading must remain disabled until these are implemented and reviewed:

- paper-trading mode
- order size limits
- per-day loss and order-count limits
- kill switch
- audit log for all generated signals and orders
- explicit user confirmation before enabling live orders
