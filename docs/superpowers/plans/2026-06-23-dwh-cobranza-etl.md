# DWH Cobranza — ETL CSV → PostgreSQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el ETL en Python que ingiere los CSV de cobranza de SAS y SCC a PostgreSQL (staging → core estrella), aplicando las reglas de exclusión/clasificación, con snapshots diarios históricos listos para consumir en Power BI.

**Architecture:** Paquete Python con lógica pura testeable (normalización de columnas, motor de reglas) separada de la capa de datos (carga `COPY` a staging, upsert a core). Un runner orquesta cada corrida y registra control/auditoría en el esquema `meta`. El SQL (esquemas, particiones, dimensiones, hecho y vistas BI) vive en archivos versionados. La infraestructura (VM ya provisionada, PostgreSQL, Power BI) se configura mediante checklists.

**Tech Stack:** Python 3.12, psycopg2, pandas (solo si hay que limpiar), PyYAML, python-dotenv, pytest. PostgreSQL 16 en VM Windows Server (`vm-uphone-data-gw-01`, datos en `F:`). Power BI Desktop (consumo manual).

**Spec de referencia:** `docs/superpowers/specs/2026-06-22-dwh-staging-etl-azure-design.md`

---

## File Structure

Desarrollo en el repo del proyecto (`dwh_stagin_etl/`); despliegue posterior a `C:\dwh\etl` en la VM.

```
etl/
  requirements.txt
  .env.example                  # plantilla de credenciales (DATABASE_URL)
  config/empresas.yaml          # por empresa: inbox, patrón de archivo, overrides de columnas
  src/etl/
    __init__.py
    normalize.py                # normalización de nombres de columna (puro)
    rules.py                    # motor de reglas: clasificar() + estado_dias() (puro)
    config.py                   # carga empresas.yaml + .env
    db.py                       # conexión + helpers COPY
    meta.py                     # job_run + archivo_procesado
    ingest.py                   # CSV -> staging (vía tabla temporal + COPY)
    load_core.py                # staging -> dims + fact + estado de reglas
    runner.py                   # orquestador de la corrida diaria
  tests/
    conftest.py                 # fixture de conexión a BD de test (marker 'db')
    test_normalize.py
    test_rules.py
    test_config.py
    test_ingest.py              # marker 'db'
    test_meta.py                # marker 'db'
    test_load_core.py           # marker 'db'
sql/
  01_schema_roles.sql           # esquemas + roles etl_app / bi_reader
  02_meta.sql                   # meta.job_run, meta.archivo_procesado, meta.crear_particion
  03_staging.sql                # staging.reporte_cobranza particionada
  04_core.sql                   # dimensiones + fact_cobranza_snapshot
  05_views.sql                  # core.vw_cobranza, core.vw_resumen_clasificacion
  06_postgresql.conf.md         # parámetros de tuning (32 GB RAM)
docs/
  setup-vm.md                   # checklist de infraestructura
run_etl.bat                     # entrypoint para el Programador de tareas
```

**Convenciones de columnas canónicas** (tras normalizar): `numero_contrato`, `cedula`, `dias_impago`, `valor_en_mora`, `monto_por_cobrar`, etc. La normalización produce snake_case ASCII; `empresas.yaml` permite overrides puntuales (ej. `n_contrato` → `numero_contrato`).

---

## Task 0: Scaffold del proyecto y control de versiones

**Files:**
- Create: `etl/requirements.txt`, `etl/.env.example`, `etl/src/etl/__init__.py`, `etl/tests/__init__.py`, `pytest.ini`, `.gitignore`

- [ ] **Step 1: Inicializar git (el directorio aún no es repo)**

Run:
```bash
cd "C:/Users/HP/Desktop/DESARROLLOS_UPHONE/Flujo_datos" && git init && git add docs/ && git commit -m "chore: add design spec and implementation plan"
```
Expected: repo inicializado y primer commit con la documentación existente.

- [ ] **Step 2: Crear `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
.env
etl/config/empresas.local.yaml
*.pbix
F:/dwh/inbox/**
```

- [ ] **Step 3: Crear `etl/requirements.txt`**

```
psycopg2-binary==2.9.9
pandas==2.3.2
PyYAML==6.0.2
python-dotenv==1.0.1
pytest==8.3.3
```

- [ ] **Step 4: Crear `etl/.env.example`**

```
# Copiar a etl/.env y completar. En la VM apunta a localhost.
DATABASE_URL=postgresql://etl_app:CHANGEME@localhost:5432/dwh
# BD de pruebas para los tests con marker 'db' (puede ser la misma con otro esquema)
TEST_DATABASE_URL=postgresql://etl_app:CHANGEME@localhost:5432/dwh_test
```

- [ ] **Step 5: Crear `pytest.ini` (registra el marker `db`)**

