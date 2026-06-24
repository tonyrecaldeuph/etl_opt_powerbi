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

# etl/tests/test_meta.py (parte 2: control)
import hashlib
from etl import meta

@pytest.mark.db
def test_job_run_lifecycle(db_conn):
    run_id = meta.start_run(db_conn, "ingest", "SAS", "2026-06-22", bytes_file=123)
    meta.finish_run(db_conn, run_id, status="success", rows_read=10, rows_loaded=10)
    with db_conn.cursor() as cur:
        cur.execute("SELECT status, rows_loaded FROM meta.job_run WHERE run_id=%s", (run_id,))
        assert cur.fetchone() == ("success", 10)

@pytest.mark.db
def test_archivo_ya_procesado(db_conn):
    h = hashlib.sha256(b"x").hexdigest()
    assert meta.archivo_ya_procesado(db_conn, "SAS", "RV_SAS 22-06-2026.csv", h) is False
    meta.registrar_archivo(db_conn, "SAS", "RV_SAS 22-06-2026.csv", h, "2026-06-22", 10)
    assert meta.archivo_ya_procesado(db_conn, "SAS", "RV_SAS 22-06-2026.csv", h) is True
