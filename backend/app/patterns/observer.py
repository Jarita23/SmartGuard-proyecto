"""Patrón Observer: notificación de alertas a múltiples suscriptores."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AlertEvent:
    """Evento inmutable publicado cuando el sistema detecta una situación relevante."""

    tipo: str
    severidad: str
    descripcion: str
    # FK a ``camaras.id`` (bigint / int8 en Supabase).
    camara_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ocurrido_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AlertObserver(ABC):
    @abstractmethod
    def on_alert(self, event: AlertEvent) -> None:
        """Recibe una alerta publicada por el sujeto."""


class AlertSubject:
    """Sujeto observable: mantiene suscriptores y les notifica alertas."""

    def __init__(self) -> None:
        self._observers: list[AlertObserver] = []

    def attach(self, observer: AlertObserver) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: AlertObserver) -> None:
        self._observers.remove(observer)

    def notify(self, event: AlertEvent) -> None:
        for obs in list(self._observers):
            obs.on_alert(event)


class ConsoleAlertObserver(AlertObserver):
    """Observador de depuración: imprime alertas en consola."""

    def on_alert(self, event: AlertEvent) -> None:
        cam = f" | cam={event.camara_id}" if event.camara_id is not None else ""
        print(
            f"[ALERTA] {event.ocurrido_en.isoformat()} | "
            f"{event.severidad} | {event.tipo} | {event.descripcion}{cam}"
        )


class SupabaseAlertObserver(AlertObserver):
    """Persiste alertas en Supabase (tabla `alertas`) si hay cliente configurado."""

    def __init__(self, insert_fn: Any | None = None) -> None:
        """
        insert_fn: callable que recibe un dict fila-compatible con `alertas`.
        Permite inyectar el cliente en tests sin acoplar al singleton aquí.
        """
        self._insert = insert_fn

    def on_alert(self, event: AlertEvent) -> None:
        if self._insert is None:
            return
        row = {
            "tipo": event.tipo,
            "severidad": event.severidad,
            "descripcion": event.descripcion,
            "metadata": dict(event.metadata),
        }
        if event.camara_id is not None:
            row["camara_id"] = int(event.camara_id)
        self._insert(row)
