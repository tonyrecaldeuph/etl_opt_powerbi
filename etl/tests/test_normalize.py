# etl/tests/test_normalize.py
import pytest
from etl.normalize import normalize_column, normalize_headers

@pytest.mark.parametrize("raw,expected", [
    ("Nº CONTRATO", "numero_contrato"),   # encabezado real: º ordinal (U+00BA) -> "no_contrato" -> rename
    ("N° CONTRATO", "numero_contrato"),   # variante con ° grados (U+00B0) -> "n_contrato" -> rename
    ("FECHA DE VENTA", "fecha_venta"),    # override canónico
    ("CÉDULA", "cedula"),
    ("DIAS IMPAGO", "dias_impago"),
    ("MONTO POR COBRAR", "monto_por_cobrar"),
    ("VALOR EN MORA", "valor_en_mora"),
    ("OFICIAL CRÉDITO SOLICITUD", "oficial_credito_solicitud"),
    ("  Teléfono 1 ", "telefono_1"),
])
def test_normalize_column(raw, expected):
    assert normalize_column(raw) == expected

def test_normalize_headers_dedup():
    # nombres que colisionan tras normalizar reciben sufijo incremental
    assert normalize_headers(["Teléfono", "TELEFONO"]) == ["telefono", "telefono_2"]
