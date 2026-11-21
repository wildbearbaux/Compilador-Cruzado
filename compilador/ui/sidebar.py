"""Barra lateral con el explorador de archivos."""

import os
import tkinter as tk
from tkinter import messagebox, simpledialog

from ..config import EXTENSION


# ======================================================================
# BARRA LATERAL DE ARCHIVOS
# ======================================================================

class Sidebar:
    def __init__(self, frame, callback):
        self.frame = frame
        self.callback = callback
        self.ruta_actual = os.path.abspath(os.getcwd())
        
        self.crear_barra_herramientas()
        
        self.lista = tk.Frame(self.frame, bg="#002b2b")
        self.lista.pack(fill=tk.BOTH, expand=True)
    
    def crear_barra_herramientas(self):
        barra = tk.Frame(self.frame, bg="#002b2b")
        barra.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        estilo = {
            "bg": "#004444",
            "fg": "#ffffff",
            "activebackground": "#006666",
            "activeforeground": "#ffffff",
            "bd": 0,
            "relief": tk.FLAT,
            "font": ("Segoe UI", 9),
            "cursor": "hand2",
        }
        
        self.btn_archivo = tk.Button(barra, text="+ Archivo", command=self.nuevo_archivo, **estilo)
        self.btn_archivo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        
        self.btn_carpeta = tk.Button(barra, text="+ Carpeta", command=self.nueva_carpeta, **estilo)
        self.btn_carpeta.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))
    
    def cargar(self, ruta_directorio=None):
        if ruta_directorio is None:
            ruta_directorio = self.ruta_actual
        ruta_directorio = os.path.abspath(ruta_directorio)
        self.ruta_actual = ruta_directorio
        
        for widget in self.lista.winfo_children():
            widget.destroy()
        
        try:
            elementos = os.listdir(ruta_directorio)
            elementos = [e for e in elementos if not e.startswith('.')]
            elementos.sort(key=lambda x: (not os.path.isdir(os.path.join(ruta_directorio, x)), x.lower()))
            
            padre = os.path.dirname(ruta_directorio)
            if ruta_directorio != padre and padre:
                lbl_back = tk.Label(self.lista, text=".. (Atras)", fg="#aadddd", bg="#002b2b", 
                                    font=("Segoe UI", 10, "bold"), anchor="w", cursor="hand2")
                lbl_back.pack(fill=tk.X, padx=15, pady=5)
                lbl_back.bind("<Button-1>", lambda e, path=padre: self.cargar(path))
            
            for elemento in elementos:
                ruta_completa = os.path.join(ruta_directorio, elemento)
                
                if elemento.endswith('.tmp'):
                    color_texto = "#ff8c00"
                elif elemento.endswith('.asm'):
                    color_texto = "#76ff03"
                else:
                    color_texto = "#cccccc"
                
                texto = f"{elemento}/" if os.path.isdir(ruta_completa) else elemento
                lbl = tk.Label(self.lista, text=texto, fg=color_texto, bg="#002b2b", 
                               font=("Segoe UI", 10), anchor="w", cursor="hand2")
                lbl.pack(fill=tk.X, padx=15, pady=2)
                lbl.bind("<Button-1>", lambda e, path=ruta_completa: self.callback(path))
        
        except Exception:
            lbl_error = tk.Label(self.lista, text="Acceso denegado", fg="red", bg="#002b2b")
            lbl_error.pack(fill=tk.X, padx=15, pady=2)
    
    def _validar_nombre(self, nombre):
        if nombre is None:
            return None
        nombre = nombre.strip()
        if not nombre:
            return None
        if nombre in ('.', '..') or os.sep in nombre or (os.altsep and os.altsep in nombre):
            messagebox.showerror("Nombre no valido", 
                                 "El nombre no puede contener separadores de ruta.", parent=self.frame)
            return None
        return nombre
    
    def nuevo_archivo(self, event=None):
        nombre = simpledialog.askstring(
            "Nuevo archivo",
            "Nombre del archivo:",
            initialvalue=f"nuevo{EXTENSION}",
            parent=self.frame
        )
        nombre = self._validar_nombre(nombre)
        if not nombre:
            return
        
        ruta = os.path.join(self.ruta_actual, nombre)
        if os.path.exists(ruta):
            messagebox.showerror("Archivo existente", 
                                 f"Ya existe un elemento llamado '{nombre}'.", parent=self.frame)
            return
        
        try:
            with open(ruta, 'x', encoding='utf-8'):
                pass
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear el archivo:\n{e}", parent=self.frame)
            return
        
        self.cargar(self.ruta_actual)
        self.callback(ruta)
    
    def nueva_carpeta(self, event=None):
        nombre = simpledialog.askstring(
            "Nueva carpeta",
            "Nombre de la carpeta:",
            parent=self.frame
        )
        nombre = self._validar_nombre(nombre)
        if not nombre:
            return
        
        ruta = os.path.join(self.ruta_actual, nombre)
        if os.path.exists(ruta):
            messagebox.showerror("Carpeta existente", 
                                 f"Ya existe un elemento llamado '{nombre}'.", parent=self.frame)
            return
        
        try:
            os.makedirs(ruta)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear la carpeta:\n{e}", parent=self.frame)
            return
        
        self.cargar(self.ruta_actual)
