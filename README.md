# Transcriptor de audios

Aplicación de escritorio en Python que convierte varios audios a texto de una sola vez. Los ordena automáticamente **del más antiguo al más nuevo** leyendo la fecha escrita en el nombre de cada archivo (por ejemplo `AUD-20240315-WA0012.ogg`) y entrega una transcripción única, lista para copiar o guardar en TXT, Markdown, Word o subtítulos.

Todo el reconocimiento de voz se hace **en tu computadora** con [faster-whisper](https://github.com/SYSTRAN/faster-whisper), una versión optimizada del modelo Whisper. Tus audios no se envían a ningún servidor; solo se necesita internet la primera vez, para descargar el modelo.

---

## Contenido

1. [Qué hace](#qué-hace)
2. [Requisitos](#requisitos)
3. [Instalación](#instalación)
4. [Uso paso a paso](#uso-paso-a-paso)
5. [Cómo se detecta la fecha](#cómo-se-detecta-la-fecha)
6. [Elegir el modelo](#elegir-el-modelo)
7. [Formatos de salida](#formatos-de-salida)
8. [Uso desde la terminal](#uso-desde-la-terminal)
9. [Usar la GPU (opcional)](#usar-la-gpu-opcional)
10. [Solución de problemas](#solución-de-problemas)
11. [Estructura del proyecto](#estructura-del-proyecto)

---

## Qué hace

| Función | Detalle |
|---|---|
| Formatos de entrada | `.mp3` `.wav` `.ogg` `.opus` `.m4a` `.flac` `.aac` `.wma` `.webm` `.mp4` `.mka` `.amr` |
| Carga de archivos | Botones para agregar archivos o carpetas completas (con o sin subcarpetas) y, si está instalado `tkinterdnd2`, arrastrar y soltar sobre la ventana |
| Orden cronológico | Lee la fecha y la hora del nombre. Desempata los audios de WhatsApp del mismo día con su número `WA0001`, `WA0002`… |
| Archivos sin fecha | Usa la fecha de modificación (opcional) o los coloca al final, resaltados en color |
| Vista previa del orden | La tabla muestra la fecha usada y de dónde se tomó antes de transcribir |
| Transcripción en vivo | El texto aparece frase por frase mientras se procesa |
| Progreso | Barra del archivo actual, barra total, tiempo transcurrido y estado de cada archivo |
| Cancelar | Detiene el proceso y conserva lo ya transcrito |
| Idiomas | Español por defecto; también detección automática y otros 10 idiomas |
| Exportar | Copiar al portapapeles, TXT, Markdown, Word (.docx), un .txt por audio o subtítulos .srt |
| Otros | Tema claro/oscuro, doble clic en un archivo para escucharlo, registro técnico, versión de terminal |

---

## Requisitos

- **Python 3.9 o superior** (recomendado 3.11 o 3.12).
- **Windows 10/11, macOS o Linux.**
- **No hace falta instalar FFmpeg**: faster-whisper ya trae su propio decodificador de audio.
- Espacio en disco para el modelo: entre 75 MB y 3 GB según cuál elijas.
- Memoria RAM: 4 GB alcanzan para `small`; para `large-v3` se recomiendan 8 GB o más.

---

## Instalación

### Paso previo: descargar el proyecto

1. En la página del repositorio pulsa el botón verde **Code** y luego **Download ZIP**.
2. Descomprime el archivo donde prefieras. Se creará una carpeta llamada `audio-transcriber-main`.

Si usas Git, también puedes clonarlo:

```bash
git clone https://github.com/jorgeosmani/audio-transcriber.git
cd audio-transcriber
```
### Opción A: lanzador automático (la más fácil)

1. Abre la carpeta del proyecto que descargaste en el paso previo.
2. Ejecuta el lanzador de tu sistema:
   - **Windows:** doble clic en `iniciar_windows.bat`.
   - **macOS / Linux:** abre una terminal en la carpeta y ejecuta `bash iniciar_mac_linux.sh`.

La primera vez el lanzador crea un entorno virtual (`.venv`) e instala todo; tarda unos minutos. Las siguientes veces la aplicación abre directamente.

> **Windows:** al instalar Python desde [python.org](https://www.python.org/downloads/) marca la casilla **“Add Python to PATH”**.
>
> **Linux:** si aparece un error sobre `tkinter`, instálalo con `sudo apt install python3-tk` (Ubuntu/Debian) o `sudo dnf install python3-tkinter` (Fedora).

### Opción B: instalación manual

```bash
cd audio-transcriber-main   # o audio-transcriber si usaste git clone
python -m venv .venv

# Activar el entorno
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
python app.py
```

---

## Uso paso a paso

### 1. Agrega los audios

- **+ Agregar archivos**: selecciona uno o varios audios (Ctrl o Shift para elegir varios).
- **+ Agregar carpeta**: agrega todos los audios de una carpeta. Marca *Incluir subcarpetas* si quieres buscar también dentro de ellas.
- **Arrastrar y soltar**: suelta archivos o carpetas sobre la ventana.

Los archivos que no son audio se ignoran automáticamente y los repetidos no se duplican.

### 2. Revisa el orden

La tabla muestra cada archivo con su posición, la fecha usada y su origen:

| Color | Significado |
|---|---|
| Normal | La fecha se tomó del nombre del archivo |
| Ámbar | El nombre no tenía fecha; se usó la fecha de modificación del archivo |
| Rojo | No hay fecha; irá al final de la transcripción |

Con el selector **Orden** puedes cambiar entre *Más antiguo primero* y *Más nuevo primero*. Para quitar archivos, selecciónalos y pulsa **Quitar seleccionados** (o la tecla Supr). Haz **doble clic** en una fila para escuchar el audio con tu reproductor.

### 3. Configura

| Opción | Recomendación |
|---|---|
| Modelo de reconocimiento | `small` para empezar; `large-v3-turbo` si quieres más precisión (ver [Elegir el modelo](#elegir-el-modelo)) |
| Idioma del audio | Elige el idioma si lo conoces: es más rápido y preciso que la detección automática |
| Procesar con | *Automático* usa la GPU si hay una NVIDIA compatible; si no, la CPU |
| Incluir marcas de tiempo | Agrega `[01:23 → 01:30]` antes de cada frase. Si la desmarcas después de transcribir, el texto se reorganiza en párrafos sin volver a transcribir |
| Saltar silencios largos | Recomendado. Acelera el proceso y evita frases inventadas en los silencios |
| Usar la fecha de modificación | Para archivos cuyo nombre no tiene fecha |

### 4. Transcribe

Pulsa **▶ Transcribir**. La primera vez que uses un modelo se descargará (verás el mensaje *Cargando el modelo…*). Luego:

- el texto aparece en la pestaña **Transcripción** a medida que se reconoce;
- la columna **Estado** pasa a *En proceso…*, *✔ Listo* o *✖ Error*;
- la pestaña **Registro** guarda detalles técnicos (tiempos, idioma detectado, errores).

Puedes pulsar **■ Cancelar** en cualquier momento; lo ya transcrito se conserva y puede guardarse.

### 5. Guarda el resultado

| Botón | Resultado |
|---|---|
| Copiar texto | Copia el contenido del cuadro de texto, incluidas tus correcciones |
| Guardar TXT | Un archivo de texto con todos los audios en orden |
| Guardar Markdown | Documento `.md` con títulos por audio, ideal para Obsidian, Notion o GitHub |
| Guardar Word | Documento `.docx` con títulos y marcas de tiempo en gris |
| Un .txt por audio | Un archivo por audio, numerado `001_`, `002_`… para conservar el orden |
| Subtítulos .srt | Un archivo de subtítulos por audio, útil para video |
| Abrir carpeta de salida | Abre la carpeta donde guardaste lo último |

Ejemplo del texto generado:

```
════════════════════════════════════════════════════════════════
[1] AUD-20240315-WA0012.ogg
Fecha: 15/03/2024  (tomada del nombre del archivo)
Duración: 01:24   Idioma: es
════════════════════════════════════════════════════════════════
[00:00 → 00:04] Buenos días a todos.
[00:04 → 00:11] Les comparto el avance del proyecto de la semana.
```

> Los botones **Guardar** exportan la transcripción original. Si corriges algo en el cuadro de texto, usa **Copiar texto** para conservar tus cambios.

---

## Cómo se detecta la fecha

La aplicación busca la fecha en el nombre del archivo en este orden de prioridad:

| Patrón | Ejemplo de nombre | Fecha detectada |
|---|---|---|
| Año-mes-día sin separador | `AUD-20240315-WA0012.ogg` | 15/03/2024 |
| Año-mes-día con hora | `REC_20240315_143022.wav` | 15/03/2024 14:30:22 |
| Formato de WhatsApp “at” | `WhatsApp Audio 2024-03-15 at 14.30.22.ogg` | 15/03/2024 14:30:22 |
| Con guiones, puntos o guion bajo | `2024-03-15 14-30-22.mp3`, `2024.03.15_1430.m4a` | 15/03/2024 14:30 |
| Hora con letras | `Grabación 2023-12-01 09h05m.mp3` | 01/12/2023 09:05 |
| Día-mes-año (con separador) | `15-03-2024 entrevista.mp3`, `5_3_2024.wav` | 15/03/2024 y 05/03/2024 |
| Marca de tiempo Unix | `audio_1710512345678.ogg` (Telegram y otros) | 15/03/2024 |

Reglas de orden:

1. Primero se ordena por fecha y hora.
2. Si dos audios tienen la misma fecha y no tienen hora (típico de WhatsApp), se usa el número `WA0001`, `WA0002`… para respetar el orden en que fueron enviados.
3. Si aún empatan, se ordena por nombre de forma natural (`audio2` antes que `audio10`).
4. Los archivos sin ninguna fecha siempre van al final.

Las fechas imposibles (como `20240231`, un 31 de febrero) se descartan. El formato día-mes-año exige separador para no confundirlo con otros números.

> **Consejo:** si tus archivos no tienen fecha, renómbralos con el formato `AAAA-MM-DD_HH-MM-SS nombre.mp3` y el orden será exacto.

---

## Elegir el modelo

| Modelo | Tamaño | Velocidad | Precisión | Cuándo usarlo |
|---|---|---|---|---|
| `tiny` | ~75 MB | Muy alta | Básica | Pruebas rápidas |
| `base` | ~145 MB | Alta | Aceptable | Audios claros y computadoras modestas |
| `small` | ~480 MB | Media | Buena | **Recomendado para empezar** |
| `medium` | ~1,5 GB | Baja | Muy buena | Audios con ruido o acentos marcados |
| `large-v3-turbo` | ~1,6 GB | Media | Excelente | El mejor equilibrio si tienes 8 GB de RAM o GPU |
| `large-v3` | ~3 GB | Muy baja en CPU | Máxima | Material importante, idealmente con GPU |

Como referencia aproximada, en una computadora portátil moderna sin GPU el modelo `small` procesa un audio de 10 minutos en unos pocos minutos. Con GPU NVIDIA el proceso es varias veces más rápido. Los modelos se descargan una sola vez y quedan guardados en la caché de Hugging Face (`~/.cache/huggingface` en macOS/Linux, `C:\Users\<usuario>\.cache\huggingface` en Windows).

---

## Formatos de salida

- **TXT:** texto plano en UTF-8, abre en cualquier editor.
- **Markdown (.md):** un título por audio y la fecha en negrita.
- **Word (.docx):** requiere `python-docx` (incluido en `requirements.txt`).
- **Un .txt por audio:** archivos numerados en orden cronológico.
- **SRT:** subtítulos estándar compatibles con VLC, YouTube, Premiere, DaVinci, etc.

---

## Uso desde la terminal

Para procesar lotes grandes o automatizar el trabajo, existe `cli.py`, que usa el mismo motor sin abrir ventanas.

```bash
# Ver el orden detectado sin transcribir
python cli.py carpeta_audios/ --solo-listar

# Transcribir una carpeta y guardar en TXT
python cli.py carpeta_audios/

# Guardar en Word con el modelo medium y buscar en subcarpetas
python cli.py carpeta_audios/ -r -m medium -o resultado.docx

# Varios archivos, sin marcas de tiempo, del más nuevo al más antiguo
python cli.py a.mp3 b.ogg c.wav --sin-marcas --descendente

# Además del archivo general, un .srt por audio en la carpeta transcripciones/
python cli.py carpeta_audios/ --individuales srt
```

| Opción | Descripción |
|---|---|
| `-o`, `--salida` | Archivo de salida `.txt`, `.md` o `.docx` |
| `-m`, `--modelo` | `tiny`, `base`, `small`, `medium`, `large-v3-turbo`, `large-v3` |
| `-i`, `--idioma` | `es`, `en`, `pt`… o `auto` (por defecto `es`) |
| `-d`, `--dispositivo` | `auto`, `cpu` o `cuda` |
| `-r`, `--recursivo` | Incluir subcarpetas |
| `--descendente` | Del más nuevo al más antiguo |
| `--sin-marcas` | Texto corrido sin marcas de tiempo |
| `--sin-vad` | No saltar silencios |
| `--sin-fecha-modificacion` | No usar la fecha de modificación como respaldo |
| `--individuales txt\|srt` | Además, un archivo por audio |
| `--solo-listar` | Mostrar el orden y salir |

Con `Ctrl+C` se interrumpe el proceso y se guarda lo transcrito hasta ese momento.

---

## Usar la GPU (opcional)

Si tienes una tarjeta **NVIDIA**, la transcripción puede ser de 4 a 10 veces más rápida.

1. Instala un controlador NVIDIA actualizado.
2. Instala las librerías de CUDA 12 que usa faster-whisper:
   ```bash
   pip install nvidia-cublas-cu12 nvidia-cudnn-cu12==9.*
   ```
3. En la aplicación, elige *Procesar con → Automático* o *GPU NVIDIA (CUDA)*.

En modo *Automático*, si la GPU falla por falta de librerías, la aplicación sigue en CPU sin interrumpirse. Las GPU AMD, Intel y los chips Apple Silicon usan la CPU (en Apple Silicon el rendimiento en CPU es bueno).

---

## Solución de problemas

| Problema | Solución |
|---|---|
| `No module named 'tkinter'` | Linux: `sudo apt install python3-tk`. macOS con Homebrew: `brew install python-tk`. En Windows, reinstala Python con la opción *tcl/tk* marcada |
| `Falta la librería 'customtkinter'` | Activa el entorno virtual y ejecuta `pip install -r requirements.txt` |
| Se queda en “Cargando el modelo…” | La primera vez descarga el modelo; con `large-v3` pueden ser varios minutos. Revisa la conexión a internet |
| No puedo arrastrar archivos | `tkinterdnd2` no se instaló o no es compatible con tu sistema. Usa los botones de agregar; el resto funciona igual |
| El texto tiene frases repetidas o inventadas en silencios | Deja marcado *Saltar silencios largos* y prueba un modelo más grande |
| Transcribe en el idioma equivocado | Elige el idioma manualmente en lugar de *Detectar automáticamente* |
| Muy lento | Usa `small` o `base`, elige el idioma, o usa una GPU NVIDIA |
| Error de memoria | Usa un modelo más pequeño o cierra otros programas |
| Un archivo da error | Puede estar dañado o ser un formato poco común. Conviértelo a `.wav` o `.mp3` y vuelve a intentarlo. Los demás archivos siguen procesándose |
| En macOS no abre por permisos | Ejecuta `chmod +x iniciar_mac_linux.sh` |

---

## Estructura del proyecto

```
audio-transcriber/
├── app.py                 # Interfaz gráfica (ejecutar este)
├── cli.py                 # Versión de terminal
├── motor.py               # Carga del modelo y transcripción (faster-whisper)
├── fechas.py              # Detección de fechas en nombres y ordenamiento
├── exportar.py            # Exportación a TXT, Markdown, Word y SRT
├── requirements.txt       # Dependencias
├── iniciar_windows.bat    # Lanzador para Windows
├── iniciar_mac_linux.sh   # Lanzador para macOS y Linux
└── README.md
```

Para agregar un nuevo formato de nombre, edita las expresiones regulares al inicio de `fechas.py`. Para agregar idiomas, añade una entrada al diccionario `IDIOMAS` en `motor.py` usando su [código ISO 639-1](https://es.wikipedia.org/wiki/ISO_639-1).

---

## Privacidad

El audio se procesa localmente. Después de descargar el modelo, la aplicación funciona sin conexión a internet.

## Créditos

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper), basado en [Whisper](https://github.com/openai/whisper) de OpenAI (licencia MIT).
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) para la interfaz.
- [python-docx](https://github.com/python-openxml/python-docx) para la exportación a Word.
