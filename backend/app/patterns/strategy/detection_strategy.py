"""Patrón Strategy: intercambiar motores de análisis (Gemini, modelos locales, etc.)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class DetectionResult:
    """Salida normalizada del motor de detección."""

    etiqueta: str
    confianza: float
    detalle: str
    raw: dict[str, Any] | None = None


@dataclass
class DetectionContext:
    """Contexto mínimo para una inferencia (extensible)."""

    prompt_sistema: str
    frame_base64: str | None = None
    metadata: dict[str, Any] | None = None


class DetectionStrategy(ABC):
    """Estrategia intercambiable de análisis de escena / comportamiento."""

    @abstractmethod
    def analyze(self, context: DetectionContext) -> DetectionResult:
        """Ejecuta el análisis según el proveedor concreto."""
