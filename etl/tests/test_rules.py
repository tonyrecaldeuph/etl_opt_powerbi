# etl/tests/test_rules.py
import math
import pytest
from etl.rules import clasificar, estado_dias

@pytest.mark.parametrize("monto,mora,esperado", [
    (0, 0, "EXCLUIDO"),
    (0, 50, "EXCLUIDO"),       # mora sin saldo -> EXCLUIDO (regla confirmada)
    (None, 0, "EXCLUIDO"),     # nulos = 0
    (100, 0, "PREVENTIVA"),
    (100, 0.01, "MORA"),
    (100, 50, "MORA"),
])
def test_clasificar(monto, mora, esperado):
    assert clasificar(monto, mora) == esperado

@pytest.mark.parametrize("dias,esperado", [
    (None, "SIN_DATO"),
    (float("nan"), "SIN_DATO"),
    (-5, "ADELANTADO"),
    (0, "AL_DIA"),
    (1, "EN_MORA"),
    (160, "EN_MORA"),
])
def test_estado_dias(dias, esperado):
    assert estado_dias(dias) == esperado
