"""Database handle: one pool for every write, and a circuit breaker so a dead database is skipped at once (the
lead falls back to the e-mail, the question log is skipped) instead of every request waiting on it."""

from contextlib import contextmanager

import psycopg
import pytest

from app.adapters.postgres import Db


class FakePool:
    def __init__(self, down=False):
        self.down, self.taken, self.statements = down, 0, []

    @contextmanager
    def connection(self):
        self.taken += 1
        if self.down:
            raise psycopg.OperationalError("server closed")
        yield self

    def execute(self, sql, values):
        self.statements.append((sql, values))
        return type("Cursor", (), {"rowcount": 1})()


def test_writes_borrow_from_the_pool_and_return_the_row_count():
    pool = FakePool()
    db = Db("postgresql://unused", pool=pool)
    assert db.write("DELETE FROM t WHERE id = %s", (1,)) == 1
    assert db.write("DELETE FROM t WHERE id = %s", (2,)) == 1
    assert (pool.taken, len(pool.statements)) == (2, 2)


def test_a_dead_database_is_skipped_after_three_failures():
    pool = FakePool(down=True)
    db = Db("postgresql://unused", pool=pool)
    for _ in range(4):
        with pytest.raises(psycopg.OperationalError):
            db.write("SELECT 1")
    assert pool.taken == 3
