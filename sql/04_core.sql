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
  gestor_hash text UNIQUE NOT NULL,   -- md5 de las 6 columnas; permite join por igualdad (hash join)
  distribuidor text, vendedor text,
  oficial_credito_solicitud text, oficial_credito_archivos text,
  oficial_credito_contrato text, oficial_credito_llamada text
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
  valor_cuota numeric, numero_cuota numeric, plazo text,
  clasificacion    text NOT NULL,
  estado_dias      text NOT NULL,
  PRIMARY KEY (fecha_carga, empresa_key, numero_contrato)
) PARTITION BY RANGE (fecha_carga);

CREATE INDEX IF NOT EXISTS ix_fact_clasif
  ON core.fact_cobranza_snapshot (fecha_carga, clasificacion);

-- Crea la partición mensual del hecho si no existe
CREATE OR REPLACE FUNCTION core.crear_particion_fact(p_fecha date)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
  ini date := date_trunc('month', p_fecha)::date;
  fin date := (date_trunc('month', p_fecha) + interval '1 month')::date;
  nom text := format('fact_cobranza_snapshot_%s', to_char(ini, 'YYYYMM'));
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = nom) THEN
    EXECUTE format(
      'CREATE TABLE core.%I PARTITION OF core.fact_cobranza_snapshot FOR VALUES FROM (%L) TO (%L)',
      nom, ini, fin);
  END IF;
END $$;
