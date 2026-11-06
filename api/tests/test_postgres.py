"""Postgres lead sink and question log, with their retention (leads 12 months, questions 30 days).

Integration tests: they need a local Postgres in POSTGRES_TEST_URL (the tests drop and recreate the tables).
"""

import os
from urllib.parse import urlparse

import psycopg
import pytest

from app.adapters.postgres import PostgresLeadSink, PostgresQuestionLog, ensure_schema
from app.ports import Lead, LeadUnavailable, QuestionLogUnavailable

URL = os.environ.get("POSTGRES_TEST_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set POSTGRES_TEST_URL to a local Postgres")
LEAD = Lead("Jane Doe", "Acme", "jane@acme.com", "https://www.linkedin.com/in/jane-doe", "hiring", "pt")
DOWN = "postgresql://nobody:x@127.0.0.1:1/none?connect_timeout=1"


@pytest.fixture
def db():
    assert urlparse(URL).hostname in ("localhost", "127.0.0.1"), "these tests drop tables"
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS portfolio_leads, portfolio_questions")
    ensure_schema(URL)
    with psycopg.connect(URL, autocommit=True) as conn:
        yield conn


def test_saved_lead_keeps_every_field(db):
    PostgresLeadSink(URL).save(LEAD)
    row = db.execute("SELECT name, company, email, linkedin, kind, page_lang FROM portfolio_leads").fetchall()
    assert row == [("Jane Doe", "Acme", "jane@acme.com", "https://www.linkedin.com/in/jane-doe", "hiring", "pt")]


def test_leads_older_than_12_months_are_deleted(db):
    db.execute(
        "INSERT INTO portfolio_leads (created_at, name, company, email, kind, page_lang) "
        "VALUES (now() - interval '13 months', 'Old', 'Co', 'old@co.com', 'project', 'en'),"
        "       (now() - interval '11 months', 'Recent', 'Co', 'recent@co.com', 'project', 'en')"
    )
    PostgresLeadSink(URL).save(LEAD)
    assert [r[0] for r in db.execute("SELECT name FROM portfolio_leads ORDER BY created_at")] == ["Recent", "Jane Doe"]


def test_questions_are_kept_for_30_days(db):
    db.execute(
        "INSERT INTO portfolio_questions (created_at, question, page_lang) "
        "VALUES (now() - interval '31 days', 'old', 'en'), (now() - interval '29 days', 'recent', 'en')"
    )
    PostgresQuestionLog(URL).record("Is he open to roles?", "pt")
    rows = db.execute("SELECT question, page_lang FROM portfolio_questions ORDER BY created_at").fetchall()
    assert rows == [("recent", "en"), ("Is he open to roles?", "pt")]


def test_database_down_is_reported_as_unavailable():
    with pytest.raises(LeadUnavailable):
        PostgresLeadSink(DOWN).save(LEAD)
    with pytest.raises(QuestionLogUnavailable):
        PostgresQuestionLog(DOWN).record("hi", "en")
