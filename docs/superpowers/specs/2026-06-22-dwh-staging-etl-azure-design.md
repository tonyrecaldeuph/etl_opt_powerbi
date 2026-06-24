# SOP — Data Warehouse de Cobranza con Staging y ETL en Python sobre VM Azure (Windows Server) + PostgreSQL, consumido en Power BI

- **Fecha:** 2026-06-22 (actualizado 2026-06-23)
- **Autor:** Equipo de Analitica UPHONE
- **Estado:** Diseño aprobado — pendiente revisión final del spec
- **Alcance:** Crear, desde cero, un flujo de datos con nivel de carga *staging* hacia un Data Warehouse en PostgreSQL, con ETL en Python sobre una VM de Azure con **Windows Server**, que ingiere reportes **XLS de cobranza de dos empresas (SAS y SCC)**, aplica reglas de negocio (exclusión + clasificación PREVENTIVA/MORA) y expone los datos limpios y modelados para su **consumo en Power BI** (visualización y distribución). La capa de analítica/ML y gobierno avanzado queda como fase futura.

---

## 1. Objetivo y resultados esperados

Establecer un procedimiento operativo estándar (SOP) reproducible para:

1. Provisionar y endurecer una VM de Azure con Windows Server.
2. Instalar y optimizar PostgreSQL como motor del DWH.
3. Ingerir los XLS diarios de cobranza de las dos empresas (SAS, SCC) a la capa `staging` (**get / store data**).
4. Aplicar el **motor de reglas** de exclusión y clasificación (PREVENTIVA / MORA) y construir vistas listas para BI (**prepare data**).
5. Historizar cada carga como **snapshot diario** (la información persiste).
6. Orquestar las cargas con el Programador de tareas de Windows.
7. **Consumir los datos en Power BI** (visualizar y distribuir), con conexión directa al DWH y refresco **manual**.

**Criterios de éxito**
- Carga diaria automática que finaliza sin intervención manual.
- 100% de los contratos clasificados (EXCLUIDO / PREVENTIVA / MORA).
- Histórico consultable: evolución día a día de cada contrato.
- Un modelo/vista en PostgreSQL listo para que Power BI lo importe sin transformaciones complejas.
- Informe de Power BI publicado/compartido con los usuarios de negocio.

---

## 2. Decisiones de diseño confirmadas

| Tema | Decisión |
|---|---|
| **Fuente de datos** | Archivos **XLS** (no BD operacional). Dos empresas: **SAS** y **SCC**. |
| **SO de la VM** | **Windows Server** (no Linux). |
| **ETL** | Python (pandas/openpyxl + SQLAlchemy/psycopg2). |
| **Orquestación** | Programador de tareas de Windows + runner Python (sin Airflow). |
| **Almacén** | **PostgreSQL en la VM** (se conserva; no se migra a Fabric). |
| **Modelo `core`** | **Dimensional / estrella** + vistas planas para BI. |
| **Capa de consumo** | **Power BI** (reemplaza el frontend custom y Metabase, que se descartan). |
| **Refresco Power BI** | **Manual** (analista refresca y publica; sin gateway). |
| **Historización** | **Snapshot diario con `fecha_carga`** (la información persiste). |
| **Regla de EXCLUSIÓN** | `monto_por_cobrar = 0` → EXCLUIDO. |
| **Regla PREVENTIVA** | `monto_por_cobrar > 0` Y `valor_en_mora = 0`. |
| **Regla MORA** | `monto_por_cobrar > 0` Y `valor_en_mora > 0`. |
| **Días impago negativos** | Etiqueta `estado_dias = 'ADELANTADO'`. |
| **Alcance del flujo** | get → store → prepare → **visualize → distribute** (Power BI). ML y gobierno = fase futura. |

---

## 3. Mapeo al flujo de referencia (diagrama)

El diagrama corresponde al flujo end-to-end de datos. Así se implementa cada etapa en este proyecto:

