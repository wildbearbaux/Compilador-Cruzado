"""Manejo de archivos del editor (abrir, guardar, temporales)."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox


# ======================================================================
# MANEJADOR DE ARCHIVOS
# ======================================================================

class ManejadorArchivos:
    def __init__(self, editor, consola, lbl_ruta, sidebar, analizador=None, root=None):
        self.editor = editor
        self.consola = consola
        self.lbl_ruta = lbl_ruta
        self.sidebar = sidebar
        self.analizador = analizador
        self.root = root
        self.current_file = ''
        self.temp_file_path = ''
        self.extension = '.txt'
    
    def actualizar_temporal(self, event=None):
        if event and event.keysym in ['Up', 'Down', 'Left', 'Right', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R']:
            return
        
        if self.current_file:
            carpeta = os.path.dirname(self.current_file)
            nombre_base = os.path.basename(self.current_file)
        else:
            carpeta = os.getcwd()
            nombre_base = "Sin_titulo"
        
        nueva_ruta = os.path.join(carpeta, f"{nombre_base}_temporal.tmp")
        es_nuevo = not os.path.exists(nueva_ruta)
        self.temp_file_path = nueva_ruta
        
        try:
            with open(self.temp_file_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.get('1.0', tk.END))
            if es_nuevo:
                self.sidebar.cargar(carpeta)
        except Exception:
            pass
        
        if self.analizador:
            self.analizador.sintactico(en_vivo=True)
    
    def limpiar_temporal(self):
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            carpeta = os.path.dirname(self.temp_file_path)
            try:
                os.remove(self.temp_file_path)
                self.temp_file_path = ''
                self.sidebar.cargar(carpeta)
            except Exception:
                pass
    
    def abrir(self, event=None):
        try:
            ruta = filedialog.askopenfilename(
                parent=self.root,
                title="Seleccionar archivo",
                initialdir=os.path.dirname(self.current_file) if self.current_file else os.getcwd(),
                filetypes=[("Archivos", f"*{self.extension}"), ("Todos los archivos", "*.*")]
            )
            if ruta:
                self.abrir_en_editor(ruta)
        except Exception:
            ruta = filedialog.askopenfilename(
                title="Seleccionar archivo",
                filetypes=[("Archivos", f"*{self.extension}"), ("Todos los archivos", "*.*")]
            )
            if ruta:
                self.abrir_en_editor(ruta)
    
    def guardar(self, event=None):
        if not self.current_file:
            try:
                self.current_file = filedialog.asksaveasfilename(
                    parent=self.root,
                    title="Guardar como",
                    defaultextension=".txt",
                    initialdir=os.getcwd()
                )
            except Exception:
                self.current_file = filedialog.asksaveasfilename(
                    title="Guardar como", defaultextension=".txt"
                )
            if not self.current_file:
                return
        
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(self.editor.get('1.0', 'end-1c'))
            self.limpiar_temporal()
            try:
                messagebox.showinfo('Archivo guardado', "El archivo fue guardado con éxito!", parent=self.root)
            except Exception:
                messagebox.showinfo('Archivo guardado', "El archivo fue guardado con éxito!")
            self.lbl_ruta.config(text=f"Archivo actual: {self.current_file}")
            self.sidebar.cargar(os.path.dirname(self.current_file))
        except Exception:
            try:
                messagebox.showerror('Error', 'Ha ocurrido un error al guardar.', parent=self.root)
            except Exception:
                messagebox.showerror('Error', 'Ha ocurrido un error al guardar.')
    
    def limpiar(self, event=None):
        self.editor.delete('1.0', tk.END)
        self.limpiar_temporal()
        self.actualizar_temporal()
        self.consola.delete('1.0', tk.END)
    
    def salir(self, event=None):
        self.limpiar_temporal()
        self.editor.winfo_toplevel().destroy()
    
    def abrir_en_editor(self, ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                contenido = f.read()
            self.editor.delete('1.0', tk.END)
            self.editor.insert(tk.END, contenido)
            self.limpiar_temporal()
            self.editor.edit_reset()
            self.current_file = ruta
            self.lbl_ruta.config(text=f"Archivo actual: {self.current_file}")
            self.sidebar.cargar(os.path.dirname(ruta))
            self.actualizar_temporal()
            if self.analizador:
                self.analizador.resaltar()
        except Exception as e:
            messagebox.showerror("Error de lectura", f"No se pudo abrir el archivo:\n{e}")
    
    def insertar(self, texto):
        self.editor.insert(tk.INSERT, texto)
        self.actualizar_temporal()
