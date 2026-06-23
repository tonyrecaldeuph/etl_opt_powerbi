# etl/src/etl/rules.py
import math

def _num(x) -> float:
    """Convierte a float tratando None/NaN/vacío como 0."""
    if x is None:
        return 0.0
    if isinstance(x, float) and math.isnan(x):
        return 0.0
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0

def clasificar(monto_por_cobrar, valor_en_mora) -> str:
    monto = _num(monto_por_cobrar)
    mora = _num(valor_en_mora)
    if monto == 0:
        return "EXCLUIDO"
    if mora == 0:
        return "PREVENTIVA"
    return "MORA"

def estado_dias(dias_impago) -> str:
    if dias_impago is None:
        return "SIN_DATO"
    if isinstance(dias_impago, float) and math.isnan(dias_impago):
        return "SIN_DATO"
    try:
        d = float(dias_impago)
    except (TypeError, ValueError):
        return "SIN_DATO"
    if d < 0:
        return "ADELANTADO"
    if d == 0:
        return "AL_DIA"
    return "EN_MORA"
