# etl/tests/test_runner.py
from pathlib import Path
from etl.runner import descubrir_archivos
from etl.config import AppConfig, EmpresaCfg

def test_descubrir_archivos(tmp_path):
    inbox = tmp_path / "SAS"; inbox.mkdir()
    (inbox / "RV_SAS 22-06-2026.csv").write_text("x", encoding="utf-8")
    (inbox / "otro.txt").write_text("x", encoding="utf-8")
    cfg = AppConfig(
        empresas={"SAS": EmpresaCfg("SAS", str(inbox), "RV_SAS *.csv", ",", "utf-8")},
        procesados=str(tmp_path / "proc"))
    encontrados = descubrir_archivos(cfg)
    assert len(encontrados) == 1
    assert encontrados[0][0] == "SAS"
    assert Path(encontrados[0][1]).name == "RV_SAS 22-06-2026.csv"

import os, pytest
from etl import runner
from etl.config import AppConfig, EmpresaCfg

@pytest.mark.db
def test_runner_end_to_end(db_conn, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    inbox = tmp_path / "SAS"; inbox.mkdir()
    (inbox / "RV_SAS 22-06-2026.csv").write_text(
        "N° CONTRATO,CÉDULA,MONTO POR COBRAR,VALOR EN MORA,DIAS IMPAGO\n"
        "C-1,001,100,0,5\n", encoding="utf-8")
    cfg = AppConfig(
        empresas={"SAS": EmpresaCfg("SAS", str(inbox), "RV_SAS *.csv", ",", "utf-8")},
        procesados=str(tmp_path / "proc"))
    conn = runner.get_connection()
    res = runner.procesar_archivo(conn, cfg, "SAS", str(inbox / "RV_SAS 22-06-2026.csv"))
    conn.close()
    assert res == "success"