```ini
[pytest]
markers =
    db: requiere conexión a PostgreSQL (TEST_DATABASE_URL)
testpaths = etl/tests
```

- [ ] **Step 6: Crear paquetes vacíos**

`etl/src/etl/__init__.py` y `etl/tests/__init__.py` con contenido vacío.

- [ ] **Step 7: Crear y activar el entorno virtual**

Run (PowerShell):
```powershell
cd C:\Users\HP\Desktop\DESARROLLOS_UPHONE\Flujo_datos\etl; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Expected: instala dependencias sin error.

- [ ] **Step 8: Commit**

```bash
git add etl/ pytest.ini .gitignore && git commit -m "chore: scaffold etl package"
```

---

## Task 1: Normalización de nombres de columna (puro, TDD)

**Files:**
- Create: `etl/src/etl/normalize.py`
- Test: `etl/tests/test_normalize.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# etl/tests/test_normalize.py
import pytest
from etl.normalize import normalize_column, normalize_headers

@pytest.mark.parametrize("raw,expected", [
    ("N° CONTRATO", "numero_contrato"),   # override canónico
    ("CÉDULA", "cedula"),
    ("DIAS IMPAGO", "dias_impago"),
    ("MONTO POR COBRAR", "monto_por_cobrar"),
    ("VALOR EN MORA", "valor_en_mora"),
    ("OFICIAL CRÉDITO SOLICITUD", "oficial_credito_solicitud"),
    ("  Teléfono 1 ", "telefono_1"),
])
def test_normalize_column(raw, expected):
    assert normalize_column(raw) == expected

def test_normalize_headers_dedup():
    # nombres que colisionan tras normalizar reciben sufijo incremental
    assert normalize_headers(["Teléfono", "TELEFONO"]) == ["telefono", "telefono_2"]
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `cd etl && ..\etl\.venv\Scripts\python.exe -m pytest tests/test_normalize.py -v`
Expected: FAIL (`ModuleNotFoundError: etl.normalize`). Nota: ejecutar pytest con `PYTHONPATH=src`; ver Step 4.

- [ ] **Step 3: Implementar `normalize.py`**

```python
# etl/src/etl/normalize.py
import re
import unicodedata

# Overrides canónicos tras la normalización mecánica
CANONICAL_RENAMES = {
    "n_contrato": "numero_contrato",
}

def normalize_column(name: str) -> str:
    """Convierte un encabezado a snake_case ASCII; aplica overrides canónicos."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return CANONICAL_RENAMES.get(s, s)

def normalize_headers(names: list[str]) -> list[str]:
    """Normaliza una lista de encabezados, desduplicando con sufijo _2, _3, ..."""
    out: list[str] = []
    seen: dict[str, int] = {}
    for n in names:
        base = normalize_column(n)
        if base not in seen:
            seen[base] = 1
            out.append(base)
        else:
            seen[base] += 1
            out.append(f"{base}_{seen[base]}")
    return out
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run (PowerShell, fija PYTHONPATH):
```powershell
cd C:\Users\HP\Desktop\DESARROLLOS_UPHONE\Flujo_datos\etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_normalize.py -v
```
Expected: PASS (todos los casos).

- [ ] **Step 5: Commit**

```bash
git add etl/src/etl/normalize.py etl/tests/test_normalize.py && git commit -m "feat: column name normalization"
```

---

## Task 2: Motor de reglas de negocio (puro, TDD)

**Files:**
- Create: `etl/src/etl/rules.py`
- Test: `etl/tests/test_rules.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# etl/tests/test_rules.py
import math
import pytest
from etl.rules import clasificar, estado_dias

@pytest.mark.parametrize("monto,mora,esperado", [
    (0, 0, "EXCLUIDO"),
    (0, 50, "EXCLUIDO"),       # mora sin saldo -> EXCLUIDO (regla confirmada)
    (None, 0, "EXCLUIDO"),     # nulos = 0
    (100, 0, "PREVENTIVA"),
    (100, 0.01, "MORA"),
    (100, 50, "MORA"),
])
def test_clasificar(monto, mora, esperado):
    assert clasificar(monto, mora) == esperado

@pytest.mark.parametrize("dias,esperado", [
    (None, "SIN_DATO"),
    (float("nan"), "SIN_DATO"),
    (-5, "ADELANTADO"),
    (0, "AL_DIA"),
    (1, "EN_MORA"),
    (160, "EN_MORA"),
])
def test_estado_dias(dias, esperado):
    assert estado_dias(dias) == esperado
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_rules.py -v`
Expected: FAIL (`ModuleNotFoundError: etl.rules`).

- [ ] **Step 3: Implementar `rules.py`**

```python
# etl/src/etl/rules.py
import math

def _num(x) -> float:
    """Convierte a float tratando None/NaN/vacío como 0."""
    if x is None:
        return 0.0
    if isinstance(x, float) and math.isnan(x):
        return 0.0
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0

