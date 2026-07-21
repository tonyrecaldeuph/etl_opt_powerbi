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

-- GRANT ALL ON SCHEMA solo cubre el esquema en si (USAGE/CREATE), no las tablas,
-- secuencias ni funciones que crean los scripts siguientes (02-04, ejecutados como
-- postgres). Sin estos DEFAULT PRIVILEGES, etl_app queda sin acceso real a esos
-- objetos aunque el esquema diga "ALL".
ALTER DEFAULT PRIVILEGES IN SCHEMA staging, meta, core GRANT ALL ON TABLES TO etl_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging, meta, core GRANT ALL ON SEQUENCES TO etl_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging, meta, core GRANT EXECUTE ON FUNCTIONS TO etl_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT SELECT ON TABLES TO bi_reader;