| Etapa del diagrama | Implementación en este proyecto | Estado |
|---|---|---|
| **get data** | Ingesta de XLS (SAS/SCC) → `staging` (Python) | ✅ En alcance |
| **mirror data** | N/A hoy (no hay fuente en vivo que reflejar). Futuro: si llegan BD operacionales | ⏭️ Futuro |
| **store data** | PostgreSQL: `staging` (crudo) + `core` (estrella), snapshot diario persistente | ✅ En alcance |
| **prepare data** | Motor de reglas (EXCLUIDO/PREVENTIVA/MORA) + vistas planas para BI | ✅ En alcance |
| **visualize** | **Power BI** (modelo importado, dashboards de cobranza) | ✅ En alcance |
| **distribute data** | Publicar/compartir el informe (Power BI Service o `.pbix`/PDF) | ✅ En alcance |
| **analyze and train data** | Analítica/ML (ej. predicción de mora) | ⏭️ Futuro |
| **develop** | Ciclo de desarrollo de modelos/reportes | ⏭️ Futuro |
| **govern data** | Catálogo, control de acceso por rol, políticas | ⏭️ Futuro |
| **track data** | Linaje y monitoreo de refrescos/uso | ⏭️ Futuro |

---

## 4. Estructura real de los archivos XLS

Ambos archivos tienen una sola hoja: **`ReportUphone1`**, una fila por contrato (sin duplicados por `N° CONTRATO`).

| | **RV_SAS** | **RV_SCC** |
|---|---|---|
| Filas (medición 22-06-2026) | 42.093 | 170.236 |
| Columnas | 31 | 30 |
| Exclusivas de la empresa | `TELEFONO FINAL`, `TELEFONO REF`, `OFICIAL CRÉDITO LLAMADA` | `CONTRATO REFINANCIADO` |

**Columnas comunes (29):** `N° CONTRATO`, `DISTRIBUIDOR`, `VENDEDOR`, `OFICIAL CRÉDITO SOLICITUD`, `OFICIAL CRÉDITO ARCHIVOS`, `OFICIAL CRÉDITO CONTRATO`, `CÉDULA`, `NOMBRE CLIENTE`, `APELLIDO CLIENTE`, `FECHA DE VENTA`, `MARCA`, `MODELO`, `IMEI`, `COSTO`, `ENTRADA`, `PLAZO`, `MONTO TOTAL`, `MONTO POR COBRAR`, `GRUPO`, `ESTADO DISPOSITIVO`, `DIAS IMPAGO`, `TELEFONO 1`, `TELEFONO 2`, `VALOR EN MORA`, `VALOR CUOTA`, `NUMERO CUOTA`, `DIRECCION CLIENTE`, `CORREO CLIENTE`.

**Columnas que gobiernan las reglas:** `DIAS IMPAGO`, `VALOR EN MORA`, `MONTO POR COBRAR`.

**Calidad de datos detectada (a tratar en el ETL):**
- `DIAS IMPAGO`: contiene **nulos** (513 SAS / 115.792 SCC) y **valores negativos** (hasta −10.970 = pago adelantado).
- `VALOR EN MORA` y `MONTO POR COBRAR`: sin nulos, mínimo 0.
- **Nombres de columna con acentos/Ñ/°** → se normalizan a `snake_case` ASCII al ingestar. Ojo: el encabezado real es **`Nº CONTRATO`** con `º` ordinal (U+00BA), que en NFKD se descompone a `o` (→ `no_contrato`); se mapea a `numero_contrato` vía alias canónico. Igual `FECHA DE VENTA` → `fecha_venta`.
- **`PLAZO` es texto** (incluye la unidad: `"13 QUINCENAS"`, `"12 MESES"`, `"26 SEMANAS"`) → se conserva como `text`, no numérico.
- **Esquema distinto entre empresas** → se unifica; las columnas ausentes en una empresa quedan `NULL`.

> Hallazgos confirmados al validar el ETL contra los archivos reales (carga end-to-end: distribución idéntica a la tabla de arriba, 212.329 filas).

**Distribución según reglas (datos del 22-06-2026):**

| | EXCLUIDO | PREVENTIVA | MORA | Adelantados (días<0) |
|---|---|---|---|---|
| **SAS** | 516 | 29.668 | 11.909 | 19.144 |
| **SCC** | 115.915 | 16.782 | 37.539 | 13.324 |

