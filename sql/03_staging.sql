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
