"""Estrategia concreta: Google Gemini vía SDK oficial google-genai."""

from __future__ import annotations

import base64
import json
import re

from google import genai
from google.genai import types

from app.config.env_loader import optional_env, require_env
from app.patterns.strategy.detection_strategy import (
    DetectionContext,
    DetectionResult,
    DetectionStrategy,
)

# Valor por defecto si GEMINI_MODEL está vacío en .env (modelo reciente; ajusta según AI Studio)
_DEFAULT_MODEL = "gemini-3-flash"


def _bare_model_id(name: str) -> str:
    """
    Devuelve solo el id del modelo (p. ej. gemini-3-flash).
    Quita un prefijo ``models/`` si el usuario lo puso en .env; generate_content recibe
    siempre el string corto y el SDK añade ``models/`` internamente donde corresponda.
    """
    n = name.strip()
    if n.startswith("models/"):
        n = n.removeprefix("models/").strip()
    return n


class GeminiDetectionStrategy(DetectionStrategy):
    def __init__(self, model_name: str | None = None) -> None:
        api_key = require_env("GOOGLE_API_KEY")
        if model_name is not None and str(model_name).strip():
            resolved = str(model_name).strip()
        else:
            resolved = optional_env("GEMINI_MODEL", "").strip() or _DEFAULT_MODEL
        self._model_name = _bare_model_id(resolved)

        api_version = optional_env("GEMINI_API_VERSION", "v1").strip() or "v1"
        self._client = genai.Client(
            api_key=api_key,
            http_options={"api_version": api_version},
        )

    def analyze(self, context: DetectionContext) -> DetectionResult:
        prompt = context.prompt_sistema
        if context.frame_base64:
            raw = base64.b64decode(context.frame_base64)
            contents = [
                types.Part.from_bytes(data=raw, mime_type="image/jpeg"),
                types.Part.from_text(text=prompt),
            ]
        else:
            contents = prompt

        # Solo el id del modelo (sin models/ ni publishers/); el SDK normaliza la URL.
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=contents,
        )
        text = (response.text or "").strip()
        return self._parse_response(text)

    @staticmethod
    def _parse_response(text: str) -> DetectionResult:
        """Intenta JSON; si falla, devuelve resultado genérico."""
        try:
            m = re.search(r"\{[\s\S]*\}", text)
            blob = m.group(0) if m else text
            data = json.loads(blob)
            return DetectionResult(
                etiqueta=str(data.get("etiqueta", "desconocido")),
                confianza=float(data.get("confianza", 0.0)),
                detalle=str(data.get("detalle", text)),
                raw=data if isinstance(data, dict) else None,
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            return DetectionResult(
                etiqueta="sin_parseo",
                confianza=0.0,
                detalle=text[:2000],
                raw=None,
            )
