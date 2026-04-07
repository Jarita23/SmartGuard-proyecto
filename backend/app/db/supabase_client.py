"""Patrón Singleton: una única instancia del cliente Supabase en el proceso."""

from __future__ import annotations

import threading
from typing import Any

from supabase import Client, create_client

from app.config.env_loader import optional_env, require_env


def _supabase_api_key() -> str:
    """Prioriza la anon key (recomendada para el cliente con RLS); si no, service_role."""
    anon = optional_env("SUPABASE_ANON_KEY", "").strip()
    if anon:
        return anon
    return require_env("SUPABASE_SERVICE_ROLE_KEY")


class SupabaseManager:
    """Garantiza una sola inicialización del cliente (thread-safe simple)."""

    _instance: SupabaseManager | None = None
    _lock = threading.Lock()
    _client: Client | None = None

    def __new__(cls) -> SupabaseManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def client(self) -> Client:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    url = require_env("SUPABASE_URL")
                    key = _supabase_api_key()
                    self._client = create_client(url, key)
        return self._client

    def reset_for_tests(self) -> None:
        """Solo para pruebas unitarias."""
        with self._lock:
            self._client = None


def get_supabase() -> Client:
    """Acceso de conveniencia al cliente singleton."""
    return SupabaseManager().client()


def insert_alerta_row(row: dict[str, Any]) -> None:
    """
    Inserta en ``alertas``. ``camara_id`` debe ser un entero (bigint) que exista en ``camaras.id``.
    """
    if row.get("camara_id") is None:
        return
    get_supabase().table("alertas").insert(row).execute()


def fetch_camara_by_id(camara_id: int) -> dict[str, Any] | None:
    """
    Obtiene una fila de ``camaras`` por ``id`` numérico (int8). El filtro usa entero, no string.
    """
    cid = int(camara_id)
    res = (
        get_supabase()
        .table("camaras")
        .select("*")
        .eq("id", cid)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None
