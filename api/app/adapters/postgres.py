"""Postgres lead sink and question log.

Responsibility: store contact-form leads (kept 12 months) and redacted questions (kept 30 days). purge_expired
deletes what is past retention; the API runs it at startup and every few hours, so old data goes even with no
traffic. forget_lead deletes a person's leads on request. A database that can't be reached raises the port's
Unavailable exception. One short connection per write: traffic is a few hundred writes a day at most.
Admin, from the API container: `python -m app.adapters.postgres forget-lead someone@example.com` or `... purge`
(reads DATABASE_URL).
Public API: ensure_schema, purge_expired, forget_lead, PostgresLeadSink, PostgresQuestionLog.
Used by: the API composition (app.main).
Depends on: psycopg 3, app.ports.
Tests: tests/test_postgres.py (needs a local Postgres in POSTGRES_TEST_URL).
"""

import psycopg

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


def ensure_schema(url: str) -> None:
    with psycopg.connect(url, autocommit=True, connect_timeout=5) as conn:
        conn.execute(SCHEMA)


KEPT = {"portfolio_leads": "12 months", "portfolio_questions": "30 days"}


def _write(url: str, sql: str, values: tuple) -> int:
    """Run one statement and return the rows it touched. Raises psycopg.Error when the database is unreachable."""
    with psycopg.connect(url, connect_timeout=5) as conn:
        return conn.execute(sql, values).rowcount


def purge_expired(url: str) -> None:
    for table, kept in KEPT.items():
        _write(url, f"DELETE FROM {table} WHERE created_at < now() - %s::interval", (kept,))


def forget_lead(url: str, email: str) -> int:
    """Delete every lead with this e-mail (any case) and return how many there were."""
    return _write(url, "DELETE FROM portfolio_leads WHERE lower(email) = lower(%s)", (email.strip(),))


class PostgresLeadSink:
    def __init__(self, url: str):
        self.url = url

    def save(self, lead: Lead) -> None:
        try:
            _write(
                self.url,
                "INSERT INTO portfolio_leads (name, company, email, linkedin, kind, page_lang) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (lead.name, lead.company, lead.email, lead.linkedin, lead.kind, lead.page_lang),
            )
        except psycopg.Error as error:
            raise LeadUnavailable() from error


class PostgresQuestionLog:
    def __init__(self, url: str):
        self.url = url

    def record(self, question: str, page_lang: str) -> None:
        try:
            _write(
                self.url,
                "INSERT INTO portfolio_questions (question, page_lang) VALUES (%s, %s)",
                (question, page_lang),
            )
        except psycopg.Error as error:
            raise QuestionLogUnavailable() from error


if __name__ == "__main__":
    import os
    import sys

    match sys.argv[1:]:
        case ["forget-lead", email]:
            print(f"deleted {forget_lead(os.environ['DATABASE_URL'], email)} lead(s)")
        case ["purge"]:
            purge_expired(os.environ["DATABASE_URL"])
            print("purged")
        case _:
            sys.exit("usage: python -m app.adapters.postgres forget-lead EMAIL | purge")
