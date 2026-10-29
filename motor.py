"""
motor.py
--------
Envoltura sobre faster-whisper: carga el modelo una sola vez, elige CPU o GPU
automáticamente y transcribe archivo por archivo informando el progreso.

faster-whisper lee directamente mp3, wav, ogg, opus, m4a, flac, etc.
(no hace falta instalar FFmpeg por separado).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

EXTENSIONES_AUDIO = (
    ".mp3", ".wav", ".ogg", ".opus", ".m4a", ".flac",
    ".aac", ".wma", ".webm", ".mp4", ".mka", ".amr",
)

# Nombre del modelo -> descripción para el usuario
MODELOS: dict[str, str] = {
    "tiny": "El más rápido, precisión básica (~75 MB)",
    "base": "Muy rápido, precisión aceptable (~145 MB)",
    "small": "Equilibrado, recomendado para empezar (~480 MB)",
    "medium": "Muy preciso, más lento (~1,5 GB)",
    "large-v3-turbo": "Casi tan preciso como large y mucho más rápido (~1,6 GB)",
    "large-v3": "Máxima precisión, el más lento (~3 GB)",
}
MODELO_POR_DEFECTO = "small"

# Nombre visible -> código de idioma (None = detección automática)
IDIOMAS: dict[str, str | None] = {
    "Detectar automáticamente": None,
    "Español": "es",
    "Inglés": "en",
    "Portugués": "pt",
    "Francés": "fr",
    "Italiano": "it",
    "Alemán": "de",
    "Catalán": "ca",
    "Quechua": "qu",
    "Chino": "zh",
    "Japonés": "ja",
    "Ruso": "ru",
}

DISPOSITIVOS: dict[str, str] = {
    "Automático": "auto",
    "Solo CPU": "cpu",
    "GPU NVIDIA (CUDA)": "cuda",
}


class Cancelado(Exception):
    """Se lanza cuando el usuario cancela la transcripción."""


@dataclass
class Segmento:
    inicio: float
    fin: float
    texto: str


@dataclass
class Resultado:
    """Transcripción de un archivo, con los datos necesarios para exportarla."""

    ruta: Path
    fecha: datetime | None = None
    tiene_hora: bool = False
    origen_fecha: str = "sin_fecha"
    segmentos: list[Segmento] = field(default_factory=list)
    idioma: str | None = None
    duracion: float = 0.0
    error: str | None = None

    @property
    def texto(self) -> str:
        return " ".join(s.texto for s in self.segmentos if s.texto).strip()


def es_audio(ruta: str | Path) -> bool:
    return Path(ruta).suffix.lower() in EXTENSIONES_AUDIO


class MotorTranscripcion:
    """Mantiene el modelo cargado entre transcripciones."""

    def __init__(self) -> None:
        self._modelo = None
        self._clave: tuple[str, str] | None = None
        self.descripcion = ""

    # ------------------------------------------------------------------ carga
    @staticmethod
    def _hay_gpu() -> bool:
        try:
            import ctranslate2
            return ctranslate2.get_cuda_device_count() > 0
        except Exception:
            return False

    def preparar(self, modelo: str, dispositivo: str = "auto") -> str:
        """Carga el modelo (y lo descarga la primera vez). Devuelve una descripción."""
        if self._clave == (modelo, dispositivo) and self._modelo is not None:
            return self.descripcion

        from faster_whisper import WhisperModel  # import diferido: arranque más rápido

        if dispositivo == "cuda" and not self._hay_gpu():
            raise RuntimeError(
                "No se encontró una GPU NVIDIA con CUDA. Elige «Automático» o «Solo CPU»."
            )

        usar_gpu = dispositivo == "cuda" or (dispositivo == "auto" and self._hay_gpu())
        self._modelo = None
        if usar_gpu:
            try:
                self._modelo = WhisperModel(modelo, device="cuda", compute_type="float16")
                self.descripcion = f"«{modelo}» en GPU (CUDA)"
            except Exception:
                if dispositivo == "cuda":
                    raise
                self._modelo = None  # se intentará en CPU

        if self._modelo is None:
            self._modelo = WhisperModel(modelo, device="cpu", compute_type="int8")
            self.descripcion = f"«{modelo}» en CPU"

        self._clave = (modelo, dispositivo)
        return self.descripcion

    def _pasar_a_cpu(self) -> None:
        from faster_whisper import WhisperModel

        modelo = self._clave[0] if self._clave else "small"
        self._modelo = WhisperModel(modelo, device="cpu", compute_type="int8")
        self._clave = (modelo, "cpu")
        self.descripcion = f"«{modelo}» en CPU"

    # ---------------------------------------------------------- transcripción
    def transcribir(
        self,
        ruta: str | Path,
        idioma: str | None = None,
        vad: bool = True,
        al_iniciar: Callable[[str, float], None] | None = None,
        al_segmento: Callable[[Segmento, float], None] | None = None,
        cancelar: threading.Event | None = None,
    ) -> tuple[list[Segmento], str, float]:
        """
        Transcribe un archivo. Devuelve (segmentos, idioma_detectado, duración_en_segundos).

        al_iniciar(idioma, duracion) se llama cuando se conoce el idioma y la duración.
        al_segmento(segmento, fraccion_0_a_1) se llama por cada frase reconocida.
        """
        if self._modelo is None:
            raise RuntimeError("El modelo no está cargado.")

        try:
            return self._transcribir(ruta, idioma, vad, al_iniciar, al_segmento, cancelar)
        except Cancelado:
            raise
        except Exception as e:
            # Si la GPU existe pero faltan librerías (cuBLAS/cuDNN), seguimos en CPU.
            mensaje = str(e).lower()
            if any(p in mensaje for p in ("cuda", "cublas", "cudnn")) and self._clave \
                    and self._clave[1] == "auto":
                self._pasar_a_cpu()
                return self._transcribir(ruta, idioma, vad, al_iniciar, al_segmento, cancelar)
            raise

    def _transcribir(self, ruta, idioma, vad, al_iniciar, al_segmento, cancelar):
        iterador, info = self._modelo.transcribe(
            str(ruta),
            language=idioma,
            vad_filter=vad,
            beam_size=5,
        )
        duracion = float(info.duration or 0.0)
        if al_iniciar:
            al_iniciar(info.language, duracion)

        segmentos: list[Segmento] = []
        for s in iterador:  # la transcripción ocurre mientras se recorre
            if cancelar is not None and cancelar.is_set():
                raise Cancelado()
            seg = Segmento(float(s.start), float(s.end), s.text.strip())
            segmentos.append(seg)
            if al_segmento:
                fraccion = min(seg.fin / duracion, 1.0) if duracion > 0 else 0.0
                al_segmento(seg, fraccion)

        return segmentos, info.language, duracion
