from app.db.supabase_client import (
    SupabaseManager,
    fetch_camara_by_id,
    get_supabase,
    insert_alerta_row,
)

__all__ = [
    "SupabaseManager",
    "fetch_camara_by_id",
    "get_supabase",
    "insert_alerta_row",
]
