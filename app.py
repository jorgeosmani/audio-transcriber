"""
Transcriptor de audios
======================
Aplicación de escritorio para transcribir varios audios a texto, ordenados
cronológicamente según la fecha que aparece en el nombre de cada archivo.

Ejecutar:   python app.py
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import customtkinter as ctk
except ImportError:
    print("Falta la librería 'customtkinter'. Instálala con:\n    pip install -r requirements.txt")
    sys.exit(1)

# Arrastrar y soltar es opcional: si tkinterdnd2 no está instalado, la app funciona igual.
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_DISPONIBLE = True
except Exception:
    _DND_DISPONIBLE = False

import exportar
from fechas import ORIGEN_MODIFICACION, ORIGEN_SIN_FECHA, InfoFecha, analizar_archivo, ordenar_rutas
from motor import (
    DISPOSITIVOS, EXTENSIONES_AUDIO, IDIOMAS, MODELO_POR_DEFECTO, MODELOS,
    Cancelado, MotorTranscripcion, Resultado, es_audio,
)

# Paleta
AZUL = ("#1D4E89", "#3B7BC8")
AZUL_HOVER = ("#163C6A", "#2F66A8")
VERDE = ("#2E7D32", "#3E9B43")
VERDE_HOVER = ("#24622A", "#33803A")
ROJO = ("#B3261E", "#D9473F")
ROJO_HOVER = ("#8E1E18", "#B8392F")
GRIS = ("#5F6B7A", "#4A5563")
GRIS_HOVER = ("#4B5562", "#3A4350")

_BASES = (ctk.CTk, TkinterDnD.DnDWrapper) if _DND_DISPONIBLE else (ctk.CTk,)


@dataclass
class Configuracion:
    modelo: str
    idioma: str | None
    dispositivo: str
    vad: bool
    marcas: bool


class App(*_BASES):
    def __init__(self) -> None:
        super().__init__()

        self.dnd_activo = False
        if _DND_DISPONIBLE:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd_activo = True
            except Exception:
                self.dnd_activo = False

        self.title("Transcriptor de audios")
        self.geometry("1180x840")
        self.minsize(980, 720)

        # Estado
        self.archivos: dict[Path, InfoFecha] = {}
        self.orden: list[Path] = []
        self.resultados: list[Resultado] = []
        self.motor = MotorTranscripcion()
        self.cola: queue.Queue = queue.Queue()
        self.cancelar = threading.Event()
        self.hilo: threading.Thread | None = None
        self.marcas_en_vista = True
        self.inicio_trabajo = 0.0
        self.ultima_salida: Path | None = None

        self._construir_interfaz()
        self._estilo_tabla()
        self._actualizar_lista()
        self.after(80, self._procesar_cola)
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        if self.dnd_activo:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._al_soltar)

    # =================================================================== UI
    def _construir_interfaz(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=2)
        self.grid_rowconfigure(3, weight=3)

        # --- Encabezado ------------------------------------------------------
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        cab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cab, text="Transcriptor de audios",
                     font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            cab,
            text="Agrega tus audios, revisa el orden por fecha y pulsa «Transcribir». "
                 "Todo se procesa en tu computadora.",
            text_color=("gray35", "gray70"),
        ).grid(row=1, column=0, sticky="w")
        self.selector_tema = ctk.CTkSegmentedButton(
            cab, values=["Claro", "Oscuro", "Sistema"], command=self._cambiar_tema)
        self.selector_tema.set("Sistema")
        self.selector_tema.grid(row=0, column=1, rowspan=2, sticky="e")

        # --- Fila central: archivos + configuración --------------------------
        centro = ctk.CTkFrame(self, fg_color="transparent")
        centro.grid(row=1, column=0, sticky="nsew", padx=18, pady=6)
        centro.grid_columnconfigure(0, weight=3)
        centro.grid_columnconfigure(1, weight=1, minsize=300)
        centro.grid_rowconfigure(0, weight=1)
        self._panel_archivos(centro)
        self._panel_configuracion(centro)

        # --- Progreso ---------------------------------------------------------
        self._panel_progreso()

        # --- Resultado --------------------------------------------------------
        self._panel_resultado()

        # --- Barra de estado --------------------------------------------------
        self.barra_estado = ctk.CTkLabel(self, text="Listo.", anchor="w",
                                         text_color=("gray35", "gray65"))
        self.barra_estado.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 8))

    def _panel_archivos(self, padre) -> None:
        marco = ctk.CTkFrame(padre)
        marco.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        marco.grid_columnconfigure(0, weight=1)
        marco.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(marco, text="1. Archivos de audio",
                     font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 4))

        barra = ctk.CTkFrame(marco, fg_color="transparent")
        barra.grid(row=1, column=0, sticky="ew", padx=10)
        self.btn_agregar = ctk.CTkButton(barra, text="+ Agregar archivos", width=150,
                                         fg_color=AZUL, hover_color=AZUL_HOVER,
                                         command=self._agregar_archivos)
        self.btn_agregar.pack(side="left", padx=4, pady=4)
        self.btn_carpeta = ctk.CTkButton(barra, text="+ Agregar carpeta", width=150,
                                         fg_color=AZUL, hover_color=AZUL_HOVER,
                                         command=self._agregar_carpeta)
        self.btn_carpeta.pack(side="left", padx=4, pady=4)
        self.btn_quitar = ctk.CTkButton(barra, text="Quitar seleccionados", width=150,
                                        fg_color=GRIS, hover_color=GRIS_HOVER,
                                        command=self._quitar_seleccionados)
        self.btn_quitar.pack(side="left", padx=4, pady=4)
        self.btn_limpiar = ctk.CTkButton(barra, text="Vaciar lista", width=110,
                                         fg_color=GRIS, hover_color=GRIS_HOVER,
                                         command=self._vaciar_lista)
        self.btn_limpiar.pack(side="left", padx=4, pady=4)

        # Tabla
        contenedor = ctk.CTkFrame(marco, fg_color="transparent")
        contenedor.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        contenedor.grid_columnconfigure(0, weight=1)
        contenedor.grid_rowconfigure(0, weight=1)

        columnas = ("n", "archivo", "fecha", "origen", "estado")
        self.tabla = ttk.Treeview(contenedor, columns=columnas, show="headings",
                                  selectmode="extended")
        for col, titulo, ancho, estirar, alin in (
            ("n", "#", 40, False, "center"),
            ("archivo", "Archivo", 300, True, "w"),
            ("fecha", "Fecha usada", 130, False, "center"),
            ("origen", "Fecha tomada de", 150, False, "center"),
            ("estado", "Estado", 140, False, "w"),
        ):
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, stretch=estirar, anchor=alin)
        self.tabla.grid(row=0, column=0, sticky="nsew")
        barra_v = ctk.CTkScrollbar(contenedor, command=self.tabla.yview)
        barra_v.grid(row=0, column=1, sticky="ns")
        self.tabla.configure(yscrollcommand=barra_v.set)
        self.tabla.bind("<Double-1>", self._reproducir_seleccion)
        self.tabla.bind("<Delete>", lambda e: self._quitar_seleccionados())

        # Pie de la lista
        pie = ctk.CTkFrame(marco, fg_color="transparent")
        pie.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))
        pie.grid_columnconfigure(0, weight=1)
        self.lbl_resumen = ctk.CTkLabel(pie, text="", anchor="w",
                                        text_color=("gray35", "gray65"))
        self.lbl_resumen.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(pie, text="Orden:").grid(row=0, column=1, padx=(8, 6))
        self.selector_orden = ctk.CTkSegmentedButton(
            pie, values=["Más antiguo primero", "Más nuevo primero"],
            command=lambda _v: self._actualizar_lista())
        self.selector_orden.set("Más antiguo primero")
        self.selector_orden.grid(row=0, column=2)

    def _panel_configuracion(self, padre) -> None:
        marco = ctk.CTkFrame(padre)
        marco.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        marco.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(marco, text="2. Configuración",
                     font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 8))

        fila = 1

        def etiqueta(texto):
            nonlocal fila
            ctk.CTkLabel(marco, text=texto, anchor="w").grid(
                row=fila, column=0, sticky="w", padx=14, pady=(6, 0))
            fila += 1

        etiqueta("Modelo de reconocimiento")
        self.opt_modelo = ctk.CTkOptionMenu(marco, values=list(MODELOS.keys()),
                                            command=self._al_cambiar_modelo,
                                            fg_color=AZUL, button_color=AZUL_HOVER)
        self.opt_modelo.set(MODELO_POR_DEFECTO)
        self.opt_modelo.grid(row=fila, column=0, sticky="ew", padx=14)
        fila += 1
        self.lbl_modelo = ctk.CTkLabel(marco, text=MODELOS[MODELO_POR_DEFECTO], anchor="w",
                                       wraplength=260, justify="left",
                                       text_color=("gray35", "gray65"),
                                       font=ctk.CTkFont(size=12))
        self.lbl_modelo.grid(row=fila, column=0, sticky="w", padx=14)
        fila += 1

        etiqueta("Idioma del audio")
        self.opt_idioma = ctk.CTkOptionMenu(marco, values=list(IDIOMAS.keys()),
                                            fg_color=AZUL, button_color=AZUL_HOVER)
        self.opt_idioma.set("Español")
        self.opt_idioma.grid(row=fila, column=0, sticky="ew", padx=14)
        fila += 1

        etiqueta("Procesar con")
        self.opt_dispositivo = ctk.CTkOptionMenu(marco, values=list(DISPOSITIVOS.keys()),
                                                 fg_color=AZUL, button_color=AZUL_HOVER)
        self.opt_dispositivo.set("Automático")
        self.opt_dispositivo.grid(row=fila, column=0, sticky="ew", padx=14)
        fila += 1

        self.chk_marcas = ctk.CTkCheckBox(marco, text="Incluir marcas de tiempo",
                                          command=self._al_cambiar_marcas)
        self.chk_marcas.select()
        self.chk_marcas.grid(row=fila, column=0, sticky="w", padx=14, pady=(14, 4))
        fila += 1
        self.chk_vad = ctk.CTkCheckBox(marco, text="Saltar silencios largos")
        self.chk_vad.select()
        self.chk_vad.grid(row=fila, column=0, sticky="w", padx=14, pady=4)
        fila += 1
        self.chk_mtime = ctk.CTkCheckBox(
            marco, text="Si el nombre no tiene fecha,\nusar la fecha de modificación",
            command=self._reanalizar)
        self.chk_mtime.select()
        self.chk_mtime.grid(row=fila, column=0, sticky="w", padx=14, pady=4)
        fila += 1
        self.chk_subcarpetas = ctk.CTkCheckBox(marco, text="Incluir subcarpetas al agregar carpeta")
        self.chk_subcarpetas.grid(row=fila, column=0, sticky="w", padx=14, pady=(4, 12))

    def _panel_progreso(self) -> None:
        marco = ctk.CTkFrame(self)
        marco.grid(row=2, column=0, sticky="ew", padx=18, pady=6)
        marco.grid_columnconfigure(1, weight=1)

        self.btn_transcribir = ctk.CTkButton(
            marco, text="▶  Transcribir", width=170, height=44,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=VERDE, hover_color=VERDE_HOVER, command=self._iniciar)
        self.btn_transcribir.grid(row=0, column=0, rowspan=2, padx=(12, 6), pady=10)
        self.btn_cancelar = ctk.CTkButton(
            marco, text="■  Cancelar", width=120, height=44,
            fg_color=ROJO, hover_color=ROJO_HOVER, state="disabled", command=self._cancelar)
        self.btn_cancelar.grid(row=0, column=2, rowspan=2, padx=(6, 12), pady=10)

        self.lbl_progreso = ctk.CTkLabel(marco, text="Esperando archivos…", anchor="w")
        self.lbl_progreso.grid(row=0, column=1, sticky="ew", padx=10, pady=(10, 0))

        barras = ctk.CTkFrame(marco, fg_color="transparent")
        barras.grid(row=1, column=1, sticky="ew", padx=10, pady=(2, 10))
        barras.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(barras, text="Archivo actual", width=100, anchor="w",
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="w")
        self.barra_archivo = ctk.CTkProgressBar(barras, progress_color=AZUL)
        self.barra_archivo.set(0)
        self.barra_archivo.grid(row=0, column=1, sticky="ew", pady=3)
        ctk.CTkLabel(barras, text="Total", width=100, anchor="w",
                     font=ctk.CTkFont(size=12)).grid(row=1, column=0, sticky="w")
        self.barra_total = ctk.CTkProgressBar(barras, progress_color=VERDE)
        self.barra_total.set(0)
        self.barra_total.grid(row=1, column=1, sticky="ew", pady=3)

    def _panel_resultado(self) -> None:
        marco = ctk.CTkFrame(self)
        marco.grid(row=3, column=0, sticky="nsew", padx=18, pady=6)
        marco.grid_columnconfigure(0, weight=1)
        marco.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(marco, text="3. Resultado",
                     font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(10, 0))

        self.pestanas = ctk.CTkTabview(marco, height=220)
        self.pestanas.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 4))
        tab_texto = self.pestanas.add("Transcripción")
        tab_registro = self.pestanas.add("Registro")
        for tab in (tab_texto, tab_registro):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        self.txt_resultado = ctk.CTkTextbox(tab_texto, wrap="word",
                                            font=ctk.CTkFont(size=14))
        self.txt_resultado.grid(row=0, column=0, sticky="nsew")
        self.txt_resultado.insert("end", "Aquí aparecerá el texto a medida que se transcriben los audios.\n"
                                         "Puedes editarlo antes de copiarlo.")
        self.txt_registro = ctk.CTkTextbox(tab_registro, wrap="word",
                                           font=ctk.CTkFont(family="Courier", size=12))
        self.txt_registro.grid(row=0, column=0, sticky="nsew")

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.botones_exportar = []
        for texto, comando in (
            ("Copiar texto", self._copiar),
            ("Guardar TXT", lambda: self._guardar("txt")),
            ("Guardar Markdown", lambda: self._guardar("md")),
            ("Guardar Word", lambda: self._guardar("docx")),
            ("Un .txt por audio", lambda: self._guardar_individuales("txt")),
            ("Subtítulos .srt", lambda: self._guardar_individuales("srt")),
        ):
            b = ctk.CTkButton(botones, text=texto, width=130, fg_color=AZUL,
                              hover_color=AZUL_HOVER, command=comando)
            b.pack(side="left", padx=4)
            self.botones_exportar.append(b)
        self.btn_abrir_salida = ctk.CTkButton(botones, text="Abrir carpeta de salida", width=170,
                                              fg_color=GRIS, hover_color=GRIS_HOVER,
                                              command=self._abrir_salida, state="disabled")
        self.btn_abrir_salida.pack(side="right", padx=4)

    def _estilo_tabla(self) -> None:
        oscuro = ctk.get_appearance_mode() == "Dark"
        fondo = "#2B2B2B" if oscuro else "#FFFFFF"
        texto = "#E6E6E6" if oscuro else "#1C1C1C"
        cabecera = "#383C42" if oscuro else "#E4EAF2"
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure("Treeview", background=fondo, fieldbackground=fondo,
                         foreground=texto, rowheight=28, borderwidth=0)
        estilo.configure("Treeview.Heading", background=cabecera, foreground=texto,
                         relief="flat", padding=(6, 6))
        estilo.map("Treeview", background=[("selected", "#2F66A8")],
                   foreground=[("selected", "#FFFFFF")])
        estilo.map("Treeview.Heading", background=[("active", cabecera)])
        self.tabla.tag_configure("aviso", foreground="#D08A00" if oscuro else "#A86400")
        self.tabla.tag_configure("sin_fecha", foreground="#E0605A" if oscuro else "#B3261E")
        self.tabla.tag_configure("listo", foreground="#5CC062" if oscuro else "#2E7D32")
        self.tabla.tag_configure("error", foreground="#E0605A" if oscuro else "#B3261E")
        self.tabla.tag_configure("proceso", foreground="#6FA8E8" if oscuro else "#1D4E89")

    # ============================================================ archivos
    def _agregar_rutas(self, rutas) -> None:
        nuevos, ignorados = 0, 0
        usar_mtime = bool(self.chk_mtime.get())
        for ruta in rutas:
            ruta = Path(ruta)
            if ruta.is_dir():
                patron = ruta.rglob("*") if self.chk_subcarpetas.get() else ruta.glob("*")
                hijos = [p for p in patron if p.is_file()]
                n, i = self._agregar_lista(hijos, usar_mtime)
            else:
                n, i = self._agregar_lista([ruta], usar_mtime)
            nuevos += n
            ignorados += i
        self._actualizar_lista()
        mensaje = f"Se agregaron {nuevos} archivo(s)."
        if ignorados:
            mensaje += f" Se ignoraron {ignorados} por no ser audio."
        self._estado(mensaje)
        self._log(mensaje)

    def _agregar_lista(self, rutas, usar_mtime) -> tuple[int, int]:
        nuevos = ignorados = 0
        for r in rutas:
            if not es_audio(r):
                ignorados += 1
                continue
            r = r.resolve()
            if r not in self.archivos:
                self.archivos[r] = analizar_archivo(r, usar_mtime)
                nuevos += 1
        return nuevos, ignorados

    def _agregar_archivos(self) -> None:
        patrones = " ".join(f"*{e}" for e in EXTENSIONES_AUDIO)
        rutas = filedialog.askopenfilenames(
            title="Elige los audios a transcribir",
            filetypes=[("Archivos de audio", patrones), ("Todos los archivos", "*.*")])
        if rutas:
            self._agregar_rutas(rutas)

    def _agregar_carpeta(self) -> None:
        carpeta = filedialog.askdirectory(title="Elige una carpeta con audios")
        if carpeta:
            self._agregar_rutas([carpeta])

    def _al_soltar(self, evento) -> None:
        if self._trabajando():
            return
        self._agregar_rutas(self.tk.splitlist(evento.data))

    def _quitar_seleccionados(self) -> None:
        if self._trabajando():
            return
        for iid in self.tabla.selection():
            self.archivos.pop(Path(iid), None)
        self._actualizar_lista()

    def _vaciar_lista(self) -> None:
        if self._trabajando() or not self.archivos:
            return
        if messagebox.askyesno("Vaciar lista", "¿Quitar todos los archivos de la lista?"):
            self.archivos.clear()
            self._actualizar_lista()

    def _reanalizar(self) -> None:
        usar_mtime = bool(self.chk_mtime.get())
        for r in list(self.archivos):
            self.archivos[r] = analizar_archivo(r, usar_mtime)
        self._actualizar_lista()

    def _actualizar_lista(self) -> None:
        descendente = self.selector_orden.get() == "Más nuevo primero"
        self.orden = ordenar_rutas(self.archivos, descendente=descendente)
        self.tabla.delete(*self.tabla.get_children())
        sin_fecha_nombre = 0
        for i, ruta in enumerate(self.orden, 1):
            info = self.archivos[ruta]
            tag = ()
            if info.origen == ORIGEN_MODIFICACION:
                tag, sin_fecha_nombre = ("aviso",), sin_fecha_nombre + 1
            elif info.origen == ORIGEN_SIN_FECHA:
                tag, sin_fecha_nombre = ("sin_fecha",), sin_fecha_nombre + 1
            self.tabla.insert("", "end", iid=str(ruta), tags=tag, values=(
                i, ruta.name, info.texto_fecha(), info.texto_origen(), "Pendiente"))

        total = len(self.orden)
        if total == 0:
            texto = "La lista está vacía. Agrega archivos o una carpeta"
            texto += " (también puedes arrastrarlos aquí)." if self.dnd_activo else "."
        else:
            texto = f"{total} archivo(s)"
            if sin_fecha_nombre:
                texto += f" · {sin_fecha_nombre} sin fecha en el nombre (en color)"
        self.lbl_resumen.configure(text=texto)
        if not self._trabajando():
            self.lbl_progreso.configure(
                text="Listo para transcribir." if total else "Esperando archivos…")

    def _reproducir_seleccion(self, _evento=None) -> None:
        sel = self.tabla.selection()
        if sel:
            self._abrir_con_sistema(Path(sel[0]))

    # ========================================================= transcribir
    def _config_actual(self) -> Configuracion:
        return Configuracion(
            modelo=self.opt_modelo.get(),
            idioma=IDIOMAS[self.opt_idioma.get()],
            dispositivo=DISPOSITIVOS[self.opt_dispositivo.get()],
            vad=bool(self.chk_vad.get()),
            marcas=bool(self.chk_marcas.get()),
        )

    def _iniciar(self) -> None:
        if self._trabajando():
            return
        if not self.orden:
            messagebox.showinfo("Sin archivos", "Primero agrega uno o más audios a la lista.")
            return
        sin_fecha = [r.name for r in self.orden if self.archivos[r].origen == ORIGEN_SIN_FECHA]
        if sin_fecha:
            muestra = "\n".join(f"• {n}" for n in sin_fecha[:8])
            if len(sin_fecha) > 8:
                muestra += f"\n… y {len(sin_fecha) - 8} más"
            if not messagebox.askyesno(
                "Archivos sin fecha",
                "Estos archivos no tienen fecha en el nombre y se transcribirán al final:\n\n"
                f"{muestra}\n\n¿Continuar?"):
                return

        cfg = self._config_actual()
        self.marcas_en_vista = cfg.marcas
        self.resultados = []
        self.cancelar.clear()
        self.txt_resultado.delete("1.0", "end")
        self.barra_archivo.set(0)
        self.barra_total.set(0)
        for ruta in self.orden:
            self._marcar(ruta, "Pendiente", ())
        self._habilitar(False)
        self.pestanas.set("Transcripción")
        self.inicio_trabajo = time.time()

        rutas = list(self.orden)
        info = {r: self.archivos[r] for r in rutas}
        self.hilo = threading.Thread(target=self._trabajo, args=(rutas, info, cfg), daemon=True)
        self.hilo.start()

    def _cancelar(self) -> None:
        if self._trabajando():
            self.cancelar.set()
            self.btn_cancelar.configure(state="disabled")
            self.lbl_progreso.configure(text="Cancelando… (termina la frase en curso)")

    def _trabajando(self) -> bool:
        return self.hilo is not None and self.hilo.is_alive()

    def _trabajo(self, rutas: list[Path], info: dict[Path, InfoFecha], cfg: Configuracion) -> None:
        """Se ejecuta en un hilo aparte; se comunica con la interfaz solo a través de la cola."""
        enviar = self.cola.put
        try:
            enviar(("progreso", f"Cargando el modelo «{cfg.modelo}»… "
                                f"(la primera vez se descarga y puede tardar varios minutos)"))
            enviar(("log", f"Cargando modelo {cfg.modelo} (dispositivo: {cfg.dispositivo})"))
            descripcion = self.motor.preparar(cfg.modelo, cfg.dispositivo)
            enviar(("log", f"Modelo listo: {descripcion}"))
        except Exception as e:
            enviar(("error_fatal", f"No se pudo cargar el modelo.\n\n{e}\n\n"
                                   "Revisa tu conexión a internet si es la primera vez que usas este modelo."))
            enviar(("fin", False))
            return

        total = len(rutas)
        for i, ruta in enumerate(rutas):
            if self.cancelar.is_set():
                break
            datos = info[ruta]
            res = Resultado(ruta=ruta, fecha=datos.fecha, tiene_hora=datos.tiene_hora,
                            origen_fecha=datos.origen)
            enviar(("archivo_inicio", i, total, ruta))
            t0 = time.time()
            try:
                def al_iniciar(idioma, duracion, res=res, i=i):
                    res.idioma, res.duracion = idioma, duracion
                    enviar(("encabezado", i, res))

                def al_segmento(seg, fraccion, i=i):
                    enviar(("segmento", i, total, seg, fraccion))

                segs, idioma, duracion = self.motor.transcribir(
                    ruta, idioma=cfg.idioma, vad=cfg.vad,
                    al_iniciar=al_iniciar, al_segmento=al_segmento, cancelar=self.cancelar)
                res.segmentos, res.idioma, res.duracion = segs, idioma, duracion
                enviar(("archivo_fin", i, total, res, time.time() - t0))
            except Cancelado:
                enviar(("archivo_cancelado", ruta))
                break
            except Exception as e:
                res.error = str(e) or e.__class__.__name__
                enviar(("archivo_error", i, total, res))

        enviar(("fin", self.cancelar.is_set()))

    # ============================================= mensajes del hilo -> UI
    def _procesar_cola(self) -> None:
        try:
            for _ in range(300):  # evita bloquear la interfaz si llegan muchos mensajes
                self._manejar(self.cola.get_nowait())
        except queue.Empty:
            pass
        self.after(80, self._procesar_cola)

    def _manejar(self, msg) -> None:
        tipo = msg[0]

        if tipo == "log":
            self._log(msg[1])

        elif tipo == "progreso":
            self.lbl_progreso.configure(text=msg[1])
            self._estado(msg[1])

        elif tipo == "archivo_inicio":
            _, i, total, ruta = msg
            self.lbl_progreso.configure(text=f"Transcribiendo {i + 1} de {total}:  {ruta.name}")
            self.barra_archivo.set(0)
            self.barra_total.set(i / total)
            self._marcar(ruta, "En proceso…", ("proceso",))
            self.tabla.see(str(ruta))
            self._log(f"[{i + 1}/{total}] {ruta.name}")

        elif tipo == "encabezado":
            _, i, res = msg
            self._escribir(("\n" if i else "") + exportar.encabezado(i + 1, res))

        elif tipo == "segmento":
            _, i, total, seg, fraccion = msg
            self._escribir(exportar.linea_segmento(seg, self.marcas_en_vista))
            self.barra_archivo.set(fraccion)
            self.barra_total.set((i + fraccion) / total)
            self._estado(f"Tiempo transcurrido: {self._transcurrido()}")

        elif tipo == "archivo_fin":
            _, i, total, res, segundos = msg
            self.resultados.append(res)
            if not res.segmentos:
                self._escribir("(No se detectó voz en este audio)\n")
            elif not self.marcas_en_vista:
                self._escribir("\n")
            self.barra_archivo.set(1)
            self.barra_total.set((i + 1) / total)
            self._marcar(res.ruta, f"✔ Listo ({segundos:.0f} s)", ("listo",))
            self._log(f"    listo en {segundos:.1f} s · idioma: {res.idioma} · "
                      f"duración: {exportar.tiempo(res.duracion)}")

        elif tipo == "archivo_error":
            _, i, total, res = msg
            self.resultados.append(res)
            self._escribir(f"⚠ No se pudo transcribir: {res.error}\n")
            self.barra_total.set((i + 1) / total)
            self._marcar(res.ruta, "✖ Error", ("error",))
            self._log(f"    ERROR: {res.error}")

        elif tipo == "archivo_cancelado":
            self._marcar(msg[1], "Cancelado", ("aviso",))

        elif tipo == "error_fatal":
            self._log(msg[1])
            messagebox.showerror("Error", msg[1])

        elif tipo == "fin":
            cancelado = msg[1]
            self._habilitar(True)
            listos = sum(1 for r in self.resultados if not r.error)
            errores = sum(1 for r in self.resultados if r.error)
            if cancelado:
                texto = f"Cancelado. Se transcribieron {listos} archivo(s)."
            else:
                texto = f"Terminado: {listos} transcrito(s)"
                texto += f", {errores} con error." if errores else "."
            texto += f"  Tiempo total: {self._transcurrido()}"
            self.lbl_progreso.configure(text=texto)
            self._estado(texto + "  Usa los botones de abajo para guardar el resultado.")
            self._log(texto)
            if self.resultados and not cancelado:
                self.bell()

    # ============================================================ exportar
    def _hay_resultados(self) -> bool:
        if not self.resultados:
            messagebox.showinfo("Nada que guardar", "Todavía no hay transcripciones.")
            return False
        return True

    def _copiar(self) -> None:
        texto = self.txt_resultado.get("1.0", "end").strip()
        if not texto:
            return
        self.clipboard_clear()
        self.clipboard_append(texto)
        self._estado("Texto copiado al portapapeles.")

    def _guardar(self, formato: str) -> None:
        if not self._hay_resultados():
            return
        nombres = {"txt": "Texto", "md": "Markdown", "docx": "Documento de Word"}
        destino = filedialog.asksaveasfilename(
            title="Guardar transcripción",
            defaultextension=f".{formato}",
            initialfile=f"transcripcion_{datetime.now():%Y%m%d_%H%M}.{formato}",
            filetypes=[(nombres[formato], f"*.{formato}")])
        if not destino:
            return
        marcas = bool(self.chk_marcas.get())
        try:
            funcion = {"txt": exportar.guardar_txt, "md": exportar.guardar_markdown,
                       "docx": exportar.guardar_docx}[formato]
            ruta = funcion(self.resultados, destino, marcas)
        except Exception as e:
            messagebox.showerror("No se pudo guardar", str(e))
            return
        self._tras_guardar(ruta, f"Guardado en {ruta}")

    def _guardar_individuales(self, formato: str) -> None:
        if not self._hay_resultados():
            return
        carpeta = filedialog.askdirectory(title="Elige la carpeta donde guardar los archivos")
        if not carpeta:
            return
        try:
            n = exportar.guardar_individuales(self.resultados, carpeta, formato,
                                              bool(self.chk_marcas.get()))
        except Exception as e:
            messagebox.showerror("No se pudo guardar", str(e))
            return
        self._tras_guardar(Path(carpeta), f"Se guardaron {n} archivo(s) .{formato} en {carpeta}")

    def _tras_guardar(self, ruta: Path, mensaje: str) -> None:
        self.ultima_salida = ruta
        self.btn_abrir_salida.configure(state="normal")
        self._estado(mensaje)
        self._log(mensaje)
        if ruta.is_file() and messagebox.askyesno("Guardado", f"{mensaje}\n\n¿Abrir el archivo ahora?"):
            self._abrir_con_sistema(ruta)
        elif ruta.is_dir():
            messagebox.showinfo("Guardado", mensaje)

    def _abrir_salida(self) -> None:
        if self.ultima_salida:
            carpeta = self.ultima_salida if self.ultima_salida.is_dir() else self.ultima_salida.parent
            self._abrir_con_sistema(carpeta)

    # ============================================================= varios
    def _al_cambiar_modelo(self, modelo: str) -> None:
        self.lbl_modelo.configure(text=MODELOS.get(modelo, ""))

    def _al_cambiar_marcas(self) -> None:
        # Si ya hay resultados, se vuelve a dibujar el texto con o sin marcas.
        if self.resultados and not self._trabajando():
            self.marcas_en_vista = bool(self.chk_marcas.get())
            self.txt_resultado.delete("1.0", "end")
            self.txt_resultado.insert("end", exportar.texto_combinado(
                self.resultados, self.marcas_en_vista))

    def _cambiar_tema(self, valor: str) -> None:
        ctk.set_appearance_mode({"Claro": "light", "Oscuro": "dark"}.get(valor, "system"))
        self.after(60, self._estilo_tabla)

    def _habilitar(self, activo: bool) -> None:
        estado = "normal" if activo else "disabled"
        for w in (self.btn_agregar, self.btn_carpeta, self.btn_quitar, self.btn_limpiar,
                  self.btn_transcribir, self.opt_modelo, self.opt_idioma, self.opt_dispositivo,
                  self.chk_marcas, self.chk_vad, self.chk_mtime, self.selector_orden,
                  *self.botones_exportar):
            w.configure(state=estado)
        self.btn_cancelar.configure(state="disabled" if activo else "normal")

    def _marcar(self, ruta: Path, estado: str, tags: tuple) -> None:
        iid = str(ruta)
        if not self.tabla.exists(iid):
            return
        valores = list(self.tabla.item(iid, "values"))
        valores[4] = estado
        if not tags:  # sin estado especial: recupera el color de aviso de fecha
            origen = self.archivos[ruta].origen if ruta in self.archivos else ""
            tags = {ORIGEN_MODIFICACION: ("aviso",), ORIGEN_SIN_FECHA: ("sin_fecha",)}.get(origen, ())
        self.tabla.item(iid, values=valores, tags=tags)

    def _escribir(self, texto: str) -> None:
        self.txt_resultado.insert("end", texto)
        self.txt_resultado.see("end")

    def _log(self, texto: str) -> None:
        self.txt_registro.insert("end", f"{datetime.now():%H:%M:%S}  {texto}\n")
        self.txt_registro.see("end")

    def _estado(self, texto: str) -> None:
        self.barra_estado.configure(text=texto)

    def _transcurrido(self) -> str:
        return exportar.tiempo(time.time() - self.inicio_trabajo)

    @staticmethod
    def _abrir_con_sistema(ruta: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(ruta)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(ruta)])
            else:
                subprocess.Popen(["xdg-open", str(ruta)])
        except Exception as e:
            messagebox.showerror("No se pudo abrir", str(e))

    def _al_cerrar(self) -> None:
        if self._trabajando():
            if not messagebox.askyesno("Transcripción en curso",
                                       "Hay una transcripción en curso. ¿Cerrar de todos modos?"):
                return
            self.cancelar.set()
        self.destroy()


def main() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
