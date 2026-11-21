"""Gutter o margen con los numeros de linea del editor."""

import tkinter as tk
from tkinter import font as tkfont


# ======================================================================
# NUMEROS DE LINEA (GUTTER)
# ======================================================================

class NumerosLinea:
    COLOR_FONDO = "#002a2a"
    COLOR_NUMERO = "#6f9a9a"
    COLOR_ACTUAL = "#ffffff"
    COLOR_SEPARADOR = "#005555"

    def __init__(self, editor, contenedor):
        self.editor = editor
        self.fuente = tkfont.Font(font=editor.cget("font"))
        self.ancho = self._calcular_ancho(1)

        self.canvas = tk.Canvas(
            contenedor,
            width=self.ancho,
            bg=self.COLOR_FONDO,
            bd=0,
            highlightthickness=0,
            takefocus=0,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.Y)
        self._conectar()

    def _conectar(self):
        self.editor.configure(yscrollcommand=self._al_desplazar)
        self.editor.bind("<Configure>", self.actualizar, add="+")
        self.editor.bind("<KeyRelease>", self.actualizar, add="+")
        self.editor.bind("<ButtonRelease-1>", self.actualizar, add="+")
        self.editor.bind("<<Modified>>", self._al_modificar, add="+")
        self.editor.bind("<<Paste>>", self._diferido, add="+")
        self.editor.bind("<<Cut>>", self._diferido, add="+")
        self.editor.bind("<<Undo>>", self._diferido, add="+")
        self.editor.bind("<<Redo>>", self._diferido, add="+")

        self.canvas.bind("<MouseWheel>", self._rueda)
        self.canvas.bind("<Button-4>", self._rueda_linux)
        self.canvas.bind("<Button-5>", self._rueda_linux)

    def _al_desplazar(self, primero, ultimo):
        self.actualizar()

    def _al_modificar(self, event=None):
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            self.actualizar()

    def _diferido(self, event=None):
        self.editor.after_idle(self.actualizar)

    def _rueda(self, event):
        self.editor.yview_scroll(-1 * (event.delta // 120), "units")
        self.actualizar()
        return "break"

    def _rueda_linux(self, event):
        self.editor.yview_scroll(-1 if event.num == 4 else 1, "units")
        self.actualizar()
        return "break"

    def _calcular_ancho(self, total_lineas):
        digitos = max(3, len(str(max(1, total_lineas))))
        return self.fuente.measure("0") * digitos + 14

    def _total_lineas(self):
        try:
            return int(self.editor.index("end-1c").split(".")[0])
        except (tk.TclError, ValueError):
            return 1

    def actualizar(self, event=None):
        if not self.canvas.winfo_exists():
            return

        self.canvas.delete("all")
        if not self.editor.winfo_ismapped():
            return

        total = self._total_lineas()
        nuevo_ancho = self._calcular_ancho(total)
        if nuevo_ancho != self.ancho:
            self.ancho = nuevo_ancho
            self.canvas.configure(width=self.ancho)

        alto_visible = self.editor.winfo_height()
        linea_actual = int(self.editor.index("insert").split(".")[0])

        indice = self.editor.index("@0,0")
        while True:
            info = self.editor.dlineinfo(indice)
            if info is None:
                break
            _, y, _, alto, _ = info
            if y > alto_visible:
                break

            numero = int(str(indice).split(".")[0])
            color = self.COLOR_ACTUAL if numero == linea_actual else self.COLOR_NUMERO
            self.canvas.create_text(
                self.ancho - 8,
                y + (alto // 2),
                anchor="e",
                text=str(numero),
                fill=color,
                font=self.fuente,
            )
            indice = self.editor.index(f"{indice}+1line")

        self.canvas.create_line(
            self.ancho - 1,
            0,
            self.ancho - 1,
            alto_visible,
            fill=self.COLOR_SEPARADOR,
        )
