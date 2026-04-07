"""Referencias de cámara: id entero (bigint) alineado con ``camaras.id`` en Supabase."""

from __future__ import annotations


def parse_camara_id_env(raw: str) -> int | None:
    """
    Parsea ``SMARTGUARD_CAMARA_ID`` desde .env como entero (p. ej. ``1`` para int8/bigint).
    Devuelve None si está vacío o no es un entero válido.
    """
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return int(s, 10)
    except ValueError:
        return None