def clasificar(monto_por_cobrar, valor_en_mora) -> str:
    monto = _num(monto_por_cobrar)
    mora = _num(valor_en_mora)
    if monto == 0:
        return "EXCLUIDO"
    if mora == 0:
        return "PREVENTIVA"
    return "MORA"

def estado_dias(dias_impago) -> str:
    if dias_impago is None:
        return "SIN_DATO"
    if isinstance(dias_impago, float) and math.isnan(dias_impago):
        return "SIN_DATO"
    try:
        d = float(dias_impago)
    except (TypeError, ValueError):
        return "SIN_DATO"
    if d < 0:
        return "ADELANTADO"
    if d == 0:
        return "AL_DIA"
    return "EN_MORA"
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_rules.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add etl/src/etl/rules.py etl/tests/test_rules.py && git commit -m "feat: business rules engine (clasificacion + estado_dias)"
```

---

## Task 3: Configuración por empresa (TDD)

**Files:**
- Create: `etl/src/etl/config.py`, `etl/config/empresas.yaml`
- Test: `etl/tests/test_config.py`

- [ ] **Step 1: Crear `etl/config/empresas.yaml`**

```yaml
empresas:
  SAS:
    inbox: "F:/dwh/inbox/SAS"
    patron: "RV_SAS *.csv"
    delimitador: ","
    encoding: "utf-8"
  SCC:
    inbox: "F:/dwh/inbox/SCC"
    patron: "RV_SCC *.csv"
    delimitador: ","
    encoding: "utf-8"
procesados: "F:/dwh/inbox/procesados"
```

- [ ] **Step 2: Escribir el test que falla**

```python
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
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: etl.config`).

- [ ] **Step 4: Implementar `config.py`**

```python
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
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add etl/src/etl/config.py etl/config/empresas.yaml etl/tests/test_config.py && git commit -m "feat: per-company config loader"
```

---

## Task 4: DDL SQL — esquemas, meta, staging, core, vistas

**Files:**
- Create: `sql/01_schema_roles.sql`, `sql/02_meta.sql`, `sql/03_staging.sql`, `sql/04_core.sql`, `sql/05_views.sql`, `sql/06_postgresql.conf.md`

> Estas tareas no son TDD (DDL); su verificación es ejecutarlas contra PostgreSQL sin error y comprobar que crean los objetos.

- [ ] **Step 1: `sql/01_schema_roles.sql`**

```sql
-- Ejecutar como superusuario en la BD dwh
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS meta;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='etl_app') THEN
    CREATE ROLE etl_app LOGIN PASSWORD 'CHANGEME';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='bi_reader') THEN
    CREATE ROLE bi_reader LOGIN PASSWORD 'CHANGEME';
  END IF;
END $$;

GRANT ALL ON SCHEMA staging, core, meta TO etl_app;
GRANT USAGE ON SCHEMA core TO bi_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT SELECT ON TABLES TO bi_reader;
```

- [ ] **Step 2: `sql/02_meta.sql`**

```sql
CREATE TABLE IF NOT EXISTS meta.job_run (
  run_id      bigserial PRIMARY KEY,
  job_name    text NOT NULL,
  empresa     text,
  fecha_carga date,
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  status      text NOT NULL DEFAULT 'running',  -- running|success|failed
  rows_read   bigint,
  rows_loaded bigint,
  bytes_file  bigint,
  error_msg   text
);

CREATE TABLE IF NOT EXISTS meta.archivo_procesado (
  id             bigserial PRIMARY KEY,
  empresa        text NOT NULL,
  nombre_archivo text NOT NULL,
  hash_archivo   text NOT NULL,
  fecha_carga    date,
  filas          bigint,
  procesado_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa, nombre_archivo, hash_archivo)
);

-- Crea la partición mensual de staging si no existe
CREATE OR REPLACE FUNCTION meta.crear_particion_staging(p_fecha date)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
  ini date := date_trunc('month', p_fecha)::date;
  fin date := (date_trunc('month', p_fecha) + interval '1 month')::date;
  nom text := format('reporte_cobranza_%s', to_char(ini, 'YYYYMM'));
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = nom) THEN
    EXECUTE format(
      'CREATE TABLE staging.%I PARTITION OF staging.reporte_cobranza FOR VALUES FROM (%L) TO (%L)',
      nom, ini, fin);
  END IF;
