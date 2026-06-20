from sqlalchemy import create_engine

from quantmate_api.models import Base


def test_metadata_contains_initial_market_data_tables() -> None:
    assert {
        "markets",
        "instruments",
        "daily_prices",
        "data_import_jobs",
        "user_strategies",
        "backtest_runs",
    } <= set(Base.metadata.tables)


def test_models_can_create_sqlite_schema_for_contract_check() -> None:
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    assert "daily_prices" in Base.metadata.tables
