# Guía — Prueba piloto del ETL de cobranza (local)

Esta guía ejecuta el ETL de punta a punta en tu equipo local, usando el servidor PostgreSQL de pruebas (puerto **5433**) y **DBVisualizer** para crear el esquema y consultar. La carga de datos la hace el `runner` de Python (el mismo que usará el Programador de tareas en producción).

**Datos del entorno local de pruebas:**
- Servidor PostgreSQL de pruebas: `localhost:5433` (clúster en `C:\Users\HP\pgdata_etl`)
- Base de datos: `dwh_test` · Usuario: `postgres` · Contraseña: `etl_local_pw`
- El PostgreSQL del sistema (puerto 5432) **no se toca**.

---

## Paso 0 — Verifica que el servidor de pruebas esté arriba

En PowerShell:
```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" -D C:\Users\HP\pgdata_etl status
```
- "server is running" → continúa.
- Si está detenido, arráncalo:
```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" -D C:\Users\HP\pgdata_etl -o "-p 5433" -l C:\Users\HP\pgdata_etl\server.log start
```

---

## Paso 1 — Conectar DBVisualizer

`Database` → `Create Database Connection` (o el botón **+**) → driver **PostgreSQL**:

| Campo | Valor |
|---|---|
| Database Type / Driver | PostgreSQL |
| Server (Host) | `localhost` |
| Port | `5433` |
| Database | `dwh_test` |
| User ID | `postgres` |
| Password | `etl_local_pw` |

Pulsa **Connect**. DBVisualizer ya incluye el driver JDBC de PostgreSQL.

> Para producción (VM): conexión idéntica pero **Port 5432**, **Database `dwh`** y usuario `bi_reader` (consultas/BI) o `etl_app` (administración).

---

## Paso 2 — Crear el esquema con DBVisualizer

Si la base `dwh_test` no existe: clic derecho sobre el servidor → `Create Database` → `dwh_test`.

Abre el **SQL Commander** y ejecuta, **en este orden**, cada archivo de `...\Flujo_datos\sql\`:

1. `01_schema_roles.sql`
2. `02_meta.sql`
3. `03_staging.sql`
4. `04_core.sql`
5. `05_views.sql`

Para cada uno: `SQL Commander` → `Load` → selecciona el archivo → ejecútalo con **Ctrl+Enter** (o ▶ "Execute Buffer"). Los `NOTICE ... already exists` son inofensivos (el DDL usa `IF NOT EXISTS`).

> Para empezar de cero puedes hacer clic derecho en `dwh_test` → `Drop Database`, recrearla y volver a correr el DDL.

---

## Paso 3 — Preparar los archivos de entrada (CSV)

El ETL consume **CSV**. Si tus reportes son XLS, conviértelos con el Python del sistema (tiene `openpyxl`):

```powershell
python -c "import pandas as pd; pd.read_excel(r'C:\Users\HP\Downloads\RV_SAS 22-06-2026.xlsx', sheet_name='ReportUphone1', dtype=str).to_csv(r'C:\Users\HP\Desktop\DESARROLLOS_UPHONE\Flujo_datos\.pilot\inbox\SAS\RV_SAS 22-06-2026.csv', index=False, encoding='utf-8')"
python -c "import pandas as pd; pd.read_excel(r'C:\Users\HP\Downloads\RV_SCC 22-06-2026.xlsx', sheet_name='ReportUphone1', dtype=str).to_csv(r'C:\Users\HP\Desktop\DESARROLLOS_UPHONE\Flujo_datos\.pilot\inbox\SCC\RV_SCC 22-06-2026.csv', index=False, encoding='utf-8')"
```

Primero crea las carpetas inbox:
```powershell
New-Item -ItemType Directory -Force -Path `
  C:\Users\HP\Desktop\DESARROLLOS_UPHONE\Flujo_datos\.pilot\inbox\SAS, `
  C:\Users\HP\Desktop\DESARROLLOS_UPHONE\Flujo_datos\.pilot\inbox\SCC, `
  C:\Users\HP\Desktop\DESARROLLOS_UPHONE\Flujo_datos\.pilot\inbox\procesados
```

> En producción este paso desaparece: el origen entregará los CSV directamente en `F:\dwh\inbox\<empresa>`.

---

## Paso 4 — Config del piloto

Crea `etl\config\empresas.pilot.yaml` apuntando a las carpetas locales:

```yaml
empresas:
  SAS:
    inbox: "C:/Users/HP/Desktop/DESARROLLOS_UPHONE/Flujo_datos/.pilot/inbox/SAS"
    patron: "RV_SAS *.csv"
    delimitador: ","
    encoding: "utf-8"
  SCC:
    inbox: "C:/Users/HP/Desktop/DESARROLLOS_UPHONE/Flujo_datos/.pilot/inbox/SCC"
    patron: "RV_SCC *.csv"
    delimitador: ","
    encoding: "utf-8"
procesados: "C:/Users/HP/Desktop/DESARROLLOS_UPHONE/Flujo_datos/.pilot/inbox/procesados"
```

El `etl\.env` ya apunta a `dwh_test` en el 5433 (`DATABASE_URL`).

---

## Paso 5 — Ejecutar el ETL (el `runner`, igual que en producción)

```powershell
cd C:\Users\HP\Desktop\DESARROLLOS_UPHONE\Flujo_datos\etl
& .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="src"
python -c "from etl.runner import main; raise SystemExit(main('config/empresas.pilot.yaml'))"
```

Salida esperada (una línea por archivo):
```
[SAS] ...\RV_SAS 22-06-2026.csv -> success
[SCC] ...\RV_SCC 22-06-2026.csv -> success
```
Los CSV se mueven de `inbox\SAS|SCC` a `inbox\procesados`. Tarda ~45 s con ~212k filas.

**Prueba de idempotencia:** vuelve a copiar el mismo CSV a su inbox y re-ejecuta → dirá `-> omitido` (no recarga; lo controla el hash en `meta.archivo_procesado`).

---

## Paso 6 — Verificar resultados (SQL Commander de DBVisualizer)

```sql
-- Distribución por empresa y clasificación (debe coincidir con el spec)
SELECT empresa, clasificacion, contratos, total_por_cobrar, total_mora
FROM core.vw_resumen_clasificacion
ORDER BY empresa, clasificacion;

-- Bitácora de cada corrida del ETL
SELECT run_id, empresa, status, rows_loaded,
       finished_at - started_at AS duracion, error_msg
FROM meta.job_run
ORDER BY run_id;

-- Archivos ya procesados (control de idempotencia)
SELECT empresa, nombre_archivo, filas, fecha_carga, procesado_at
FROM meta.archivo_procesado
ORDER BY procesado_at;

-- Muestra del detalle que consumirá Power BI
SELECT * FROM core.vw_cobranza LIMIT 100;

-- Conteo por estado de días
SELECT empresa, estado_dias, count(*)
FROM core.fact_cobranza_snapshot f
JOIN core.dim_empresa e ON e.empresa_key = f.empresa_key
GROUP BY 1,2 ORDER BY 1,2;
```

Resultado esperado de la primera consulta:

| empresa | clasificacion | contratos |
|---|---|---|
| SAS | EXCLUIDO | 516 |
| SAS | PREVENTIVA | 29.668 |
| SAS | MORA | 11.909 |
| SCC | EXCLUIDO | 115.915 |
| SCC | PREVENTIVA | 16.782 |
| SCC | MORA | 37.539 |

---

## Paso 7 — Consumir en Power BI

1. Power BI Desktop → *Obtener datos* → **PostgreSQL**.
2. Servidor `localhost:5433` · Base `dwh_test` · modo **Import**.
3. Usuario/clave `postgres` / `etl_local_pw` (en producción: `bi_reader`).
4. Selecciona **`core.vw_cobranza`** (detalle) y **`core.vw_resumen_clasificacion`** (agregado).
5. Construye tableros; refresca con **Actualizar** tras cada carga.

---

## Diferencias piloto local → producción (VM `vm-uphone-data-gw-01`)

| Tema | Piloto local | Producción (VM) |
|---|---|---|
| PostgreSQL | `localhost:5433`, BD `dwh_test`, user `postgres` | `localhost:5432`, BD `dwh`, user `etl_app` (carga) / `bi_reader` (BI) |
| Inbox | `.pilot/inbox/<empresa>` | `F:\dwh\inbox\<empresa>` |
| Config | `empresas.pilot.yaml` | `empresas.yaml` |
| Conversión XLS→CSV | manual (si aplica) | el origen entrega CSV |
| Ejecución | a mano (`runner`) | tarea programada `DWH_ETL_Diario` (`run_etl.bat`) |
| Acceso | directo | Azure Bastion (sin IP pública) |

Checklist de despliegue completo: `docs/setup-vm.md`. Diseño: `docs/superpowers/specs/2026-06-22-dwh-staging-etl-azure-design.md`.
