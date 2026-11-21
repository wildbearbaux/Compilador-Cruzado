"""Ventana principal del IDE y conexion entre sus componentes."""

import os
import re
import shutil
import subprocess
import tempfile
import tkinter as tk
from tkinter import simpledialog

from ..analizador import Analizador
from ..ensamblador8086 import EnsambladorInterno8086, ErrorEnsamblado
from ..generador8086 import ErrorGeneracion, Generador8086
from ..interprete8086 import ErrorEjecucion, Interprete8086
from ..interprete_ast import InterpreteAST
from ..lexico import tokenize
from ..sintactico import Parser
from .archivos import ManejadorArchivos
from .busqueda import BusquedaReemplazo
from .numeros_linea import NumerosLinea
from .sidebar import Sidebar


# ======================================================================
# INTERFAZ GRAFICA (VENTANA PRINCIPAL DEL IDE)
# ======================================================================

class IDECompilador:
    def __init__(self, root):
        self.root = root
        self.root.title("IDE Compilador Java -> Ensamblador 8086")
        self.root.geometry("1200x760")
        self.root.configure(bg="#001a1a")

        self.ultimo_asm_generado = ""
        self.ultima_ruta_asm = ""
        self.ultimo_es_com_puro = True

        self._construir_ui()
        self._configurar_atajos()
        self.sidebar.cargar(os.getcwd())

    def _construir_ui(self):
        # Barra superior de informacion y botones rapidos
        barra_superior = tk.Frame(self.root, bg="#003333", height=36)
        barra_superior.pack(side=tk.TOP, fill=tk.X)

        self.lbl_ruta = tk.Label(
            barra_superior,
            text="Archivo actual: Sin guardar",
            bg="#003333",
            fg="#aadddd",
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_ruta.pack(side=tk.LEFT, padx=12, pady=6)

        estilo_btn = {
            "bg": "#005555",
            "fg": "#ffffff",
            "activebackground": "#007777",
            "activeforeground": "#ffffff",
            "bd": 0,
            "padx": 10,
            "pady": 4,
            "font": ("Segoe UI", 9, "bold"),
            "cursor": "hand2",
        }

        tk.Button(
            barra_superior,
            text="Ejecutar 8086 (Alt+5)",
            command=self.ensamblar_y_ejecutar8086,
            bg="#00796b",
            fg="#ffffff",
            activebackground="#009688",
            activeforeground="#ffffff",
            bd=0,
            padx=12,
            pady=4,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(4, 12), pady=4)

        tk.Button(
            barra_superior,
            text="Generar ASM 8086 (Alt+4)",
            command=self.generar_asm8086,
            **estilo_btn,
        ).pack(side=tk.RIGHT, padx=4, pady=4)

        tk.Button(
            barra_superior,
            text="Arbol (Alt+A)",
            command=self.ver_arbol,
            **estilo_btn,
        ).pack(side=tk.RIGHT, padx=4, pady=4)

        tk.Button(
            barra_superior,
            text="Semantico (Alt+M)",
            command=self.analisis_semantico,
            **estilo_btn,
        ).pack(side=tk.RIGHT, padx=4, pady=4)

        tk.Button(
            barra_superior,
            text="Sintactico (Alt+S)",
            command=self.analisis_sintactico,
            **estilo_btn,
        ).pack(side=tk.RIGHT, padx=4, pady=4)

        tk.Button(
            barra_superior,
            text="Lexico (Alt+L)",
            command=self.analisis_lexico,
            **estilo_btn,
        ).pack(side=tk.RIGHT, padx=4, pady=4)

        # Panel dividido principal (Sidebar izquierda | Editor + Consola derecha)
        panel_horizontal = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, bg="#004444", sashwidth=4, bd=0
        )
        panel_horizontal.pack(fill=tk.BOTH, expand=True)

        frame_sidebar = tk.Frame(panel_horizontal, bg="#002b2b", width=220)
        panel_horizontal.add(frame_sidebar, minsize=170)

        lbl_expl = tk.Label(
            frame_sidebar,
            text="EXPLORADOR",
            bg="#002222",
            fg="#80cbc4",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            padx=12,
            pady=6,
        )
        lbl_expl.pack(fill=tk.X)

        panel_vertical = tk.PanedWindow(
            panel_horizontal, orient=tk.VERTICAL, bg="#004444", sashwidth=4, bd=0
        )
        panel_horizontal.add(panel_vertical, minsize=600)

        # Area del editor con numeros de linea
        frame_editor = tk.Frame(panel_vertical, bg="#001f1f")
        panel_vertical.add(frame_editor, minsize=320)

        scroll_editor = tk.Scrollbar(frame_editor)
        scroll_editor.pack(side=tk.RIGHT, fill=tk.Y)

        self.editor = tk.Text(
            frame_editor,
            bg="#001f1f",
            fg="#e0f2f1",
            insertbackground="#ffffff",
            selectbackground="#00695c",
            font=("Consolas", 12),
            undo=True,
            wrap=tk.NONE,
            bd=0,
            padx=8,
            pady=6,
        )
        self.gutter = NumerosLinea(self.editor, frame_editor)
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor.configure(yscrollcommand=self._sync_scroll_editor(scroll_editor))
        scroll_editor.configure(command=self._scroll_ambos)

        # Etiquetas de resaltado de sintaxis y errores
        self.editor.tag_config("keyword_java", foreground="#4dd0e1", font=("Consolas", 12, "bold"))
        self.editor.tag_config("type_java", foreground="#ffb74d", font=("Consolas", 12, "bold"))
        self.editor.tag_config("variable_java", foreground="#e0f2f1")
        self.editor.tag_config("error_line", background="#4a1515")
        self.editor.tag_config("warning_line", background="#3e3511")

        # Area de consola / salida
        frame_consola = tk.Frame(panel_vertical, bg="#001414")
        panel_vertical.add(frame_consola, minsize=180)

        barra_consola = tk.Frame(frame_consola, bg="#002626")
        barra_consola.pack(fill=tk.X)
        tk.Label(
            barra_consola,
            text="CONSOLA DE SALIDA / ENSAMBLADOR 8086",
            bg="#002626",
            fg="#80cbc4",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
        ).pack(side=tk.LEFT)

        tk.Button(
            barra_consola,
            text="Ver ASM generado",
            command=self.mostrar_asm_en_consola,
            bg="#004d40",
            fg="#ffffff",
            bd=0,
            padx=8,
            pady=2,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=8, pady=2)

        scroll_consola = tk.Scrollbar(frame_consola)
        scroll_consola.pack(side=tk.RIGHT, fill=tk.Y)

        self.consola = tk.Text(
            frame_consola,
            bg="#001414",
            fg="#e0e0e0",
            font=("Consolas", 11),
            wrap=tk.WORD,
            bd=0,
            padx=10,
            pady=6,
            yscrollcommand=scroll_consola.set,
        )
        self.consola.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_consola.configure(command=self.consola.yview)

        # Inicializar componentes
        self.analizador = Analizador(self.editor, self.consola)
        self.sidebar = Sidebar(frame_sidebar, self._al_seleccionar_sidebar)
        self.archivos = ManejadorArchivos(
            self.editor, self.consola, self.lbl_ruta, self.sidebar, self.analizador, self.root
        )
        self.busqueda = BusquedaReemplazo(self.root, self.editor)

        self._construir_menu()

        self.editor.bind("<KeyRelease>", self._al_teclear, add="+")

    def _sync_scroll_editor(self, scrollbar):
        def _callback(primero, ultimo):
            scrollbar.set(primero, ultimo)
            self.gutter.actualizar()
        return _callback

    def _scroll_ambos(self, *args):
        self.editor.yview(*args)
        self.gutter.actualizar()

    def _al_teclear(self, event=None):
        self.analizador.resaltar()
        self.archivos.actualizar_temporal(event)

    def _al_seleccionar_sidebar(self, ruta):
        if os.path.isdir(ruta):
            self.sidebar.cargar(ruta)
        else:
            self.archivos.abrir_en_editor(ruta)

    def _construir_menu(self):
        menubar = tk.Menu(self.root)

        menu_archivo = tk.Menu(menubar, tearoff=0)
        menu_archivo.add_command(label="Abrir... (Ctrl+O)", command=self.archivos.abrir)
        menu_archivo.add_command(label="Guardar (Ctrl+S)", command=self.archivos.guardar)
        menu_archivo.add_command(label="Limpiar editor", command=self.archivos.limpiar)
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Salir", command=self.archivos.salir)
        menubar.add_cascade(label="Archivo", menu=menu_archivo)

        menu_editar = tk.Menu(menubar, tearoff=0)
        menu_editar.add_command(label="Buscar y Reemplazar (Ctrl+F)", command=self.busqueda.abrir)
        menubar.add_cascade(label="Editar", menu=menu_editar)

        menu_comp = tk.Menu(menubar, tearoff=0)
        menu_comp.add_command(label="Analisis Lexico (Alt+L)", command=self.analisis_lexico)
        menu_comp.add_command(label="Analisis Sintactico (Alt+S)", command=self.analisis_sintactico)
        menu_comp.add_command(label="Analisis Semantico (Alt+M)", command=self.analisis_semantico)
        menu_comp.add_command(label="Ver Arbol de Parseo (Alt+A)", command=self.ver_arbol)
        menu_comp.add_separator()
        menu_comp.add_command(label="Generar ensamblador 8086 (.asm) (Alt+4)", command=self.generar_asm8086)
        menu_comp.add_command(label="Ensamblar y ejecutar 8086 (Alt+5)", command=self.ensamblar_y_ejecutar8086)
        menu_comp.add_command(label="Ver ultimo ensamblador generado", command=self.mostrar_asm_en_consola)
        menu_comp.add_separator()
        menu_comp.add_command(label="Ejecutar con JDK Java (F5)", command=self.ejecutar_java)
        menubar.add_cascade(label="Compiladores", menu=menu_comp)

        self.root.config(menu=menubar)

    def _configurar_atajos(self):
        self.root.bind("<Control-o>", lambda e: self.archivos.abrir())
        self.root.bind("<Control-s>", lambda e: self.archivos.guardar())
        self.root.bind("<Control-f>", lambda e: self.busqueda.abrir())
        self.root.bind("<Alt-l>", lambda e: self.analisis_lexico())
        self.root.bind("<Alt-s>", lambda e: self.analisis_sintactico())
        self.root.bind("<Alt-m>", lambda e: self.analisis_semantico())
        self.root.bind("<Alt-a>", lambda e: self.ver_arbol())
        self.root.bind("<Alt-Key-4>", lambda e: self.generar_asm8086())
        self.root.bind("<Alt-Key-5>", lambda e: self.ensamblar_y_ejecutar8086())
        self.root.bind("<F5>", lambda e: self.ejecutar_java())
        self.root.protocol("WM_DELETE_WINDOW", self.archivos.salir)

    # ------------------------------------------------------------------
    # Acciones de analisis
    # ------------------------------------------------------------------
    def analisis_lexico(self):
        self.analizador.lexico()

    def analisis_sintactico(self, en_vivo=False):
        self.analizador.sintactico(en_vivo=en_vivo)

    def analisis_semantico(self):
        self.analizador.semantico()

    def ver_arbol(self):
        self.analizador.arbol()

    # ------------------------------------------------------------------
    # Generacion y ejecucion de Ensamblador 8086
    # ------------------------------------------------------------------
    def _ruta_salida_8086(self, extension):
        if self.archivos.current_file:
            carpeta = os.path.dirname(self.archivos.current_file)
            base = os.path.splitext(os.path.basename(self.archivos.current_file))[0]
        else:
            carpeta = os.getcwd()
            base = "programa8086"
        return os.path.join(carpeta, base + extension)

    def generar_asm8086(self, silencioso=False):
        texto = self.analizador._texto()
        if not silencioso:
            self.analizador._preparar_consola()
            self.consola.insert(tk.END, "--- GENERACION DE ENSAMBLADOR 8086 ---\n", "info")

        if not texto.strip():
            self.consola.insert(tk.END, "El editor esta vacio.\n", "warning")
            return None

        tokens, errores_lexicos = tokenize(texto)
        parser = Parser(tokens)
        raiz = parser.parse()
        errores = list(errores_lexicos) + list(parser.errores)
        if errores:
            self.analizador._mostrar_errores(errores)
            self.analizador._marcar_lineas(errores)
            return None

        generador = Generador8086()
        try:
            codigo_asm = generador.generar(raiz)
        except ErrorGeneracion as err:
            self.analizador._mostrar_errores([err])
            self.analizador._marcar_lineas([err])
            return None

        ruta_asm = self._ruta_salida_8086(".asm")
        with open(ruta_asm, "w", encoding="utf-8") as archivo:
            archivo.write(codigo_asm)

        self.ultimo_asm_generado = codigo_asm
        self.ultima_ruta_asm = ruta_asm
        self.ultimo_es_com_puro = generador.es_com_puro
        self.sidebar.cargar(os.path.dirname(ruta_asm))

        if not silencioso:
            self.consola.insert(
                tk.END,
                f"Archivo ensamblador 8086 generado:\n  {ruta_asm}\n"
                f"Lineas: {len(codigo_asm.splitlines())}\n\n",
                "success",
            )
            self.consola.insert(tk.END, codigo_asm, "asm")
        return ruta_asm, raiz

    def mostrar_asm_en_consola(self):
        if not self.ultimo_asm_generado:
            self.generar_asm8086(silencioso=False)
            return
        self.analizador._preparar_consola()
        self.consola.insert(
            tk.END,
            f"--- CODIGO ENSAMBLADOR 8086 ({os.path.basename(self.ultima_ruta_asm)}) ---\n\n",
            "info",
        )
        self.consola.insert(tk.END, self.ultimo_asm_generado, "asm")

    def ensamblar_y_ejecutar8086(self):
        self.analizador._preparar_consola()
        self.consola.insert(tk.END, "--- COMPILACION Y EJECUCION 8086 ---\n", "info")

        resultado = self.generar_asm8086(silencioso=True)
        if resultado is None:
            return
        ruta_asm, raiz = resultado

        self.consola.insert(
            tk.END,
            f"[1/2] Ensamblador 8086 generado: {ruta_asm}\n",
            "info",
        )

        # Si el programa es del subconjunto binario .COM puro, lo ensamblamos a .COM
        # y lo ejecutamos en la CPU virtual de 16 bits.
        if self.ultimo_es_com_puro:
            ruta_com = self._ruta_salida_8086(".com")
            try:
                ensamblador = EnsambladorInterno8086()
                binario = ensamblador.ensamblar(self.ultimo_asm_generado)
                with open(ruta_com, "wb") as f:
                    f.write(binario)
                self.sidebar.cargar(os.path.dirname(ruta_com))

                interprete = Interprete8086(ruta_com)
                salida = interprete.ejecutar()
                self.consola.insert(
                    tk.END,
                    f"[2/2] Ejecutable .COM generado ({len(binario)} bytes) y ejecutado:\n",
                    "info",
                )
                self.consola.insert(tk.END, "-" * 46 + "\n")
                self.consola.insert(tk.END, salida if salida else "(Sin salida en consola)\n")
                self.consola.insert(tk.END, "\n" + "-" * 46 + "\n")
                self.consola.insert(tk.END, "Ejecucion 8086 finalizada correctamente.\n", "success")
                return
            except (ErrorEnsamblado, ErrorEjecucion):
                # Si alguna instruccion excede el subconjunto binario, continuamos
                # con el ejecutor de alto nivel respaldado por el .asm generado.
                pass

        # Ejecucion completa (soporta try/catch/finally, Scanner, clases, metodos, String)
        self.consola.insert(
            tk.END,
            "[2/2] Ejecutando programa...\n" + "-" * 46 + "\n",
            "info",
        )
        self.root.update_idletasks()

        def pedir_dato(prompt):
            return simpledialog.askstring(
                "Entrada del programa (Scanner)",
                prompt,
                parent=self.root,
            )

        def al_imprimir(fragmento):
            self.consola.insert(tk.END, fragmento)
            self.consola.see(tk.END)
            self.root.update_idletasks()

        interprete_ast = InterpreteAST(
            pedir_entrada_fn=pedir_dato,
            al_imprimir_fn=al_imprimir,
        )
        interprete_ast.ejecutar(raiz)

        self.consola.insert(tk.END, "\n" + "-" * 46 + "\n")
        self.consola.insert(
            tk.END,
            f"Ejecucion finalizada. Codigo ASM 8086 guardado en: {os.path.basename(ruta_asm)}\n",
            "success",
        )

    # ------------------------------------------------------------------
    # Ejecucion directa con JDK Java (F5)
    # ------------------------------------------------------------------
    def ejecutar_java(self):
        texto = self.analizador._texto()
        self.analizador._preparar_consola()
        self.consola.insert(tk.END, "--- EJECUCION JAVA (JDK) ---\n", "info")

        if not texto.strip():
            self.consola.insert(tk.END, "El editor esta vacio.\n", "warning")
            return

        javac = shutil.which("javac")
        java = shutil.which("java")
        if not javac or not java:
            self.consola.insert(
                tk.END,
                "No se encontro 'javac'/'java' en el sistema. Usa 'Ejecutar 8086 (Alt+5)'.\n",
                "warning",
            )
            return

        coincidencia = re.search(r"\bpublic\s+class\s+([A-Za-z_]\w*)", texto)
        if not coincidencia:
            coincidencia = re.search(r"\bclass\s+([A-Za-z_]\w*)", texto)
        nombre_clase = coincidencia.group(1) if coincidencia else "Main"

        with tempfile.TemporaryDirectory() as tmpdir:
            ruta_java = os.path.join(tmpdir, f"{nombre_clase}.java")
            with open(ruta_java, "w", encoding="utf-8") as f:
                f.write(texto)

            comp = subprocess.run(
                [javac, ruta_java],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )
            if comp.returncode != 0:
                self.consola.insert(tk.END, comp.stderr, "error")
                return

            ejec = subprocess.run(
                [java, "-cp", tmpdir, nombre_clase],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )
            if ejec.stdout:
                self.consola.insert(tk.END, ejec.stdout)
            if ejec.stderr:
                self.consola.insert(tk.END, ejec.stderr, "error")
            if ejec.returncode == 0:
                self.consola.insert(tk.END, "\nEjecucion Java finalizada.\n", "success")
