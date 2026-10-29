"""
cli.py — Transcriptor de audios desde la terminal (sin interfaz gráfica).

Ejemplos:
    python cli.py mis_audios/
    python cli.py mis_audios/ -o resultado.docx --modelo medium
    python cli.py a.mp3 b.ogg c.wav --sin-marcas --descendente
    python cli.py carpeta/ --solo-listar
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import exportar
from fechas import ORIGEN_SIN_FECHA, analizar_archivo, ordenar_rutas
from motor import DISPOSITIVOS, MODELO_POR_DEFECTO, MODELOS, MotorTranscripcion, Resultado, es_audio


def recolectar(entradas: list[str], recursivo: bool) -> list[Path]:
    rutas: list[Path] = []
    for e in entradas:
        p = Path(e)
        if p.is_dir():
            candidatos = p.rglob("*") if recursivo else p.glob("*")
            rutas += [c.resolve() for c in candidatos if c.is_file() and es_audio(c)]
        elif p.is_file() and es_audio(p):
            rutas.append(p.resolve())
        else:
            print(f"  (se ignora: {e})", file=sys.stderr)
    return list(dict.fromkeys(rutas))  # sin duplicados, conserva orden


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Transcribe audios a texto, ordenados por la fecha de su nombre.")
    ap.add_argument("entradas", nargs="+", help="Archivos de audio y/o carpetas")
    ap.add_argument("-o", "--salida", default=None,
                    help="Archivo de salida (.txt, .md o .docx). Por defecto: transcripcion_FECHA.txt")
    ap.add_argument("-m", "--modelo", default=MODELO_POR_DEFECTO, choices=list(MODELOS),
                    help=f"Modelo de Whisper (por defecto: {MODELO_POR_DEFECTO})")
    ap.add_argument("-i", "--idioma", default="es",
                    help="Código de idioma (es, en, pt…) o 'auto' para detectarlo (por defecto: es)")
    ap.add_argument("-d", "--dispositivo", default="auto", choices=list(DISPOSITIVOS.values()))
    ap.add_argument("-r", "--recursivo", action="store_true", help="Buscar también en subcarpetas")
    ap.add_argument("--descendente", action="store_true", help="Del más nuevo al más antiguo")
    ap.add_argument("--sin-marcas", action="store_true", help="No incluir marcas de tiempo")
    ap.add_argument("--sin-vad", action="store_true", help="No saltar silencios")
    ap.add_argument("--sin-fecha-modificacion", action="store_true",
                    help="No usar la fecha de modificación cuando el nombre no tiene fecha")
    ap.add_argument("--individuales", choices=["txt", "srt"],
                    help="Además, guardar un archivo por audio en la carpeta 'transcripciones/'")
    ap.add_argument("--solo-listar", action="store_true",
                    help="Solo mostrar el orden detectado, sin transcribir")
    args = ap.parse_args()

    rutas = recolectar(args.entradas, args.recursivo)
    if not rutas:
        print("No se encontraron archivos de audio.")
        return 1

    info = {r: analizar_archivo(r, not args.sin_fecha_modificacion) for r in rutas}
    orden = ordenar_rutas(info, descendente=args.descendente)

    print(f"\nOrden de transcripción ({len(orden)} archivos):")
    for i, r in enumerate(orden, 1):
        print(f"  {i:>3}. {info[r].texto_fecha():<17} [{info[r].texto_origen():<21}] {r.name}")
    if args.solo_listar:
        return 0

    idioma = None if args.idioma.lower() == "auto" else args.idioma
    motor = MotorTranscripcion()
    print(f"\nCargando modelo «{args.modelo}» (la primera vez se descarga)…")
    print("Modelo listo:", motor.preparar(args.modelo, args.dispositivo))

    resultados: list[Resultado] = []
    inicio = time.time()
    try:
        for i, ruta in enumerate(orden, 1):
            d = info[ruta]
            res = Resultado(ruta=ruta, fecha=d.fecha, tiene_hora=d.tiene_hora, origen_fecha=d.origen)
            print(f"\n[{i}/{len(orden)}] {ruta.name}")

            def progreso(seg, fraccion):
                barra = "█" * int(fraccion * 30)
                print(f"\r  {barra:<30} {fraccion * 100:5.1f}%", end="", flush=True)

            try:
                res.segmentos, res.idioma, res.duracion = motor.transcribir(
                    ruta, idioma=idioma, vad=not args.sin_vad, al_segmento=progreso)
                print(f"\r  ✔ listo · {exportar.tiempo(res.duracion)} de audio · idioma {res.idioma}"
                      + " " * 10)
            except Exception as e:
                res.error = str(e)
                print(f"\r  ✖ error: {e}")
            resultados.append(res)
    except KeyboardInterrupt:
        print("\n\nInterrumpido. Se guardará lo transcrito hasta ahora.")

    if not resultados:
        return 1

    marcas = not args.sin_marcas
    salida = Path(args.salida or f"transcripcion_{time.strftime('%Y%m%d_%H%M')}.txt")
    sufijo = salida.suffix.lower()
    if sufijo == ".docx":
        exportar.guardar_docx(resultados, salida, marcas)
    elif sufijo == ".md":
        exportar.guardar_markdown(resultados, salida, marcas)
    else:
        exportar.guardar_txt(resultados, salida, marcas)
    print(f"\nTranscripción guardada en: {salida.resolve()}")

    if args.individuales:
        carpeta = salida.parent / "transcripciones"
        n = exportar.guardar_individuales(resultados, carpeta, args.individuales, marcas)
        print(f"{n} archivo(s) .{args.individuales} en: {carpeta.resolve()}")

    print(f"Tiempo total: {exportar.tiempo(time.time() - inicio)}")
    sin_fecha = sum(1 for r in orden if info[r].origen == ORIGEN_SIN_FECHA)
    if sin_fecha:
        print(f"Aviso: {sin_fecha} archivo(s) no tenían fecha y se colocaron al final.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
