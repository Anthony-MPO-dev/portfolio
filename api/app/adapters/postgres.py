"""Postgres lead sink and question log.

Responsibility: store contact-form leads (kept 12 months) and redacted questions (kept 30 days). Each write first
deletes what is past its retention, so the tables never grow old data without a cron. A database that can't be
reached raises the port's Unavailable exception. One short connection per write: traffic is a few hundred writes a
day at most.
Public API: ensure_schema, PostgresLeadSink, PostgresQuestionLog.
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


LEADS_KEPT = "12 months"
QUESTIONS_KEPT = "30 days"


def _write(url: str, table: str, kept: str, insert: str, values: tuple) -> None:
    """Delete what is past retention, then insert. Raises psycopg.Error when the database can't be reached."""
    with psycopg.connect(url, connect_timeout=5) as conn:
        conn.execute(f"DELETE FROM {table} WHERE created_at < now() - %s::interval", (kept,))
        conn.execute(insert, values)


class PostgresLeadSink:
    def __init__(self, url: str):
        self.url = url

    def save(self, lead: Lead) -> None:
        try:
            _write(
                self.url,
                "portfolio_leads",
                LEADS_KEPT,
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
                "portfolio_questions",
                QUESTIONS_KEPT,
                "INSERT INTO portfolio_questions (question, page_lang) VALUES (%s, %s)",
                (question, page_lang),
            )
        except psycopg.Error as error:
            raise QuestionLogUnavailable() from error
