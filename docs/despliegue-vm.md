# Despliegue en la VM y guía de ejecución (`vm-uphone-data-gw-01`)

Plan de puesta en producción del ETL de cobranza y su operación diaria. Complementa
el checklist corto de [`setup-vm.md`](setup-vm.md) y el diseño en
[`docs/superpowers/specs/2026-06-22-dwh-staging-etl-azure-design.md`](superpowers/specs/2026-06-22-dwh-staging-etl-azure-design.md).

## Modelo desplegado (dimensiones)

`core.fact_cobranza_snapshot` referencia 6 dimensiones:

| Dimensión | Contenido |
|---|---|
| `dim_empresa` | Empresa emisora (SAS / SCC) |
| `dim_cliente` | Cédula + datos de contacto |
| `dim_dispositivo` | IMEI, marca, modelo |
| `dim_contrato` | N.º contrato, fecha venta, grupo, estado |
| `dim_distribuidor` | Punto de venta (columna `distribuidor` del CSV) |
| `dim_oficiales_credito` | Vendedor + 4 `oficial_credito_*` (ex `dim_gestor`) |

Vistas de consumo Power BI: `core.vw_cobranza` (detalle) y `core.vw_resumen_clasificacion` (agregado).

---

## Parte A — Plan de despliegue (una sola vez)

### A0. Prerrequisitos
- Acceso a la VM por **Azure Bastion** (sin IP pública / sin RDP expuesto).
- Disco **F:** (1 TB) montado.
- Credenciales de `postgres` (superusuario) para crear la BD y los roles.

### A1. Carpetas
```powershell
New-Item -ItemType Directory -Force -Path `
  C:\dwh\etl, C:\dwh\logs, `
  F:\dwh\inbox\SAS, F:\dwh\inbox\SCC, F:\dwh\inbox\procesados, F:\dwh\backups
```

### A2. Software base
- **Python 3.12**, **Git**, **PostgreSQL 16** (Data Directory en `F:\PGDATA`).
- Aplicar el tuning de [`sql/06_postgresql.conf.md`](../sql/06_postgresql.conf.md) y reiniciar el servicio PostgreSQL.

### A3. Base de datos y objetos
Como superusuario, crear la BD `dwh` y aplicar el DDL **en orden**:
```powershell
$env:PGPASSWORD="<postgres>"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE DATABASE dwh;"
$psql = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
foreach ($f in "01_schema_roles","02_meta","03_staging","04_core","05_views") {
  & $psql -U postgres -d dwh -v ON_ERROR_STOP=1 -f "C:\dwh\etl\sql\$f.sql"
}
```
Luego **cambiar las contraseñas** de los roles creados con `CHANGEME`:
```sql
ALTER ROLE etl_app   PASSWORD '<clave-etl>';
ALTER ROLE bi_reader PASSWORD '<clave-bi>';
```

### A4. Código y entorno virtual
```powershell
git clone <repo> C:\dwh\etl      # o copiar el repo
cd C:\dwh\etl\etl
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### A5. Configuración
1. `etl\.env` (desde `.env.example`), apuntando a **localhost** con `etl_app`:
   ```
   DATABASE_URL=postgresql://etl_app:<clave-etl>@localhost:5432/dwh
   ```
2. `etl\config\empresas.yaml` ya trae las rutas de producción (`F:\dwh\inbox\<empresa>`).

### A6. Script de arranque `C:\dwh\etl\run_etl.bat`
```bat
@echo off
setlocal
cd /d C:\dwh\etl\etl
call .venv\Scripts\activate.bat
set PYTHONPATH=src
set LOG=C:\dwh\logs\etl_%date:~-4%%date:~3,2%%date:~0,2%.log
python -c "from etl.runner import main; raise SystemExit(main('config/empresas.yaml'))" >> "%LOG%" 2>&1
```

### A7. Tarea programada diaria
```powershell
$action    = New-ScheduledTaskAction -Execute "C:\dwh\etl\run_etl.bat"
$trigger   = New-ScheduledTaskTrigger -Daily -At 6:00AM
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
Register-ScheduledTask -TaskName "DWH_ETL_Diario" -Action $action -Trigger $trigger -Principal $principal
```

### A8. Backups
- `pg_dump` diario de `dwh` a `F:\dwh\backups`, **retención 12 meses**, más **Azure Backup** de la VM.
- Probar la restauración periódicamente.

### A9. Power BI
- Instalar Power BI Desktop (en la VM por RDP, o en el equipo del analista abriendo **5432 solo para su IP/VPN** en el NSG — nunca a Internet).
- Conectar con el rol **`bi_reader`** (solo lectura) a `core.vw_cobranza` y `core.vw_resumen_clasificacion`, modo **Import**.

---

## Parte B — Guía de ejecución diaria

### Flujo automático
1. El origen deja los CSV en `F:\dwh\inbox\SAS` y `F:\dwh\inbox\SCC`.
2. A las **06:00** la tarea `DWH_ETL_Diario` corre `run_etl.bat` → `runner.py`:
   - descubre archivos por patrón (`RV_SAS *.csv`, `RV_SCC *.csv`),
   - deriva `fecha_carga` del nombre (`DD-MM-YYYY`),
   - ingesta a `staging`, carga `core` (dimensiones + hecho),
   - mueve el CSV a `F:\dwh\inbox\procesados`,
   - registra en `meta.job_run` y `meta.archivo_procesado`.
3. **Idempotencia:** un CSV ya procesado (mismo hash) se omite. Re-ejecutar es seguro.

### Ejecución manual (validación o carga fuera de horario)
```powershell
cd C:\dwh\etl\etl
& .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="src"
python -c "from etl.runner import main; raise SystemExit(main('config/empresas.yaml'))"
```
Salida esperada: una línea `-> success` por archivo. `-> omitido` = ya cargado.

### Verificación post-carga (rol `bi_reader` o `etl_app`)
```sql
-- Corridas del día
SELECT run_id, empresa, status, rows_loaded, finished_at - started_at AS duracion, error_msg
FROM meta.job_run ORDER BY run_id DESC LIMIT 10;