---

## 5. Motor de reglas de negocio

Aplicado por contrato (nulos en mora/monto se tratan como 0):

```
# monto = MONTO POR COBRAR ; mora = VALOR EN MORA ; dias = DIAS IMPAGO

# 1) Clasificación principal
if monto == 0:
    clasificacion = "EXCLUIDO"          # cliente al día / contrato liquidado / sin saldo
elif mora == 0:                          # monto > 0
    clasificacion = "PREVENTIVA"        # al día en mora pero con saldo por cobrar
else:                                     # monto > 0 y mora > 0
    clasificacion = "MORA"

# 2) Etiqueta de estado de días
if dias is None:        estado_dias = "SIN_DATO"
elif dias < 0:          estado_dias = "ADELANTADO"
elif dias == 0:         estado_dias = "AL_DIA"
else:                   estado_dias = "EN_MORA"
```

---

## 6. Arquitectura

Todo el procesamiento reside en **una sola VM**; Power BI consume desde fuera (o desde la propia VM).

```
                          VM Azure - Windows Server
 ┌───────────────────────────────────────────────────────────────────────┐
 │  D:\dwh\inbox\  ◄── XLS diarios (RV_SAS, RV_SCC)        [get data]       │
 │        │                                                                │
 │   Ingesta (Python: openpyxl/pandas)                                     │
 │   - normaliza columnas, añade EMPRESA + fecha_carga                     │
 │        ▼                                                                │
 │   esquema STAGING (snapshot crudo, particionado)        [store data]    │
 │        │                                                                │
 │   Transform + Motor de reglas (Python + SQL)            [prepare data]  │
 │        ▼                                                                │
 │   esquema CORE (estrella) + VISTAS BI (core.vw_*)                       │
 │        │                                                                │
 │   esquema META (control de cargas, logs)                               │
 │                                                                         │
 │  Orquestación: Programador de tareas ──► runner.py                      │
 └───────────────────────────────────────────────────────────────────────┘
        │  (conexión PostgreSQL: rol bi_reader, vía VPN o en la propia VM)
        ▼
   Power BI Desktop  ── importa core.vw_* ──►  Informe (.pbix)             [visualize]
        │  publicar / compartir manualmente
        ▼
   Power BI Service / archivo / PDF  ──►  Usuarios de negocio              [distribute data]
```

### 6.1 Esquemas de PostgreSQL

| Esquema | Propósito | Estrategia |
|---|---|---|
| `staging` | Copia fiel del XLS (normalizada) | **Append** por `fecha_carga`, particionado por fecha |
| `core` | Modelo estrella + **vistas planas para BI** | Snapshot del día; hechos particionados por `fecha_carga` |
| `meta` | Control de cargas, logs, registro de archivos | Append (auditoría) |

---

## 7. Modelo dimensional `core` (estrella) y vistas para Power BI

**Hecho:** `core.fact_cobranza_snapshot`
- **Grano:** un registro por **contrato** por **fecha_carga**.
- **Medidas:** `monto_por_cobrar`, `valor_en_mora`, `dias_impago`, `costo`, `entrada`, `monto_total`, `valor_cuota`, `numero_cuota`, `plazo`.
- **Atributos calculados:** `clasificacion`, `estado_dias`.
- **Degenerados:** `numero_contrato`, `imei`.
- **FKs:** `fecha_carga_key`, `empresa_key`, `cliente_key`, `dispositivo_key`, `contrato_key`, `gestor_key`.

**Dimensiones:** `dim_fecha`, `dim_empresa` (SAS/SCC), `dim_cliente` (cédula, nombre, contacto), `dim_dispositivo` (marca/modelo/imei), `dim_contrato` (fecha_venta, grupo, estado_dispositivo, contrato_refinanciado), `dim_gestor` (distribuidor, vendedor, oficiales de crédito).

**Vista plana para BI** (clave para refresco manual sencillo): `core.vw_cobranza` une el hecho con sus dimensiones y expone columnas legibles (empresa, cédula, nombre, marca/modelo, monto_por_cobrar, valor_en_mora, dias_impago, clasificacion, estado_dias, fecha_carga, fecha_venta, gestores). Power BI importa esta vista directamente → modelo simple, sin transformaciones pesadas en Power Query.

