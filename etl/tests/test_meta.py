# etl/tests/test_meta.py (parte 1: conexión)
import pytest
from etl.db import get_connection, copy_rows

@pytest.mark.db
def test_get_connection_roundtrip(db_conn, monkeypatch):
    import os
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
    conn.close()
