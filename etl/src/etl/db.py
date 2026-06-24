# etl/src/etl/db.py
import io
import psycopg2
from etl.config import database_url

def get_connection():
    conn = psycopg2.connect(database_url())
    conn.autocommit = False
    return conn

def copy_rows(cur, table: str, columns: list[str], rows_iter) -> int:
    """Carga filas (iterable de tuplas) a `table` vía COPY. Devuelve filas cargadas."""
    buf = io.StringIO()
    n = 0
    for row in rows_iter:
        buf.write("\t".join(_fmt(v) for v in row) + "\n")
        n += 1
    buf.seek(0)
    cols = ", ".join(columns)
    cur.copy_expert(
        f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT text, NULL '\\N')", buf)
    return n

def _fmt(v) -> str:
    if v is None:
        return "\\N"
    return str(v).replace("\\", "\\\\").replace("\t", " ").replace("\n", " ")