> Recomendación: además de la vista detallada, crear `core.vw_resumen_clasificacion` (conteos y montos agregados por empresa, fecha_carga y clasificación) para dashboards rápidos.

---

## 8. SOP — Procedimiento paso a paso

> Rutas bajo `C:\dwh` (y `D:\dwh` para datos). PowerShell **como Administrador** salvo que se indique.

### Paso 1 — Provisionar la VM de Azure (Windows Server)
1. **Windows Server 2022 Datacenter**, tamaño **Standard D2s_v5** (2 vCPU / 8 GB).
2. Disco SO Premium SSD + **disco de datos `D:`** (P15/256 GB) para `PGDATA`, `inbox` y backups.
3. Red (NSG): **3389 (RDP)** solo desde IP de administración (idealmente Azure Bastion/VPN). **5432** cerrado a Internet; se habilita solo para Power BI según el Paso 8.
4. Habilitar **Azure Backup** y Windows Update.

### Paso 2 — Preparar el sistema
```powershell
New-Item -ItemType Directory -Force -Path `
  C:\dwh\etl, C:\dwh\logs, C:\dwh\backups, C:\dwh\tools, `
  D:\dwh\inbox\SAS, D:\dwh\inbox\SCC, D:\dwh\inbox\procesados
```
Instalar: **Python 3.12** (Add to PATH), **Git**, **NSSM** (opcional). *(Ya no se requieren JRE/Node: se eliminó Metabase y el frontend custom.)*

### Paso 3 — Instalar y configurar PostgreSQL
1. Instalar **PostgreSQL 16** (instalador EDB), `Data Directory` en `D:\PGDATA`. Guardar la clave de `postgres` en Key Vault.
2. Base, esquemas y roles:
   ```sql
   CREATE DATABASE dwh;
   \c dwh
   CREATE SCHEMA staging;  CREATE SCHEMA core;  CREATE SCHEMA meta;

   CREATE ROLE etl_app  LOGIN PASSWORD '***';
   GRANT ALL ON SCHEMA staging, core, meta TO etl_app;

   CREATE ROLE bi_reader LOGIN PASSWORD '***';     -- Power BI, solo lectura de core
   GRANT USAGE ON SCHEMA core TO bi_reader;
   ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT SELECT ON TABLES TO bi_reader;
   ```
3. Tablas de control en `meta`:
   ```sql
   CREATE TABLE meta.job_run (
     run_id bigserial PRIMARY KEY, job_name text NOT NULL,
     started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
     status text NOT NULL DEFAULT 'running', rows_read bigint, rows_loaded bigint, error_msg text);

   CREATE TABLE meta.archivo_procesado (
     id bigserial PRIMARY KEY, empresa text, nombre_archivo text, hash_archivo text,
     fecha_carga date, filas bigint, procesado_at timestamptz NOT NULL DEFAULT now(),
     UNIQUE (empresa, nombre_archivo, hash_archivo));
   ```
4. `staging` particionada por `fecha_carga` (ver §6.1).

### Paso 4 — Optimización de PostgreSQL (8 GB RAM, carga batch)
`D:\PGDATA\postgresql.conf`: `shared_buffers=2GB`, `effective_cache_size=6GB`, `work_mem=64MB`, `maintenance_work_mem=512MB`, `max_wal_size=4GB`, `checkpoint_completion_target=0.9`, `wal_compression=on`, `random_page_cost=1.1`, `autovacuum=on`.
Buenas prácticas: cargar `staging` con **`COPY`**; **particionar por `fecha_carga`** (partition pruning); `ANALYZE` tras cada carga; índices en `core` por `fecha_carga`, `empresa`, `cedula`, `clasificacion`; reiniciar el servicio tras cambiar la config.

