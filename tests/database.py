"""Integration tests require an explicit disposable loopback news database."""

import os
from psycopg.conninfo import conninfo_to_dict


def database_url():
    value = os.environ["NEWS_TEST_DATABASE_URL"]
    settings = conninfo_to_dict(value)
    if (
        settings.get("host") not in ("localhost", "127.0.0.1", "::1")
        or settings.get("hostaddr", settings["host"])
        not in ("127.0.0.1", "::1", "localhost")
        or settings.get("dbname") != "news"
        or "service" in settings
    ):
        raise ValueError(
            "NEWS_TEST_DATABASE_URL must name the loopback news database without service overrides"
        )
    return value


def drop_test_schema(store):
    from psycopg import sql

    if not store.schema.startswith("test_"):
        raise ValueError("Refusing cleanup outside a test schema")
    try:
        store.connection.execute(
            sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(store.schema))
        )
    finally:
        store.close()
