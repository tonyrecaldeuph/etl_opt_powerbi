# etl/src/etl/db.py
import psycopg2
from etl.config import database_url

def get_connection():
    conn = psycopg2.connect(database_url())
    conn.autocommit = False
    return conn
