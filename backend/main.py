"""
Punto de entrada SmartGuard: carga de entorno, Observer para alertas,
Strategy lista para enchufar Gemini u otros modelos, captura de webcam.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite ejecutar `python main.py` desde backend/ sin instalar el paquete
_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.config.env_loader import load_environment, optional_env
from app.db.supabase_client import fetch_camara_by_id, insert_alerta_row
from app.utils.camara_id import parse_camara_id_env
from app.patterns.observer import (
    AlertEvent,
    AlertSubject,
    ConsoleAlertObserver,
    SupabaseAlertObserver,
)
from app.services.webcam_service import WebcamCapture


def _build_alert_subject(
    camara_id: int | None,
    *,
    use_supabase: bool = False,
    use_console: bool = True,
) -> AlertSubject:
    subject = AlertSubject()
    if use_console:
        subject.attach(ConsoleAlertObserver())
    if use_supabase:
        subject.attach(SupabaseAlertObserver(insert_fn=insert_alerta_row))
    return subject


def run_demo(camara_id: int | None) -> None:
    """Inserta una alerta de prueba en Supabase (tabla ``alertas``) vía anon key + RLS."""
    if camara_id is None:
        print(
            "SMARTGUARD_CAMARA_ID debe ser un entero (ej. 1) que exista en ``camaras.id``.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        if fetch_camara_by_id(camara_id) is None:
            print(
                f"No hay fila en ``camaras`` con id entero {camara_id}.",
                file=sys.stderr,
            )
            sys.exit(1)
    except Exception as e:
        print(f"Error al consultar ``camaras`` por id={camara_id}: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        subject = _build_alert_subject(
            camara_id, use_supabase=True, use_console=False
        )
        subject.notify(
            AlertEvent(
                tipo="sistema",
                severidad="info",
                descripcion="Demo SmartGuard — alerta persistida en Supabase",
                camara_id=camara_id,
                metadata={"modo": "demo_supabase"},
            )
        )
    except Exception as e:
        print(f"No se pudo insertar en Supabase: {e}", file=sys.stderr)
        print(
            "Comprueba SUPABASE_URL, SUPABASE_ANON_KEY y políticas RLS (INSERT en alertas).",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Listo: revisa la tabla ``alertas`` en el panel de Supabase.")


def run_capture_preview(camara_id: int | None, min_seconds: float = 10.0) -> None:
    """Ventana de video (imshow + waitKey); mínimo ``min_seconds`` o tecla 'q' para salir."""
    subject = _build_alert_subject(camara_id=camara_id, use_supabase=False)

    with WebcamCapture() as cam:
        n = cam.run_preview_window(min_seconds=min_seconds)
        subject.notify(
            AlertEvent(
                tipo="captura",
                severidad="info",
                descripcion=f"Previsualización OK — frames válidos: {n} (cierra con 'q' o tras {min_seconds}s)",
                camara_id=camara_id,
            )
        )


def run_gemini_smoke() -> None:
    """Una llamada mínima a Gemini (requiere GOOGLE_API_KEY)."""
    from app.patterns.strategy.detection_strategy import DetectionContext
    from app.patterns.strategy.gemini_strategy import GeminiDetectionStrategy

    # Usa GEMINI_MODEL y GEMINI_API_VERSION desde .env (load_environment ya se llamó en main).
    strategy = GeminiDetectionStrategy()
    ctx = DetectionContext(
        prompt_sistema=(
            'Responde solo JSON: {"etiqueta":"ok","confianza":1.0,"detalle":"smoke test"}'
        )
    )
    result = strategy.analyze(ctx)
    print("Gemini strategy:", result)


def main() -> None:
    load_environment()
    parser = argparse.ArgumentParser(description="SmartGuard backend")
    parser.add_argument(
        "command",
        nargs="?",
        default="demo",
        choices=("demo", "preview", "gemini-smoke", "full"),
        help="demo: insert en Supabase | preview: webcam | gemini-smoke: Gemini",
    )
    args = parser.parse_args()

    camara_id = parse_camara_id_env(optional_env("SMARTGUARD_CAMARA_ID", ""))

    if args.command == "demo":
        run_demo(camara_id)
    elif args.command == "preview":
        run_capture_preview(camara_id)
    elif args.command == "gemini-smoke":
        run_gemini_smoke()
    elif args.command == "full":
        # Observer + Supabase si hay credenciales; fallará require_env si faltan
        try:
            subject = _build_alert_subject(
                camara_id, use_supabase=True, use_console=True
            )
            subject.notify(
                AlertEvent(
                    tipo="sistema",
                    severidad="info",
                    descripcion="Modo full: Observer con persistencia Supabase (si configurado)",
                    camara_id=camara_id,
                )
            )
        except RuntimeError as e:
            print(e)
            sys.exit(1)


if __name__ == "__main__":
    main()
