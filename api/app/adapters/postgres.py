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


class PostgresLeadSink:
    def __init__(self, url: str, keep: str = "12 months"):
        self.url = url
        self.keep = keep

    def save(self, lead: Lead) -> None:
        try:
            with psycopg.connect(self.url, connect_timeout=5) as conn:
                conn.execute("DELETE FROM portfolio_leads WHERE created_at < now() - %s::interval", (self.keep,))
                conn.execute(
                    "INSERT INTO portfolio_leads (name, company, email, linkedin, kind, page_lang) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (lead.name, lead.company, lead.email, lead.linkedin, lead.kind, lead.page_lang),
                )
        except psycopg.Error as error:
            raise LeadUnavailable() from error


class PostgresQuestionLog:
    def __init__(self, url: str, keep: str = "30 days"):
        self.url = url
        self.keep = keep

    def record(self, question: str, page_lang: str) -> None:
        try:
            with psycopg.connect(self.url, connect_timeout=5) as conn:
                conn.execute("DELETE FROM portfolio_questions WHERE created_at < now() - %s::interval", (self.keep,))
                conn.execute(
                    "INSERT INTO portfolio_questions (question, page_lang) VALUES (%s, %s)", (question, page_lang)
                )
        except psycopg.Error as error:
            raise QuestionLogUnavailable() from error
