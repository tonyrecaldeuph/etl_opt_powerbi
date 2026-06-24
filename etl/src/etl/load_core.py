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

_GESTOR_COLS = ["distribuidor", "vendedor", "oficial_credito_solicitud",
                "oficial_credito_archivos", "oficial_credito_contrato",
                "oficial_credito_llamada"]

def _gestor_hash_sql(alias: str) -> str:
    """md5 de las 6 columnas de gestor (con alias de tabla) para join por igualdad."""
    parts = "||'|'||".join(f"coalesce({alias}.{c},'')" for c in _GESTOR_COLS)
    return f"md5({parts})"

def _crear_particion_fact(cur, fecha_carga):
    # Usa la función SQL core.crear_particion_fact (definida en sql/04_core.sql)
    # para evitar el conflicto entre los directivos format() de PL/pgSQL (%s/%I/%L)
    # y el parser de placeholders de psycopg2.
    cur.execute("SELECT core.crear_particion_fact(%s)", (fecha_carga,))

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
          ORDER BY cedula, numero_contrato
          ON CONFLICT (cedula) DO UPDATE SET
            nombre_cliente=EXCLUDED.nombre_cliente, apellido_cliente=EXCLUDED.apellido_cliente,
            telefono_1=EXCLUDED.telefono_1, telefono_2=EXCLUDED.telefono_2,
            telefono_final=EXCLUDED.telefono_final, telefono_ref=EXCLUDED.telefono_ref,
            direccion_cliente=EXCLUDED.direccion_cliente, correo_cliente=EXCLUDED.correo_cliente
        """, params)

        cur.execute(f"""
          INSERT INTO core.dim_dispositivo (imei, marca, modelo)
          SELECT DISTINCT ON (imei) imei, marca, modelo FROM ({src}) s WHERE imei IS NOT NULL
          ORDER BY imei, numero_contrato
          ON CONFLICT (imei) DO UPDATE SET marca=EXCLUDED.marca, modelo=EXCLUDED.modelo
        """, params)

        cur.execute(f"""
          INSERT INTO core.dim_contrato (numero_contrato, fecha_venta, grupo,
            estado_dispositivo, contrato_refinanciado)
          SELECT DISTINCT ON (numero_contrato) numero_contrato,
            NULLIF(trim(fecha_venta),'')::date, grupo, estado_dispositivo, contrato_refinanciado
          FROM ({src}) s WHERE numero_contrato IS NOT NULL
          ORDER BY numero_contrato
          ON CONFLICT (numero_contrato) DO UPDATE SET grupo=EXCLUDED.grupo,
            estado_dispositivo=EXCLUDED.estado_dispositivo
        """, params)

        cur.execute(f"""
          INSERT INTO core.dim_gestor (gestor_hash, distribuidor, vendedor,
            oficial_credito_solicitud, oficial_credito_archivos,
            oficial_credito_contrato, oficial_credito_llamada)
          SELECT DISTINCT {_gestor_hash_sql('s')}, distribuidor, vendedor,
            oficial_credito_solicitud, oficial_credito_archivos,
            oficial_credito_contrato, oficial_credito_llamada
          FROM ({src}) s
          ON CONFLICT (gestor_hash) DO NOTHING
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
          LEFT JOIN core.dim_gestor g ON g.gestor_hash = {_gestor_hash_sql('s')}
          WHERE s.empresa=%s AND s.fecha_carga=%s
        """, (empresa, fecha_carga))
    conn.commit()
