# etl/src/etl/normalize.py
import re
import unicodedata

# Overrides canónicos tras la normalización mecánica.
# Nota: el encabezado real es "Nº CONTRATO" con º ordinal (U+00BA), que en NFKD
# se descompone a "o" -> "no_contrato". También aceptamos "n_contrato" (con ° grados).
CANONICAL_RENAMES = {
    "no_contrato": "numero_contrato",
    "n_contrato": "numero_contrato",
    "fecha_de_venta": "fecha_venta",
}

def normalize_column(name: str) -> str:
    """Convierte un encabezado a snake_case ASCII; aplica overrides canónicos."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return CANONICAL_RENAMES.get(s, s)

def normalize_headers(names: list[str]) -> list[str]:
    """Normaliza una lista de encabezados, desduplicando con sufijo _2, _3, ..."""
    out: list[str] = []
    seen: dict[str, int] = {}
    for n in names:
        base = normalize_column(n)
        if base not in seen:
            seen[base] = 1
            out.append(base)
        else:
            seen[base] += 1
            out.append(f"{base}_{seen[base]}")
    return out
