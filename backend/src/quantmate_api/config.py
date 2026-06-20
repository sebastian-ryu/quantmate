from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def load_local_env() -> None:
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env", override=False)


load_local_env()


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://quantmate:quantmate@127.0.0.1:3306/quantmate",
    )
