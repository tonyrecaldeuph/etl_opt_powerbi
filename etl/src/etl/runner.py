# etl/src/etl/runner.py
import hashlib
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from etl.config import load_config, AppConfig
from etl.db import get_connection
from etl import meta, ingest, load_core

_FECHA_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")  # DD-MM-YYYY en el nombre

def descubrir_archivos(cfg: AppConfig) -> list[tuple[str, str]]:
    out = []
    for nombre, e in cfg.empresas.items():
        for p in sorted(Path(e.inbox).glob(e.patron)):
            out.append((nombre, str(p)))
    return out

def _fecha_de_nombre(nombre: str) -> str:
    m = _FECHA_RE.search(nombre)
    if not m:
        return date.today().isoformat()
    dd, mm, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"

def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def procesar_archivo(conn, cfg, empresa, ruta) -> str:
    p = Path(ruta)
    fecha = _fecha_de_nombre(p.name)
    e = cfg.empresas[empresa]
    if meta.archivo_ya_procesado(conn, empresa, p.name, _hash(p)):
        return "omitido"
    run_id = meta.start_run(conn, "etl", empresa, fecha, bytes_file=p.stat().st_size)
    try:
        n = ingest.ingest_csv(conn, p, empresa, fecha, e.delimitador, e.encoding)
        load_core.load_core(conn, empresa, fecha)
        meta.registrar_archivo(conn, empresa, p.name, _hash(p), fecha, n)
        meta.finish_run(conn, run_id, "success", rows_read=n, rows_loaded=n)
        Path(cfg.procesados).mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(Path(cfg.procesados) / p.name))
        return "success"
    except Exception as ex:  # noqa: BLE001 - se registra y se re-lanza
        conn.rollback()
        meta.finish_run(conn, run_id, "failed", error_msg=str(ex)[:2000])
        raise

def main(config_path="config/empresas.yaml") -> int:
    cfg = load_config(config_path)
    conn = get_connection()
    fallos = 0
    try:
        for empresa, ruta in descubrir_archivos(cfg):
            try:
                print(f"[{empresa}] {ruta} -> {procesar_archivo(conn, cfg, empresa, ruta)}")
            except Exception as ex:  # noqa: BLE001
                fallos += 1
                print(f"[{empresa}] ERROR {ruta}: {ex}", file=sys.stderr)
    finally:
        conn.close()
    return 1 if fallos else 0

if __name__ == "__main__":
    raise SystemExit(main())