### Paso 5 — ETL en Python
1. Entorno: `python -m venv .venv` y `pip install pandas openpyxl sqlalchemy psycopg2-binary python-dotenv pyyaml`.
2. Estructura:
   ```
   C:\dwh\etl\
     .env                       # credenciales (NUNCA en git)
     config\empresas.yaml       # rutas inbox, patrón de archivo y mapeo de columnas por empresa
     src\
       db.py                    # conexión al DWH
       ingest_xls.py            # XLS -> staging (normaliza columnas, añade empresa + fecha_carga)
       rules.py                 # motor de reglas (§5)
       load_core.py             # staging -> core (dims + fact) + refresco de vistas BI
       meta.py                  # registro de corridas y archivos procesados
       runner.py                # orquesta: detecta archivos, ingesta, reglas, carga, log
     tests\                     # pytest: reglas, idempotencia, normalización
   ```
3. **Ingesta:** detecta `RV_<EMP> <fecha>.xlsx` en `D:\dwh\inbox\<empresa>`, lee hoja `ReportUphone1`, normaliza columnas a `snake_case` ASCII, añade `empresa` + `fecha_carga`, verifica hash en `meta.archivo_procesado` (**idempotencia**), `COPY` a `staging`, mueve el archivo a `procesados`.
4. **Reglas (`rules.py`):** funciones puras del §5, testeables.
5. **Carga a core:** upsert de dimensiones e inserción del snapshot del día en `fact_cobranza_snapshot` con `clasificacion` y `estado_dias`. Las vistas BI (`core.vw_*`) se crean una vez y reflejan siempre el dato actual.
6. **Runner:** por archivo/empresa → `running` en `meta.job_run`, ejecuta ingesta→reglas→core, captura errores, marca `success`/`failed`. Crea la partición del mes si falta.
7. **Tests (pytest):** casos límite de reglas (monto=0, mora=0, días null/negativos), idempotencia y normalización.

### Paso 6 — Orquestación con Programador de tareas
1. `C:\dwh\etl\run_etl.bat` activa el venv y ejecuta `runner.py` con log a `C:\dwh\logs`.
2. Registrar tarea diaria:
   ```powershell
   $action  = New-ScheduledTaskAction -Execute "C:\dwh\etl\run_etl.bat"
   $trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
   $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
   Register-ScheduledTask -TaskName "DWH_ETL_Diario" -Action $action -Trigger $trigger -Principal $principal
   ```
3. Verificar con `Start-ScheduledTask` y revisar `meta.job_run` + log.

### Paso 7 — Preparar las vistas para Power BI (prepare data)
1. Crear `core.vw_cobranza` (detalle, una fila por contrato×fecha_carga con columnas legibles) y `core.vw_resumen_clasificacion` (agregados por empresa/fecha/clasificación).
2. Conceder `SELECT` de estas vistas a `bi_reader`.
3. Validar que las vistas devuelven los conteos esperados (EXCLUIDO/PREVENTIVA/MORA) contra §4.

### Paso 8 — Consumo en Power BI (visualize + distribute)
**Conexión (refresco manual):**
1. Instalar **Power BI Desktop** y el conector **PostgreSQL** (provider Npgsql) en la máquina del analista. Alternativa simple: instalar Power BI Desktop **en la propia VM** y trabajar por RDP (evita abrir 5432).
2. Acceso de red: si el analista trabaja desde su equipo, habilitar **5432 solo para su IP/VPN** en el NSG; conectar con el rol **`bi_reader`** (solo lectura). Nunca exponer 5432 a Internet.
3. En Power BI Desktop: `Obtener datos → PostgreSQL`, modo **Import**, seleccionar `core.vw_cobranza` y `core.vw_resumen_clasificacion`.

**Modelado y visualización:**
4. Construir medidas DAX básicas (conteos y montos por `clasificacion`, `empresa`, `fecha_carga`; % de mora; antigüedad por `dias_impago`).
5. Dashboards sugeridos: cartera por clasificación y empresa, evolución diaria de MORA, monto por cobrar vs. valor en mora, antigüedad de mora, top oficiales/distribuidores, clientes ADELANTADO.

**Distribución (manual):**
6. Publicar el `.pbix` a **Power BI Service** (workspace del equipo) y compartir con los usuarios, **o** distribuir el `.pbix`/exportar a PDF según la política interna.
7. Cada actualización: el analista abre el `.pbix`, pulsa **Actualizar** (tras la carga diaria) y vuelve a publicar/compartir.

