# etl/src/etl/ingest.py
import csv
from pathlib import Path
from etl.normalize import normalize_headers
from etl import meta

# Columnas que se castean a numeric al pasar de temp -> staging.
# OJO: 'plazo' NO va aquí: en el origen real es texto con unidad ("13 QUINCENAS",
# "12 MESES", "26 SEMANAS"), por lo que se conserva como texto.
NUMERIC_COLS = {
    "costo", "entrada", "monto_total", "monto_por_cobrar",
    "valor_en_mora", "valor_cuota", "numero_cuota", "dias_impago",
}
# Columnas válidas en staging.reporte_cobranza (sin empresa/fecha_carga)
STAGING_COLS = {
    "numero_contrato","cedula","nombre_cliente","apellido_cliente","distribuidor",
    "vendedor","marca","modelo","imei","fecha_venta","grupo","estado_dispositivo",
    "contrato_refinanciado","plazo","costo","entrada","monto_total","monto_por_cobrar",
    "valor_en_mora","valor_cuota","numero_cuota","dias_impago","telefono_1","telefono_2",
    "telefono_final","telefono_ref","direccion_cliente","correo_cliente",
    "oficial_credito_solicitud","oficial_credito_archivos","oficial_credito_contrato",
    "oficial_credito_llamada",
}

def ingest_csv(conn, path, empresa: str, fecha_carga: str, delimitador: str = ",",
               encoding: str = "utf-8") -> int:
    path = Path(path)
    with path.open("r", encoding=encoding, newline="") as fh:
        reader = csv.reader(fh, delimiter=delimitador)
        raw_header = next(reader)
    norm = normalize_headers(raw_header)
    # columnas presentes en el CSV que existen en staging
    cols = [c for c in norm if c in STAGING_COLS]

    meta.crear_particion_staging(conn, fecha_carga)

    # La carga (TEMP + COPY + INSERT) debe correr en UNA sola transacción para que
    # la tabla temporal sobreviva al COPY. Forzamos modo transaccional sin importar
    # el autocommit del caller, y lo restauramos al terminar.
    prev_autocommit = conn.autocommit
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE _tmp_ingest (" +
                        ", ".join(f"{c} text" for c in norm) + ") ON COMMIT DROP")
            with path.open("r", encoding=encoding, newline="") as fh:
                cur.copy_expert(
                    f"COPY _tmp_ingest FROM STDIN WITH (FORMAT csv, HEADER true, "
                    f"DELIMITER '{delimitador}')", fh)
            cur.execute("SELECT count(*) FROM _tmp_ingest")
            n = cur.fetchone()[0]

            select_cols = []
            for c in cols:
                if c in NUMERIC_COLS:
                    select_cols.append(f"NULLIF(trim({c}),'')::numeric AS {c}")
                else:
                    select_cols.append(c)
            insert_cols = ["empresa", "fecha_carga"] + cols
            cur.execute(
                f"INSERT INTO staging.reporte_cobranza ({', '.join(insert_cols)}) "
                f"SELECT %s, %s, {', '.join(select_cols)} FROM _tmp_ingest",
                (empresa, fecha_carga))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = prev_autocommit
    return n
