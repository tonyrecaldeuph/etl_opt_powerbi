# etl/tests/test_ingest.py
import pytest
from pathlib import Path
from etl.ingest import ingest_csv

CSV = (
    "N° CONTRATO,CÉDULA,MONTO POR COBRAR,VALOR EN MORA,DIAS IMPAGO\n"
    "C-1,0102030405,100,0,5\n"
    "C-2,0607080910,0,0,\n"
)

@pytest.mark.db
def test_ingest_csv_carga_staging(db_conn, tmp_path):
    f = tmp_path / "RV_SAS 22-06-2026.csv"
    f.write_text(CSV, encoding="utf-8")
    n = ingest_csv(db_conn, f, empresa="SAS", fecha_carga="2026-06-22", delimitador=",")
    assert n == 2
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM staging.reporte_cobranza "
                    "WHERE empresa='SAS' AND fecha_carga='2026-06-22'")
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT monto_por_cobrar FROM staging.reporte_cobranza "
                    "WHERE numero_contrato='C-1' AND fecha_carga='2026-06-22'")
        assert cur.fetchone()[0] == 100
