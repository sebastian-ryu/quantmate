from __future__ import annotations

import os


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://quantmate:quantmate@127.0.0.1:3306/quantmate",
    )