END $$;
```

- [ ] **Step 3: `sql/03_staging.sql`**

```sql
-- Tabla padre particionada por fecha_carga. Columnas de las reglas tipadas;
-- el resto se conserva como texto para fidelidad al CSV.
CREATE TABLE IF NOT EXISTS staging.reporte_cobranza (
  fecha_carga       date    NOT NULL,
  empresa           text    NOT NULL,
  numero_contrato   text,
  cedula            text,
  nombre_cliente    text,
  apellido_cliente  text,
  distribuidor      text,
  vendedor          text,
  marca             text,
  modelo            text,
  imei              text,
  fecha_venta       text,
  grupo             text,
  estado_dispositivo text,
  contrato_refinanciado text,
  plazo             numeric,
  costo             numeric,
  entrada           numeric,
  monto_total       numeric,
  monto_por_cobrar  numeric,
  valor_en_mora     numeric,
  valor_cuota       numeric,
  numero_cuota      numeric,
  dias_impago       numeric,
  telefono_1        text,
  telefono_2        text,
  telefono_final    text,
  telefono_ref      text,
  direccion_cliente text,
  correo_cliente    text,
  oficial_credito_solicitud text,
  oficial_credito_archivos  text,
  oficial_credito_contrato  text,
  oficial_credito_llamada   text
) PARTITION BY RANGE (fecha_carga);

CREATE INDEX IF NOT EXISTS ix_staging_fecha_emp
  ON staging.reporte_cobranza (fecha_carga, empresa);
