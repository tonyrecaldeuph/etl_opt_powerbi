# etl/src/etl/config.py
import os
from dataclasses import dataclass
from pathlib import Path
import yaml
from dotenv import load_dotenv

@dataclass
class EmpresaCfg:
    nombre: str
    inbox: str
    patron: str
    delimitador: str
    encoding: str

@dataclass
class AppConfig:
    empresas: dict[str, EmpresaCfg]
    procesados: str

def load_config(path: str | Path) -> AppConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    empresas = {
        nombre: EmpresaCfg(
            nombre=nombre,
            inbox=e["inbox"],
            patron=e["patron"],
            delimitador=e.get("delimitador", ","),
            encoding=e.get("encoding", "utf-8"),
        )
        for nombre, e in data["empresas"].items()
    }
    return AppConfig(empresas=empresas, procesados=data["procesados"])

def database_url() -> str:
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no está definida (.env)")
    return url
