import os
import subprocess
from pathlib import Path

import psycopg2
import pytest


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://sp_app:sp_app@db:5432/sp_app_test",
)

SAFE_TEST_DB_NAME = "sp_app_test"


def _database_name_from_url(url: str) -> str:
    return url.rsplit("/", 1)[-1].split("?", 1)[0]


def _psycopg2_dsn(url: str, database_name: str | None = None) -> str:
    dsn = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    if database_name is None:
        return dsn

    base = dsn.rsplit("/", 1)[0]
    return f"{base}/{database_name}"


def _ensure_safe_test_database() -> None:
    database_name = _database_name_from_url(TEST_DATABASE_URL)

    if database_name != SAFE_TEST_DB_NAME:
        raise RuntimeError(
            f"Refusing to run tests against unsafe database: {database_name!r}. "
            f"Expected {SAFE_TEST_DB_NAME!r}."
        )

    admin_dsn = _psycopg2_dsn(TEST_DATABASE_URL, "postgres")

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (SAFE_TEST_DB_NAME,),
            )
            exists = cur.fetchone() is not None

            if not exists:
                cur.execute(f'CREATE DATABASE "{SAFE_TEST_DB_NAME}"')
    finally:
        conn.close()


def _run_alembic_upgrade_head() -> None:
    backend_root = Path(__file__).resolve().parents[1]

    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DATABASE_URL

    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=str(backend_root),
        env=env,
        check=True,
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    _ensure_safe_test_database()
    _run_alembic_upgrade_head()