"""Postgres lead sink and question log.

Responsibility: store contact-form leads (kept 12 months) and redacted questions (kept 30 days). purge_expired
deletes what is past retention; the API runs it at startup and every few hours, so old data goes even with no
traffic. forget_lead deletes a person's leads on request. Every write borrows a connection from one pool (Db), and
a circuit breaker skips a dead database for 30 s after 3 failures; a database that can't be reached, or is being
skipped, raises the port's Unavailable exception.
Admin, from the API container: `python -m app.adapters.postgres forget-lead someone@example.com` or `... purge`
(reads DATABASE_URL).
Public API: Db, ensure_schema, purge_expired, forget_lead, PostgresLeadSink, PostgresQuestionLog.
Used by: the API composition (app.main).
Depends on: psycopg 3, psycopg_pool, app.breaker, app.ports.
Tests: tests/test_postgres.py (needs a local Postgres in POSTGRES_TEST_URL).
"""

import psycopg
from psycopg_pool import ConnectionPool

from app.breaker import CircuitBreaker, CircuitOpen
from app.ports import Lead, LeadUnavailable, QuestionLogUnavailable

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio_leads (
    id bigserial PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    name text NOT NULL,
    company text NOT NULL,
    email text NOT NULL,
    linkedin text,
    kind text NOT NULL,
    page_lang text NOT NULL
);
CREATE INDEX IF NOT EXISTS portfolio_leads_created_at ON portfolio_leads (created_at);
CREATE TABLE IF NOT EXISTS portfolio_questions (
    id bigserial PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    question text NOT NULL,
    page_lang text NOT NULL
);
CREATE INDEX IF NOT EXISTS portfolio_questions_created_at ON portfolio_questions (created_at);
"""


class Db:
    """The portfolio database: one connection pool (opened when the API starts, never in build) and one breaker."""

    def __init__(self, url: str, pool=None, breaker: CircuitBreaker | None = None):
        self.pool = pool or ConnectionPool(
            url, min_size=1, max_size=4, timeout=5, kwargs={"connect_timeout": 5}, open=False
        )
        self.breaker = breaker or CircuitBreaker()

    def open(self, wait: bool = False) -> None:
        self.pool.open(wait=wait)

    def write(self, sql: str, values: tuple = ()) -> int:
        """Run one statement and return the rows it touched. Raises psycopg.Error when the database is unreachable
        or being skipped."""
        try:
            return self.breaker.call(self._write, sql, values)
        except CircuitOpen as error:
            raise psycopg.OperationalError("database skipped: circuit open") from error

    def _write(self, sql: str, values: tuple) -> int:
        with self.pool.connection() as conn:
            return conn.execute(sql, values).rowcount


def ensure_schema(db: Db) -> None:
    db.write(SCHEMA)


KEPT = {"portfolio_leads": "12 months", "portfolio_questions": "30 days"}


def purge_expired(db: Db) -> None:
    for table, kept in KEPT.items():
        db.write(f"DELETE FROM {table} WHERE created_at < now() - %s::interval", (kept,))


def forget_lead(db: Db, email: str) -> int:
    """Delete every lead with this e-mail (any case) and return how many there were."""
    return db.write("DELETE FROM portfolio_leads WHERE lower(email) = lower(%s)", (email.strip(),))


class PostgresLeadSink:
    def __init__(self, db: Db):
        self.db = db

    def save(self, lead: Lead) -> None:
        try:
            self.db.write(
                "INSERT INTO portfolio_leads (name, company, email, linkedin, kind, page_lang) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (lead.name, lead.company, lead.email, lead.linkedin, lead.kind, lead.page_lang),
            )
        except psycopg.Error as error:
            raise LeadUnavailable() from error


class PostgresQuestionLog:
    def __init__(self, db: Db):
        self.db = db

    def record(self, question: str, page_lang: str) -> None:
        try:
            self.db.write(
                "INSERT INTO portfolio_questions (question, page_lang) VALUES (%s, %s)",
                (question, page_lang),
            )
        except psycopg.Error as error:
            raise QuestionLogUnavailable() from error


if __name__ == "__main__":
    import os
    import sys

    cli_db = Db(os.environ["DATABASE_URL"])
    cli_db.open(wait=True)
    match sys.argv[1:]:
        case ["forget-lead", email]:
            print(f"deleted {forget_lead(cli_db, email)} lead(s)")
        case ["purge"]:
            purge_expired(cli_db)
            print("purged")
        case _:
            sys.exit("usage: python -m app.adapters.postgres forget-lead EMAIL | purge")
