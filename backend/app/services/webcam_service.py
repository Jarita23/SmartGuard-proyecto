"""Captura eficiente desde webcam con OpenCV (índice configurable)."""

from __future__ import annotations

import base64
import os
import platform
import sys
import time

import cv2

# MSI Raider y muchos portátiles: cámara integrada en índice 0
DEFAULT_INDEX = 0


class WebcamCapture:
    """
    Mantiene un VideoCapture abierto y expone lectura de frames.
    En Windows abre con DirectShow (CAP_DSHOW) en primer lugar.
    """

    def __init__(self, index: int | None = None) -> None:
        if index is not None:
            self._index = index
        else:
            raw = os.environ.get("WEBCAM_INDEX", "").strip()
            self._index = int(raw) if raw else DEFAULT_INDEX
        self._cap: cv2.VideoCapture | None = None

    def _windows_open_attempts(self) -> list[tuple[int, int]]:
        """Orden: primero índice 0 + DSHOW, luego el índice configurado si distinto."""
        order: list[tuple[int, int]] = [
            (0, cv2.CAP_DSHOW),
            (0, 0),
        ]
        if self._index != 0:
            order.append((self._index, cv2.CAP_DSHOW))
            order.append((self._index, 0))
        seen: set[tuple[int, int]] = set()
        unique: list[tuple[int, int]] = []
        for pair in order:
            if pair not in seen:
                seen.add(pair)
                unique.append(pair)
        return unique

    def open(self) -> None:
        if self._cap is not None and self._cap.isOpened():
            return

        if platform.system() == "Windows":
            last_failed: tuple[int, int] | None = None
            for dev_index, api in self._windows_open_attempts():
                cap = cv2.VideoCapture(dev_index, api) if api else cv2.VideoCapture(dev_index)
                if cap.isOpened():
                    self._cap = cap
                    break
                cap.release()
                last_failed = (dev_index, api)

            if self._cap is None or not self._cap.isOpened():
                print(
                    "\n[SmartGuard — cámara] No se pudo abrir la webcam.\n"
                    "  • En MSI Raider la cámara integrada suele ser el **índice 0** (no el 1).\n"
                    "  • Comprueba `WEBCAM_INDEX` en `backend/.env` o déjalo vacío para usar 0.\n"
                    "  • Cierra Zoom, Teams, la app Cámara de Windows u otra app que use el dispositivo.\n"
                    "  • Último intento fallido: "
                    f"índice {last_failed[0] if last_failed else '?'}, API OpenCV {last_failed[1] if last_failed else '?'}\n",
                    file=sys.stderr,
                )
                raise RuntimeError(
                    "No se pudo abrir la webcam en Windows (CAP_DSHOW priorizado). "
                    "Revisa el mensaje anterior en stderr."
                )
        else:
            self._cap = cv2.VideoCapture(self._index)
            if not self._cap.isOpened():
                print(
                    f"\n[SmartGuard — cámara] No se pudo abrir el dispositivo índice {self._index}.\n",
                    file=sys.stderr,
                )
                raise RuntimeError(f"No se pudo abrir la webcam en el índice {self._index}")

        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FPS, 30)

    def read_bgr(self):
        """Devuelve (ok, frame_bgr)."""
        if self._cap is None:
            self.open()
        assert self._cap is not None
        return self._cap.read()

    def read_jpeg_base64(self, quality: int = 85) -> tuple[bool, str | None]:
        ok, frame = self.read_bgr()
        if not ok or frame is None:
            return False, None
        params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, buf = cv2.imencode(".jpg", frame, params)
        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        return True, b64

    def run_preview_window(
        self,
        *,
        min_seconds: float = 10.0,
        window_name: str = "SmartGuard — previsualización",
    ) -> int:
        """
        Muestra el video en una ventana con cv2.imshow.
        El bucle dura al menos ``min_seconds`` o hasta pulsar la tecla 'q'.
        ``cv2.waitKey(1)`` en cada iteración mantiene la ventana responsive en Windows.
        Devuelve la cantidad de frames mostrados correctamente.
        """
        self.open()
        frames_ok = 0
        t0 = time.monotonic()
        try:
            while True:
                ok, frame = self.read_bgr()
                if ok and frame is not None:
                    frames_ok += 1
                    cv2.imshow(window_name, frame)
                else:
                    blank = cv2.zeros((240, 320, 3), dtype="uint8")
                    cv2.putText(
                        blank,
                        "Sin frame",
                        (40, 120),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 0, 255),
                        2,
                    )
                    cv2.imshow(window_name, blank)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == ord("Q"):
                    break
                if time.monotonic() - t0 >= min_seconds:
                    break
        finally:
            cv2.destroyAllWindows()
        return frames_ok

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> WebcamCapture:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()
