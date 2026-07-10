CREATE OR REPLACE VIEW core.vw_cobranza AS
SELECT f.fecha_carga, e.empresa, f.numero_contrato, c.cedula,
       c.nombre_cliente, c.apellido_cliente,
       d.marca, d.modelo, f.imei,
       f.monto_por_cobrar, f.valor_en_mora, f.dias_impago,
       f.monto_total, f.valor_cuota, f.numero_cuota, f.plazo,
       f.clasificacion, f.estado_dias,
       k.fecha_venta, k.grupo, k.estado_dispositivo, k.contrato_refinanciado,
       dist.distribuidor, oc.vendedor,
       oc.oficial_credito_solicitud, oc.oficial_credito_archivos,
       oc.oficial_credito_contrato, oc.oficial_credito_llamada
FROM core.fact_cobranza_snapshot f
JOIN core.dim_empresa e   ON e.empresa_key = f.empresa_key
LEFT JOIN core.dim_cliente c ON c.cliente_key = f.cliente_key
LEFT JOIN core.dim_dispositivo d ON d.dispositivo_key = f.dispositivo_key
JOIN core.dim_contrato k  ON k.contrato_key = f.contrato_key
LEFT JOIN core.dim_oficiales_credito oc ON oc.oficial_credito_key = f.oficial_credito_key
LEFT JOIN core.dim_distribuidor dist ON dist.distribuidor_key = f.distribuidor_key;

CREATE OR REPLACE VIEW core.vw_resumen_clasificacion AS
SELECT fecha_carga, e.empresa, f.clasificacion,
       count(*) AS contratos,
       sum(f.monto_por_cobrar) AS total_por_cobrar,
       sum(f.valor_en_mora)    AS total_mora
FROM core.fact_cobranza_snapshot f
JOIN core.dim_empresa e ON e.empresa_key = f.empresa_key
GROUP BY fecha_carga, e.empresa, f.clasificacion;

GRANT SELECT ON core.vw_cobranza, core.vw_resumen_clasificacion TO bi_reader;
