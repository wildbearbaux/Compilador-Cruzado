"""Ventana de buscar y reemplazar."""

import tkinter as tk
from tkinter import messagebox


# ======================================================================
# BUSCAR Y REEMPLAZAR
# ======================================================================

class BusquedaReemplazo:
    def __init__(self, root, editor):
        self.root = root
        self.editor = editor
    
    def abrir(self, event=None):
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar y Reemplazar")
        ventana.geometry("400x180")
        ventana.configure(bg="#002222")
        ventana.transient(self.root)
        
        tk.Label(ventana, text="Buscar:", bg="#002222", fg="white").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        entry_buscar = tk.Entry(ventana, width=28)
        entry_buscar.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Label(ventana, text="Reemplazar:", bg="#002222", fg="white").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        entry_reemplazar = tk.Entry(ventana, width=28)
        entry_reemplazar.grid(row=1, column=1, padx=10, pady=10)
        
        def obtener_palabra():
            palabra = entry_buscar.get()
            for op in ['+', '-', '*', '/', '=']:
                palabra = palabra.replace(op, '')
            return palabra
        
        def buscar_siguiente():
            palabra = obtener_palabra()
            if not palabra.strip():
                return
            try:
                start_pos = self.editor.index(tk.SEL_LAST)
            except tk.TclError:
                start_pos = self.editor.index(tk.INSERT)
            
            wrapped = False
            original_start = start_pos
            
            while True:
                pos = self.editor.search(palabra, start_pos, stopindex=tk.END)
                if not pos:
                    if not wrapped:
                        start_pos = '1.0'
                        wrapped = True
                        continue
                    else:
                        messagebox.showinfo("Busqueda finalizada", "No se encontraron mas coincidencias.", parent=ventana)
                        return
                
                fin_pos = f"{pos}+{len(palabra)}c"
                char_prev = self.editor.get(f"{pos}-1c", pos) if pos != '1.0' else ' '
                char_next = self.editor.get(fin_pos, f"{fin_pos}+1c")
                
                if (char_prev.isalnum() or char_prev == '_') or (char_next.isalnum() or char_next == '_'):
                    start_pos = fin_pos
                    if wrapped and self.editor.compare(start_pos, '>=', original_start):
                        messagebox.showinfo("Busqueda finalizada", "No se encontraron mas coincidencias.", parent=ventana)
                        return
                    continue
                
                self.editor.tag_remove('sel', '1.0', tk.END)
                self.editor.tag_add('sel', pos, fin_pos)
                self.editor.mark_set(tk.INSERT, fin_pos)
                self.editor.see(pos)
                break
        
        def buscar_anterior():
            palabra = obtener_palabra()
            if not palabra.strip():
                return
            try:
                start_pos = self.editor.index(tk.SEL_FIRST)
            except tk.TclError:
                start_pos = self.editor.index(tk.INSERT)
            
            wrapped = False
            original_start = start_pos
            
            while True:
                pos = self.editor.search(palabra, start_pos, backwards=True, stopindex='1.0')
                if not pos:
                    if not wrapped:
                        start_pos = tk.END
                        wrapped = True
                        continue
                    else:
                        messagebox.showinfo("Busqueda finalizada", "No se encontraron mas coincidencias.", parent=ventana)
                        return
                
                fin_pos = f"{pos}+{len(palabra)}c"
                char_prev = self.editor.get(f"{pos}-1c", pos) if pos != '1.0' else ' '
                char_next = self.editor.get(fin_pos, f"{fin_pos}+1c")
                
                if (char_prev.isalnum() or char_prev == '_') or (char_next.isalnum() or char_next == '_'):
                    start_pos = pos
                    if wrapped and self.editor.compare(start_pos, '<=', original_start):
                        messagebox.showinfo("Busqueda finalizada", "No se encontraron mas coincidencias.", parent=ventana)
                        return
                    continue
                
                self.editor.tag_remove('sel', '1.0', tk.END)
                self.editor.tag_add('sel', pos, fin_pos)
                self.editor.mark_set(tk.INSERT, pos)
                self.editor.see(pos)
                break
        
        def reemplazar_actual():
            palabra = obtener_palabra()
            if not palabra.strip():
                return
            try:
                sel_start = self.editor.index(tk.SEL_FIRST)
                sel_end = self.editor.index(tk.SEL_LAST)
                seleccionado = self.editor.get(sel_start, sel_end)
                if seleccionado == palabra:
                    reemplazo = entry_reemplazar.get()
                    self.editor.delete(sel_start, sel_end)
                    self.editor.insert(sel_start, reemplazo)
                    self.root.analisis_sintactico(en_vivo=True)
                buscar_siguiente()
            except tk.TclError:
                buscar_siguiente()
        
        def reemplazar_todo():
            palabra = obtener_palabra()
            if not palabra.strip():
                return
            reemplazo = entry_reemplazar.get()
            start_pos = '1.0'
            count = 0
            while True:
                pos = self.editor.search(palabra, start_pos, stopindex=tk.END)
                if not pos:
                    break
                fin_pos = f"{pos}+{len(palabra)}c"
                char_prev = self.editor.get(f"{pos}-1c", pos) if pos != '1.0' else ' '
                char_next = self.editor.get(fin_pos, f"{fin_pos}+1c")
                
                if (char_prev.isalnum() or char_prev == '_') or (char_next.isalnum() or char_next == '_'):
                    start_pos = fin_pos
                    continue
                
                self.editor.delete(pos, fin_pos)
                self.editor.insert(pos, reemplazo)
                start_pos = f"{pos}+{len(reemplazo)}c"
                count += 1
            
            if count > 0:
                self.root.analisis_sintactico(en_vivo=True)
                messagebox.showinfo("Exito", f"Se reemplazaron {count} coincidencias.", parent=ventana)
            else:
                messagebox.showinfo("Sin resultados", "No se encontraron coincidencias exactas.", parent=ventana)
        
        frame_btns = tk.Frame(ventana, bg="#002222")
        frame_btns.grid(row=2, column=0, columnspan=2, pady=10)
        
        tk.Button(frame_btns, text="Buscar Anterior", command=buscar_anterior, width=15).grid(row=0, column=0, padx=5, pady=2)
        tk.Button(frame_btns, text="Buscar Siguiente", command=buscar_siguiente, width=15).grid(row=0, column=1, padx=5, pady=2)
        tk.Button(frame_btns, text="Reemplazar", command=reemplazar_actual, width=15).grid(row=1, column=0, padx=5, pady=2)
        tk.Button(frame_btns, text="Reemplazar Todo", command=reemplazar_todo, width=15).grid(row=1, column=1, padx=5, pady=2)
