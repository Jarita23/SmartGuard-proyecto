"""
Lista modelos disponibles en la cuenta (Gemini API) para copiar el id exacto a GEMINI_MODEL.

Uso (desde la carpeta backend/):
  python list_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from google import genai

from app.config.env_loader import load_environment, optional_env, require_env


def _short_model_id(full_name: str) -> str:
    n = full_name.strip()
    return n.removeprefix("models/").strip()


def main() -> None:
    load_environment()
    api_key = require_env("GOOGLE_API_KEY")
    api_version = optional_env("GEMINI_API_VERSION", "v1").strip() or "v1"

    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": api_version},
    )

    print(f"API version: {api_version}\n")
    pager = client.models.list(config={"page_size": 100, "query_base": True})

    n = 0
    for m in pager:
        n += 1
        name = m.name or "(sin nombre)"
        print(f"--- [{n}] ---")
        print(f"  name (recurso):  {name}")
        if m.display_name:
            print(f"  display_name:    {m.display_name}")
        if m.description:
            desc = " ".join(m.description.split())
            if len(desc) > 280:
                desc = desc[:280] + "…"
            print(f"  descripcion:     {desc}")
        actions = m.supported_actions
        if actions:
            print(f"  capacidades:     {', '.join(actions)}")
        else:
            print("  capacidades:     (no informadas por la API para este modelo)")
        if m.input_token_limit is not None or m.output_token_limit is not None:
            print(
                f"  limites tokens:  entrada={m.input_token_limit}  salida={m.output_token_limit}"
            )
        sid = _short_model_id(name)
        print(f"  → GEMINI_MODEL:  {sid}")
        print()

    if n == 0:
        print("No se devolvió ningún modelo (revisa clave, cuota o GEMINI_API_VERSION).")


if __name__ == "__main__":
    main()