> **Datos sensibles** (cédula, teléfonos, dirección, correo): limitar quién accede al informe; considerar enmascarar PII en vistas/Power BI para audiencias amplias.

---

## 9. Operación y mantenimiento (Runbook)

| Situación | Acción |
|---|---|
| Falló una corrida | Revisar `meta.job_run` (status=failed, error_msg) y log en `C:\dwh\logs`. Corregir y re-ejecutar (`Start-ScheduledTask`). |
| Archivo no llegó | El runner registra ausencia del XLS esperado; alertar y reintentar tras depositarlo en `inbox`. |
| Archivo duplicado | `meta.archivo_procesado` (hash) evita recargarlo. |
| Cambió el layout del XLS | Actualizar mapeo en `config\empresas.yaml`; ajustar vistas BI si hay columnas nuevas. |
| Power BI no muestra datos del día | Confirmar que la carga diaria terminó (`meta.job_run` success) y **actualizar manualmente** el `.pbix`. |
| Clasificación inesperada | Validar `MONTO POR COBRAR` / `VALOR EN MORA` del contrato contra §5. |
| Crecimiento de disco | Monitorear `D:`; archivar/purgar particiones antiguas (§11). |

**Backups:** `pg_dump` diario de `dwh` a `C:\dwh\backups` con **retención 12 meses** + Azure Backup de la VM. Probar restauración periódicamente.
**Monitoreo:** alerta si `job_run` no registra `success` tras la ventana de carga; vigilar disco y el servicio `postgresql`.

---

## 10. Decisiones de diseño (y por qué)

- **PostgreSQL en VM + Power BI (no Fabric):** reutiliza todo el trabajo, menor costo; el flujo del diagrama se cubre como capas conceptuales sobre este stack.
- **Refresco manual:** sin gateway ni infraestructura extra; suficiente para una operación diaria con un analista. Se puede automatizar después instalando el On-premises Data Gateway.
- **Vistas planas para BI:** mueven la complejidad al SQL (versionable y testeable) y dejan Power BI simple, con refresco rápido.
- **Snapshot diario particionado:** cumple "que la información persista" sin degradar rendimiento (partition pruning).
- **Idempotencia por hash de archivo:** re-ejecutar nunca duplica datos.
- **Reglas como funciones puras y testeadas:** la lógica de negocio es verificable y fácil de ajustar.
- **`etl_app` vs `bi_reader`:** mínimo privilegio; Power BI solo lee `core`.

---

## 11. Dimensionamiento y retención

- **Crecimiento:** ~212k filas/día → orden de **30–40 GB/año** en `core`+`staging`. El disco `D:` de 256 GB cubre varios años.
- **Retención:** la información persiste; al acercarse al límite de disco, **archivar** particiones antiguas (export a Parquet/Blob) en lugar de borrarlas.
- **Backups:** retención 12 meses (`pg_dump`) + Azure Backup de la VM.

---

## 12. Fase futura (fuera del alcance actual)

- **mirror data:** integrar BD operacionales en vivo si reemplazan/complementan los XLS.
- **analyze and train data / develop:** modelo predictivo de mora, scoring de clientes.
- **govern data / track data:** catálogo de datos, control de acceso por rol, linaje y monitoreo de uso.
- **Refresco automático de Power BI:** instalar On-premises Data Gateway y programar refresco en Power BI Service.

---

## 13. Supuestos a validar antes de implementar

- La **fecha del archivo** (`RV_SAS 22-06-2026.xlsx`) es la `fecha_carga` oficial del snapshot.
- Identificador de cliente = **`CÉDULA`**; de contrato = **`N° CONTRATO`**.
- Los XLS se depositan en `D:\dwh\inbox\<empresa>` antes de la ventana de carga.
- El analista de Power BI accede a PostgreSQL desde la VM (RDP) o vía VPN/IP autorizada (no se abre 5432 a Internet).
- Una corrida diaria es suficiente (no se requiere tiempo real).