```

- [ ] **Step 4: `sql/04_core.sql`**

```sql
CREATE TABLE IF NOT EXISTS core.dim_empresa (
  empresa_key serial PRIMARY KEY,
  empresa     text UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS core.dim_cliente (
  cliente_key serial PRIMARY KEY,
  cedula      text UNIQUE NOT NULL,
  nombre_cliente text, apellido_cliente text,
  telefono_1 text, telefono_2 text, telefono_final text, telefono_ref text,
  direccion_cliente text, correo_cliente text
);

CREATE TABLE IF NOT EXISTS core.dim_dispositivo (
  dispositivo_key serial PRIMARY KEY,
  imei  text UNIQUE,
  marca text, modelo text
);

CREATE TABLE IF NOT EXISTS core.dim_contrato (
  contrato_key serial PRIMARY KEY,
  numero_contrato text UNIQUE NOT NULL,
  fecha_venta date, grupo text, estado_dispositivo text, contrato_refinanciado text
);

CREATE TABLE IF NOT EXISTS core.dim_gestor (
  gestor_key serial PRIMARY KEY,
  distribuidor text, vendedor text,
  oficial_credito_solicitud text, oficial_credito_archivos text,
  oficial_credito_contrato text, oficial_credito_llamada text,
  UNIQUE (distribuidor, vendedor, oficial_credito_solicitud,
          oficial_credito_archivos, oficial_credito_contrato, oficial_credito_llamada)
);

CREATE TABLE IF NOT EXISTS core.fact_cobranza_snapshot (
  fecha_carga      date NOT NULL,
  empresa_key      int  NOT NULL REFERENCES core.dim_empresa,
  cliente_key      int  REFERENCES core.dim_cliente,
  dispositivo_key  int  REFERENCES core.dim_dispositivo,
  contrato_key     int  NOT NULL REFERENCES core.dim_contrato,
  gestor_key       int  REFERENCES core.dim_gestor,
  numero_contrato  text NOT NULL,
  imei             text,
  monto_por_cobrar numeric, valor_en_mora numeric, dias_impago numeric,
  costo numeric, entrada numeric, monto_total numeric,
  valor_cuota numeric, numero_cuota numeric, plazo numeric,
  clasificacion    text NOT NULL,
  estado_dias      text NOT NULL,
  PRIMARY KEY (fecha_carga, empresa_key, numero_contrato)
) PARTITION BY RANGE (fecha_carga);

CREATE INDEX IF NOT EXISTS ix_fact_clasif
  ON core.fact_cobranza_snapshot (fecha_carga, clasificacion);
```

- [ ] **Step 5: `sql/05_views.sql`**

```sql
CREATE OR REPLACE VIEW core.vw_cobranza AS
SELECT f.fecha_carga, e.empresa, f.numero_contrato, c.cedula,
       c.nombre_cliente, c.apellido_cliente,
       d.marca, d.modelo, f.imei,
       f.monto_por_cobrar, f.valor_en_mora, f.dias_impago,
       f.monto_total, f.valor_cuota, f.numero_cuota, f.plazo,
       f.clasificacion, f.estado_dias,
       k.fecha_venta, k.grupo, k.estado_dispositivo, k.contrato_refinanciado,
       g.distribuidor, g.vendedor,
       g.oficial_credito_solicitud, g.oficial_credito_archivos,
       g.oficial_credito_contrato, g.oficial_credito_llamada
FROM core.fact_cobranza_snapshot f
JOIN core.dim_empresa e   ON e.empresa_key = f.empresa_key
LEFT JOIN core.dim_cliente c ON c.cliente_key = f.cliente_key
LEFT JOIN core.dim_dispositivo d ON d.dispositivo_key = f.dispositivo_key
JOIN core.dim_contrato k  ON k.contrato_key = f.contrato_key
LEFT JOIN core.dim_gestor g ON g.gestor_key = f.gestor_key;

CREATE OR REPLACE VIEW core.vw_resumen_clasificacion AS
SELECT fecha_carga, e.empresa, f.clasificacion,
       count(*) AS contratos,
       sum(f.monto_por_cobrar) AS total_por_cobrar,
       sum(f.valor_en_mora)    AS total_mora
FROM core.fact_cobranza_snapshot f
JOIN core.dim_empresa e ON e.empresa_key = f.empresa_key
GROUP BY fecha_carga, e.empresa, f.clasificacion;

GRANT SELECT ON core.vw_cobranza, core.vw_resumen_clasificacion TO bi_reader;
```

- [ ] **Step 6: `sql/06_postgresql.conf.md`** (parámetros de tuning para 32 GB RAM)

```markdown
# Tuning de postgresql.conf (F:\PGDATA\postgresql.conf) — VM 32 GB RAM
shared_buffers = 8GB
effective_cache_size = 24GB
work_mem = 128MB
maintenance_work_mem = 2GB
max_wal_size = 8GB
checkpoint_completion_target = 0.9
wal_compression = on
random_page_cost = 1.1
autovacuum = on
# Reiniciar el servicio PostgreSQL tras cambiar este archivo.
```

- [ ] **Step 7: Verificar el DDL contra PostgreSQL**

Run (en la VM o BD de test):
```powershell
$env:PGPASSWORD="<postgres>"; psql -U postgres -d dwh -f sql/01_schema_roles.sql -f sql/02_meta.sql -f sql/03_staging.sql -f sql/04_core.sql -f sql/05_views.sql
```
Expected: sin errores; `\dt staging.*`, `\dt core.*`, `\dv core.*` muestran los objetos.

- [ ] **Step 8: Commit**

```bash
git add sql/ && git commit -m "feat: postgresql ddl (schemas, meta, staging, core, views)"
```

---

## Task 5: Capa de datos — conexión y helpers COPY (TDD con marker db)

**Files:**
- Create: `etl/src/etl/db.py`, `etl/tests/conftest.py`
- Test: `etl/tests/test_meta.py` (Task 7 lo amplía)

- [ ] **Step 1: Crear `etl/tests/conftest.py` (fixture de BD de test)**

```python
# etl/tests/conftest.py
import os
import pytest
import psycopg2

@pytest.fixture
def db_conn():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL no definida; se omiten tests de BD")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    yield conn
    conn.close()
```

- [ ] **Step 2: Escribir el test que falla**

```python
# etl/tests/test_meta.py (parte 1: conexión)
import pytest
from etl.db import get_connection, copy_rows

@pytest.mark.db
def test_get_connection_roundtrip(db_conn, monkeypatch):
    import os
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
    conn.close()
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_meta.py -v -m db`
Expected: FAIL (`ModuleNotFoundError: etl.db`) o SKIP si no hay BD de test.

- [ ] **Step 4: Implementar `db.py`**

```python
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
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_meta.py::test_get_connection_roundtrip -v`
Expected: PASS (o SKIP sin BD).

- [ ] **Step 6: Commit**

```bash
git add etl/src/etl/db.py etl/tests/conftest.py etl/tests/test_meta.py && git commit -m "feat: db connection and COPY helper"
```

---

## Task 6: Registro de control en `meta` (TDD con marker db)

**Files:**
- Create: `etl/src/etl/meta.py`
- Test: `etl/tests/test_meta.py` (ampliar)

- [ ] **Step 1: Añadir el test que falla**

```python
# etl/tests/test_meta.py (parte 2: control)
import hashlib
from etl import meta

@pytest.mark.db
def test_job_run_lifecycle(db_conn):
    run_id = meta.start_run(db_conn, "ingest", "SAS", "2026-06-22", bytes_file=123)
    meta.finish_run(db_conn, run_id, status="success", rows_read=10, rows_loaded=10)
    with db_conn.cursor() as cur:
        cur.execute("SELECT status, rows_loaded FROM meta.job_run WHERE run_id=%s", (run_id,))
        assert cur.fetchone() == ("success", 10)

@pytest.mark.db
def test_archivo_ya_procesado(db_conn):
    h = hashlib.sha256(b"x").hexdigest()
    assert meta.archivo_ya_procesado(db_conn, "SAS", "RV_SAS 22-06-2026.csv", h) is False
    meta.registrar_archivo(db_conn, "SAS", "RV_SAS 22-06-2026.csv", h, "2026-06-22", 10)
    assert meta.archivo_ya_procesado(db_conn, "SAS", "RV_SAS 22-06-2026.csv", h) is True
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_meta.py -v -m db`
Expected: FAIL (`ModuleNotFoundError: etl.meta`).

- [ ] **Step 3: Implementar `meta.py`**

```python
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
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_meta.py -v -m db`
Expected: PASS (o SKIP sin BD).

- [ ] **Step 5: Commit**

```bash
git add etl/src/etl/meta.py etl/tests/test_meta.py && git commit -m "feat: meta control (job_run, archivo_procesado, particiones)"
```

---

## Task 7: Ingesta CSV → staging (TDD con marker db)

**Files:**
- Create: `etl/src/etl/ingest.py`
- Test: `etl/tests/test_ingest.py`

**Diseño:** leer encabezado, normalizar nombres, `COPY` el CSV a una tabla temporal de texto, luego `INSERT ... SELECT` a `staging.reporte_cobranza` añadiendo `empresa`+`fecha_carga` y casteando numéricos. Esto absorbe las diferencias de columnas entre SAS y SCC.

- [ ] **Step 1: Escribir el test que falla**

```python
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
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_ingest.py -v -m db`
Expected: FAIL (`ModuleNotFoundError: etl.ingest`).

- [ ] **Step 3: Implementar `ingest.py`**

```python
# etl/src/etl/ingest.py
import csv
from pathlib import Path
from etl.normalize import normalize_headers
from etl import meta

# Columnas que se castean a numeric al pasar de temp -> staging
NUMERIC_COLS = {
    "plazo", "costo", "entrada", "monto_total", "monto_por_cobrar",
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
    return n
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_ingest.py -v -m db`
Expected: PASS (o SKIP sin BD).

- [ ] **Step 5: Commit**

```bash
git add etl/src/etl/ingest.py etl/tests/test_ingest.py && git commit -m "feat: csv ingestion to staging via COPY"
```

---

## Task 8: Carga a core — dimensiones + hecho con reglas (TDD con marker db)

**Files:**
- Create: `etl/src/etl/load_core.py`
- Test: `etl/tests/test_load_core.py`

**Diseño:** para una `(empresa, fecha_carga)` ya en staging: (1) upsert de dimensiones por clave natural, (2) crear partición del hecho, (3) insertar el hecho uniendo a las dims y calculando `clasificacion`/`estado_dias` con SQL equivalente a las reglas (validado contra `rules.py` en los tests).

- [ ] **Step 1: Escribir el test que falla**

```python
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
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_load_core.py -v -m db`
Expected: FAIL (`ModuleNotFoundError: etl.load_core`).

- [ ] **Step 3: Implementar `load_core.py`**

```python
# etl/src/etl/load_core.py
_CLASIF_SQL = """
  CASE WHEN COALESCE(monto_por_cobrar,0)=0 THEN 'EXCLUIDO'
       WHEN COALESCE(valor_en_mora,0)=0 THEN 'PREVENTIVA'
       ELSE 'MORA' END
"""
_ESTADO_SQL = """
  CASE WHEN dias_impago IS NULL THEN 'SIN_DATO'
       WHEN dias_impago < 0 THEN 'ADELANTADO'
       WHEN dias_impago = 0 THEN 'AL_DIA'
       ELSE 'EN_MORA' END
"""

def _crear_particion_fact(cur, fecha_carga):
    cur.execute("""
      DO $$ DECLARE
        ini date := date_trunc('month', %s::date)::date;
        fin date := (date_trunc('month', %s::date) + interval '1 month')::date;
        nom text := format('fact_cobranza_snapshot_%s', to_char(ini,'YYYYMM'));
      BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname=nom) THEN
          EXECUTE format('CREATE TABLE core.%I PARTITION OF core.fact_cobranza_snapshot
                          FOR VALUES FROM (%L) TO (%L)', nom, ini, fin);
        END IF;
      END $$;
    """, (fecha_carga, fecha_carga))

def load_core(conn, empresa: str, fecha_carga: str):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO core.dim_empresa (empresa) VALUES (%s) "
                    "ON CONFLICT (empresa) DO NOTHING", (empresa,))

        src = ("SELECT * FROM staging.reporte_cobranza "
               "WHERE empresa=%(e)s AND fecha_carga=%(f)s")
        params = {"e": empresa, "f": fecha_carga}

        cur.execute(f"""
          INSERT INTO core.dim_cliente (cedula, nombre_cliente, apellido_cliente,
            telefono_1, telefono_2, telefono_final, telefono_ref, direccion_cliente, correo_cliente)
          SELECT DISTINCT ON (cedula) cedula, nombre_cliente, apellido_cliente,
            telefono_1, telefono_2, telefono_final, telefono_ref, direccion_cliente, correo_cliente
          FROM ({src}) s WHERE cedula IS NOT NULL
          ON CONFLICT (cedula) DO UPDATE SET
            nombre_cliente=EXCLUDED.nombre_cliente, apellido_cliente=EXCLUDED.apellido_cliente,
            telefono_1=EXCLUDED.telefono_1, telefono_2=EXCLUDED.telefono_2,
            direccion_cliente=EXCLUDED.direccion_cliente, correo_cliente=EXCLUDED.correo_cliente
        """, params)

        cur.execute(f"""
          INSERT INTO core.dim_dispositivo (imei, marca, modelo)
          SELECT DISTINCT ON (imei) imei, marca, modelo FROM ({src}) s WHERE imei IS NOT NULL
          ON CONFLICT (imei) DO UPDATE SET marca=EXCLUDED.marca, modelo=EXCLUDED.modelo
        """, params)

        cur.execute(f"""
          INSERT INTO core.dim_contrato (numero_contrato, fecha_venta, grupo,
            estado_dispositivo, contrato_refinanciado)
          SELECT DISTINCT ON (numero_contrato) numero_contrato,
            NULLIF(trim(fecha_venta),'')::date, grupo, estado_dispositivo, contrato_refinanciado
          FROM ({src}) s WHERE numero_contrato IS NOT NULL
          ON CONFLICT (numero_contrato) DO UPDATE SET grupo=EXCLUDED.grupo,
            estado_dispositivo=EXCLUDED.estado_dispositivo
        """, params)

        cur.execute(f"""
          INSERT INTO core.dim_gestor (distribuidor, vendedor, oficial_credito_solicitud,
            oficial_credito_archivos, oficial_credito_contrato, oficial_credito_llamada)
          SELECT DISTINCT distribuidor, vendedor, oficial_credito_solicitud,
            oficial_credito_archivos, oficial_credito_contrato, oficial_credito_llamada
          FROM ({src}) s
          ON CONFLICT DO NOTHING
        """, params)

        _crear_particion_fact(cur, fecha_carga)

        # Re-cargar idempotente: borrar el snapshot del día de esa empresa y reinsertar
        cur.execute("""DELETE FROM core.fact_cobranza_snapshot f
                       USING core.dim_empresa e
                       WHERE f.empresa_key=e.empresa_key AND e.empresa=%s
                         AND f.fecha_carga=%s""", (empresa, fecha_carga))

        cur.execute(f"""
          INSERT INTO core.fact_cobranza_snapshot (fecha_carga, empresa_key, cliente_key,
            dispositivo_key, contrato_key, gestor_key, numero_contrato, imei,
            monto_por_cobrar, valor_en_mora, dias_impago, costo, entrada, monto_total,
            valor_cuota, numero_cuota, plazo, clasificacion, estado_dias)
          SELECT s.fecha_carga, e.empresa_key, c.cliente_key, d.dispositivo_key,
            k.contrato_key, g.gestor_key, s.numero_contrato, s.imei,
            s.monto_por_cobrar, s.valor_en_mora, s.dias_impago, s.costo, s.entrada,
            s.monto_total, s.valor_cuota, s.numero_cuota, s.plazo,
            {_CLASIF_SQL}, {_ESTADO_SQL}
          FROM staging.reporte_cobranza s
          JOIN core.dim_empresa e ON e.empresa = s.empresa
          LEFT JOIN core.dim_cliente c ON c.cedula = s.cedula
          LEFT JOIN core.dim_dispositivo d ON d.imei = s.imei
          JOIN core.dim_contrato k ON k.numero_contrato = s.numero_contrato
          LEFT JOIN core.dim_gestor g
            ON g.distribuidor IS NOT DISTINCT FROM s.distribuidor
           AND g.vendedor IS NOT DISTINCT FROM s.vendedor
           AND g.oficial_credito_solicitud IS NOT DISTINCT FROM s.oficial_credito_solicitud
           AND g.oficial_credito_archivos IS NOT DISTINCT FROM s.oficial_credito_archivos
           AND g.oficial_credito_contrato IS NOT DISTINCT FROM s.oficial_credito_contrato
           AND g.oficial_credito_llamada IS NOT DISTINCT FROM s.oficial_credito_llamada
          WHERE s.empresa=%s AND s.fecha_carga=%s
        """, (empresa, fecha_carga))
    conn.commit()
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_load_core.py -v -m db`
Expected: PASS (o SKIP sin BD).

- [ ] **Step 5: Commit**

```bash
git add etl/src/etl/load_core.py etl/tests/test_load_core.py && git commit -m "feat: load staging into core star model with rules"
```

---

## Task 9: Runner — orquestación de la corrida diaria

**Files:**
- Create: `etl/src/etl/runner.py`
- Test: `etl/tests/test_runner.py`

- [ ] **Step 1: Escribir el test que falla (descubrimiento de archivos, sin BD)**

```python
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
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_runner.py -v`
Expected: FAIL (`ModuleNotFoundError: etl.runner`).

- [ ] **Step 3: Implementar `runner.py`**

```python
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
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_runner.py -v`
Expected: PASS.

- [ ] **Step 5: (Opcional, con BD) prueba end-to-end del runner**

Añadir a `tests/test_runner.py`:
```python
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
```
Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest tests/test_runner.py -v -m db`
Expected: PASS (o SKIP sin BD).

- [ ] **Step 6: Commit**

```bash
git add etl/src/etl/runner.py etl/tests/test_runner.py && git commit -m "feat: daily ETL runner orchestrator"
```

---

## Task 10: Entrypoint y orquestación en Windows

**Files:**
- Create: `run_etl.bat`
- Create: `docs/setup-vm.md`

- [ ] **Step 1: Crear `run_etl.bat`**

```bat
@echo off
REM Entrypoint del ETL para el Programador de tareas de Windows
cd /d C:\dwh\etl
call .venv\Scripts\activate.bat
set PYTHONPATH=src
python -m etl.runner >> C:\dwh\logs\etl_%date:~-4%%date:~3,2%%date:~0,2%.log 2>&1
```

- [ ] **Step 2: Crear `docs/setup-vm.md` (checklist de despliegue)**

```markdown
# Checklist de despliegue en la VM (vm-uphone-data-gw-01)

1. Conectar por Azure Bastion (sin IP pública / sin RDP público).
2. Verificar disco F: (1 TB) montado; crear carpetas:
   New-Item -ItemType Directory -Force -Path C:\dwh\etl, C:\dwh\logs, F:\dwh\inbox\SAS, F:\dwh\inbox\SCC, F:\dwh\inbox\procesados, F:\dwh\backups
3. Instalar Python 3.12, Git, PostgreSQL 16 (Data Directory en F:\PGDATA).
4. Aplicar tuning de sql/06_postgresql.conf.md y reiniciar el servicio PostgreSQL.
5. Crear la BD y objetos: psql -U postgres -d dwh -f sql\01..05.sql ; cambiar passwords de etl_app/bi_reader.
6. Clonar/copiar el repo a C:\dwh\etl; crear .venv e instalar requirements.txt.
7. Copiar .env (DATABASE_URL apuntando a localhost con etl_app) y config/empresas.yaml.
8. Registrar la tarea programada diaria (DWH_ETL_Diario) que ejecuta run_etl.bat.
9. Instalar Power BI Desktop en la VM; conectar a localhost con bi_reader a core.vw_*.
10. Backups: tarea pg_dump diario a F:\dwh\backups (retención 12 meses) + Azure Backup.
```

- [ ] **Step 3: Registrar la tarea programada (en la VM)**

Run (PowerShell como Admin, en la VM):
```powershell
$action  = New-ScheduledTaskAction -Execute "C:\dwh\etl\run_etl.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
Register-ScheduledTask -TaskName "DWH_ETL_Diario" -Action $action -Trigger $trigger -Principal $principal
```
Expected: tarea creada; `Start-ScheduledTask -TaskName "DWH_ETL_Diario"` corre el ETL y `meta.job_run` registra `success`.

- [ ] **Step 4: Commit**

```bash
git add run_etl.bat docs/setup-vm.md && git commit -m "chore: windows entrypoint and deployment checklist"
```

---

## Task 11: Suite completa y validación contra datos reales

**Files:**
- Modify: ninguno (validación)

- [ ] **Step 1: Ejecutar toda la suite (sin BD)**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest -v -m "not db"`
Expected: PASS (normalize, rules, config, runner discovery).

- [ ] **Step 2: Ejecutar toda la suite (con BD de test)**

Run: `cd etl; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest -v`
Expected: PASS todo (requiere TEST_DATABASE_URL).

- [ ] **Step 3: Validar la distribución contra las cifras del spec**

Con los CSV reales de 2026-06-22 cargados, ejecutar:
```sql
SELECT empresa, clasificacion, contratos FROM core.vw_resumen_clasificacion
WHERE fecha_carga='2026-06-22' ORDER BY empresa, clasificacion;
```
Expected (de §4 del spec): SAS → EXCLUIDO 516, PREVENTIVA 29.668, MORA 11.909; SCC → EXCLUIDO 115.915, PREVENTIVA 16.782, MORA 37.539.

- [ ] **Step 4: Commit de cierre**

```bash
git add -A && git commit -m "test: full suite green and real-data distribution validated"
```

---

## Self-Review (cubierto por el plan)

- **Cobertura del spec:** get/ingesta (T7) · store/staging+core (T4,T8) · prepare/reglas+vistas (T2,T4,T8) · snapshot histórico particionado (T4,T8) · idempotencia por hash (T6,T9) · control/auditoría meta (T6) · orquestación Windows (T10) · tuning 32 GB y rutas F: (T4,T10) · consumo Power BI manual por Bastion (checklist T10/setup-vm) · velocidad ~2 GB vía COPY de CSV (T7).
- **Fase futura (no en plan):** mirror data, ML, gobierno, refresco automático con gateway — documentados en el spec §12.
- **Consistencia de tipos/nombres:** `clasificar`/`estado_dias` (T2) reutilizados como SQL equivalente en `load_core` (T8) y validados por test; `ingest_csv`, `load_core`, `meta.*` con firmas usadas igual en `runner` (T9).
```
