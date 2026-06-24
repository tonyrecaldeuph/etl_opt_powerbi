# etl/tests/test_load_core.py
import pytest
from etl.ingest import ingest_csv
from etl.load_core import load_core

CSV = (
    "N° CONTRATO,CÉDULA,NOMBRE CLIENTE,IMEI,MARCA,MODELO,"
    "MONTO POR COBRAR,VALOR EN MORA,DIAS IMPAGO\n"
    "C-1,001,ANA,IMEI1,XIAOMI,A1,100,0,5\n"      # PREVENTIVA / EN_MORA
    "C-2,002,LUIS,IMEI2,SAMSUNG,S2,0,50,-3\n"    # EXCLUIDO / ADELANTADO
    "C-3,003,EVA,IMEI3,APPLE,I3,200,30,0\n"      # MORA / AL_DIA
)

@pytest.mark.db
def test_load_core_clasifica(db_conn, tmp_path):
    f = tmp_path / "RV_SAS 22-06-2026.csv"
    f.write_text(CSV, encoding="utf-8")
    ingest_csv(db_conn, f, empresa="SAS", fecha_carga="2026-06-22", delimitador=",")
    load_core(db_conn, empresa="SAS", fecha_carga="2026-06-22")
    with db_conn.cursor() as cur:
        cur.execute("SELECT numero_contrato, clasificacion, estado_dias "
                    "FROM core.vw_cobranza WHERE fecha_carga='2026-06-22' "
                    "ORDER BY numero_contrato")
        assert cur.fetchall() == [
            ("C-1", "PREVENTIVA", "EN_MORA"),
            ("C-2", "EXCLUIDO", "ADELANTADO"),
            ("C-3", "MORA", "AL_DIA"),
        ]
