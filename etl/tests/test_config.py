# etl/tests/test_config.py
from pathlib import Path
from etl.config import load_config

def test_load_config(tmp_path):
    yaml_text = (
        "empresas:\n"
        "  SAS:\n"
        "    inbox: 'X:/in/SAS'\n"
        "    patron: 'RV_SAS *.csv'\n"
        "    delimitador: ','\n"
        "    encoding: 'utf-8'\n"
        "procesados: 'X:/in/proc'\n"
    )
    f = tmp_path / "empresas.yaml"
    f.write_text(yaml_text, encoding="utf-8")
    cfg = load_config(f)
    assert cfg.procesados == "X:/in/proc"
    assert cfg.empresas["SAS"].patron == "RV_SAS *.csv"
    assert cfg.empresas["SAS"].delimitador == ","
