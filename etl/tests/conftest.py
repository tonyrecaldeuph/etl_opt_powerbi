# etl/tests/conftest.py
import os
import pytest
import psycopg2
from dotenv import load_dotenv

load_dotenv()  # carga etl/.env cuando pytest corre desde el dir etl

@pytest.fixture
def db_conn():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL no definida; se omiten tests de BD")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    yield conn
    conn.close()
