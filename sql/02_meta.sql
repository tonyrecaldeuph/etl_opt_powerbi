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
RETURNS void LANGUAGE plpgsql SECURITY DEFINER AS $$
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
