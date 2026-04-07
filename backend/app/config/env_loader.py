"""Carga variables de entorno desde archivo .env (sin exponer secretos en código)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _find_backend_root() -> Path:
    """Directorio que contiene .env (carpeta backend/)."""
    here = Path(__file__).resolve()
    return here.parents[2]


def load_environment(env_file: str | None = None) -> bool:
    """
    Carga variables desde `.env` en la carpeta `backend/` (ruta fija respecto a este paquete),
    o desde ``env_file`` si se indica.

    Si el archivo no existe, escribe un aviso claro en stderr y no falla (puedes usar
    variables ya exportadas en el sistema).

    Returns:
        True si existía el archivo y se intentó cargar; False si no existía.
    """
    if env_file:
        path = Path(env_file).expanduser().resolve()
    else:
        path = _find_backend_root() / ".env"

    if not path.is_file():
        example = path.parent / ".env.example"
        print(
            "[SmartGuard] Aviso: no se encontró el archivo .env.\n"
            f"  Ruta esperada: {path}\n"
            f"  Directorio de trabajo actual (cwd): {Path.cwd()}\n"
            f"  Copia y renombra: {example} → .env en la carpeta backend/.\n"
            "  Las variables solo definidas en .env no estarán disponibles hasta entonces.",
            file=sys.stderr,
        )
        return False

    load_dotenv(path, override=False)
    return True


def require_env(name: str) -> str:
    """Obtiene una variable obligatoria; falla con mensaje claro si falta."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno {name}. "
            "Copia backend/.env.example a backend/.env y configúrala."
        )
    return value


def optional_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip() or default
