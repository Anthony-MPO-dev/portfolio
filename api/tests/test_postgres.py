"""Postgres lead sink and question log, with their retention (leads 12 months, questions 30 days).

Integration tests: they need a local Postgres in POSTGRES_TEST_URL (the tests drop and recreate the tables).
"""

import os
from urllib.parse import urlparse

import psycopg
import pytest

from app.adapters.postgres import (
    Db,
    PostgresLeadSink,
    PostgresQuestionLog,
    ensure_schema,
    forget_lead,
    purge_expired,
)
from app.ports import Lead, LeadUnavailable, QuestionLogUnavailable

URL = os.environ.get("POSTGRES_TEST_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set POSTGRES_TEST_URL to a local Postgres")
LEAD = Lead("Jane Doe", "Acme", "jane@acme.com", "https://www.linkedin.com/in/jane-doe", "hiring", "pt")
DOWN = "postgresql://nobody:x@127.0.0.1:1/none?connect_timeout=1"


@pytest.fixture
def pg():
    assert urlparse(URL).hostname in ("localhost", "127.0.0.1"), "these tests drop tables"
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS portfolio_leads, portfolio_questions")
    handle = Db(URL)
    handle.open(wait=True)
    ensure_schema(handle)
    yield handle
    handle.pool.close()


@pytest.fixture
def db(pg):
    with psycopg.connect(URL, autocommit=True) as conn:
        yield conn


def test_saved_lead_keeps_every_field(db, pg):
    PostgresLeadSink(pg).save(LEAD)
    row = db.execute("SELECT name, company, email, linkedin, kind, page_lang FROM portfolio_leads").fetchall()
    assert row == [("Jane Doe", "Acme", "jane@acme.com", "https://www.linkedin.com/in/jane-doe", "hiring", "pt")]


def test_purge_deletes_leads_after_12_months_and_questions_after_30_days(db, pg):
    db.execute(
        "INSERT INTO portfolio_leads (created_at, name, company, email, kind, page_lang) "
        "VALUES (now() - interval '13 months', 'Old', 'Co', 'old@co.com', 'project', 'en'),"
        "       (now() - interval '11 months', 'Recent', 'Co', 'recent@co.com', 'project', 'en')"
    )
    db.execute(
        "INSERT INTO portfolio_questions (created_at, question, page_lang) "
        "VALUES (now() - interval '31 days', 'old', 'en'), (now() - interval '29 days', 'recent', 'en')"
    )
    purge_expired(pg)
    leads = [r[0] for r in db.execute("SELECT name FROM portfolio_leads")]
    questions = [r[0] for r in db.execute("SELECT question FROM portfolio_questions")]
    assert (leads, questions) == (["Recent"], ["recent"])


def test_saved_question_keeps_its_language(db, pg):
    PostgresQuestionLog(pg).record("Is he open to roles?", "pt")
    assert db.execute("SELECT question, page_lang FROM portfolio_questions").fetchall() == [
        ("Is he open to roles?", "pt")
    ]


def test_a_lead_is_deleted_on_request_by_email(db, pg):
    sink = PostgresLeadSink(pg)
    sink.save(LEAD)
    sink.save(Lead("Jane Doe", "Acme", "JANE@acme.com", None, "project", "en"))
    sink.save(Lead("John Roe", "Beta", "john@beta.com", None, "project", "en"))
    removed = forget_lead(pg, " Jane@Acme.com ")
    assert (removed, [r[0] for r in db.execute("SELECT email FROM portfolio_leads")]) == (2, ["john@beta.com"])


def test_database_down_is_reported_as_unavailable():
    with pytest.raises(LeadUnavailable):
        PostgresLeadSink(Db(DOWN)).save(LEAD)
    with pytest.raises(QuestionLogUnavailable):
        PostgresQuestionLog(Db(DOWN)).record("hi", "en")
