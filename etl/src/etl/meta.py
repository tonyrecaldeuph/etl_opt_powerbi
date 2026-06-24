# etl/src/etl/meta.py
def start_run(conn, job_name, empresa, fecha_carga, bytes_file=None) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO meta.job_run (job_name, empresa, fecha_carga, bytes_file) "
            "VALUES (%s,%s,%s,%s) RETURNING run_id",
            (job_name, empresa, fecha_carga, bytes_file))
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id

def finish_run(conn, run_id, status, rows_read=None, rows_loaded=None, error_msg=None):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE meta.job_run SET finished_at=now(), status=%s, rows_read=%s, "
            "rows_loaded=%s, error_msg=%s WHERE run_id=%s",
            (status, rows_read, rows_loaded, error_msg, run_id))
    conn.commit()

def archivo_ya_procesado(conn, empresa, nombre, hash_archivo) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM meta.archivo_procesado "
            "WHERE empresa=%s AND nombre_archivo=%s AND hash_archivo=%s",
            (empresa, nombre, hash_archivo))
        return cur.fetchone() is not None

def registrar_archivo(conn, empresa, nombre, hash_archivo, fecha_carga, filas):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO meta.archivo_procesado "
            "(empresa, nombre_archivo, hash_archivo, fecha_carga, filas) "
            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (empresa, nombre, hash_archivo, fecha_carga, filas))
    conn.commit()

def crear_particion_staging(conn, fecha_carga):
    with conn.cursor() as cur:
        cur.execute("SELECT meta.crear_particion_staging(%s)", (fecha_carga,))
    conn.commit()
