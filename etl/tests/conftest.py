# etl/tests/conftest.py
import os
import pytest
import psycopg2
from dotenv import load_dotenv

load_dotenv()  # carga etl/.env cuando pytest corre desde el dir etl

_CLEAN_SQL = (
    "TRUNCATE staging.reporte_cobranza, core.fact_cobranza_snapshot, "
    "core.dim_cliente, core.dim_dispositivo, core.dim_contrato, "
    "core.dim_oficiales_credito, core.dim_distribuidor, core.dim_empresa, "
    "meta.job_run, meta.archivo_procesado "
    "RESTART IDENTITY CASCADE"
)

@pytest.fixture(autouse=True)
def _clean_db(request):
    """Aísla los tests de BD: vacía las tablas de datos antes de cada test marcado 'db'."""
    if request.node.get_closest_marker("db") is None:
        return
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        return
    conn = psycopg2.connect(url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(_CLEAN_SQL)
    conn.close()

@pytest.fixture
def db_conn():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL no definida; se omiten tests de BD")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    yield conn
    conn.close()
