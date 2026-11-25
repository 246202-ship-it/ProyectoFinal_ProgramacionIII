"""Utilidades comunes."""
from src.graph import GrafoError


def a_numero(valor, nombre):
    """Convierte a float o lanza GrafoError con un mensaje claro."""
    try:
        return float(valor.replace(",", ".")) if isinstance(valor, str) else float(valor)
    except (TypeError, ValueError):
        raise GrafoError(f"'{nombre}' debe ser un número y es '{valor}'") from None