-- Distribución por empresa/clasificación
SELECT empresa, clasificacion, contratos FROM core.vw_resumen_clasificacion
ORDER BY empresa, clasificacion;

-- Dimensiones nuevas pobladas
SELECT count(*) FROM core.dim_distribuidor;
SELECT count(*) FROM core.dim_oficiales_credito;
```

---

## Parte C — Actualizar un esquema `core` ya existente

> **Importante.** El DDL usa `CREATE TABLE IF NOT EXISTS`: re-correr `04_core.sql` **no**
> migra una BD que ya tenía el modelo viejo (`dim_gestor` con `distribuidor`). Para
> aplicar `dim_distribuidor` + `dim_oficiales_credito` sobre un `dwh` existente:

1. **Detener** la tarea programada mientras dure la actualización.
2. **Backup previo:** `pg_dump` de `dwh`.
3. Recrear el esquema `core` (staging y meta se conservan):
   ```sql
   DROP SCHEMA core CASCADE;
   ```
   ```powershell
   foreach ($f in "01_schema_roles","04_core","05_views") {
     & $psql -U postgres -d dwh -v ON_ERROR_STOP=1 -f "C:\dwh\etl\sql\$f.sql"
   }
   ```
4. **Recargar** el hecho desde `staging` (fuente cruda, ya tiene `distribuidor`), sin re-ingestar CSV:
   ```python
   # python -c ...  (PYTHONPATH=src, DATABASE_URL a dwh)
   import psycopg2
   from etl.load_core import load_core
   conn = psycopg2.connect("postgresql://etl_app:<clave-etl>@localhost:5432/dwh")
   with conn.cursor() as cur:
       cur.execute("SELECT DISTINCT empresa, fecha_carga FROM staging.reporte_cobranza")
       pares = cur.fetchall()
   for empresa, fecha in pares:
       load_core(conn, empresa=empresa, fecha_carga=str(fecha))
   conn.close()
   ```
   Alternativa (empezar de cero): re-ingestar desde CSV moviéndolos de `procesados` a `inbox` y limpiando `meta.archivo_procesado`.
5. Re-conceder lectura a `bi_reader` la aplica `05_views.sql` (incluye el `GRANT`).
6. **Reanudar** la tarea programada y verificar (Parte B).

Validado en el piloto: la reorganización de dimensiones produce **la misma** distribución
EXCLUIDO/PREVENTIVA/MORA que el modelo anterior (212.329 contratos SAS+SCC).

---

## Parte D — Troubleshooting

| Síntoma | Causa probable → acción |
|---|---|
| `-> omitido` inesperado | CSV con mismo hash ya en `meta.archivo_procesado` → renombrar/reenviar o borrar el registro si es recarga intencional. |
| `job_run.status = failed` | Ver `error_msg` en `meta.job_run` y el log en `C:\dwh\logs`. La corrida hace rollback; el CSV **no** se mueve. |
| Vistas sin datos nuevos | La carga corrió pero Power BI no refrescó → *Actualizar* en Power BI. |
| Power BI no conecta | Revisar NSG (5432 solo IP/VPN) y rol `bi_reader`. |
| Columna `distribuidor`/oficiales vacía | Normal si el CSV no traía esos campos; se conserva NULL. |

### Diferencias piloto local → producción

| Tema | Piloto local | Producción (VM) |
|---|---|---|
| PostgreSQL | `localhost:5433`, BD `dwh_test`, user `postgres` | `localhost:5432`, BD `dwh`, `etl_app` (carga) / `bi_reader` (BI) |
| Inbox | `.pilot/inbox/<empresa>` | `F:\dwh\inbox\<empresa>` |
| Config | `empresas.pilot.yaml` | `empresas.yaml` |
| Ejecución | manual (`runner`) | tarea `DWH_ETL_Diario` (`run_etl.bat`) a las 06:00 |
| Acceso | directo | Azure Bastion |
