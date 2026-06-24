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
