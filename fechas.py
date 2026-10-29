"""
fechas.py
---------
Detecta la fecha (y hora, si existe) escrita en el nombre de un archivo de audio
y ordena una lista de archivos cronológicamente.

Formatos reconocidos (ejemplos):
    AUD-20240315-WA0012.ogg            WhatsApp (Android)
    PTT-20240315-WA0003.opus           Nota de voz de WhatsApp
    WhatsApp Audio 2024-03-15 at 14.30.22.ogg
    REC_20240315_143022.wav            Grabadoras de voz
    2024-03-15 14-30-22.mp3
    2024.03.15_1430.m4a
    15-03-2024 entrevista.mp3          Día-mes-año (con separador)
    audio_1710512345678.ogg            Marca de tiempo Unix (Telegram y otros)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

# Hora opcional que puede venir después de la fecha: "_143022", " 14.30.22", " at 14.30", "T14:30"
_HORA = (
    r"(?:[ _T.\-]*(?:at[ _\-]?|a las[ _\-]?)?"
    r"(?P<H>[01]\d|2[0-3])[\-_.:hH]?(?P<M>[0-5]\d)(?:[\-_.:mM]?(?P<S>[0-5]\d))?)?"
)

# Año-Mes-Día: 20240315, 2024-03-15, 2024_03_15, 2024.03.15
_PATRON_AMD = re.compile(
    r"(?<!\d)(?P<Y>(?:19|20)\d{2})(?P<sep>[\-_.]?)(?P<m>0[1-9]|1[0-2])(?P=sep)"
    r"(?P<d>0[1-9]|[12]\d|3[01])" + _HORA + r"(?!\d)",
    re.IGNORECASE,
)

# Día-Mes-Año (exige separador para no confundirse): 15-03-2024, 5_3_2024, 15.03.2024
_PATRON_DMA = re.compile(
    r"(?<!\d)(?P<d>0?[1-9]|[12]\d|3[01])(?P<sep>[\-_.])(?P<m>0?[1-9]|1[0-2])(?P=sep)"
    r"(?P<Y>(?:19|20)\d{2})" + _HORA + r"(?!\d)",
    re.IGNORECASE,
)

# Marca de tiempo Unix en segundos (10 dígitos) o milisegundos (13 dígitos), años ~2014-2033
_PATRON_UNIX = re.compile(r"(?<!\d)(?P<s>1[4-9]\d{8})(?P<ms>\d{3})?(?!\d)")

# Número de secuencia de WhatsApp (WA0012) para desempatar audios del mismo día
_PATRON_WA = re.compile(r"WA(\d+)", re.IGNORECASE)


# Valores posibles de InfoFecha.origen
ORIGEN_NOMBRE = "nombre"
ORIGEN_MODIFICACION = "modificacion"
ORIGEN_SIN_FECHA = "sin_fecha"


@dataclass
class InfoFecha:
    """Resultado del análisis de un archivo."""

    fecha: datetime | None
    origen: str          # "nombre", "modificacion" o "sin_fecha"
    tiene_hora: bool
    secuencia: int       # p. ej. el 12 de "WA0012"; 0 si no hay

    def texto_fecha(self) -> str:
        if self.fecha is None:
            return "—"
        formato = "%d/%m/%Y %H:%M" if self.tiene_hora else "%d/%m/%Y"
        return self.fecha.strftime(formato)

    def texto_origen(self) -> str:
        return {
            ORIGEN_NOMBRE: "Nombre del archivo",
            ORIGEN_MODIFICACION: "Fecha de modificación",
            ORIGEN_SIN_FECHA: "Sin fecha",
        }.get(self.origen, self.origen)


def detectar_fecha_en_nombre(nombre: str) -> tuple[datetime | None, bool]:
    """Devuelve (fecha, tiene_hora) a partir del nombre del archivo, o (None, False)."""
    base = Path(nombre).stem

    for patron in (_PATRON_AMD, _PATRON_DMA):
        for m in patron.finditer(base):
            try:
                fecha = datetime(
                    int(m["Y"]), int(m["m"]), int(m["d"]),
                    int(m["H"] or 0), int(m["M"] or 0), int(m["S"] or 0),
                )
            except ValueError:  # p. ej. 31 de febrero
                continue
            return fecha, m["H"] is not None

    m = _PATRON_UNIX.search(base)
    if m:
        try:
            return datetime.fromtimestamp(int(m["s"])), True
        except (OverflowError, OSError, ValueError):
            pass

    return None, False


def analizar_archivo(ruta: str | os.PathLike, usar_fecha_modificacion: bool = True) -> InfoFecha:
    """Analiza un archivo y decide qué fecha usar para ordenarlo."""
    ruta = Path(ruta)
    secuencia = 0
    m = _PATRON_WA.search(ruta.stem)
    if m:
        secuencia = int(m.group(1))

    fecha, tiene_hora = detectar_fecha_en_nombre(ruta.name)
    if fecha is not None:
        return InfoFecha(fecha, ORIGEN_NOMBRE, tiene_hora, secuencia)

    if usar_fecha_modificacion:
        try:
            fecha = datetime.fromtimestamp(ruta.stat().st_mtime)
            return InfoFecha(fecha, ORIGEN_MODIFICACION, True, secuencia)
        except OSError:
            pass

    return InfoFecha(None, ORIGEN_SIN_FECHA, False, secuencia)


def _clave_natural(texto: str) -> list:
    """'audio2' antes que 'audio10'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", texto)]


def ordenar_rutas(
    info: dict[Path, InfoFecha],
    rutas: Iterable[Path] | None = None,
    descendente: bool = False,
) -> list[Path]:
    """
    Ordena las rutas por fecha. Los archivos sin fecha van siempre al final,
    ordenados alfabéticamente, sin importar si el orden es ascendente o descendente.
    """
    rutas = list(rutas if rutas is not None else info.keys())
    con_fecha = [r for r in rutas if info[r].fecha is not None]
    sin_fecha = [r for r in rutas if info[r].fecha is None]

    con_fecha.sort(
        key=lambda r: (info[r].fecha, info[r].secuencia, _clave_natural(r.name)),
        reverse=descendente,
    )
    sin_fecha.sort(key=lambda r: _clave_natural(r.name))
    return con_fecha + sin_fecha
