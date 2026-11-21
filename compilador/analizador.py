"""Orquestador de los analisis lexico, sintactico, semantico y del AST."""

import tkinter as tk

from .arbol import arbol_a_texto, contar_nodos, profundidad
from .lexico import tokenize
from .reglas import validar_reglas
from .semantico import AnalizadorSemantico
from .sintactico import Parser


# ======================================================================
# ORQUESTADOR DE ANALISIS
# ======================================================================

class Analizador:
    def __init__(self, editor, consola):
        self.editor = editor
        self.consola = consola

    def _texto(self):
        return self.editor.get("1.0", "end-1c")

    def _preparar_consola(self):
        self.consola.tag_config("warning", foreground="yellow")
        self.consola.tag_config("error", foreground="#ff4444",
                                font=("Consolas", 11, "bold"))
        self.consola.tag_config("success", foreground="#00ff00",
                                font=("Consolas", 12, "bold"))
        self.consola.tag_config("info", foreground="#00cccc")
        self.consola.tag_config("asm", foreground="#aaffaa",
                                font=("Consolas", 10))
        self.consola.delete("1.0", tk.END)
        self.editor.tag_remove("error_line", "1.0", tk.END)
        self.editor.tag_remove("warning_line", "1.0", tk.END)

    def _mostrar_errores(self, errores):
        for e in errores:
            ubicacion = f"Linea {e.linea}"
            if getattr(e, "columna", 0):
                ubicacion += f", Col {e.columna}"
            if e.tipo == "warning":
                self.consola.insert(
                    tk.END, f"{ubicacion} -> Advertencia: {e.mensaje}\n", "warning"
                )
            else:
                self.consola.insert(
                    tk.END, f"{ubicacion} -> Error: {e.mensaje}\n", "error"
                )

    def _marcar_lineas(self, errores):
        for e in errores:
            if e.tipo == "warning" and e.linea:
                self.editor.tag_add(
                    "warning_line", f"{e.linea}.0", f"{e.linea}.end"
                )
        for e in errores:
            if e.tipo != "warning" and e.linea:
                self.editor.tag_add(
                    "error_line", f"{e.linea}.0", f"{e.linea}.end"
                )

    def _resumen(self, errores, texto):
        errores_reales = [e for e in errores if e.tipo != "warning"]
        advertencias = [e for e in errores if e.tipo == "warning"]
        self.consola.insert(tk.END, "\n" + "=" * 46 + "\n")
        if not texto.strip():
            self.consola.insert(tk.END, "El editor esta vacio.\n", "warning")
        elif not errores_reales:
            mensaje = "CODIGO CORRECTO"
            if advertencias:
                mensaje += f" ({len(advertencias)} advertencia(s))"
            self.consola.insert(tk.END, mensaje + "\n", "success")
        else:
            self.consola.insert(
                tk.END,
                f"CODIGO INCORRECTO ({len(errores_reales)} errores, "
                f"{len(advertencias)} advertencias)\n",
                "error",
            )
        return errores_reales, advertencias

    def resaltar(self, event=None):
        for etiqueta in ("keyword_java", "type_java", "variable_java"):
            self.editor.tag_remove(etiqueta, "1.0", tk.END)
        try:
            texto = self._texto()
            tokens, _ = tokenize(texto)
        except Exception:
            return
        for token in tokens:
            if token.tipo in ("RESERVADA", "BOOLEANO", "NULO"):
                etiqueta = "keyword_java"
            elif token.tipo == "TIPO":
                etiqueta = "type_java"
            elif token.tipo in ("IDENTIFICADOR", "IDENTIFICADOR_INVALIDO"):
                etiqueta = "variable_java"
            else:
                continue
            inicio = f"1.0 + {token.offset} chars"
            fin = f"1.0 + {token.offset + len(token.valor)} chars"
            self.editor.tag_add(etiqueta, inicio, fin)

    def lexico(self):
        texto = self._texto()
        tokens, errores = tokenize(texto)
        self._preparar_consola()
        self.consola.insert(tk.END, "--- ANALISIS LEXICO ---\n", "info")

        if not texto.strip():
            self.consola.insert(tk.END, "El editor esta vacio.\n", "warning")
            return

        self.consola.insert(
            tk.END,
            f"{'#':>4}  {'TIPO':<20} {'VALOR':<30} {'LINEA':>5} {'COL':>4}\n",
        )
        self.consola.insert(tk.END, "-" * 70 + "\n")
        numero = 0
        for token in tokens:
            if token.tipo == "EOF":
                continue
            numero += 1
            valor = token.valor.replace("\n", "\\n").replace("\t", "\\t")
            if len(valor) > 28:
                valor = valor[:25] + "..."
            self.consola.insert(
                tk.END,
                f"{numero:>4}  {token.tipo:<20} {valor:<30} "
                f"{token.linea:>5} {token.columna:>4}\n",
            )

        self.consola.insert(tk.END, "-" * 70 + "\n")
        self.consola.insert(
            tk.END,
            f"Total: {numero} token(s) | Errores lexicos: {len(errores)}\n",
        )
        if errores:
            self.consola.insert(tk.END, "\nErrores lexicos:\n", "error")
            self._mostrar_errores(errores)
        else:
            self.consola.insert(tk.END, "\nSin errores lexicos.\n", "success")

    def sintactico(self, en_vivo=False):
        texto = self._texto()
        self._preparar_consola()
        if en_vivo:
            self.consola.insert(
                tk.END, "--- ANALISIS SINTACTICO Y SEMANTICO (TIEMPO REAL) ---\n",
                "info",
            )
        else:
            self.consola.insert(
                tk.END, "--- ANALISIS SINTACTICO Y SEMANTICO ---\n", "info"
            )

        tokens, errores_lexicos = tokenize(texto)
        parser = Parser(tokens)
        raiz = parser.parse()
        reglas = validar_reglas(raiz, tokens)
        errores_sintacticos = list(parser.errores) + [
            r for r in reglas if r.tipo != "warning"]
        advertencias_reglas = [r for r in reglas if r.tipo == "warning"]

        if en_vivo and (errores_lexicos or errores_sintacticos):
            errores_semanticos = []
        else:
            analizador = AnalizadorSemantico()
            errores_semanticos = analizador.analizar(raiz) + advertencias_reglas

        todos = list(errores_lexicos) + list(errores_sintacticos) + list(errores_semanticos)

        if errores_lexicos:
            if not en_vivo:
                self.consola.insert(tk.END, "\n[ERRORES LEXICOS]\n", "info")
            self._mostrar_errores(errores_lexicos)
        if errores_sintacticos:
            if not en_vivo:
                self.consola.insert(tk.END, "\n[ERRORES SINTACTICOS]\n", "info")
            self._mostrar_errores(errores_sintacticos)
        if errores_semanticos:
            if not en_vivo:
                self.consola.insert(tk.END, "\n[ANALISIS SEMANTICO]\n", "info")
            self._mostrar_errores(errores_semanticos)

        self._marcar_lineas(todos)
        self._resumen(todos, texto)

    def semantico(self):
        texto = self._texto()
        self._preparar_consola()
        self.consola.insert(tk.END, "--- ANALISIS SEMANTICO ---\n", "info")

        if not texto.strip():
            self.consola.insert(tk.END, "El editor esta vacio.\n", "warning")
            return

        tokens, errores_lexicos = tokenize(texto)
        parser = Parser(tokens)
        raiz = parser.parse()
        if errores_lexicos or parser.errores:
            self.consola.insert(
                tk.END,
                "Nota: el codigo tiene errores lexicos/sintacticos; "
                "el resultado semantico puede ser parcial.\n",
                "warning",
            )
            self._mostrar_errores(list(errores_lexicos) + list(parser.errores))

        analizador = AnalizadorSemantico()
        errores = analizador.analizar(raiz)
        if errores:
            self.consola.insert(tk.END, "\n[RESULTADO SEMANTICO]\n", "info")
            self._mostrar_errores(errores)
        else:
            self.consola.insert(
                tk.END, "\nSin errores semanticos.\n", "success"
            )
        self._marcar_lineas(list(errores_lexicos) + list(parser.errores) + list(errores))

    def arbol(self):
        texto = self._texto()
        self._preparar_consola()
        self.consola.insert(tk.END, "--- ARBOL DE PARSEO ---\n", "info")

        if not texto.strip():
            self.consola.insert(tk.END, "El editor esta vacio.\n", "warning")
            return

        tokens, errores_lexicos = tokenize(texto)
        parser = Parser(tokens)
        raiz = parser.parse()
        analizador = AnalizadorSemantico()
        errores_semanticos = analizador.analizar(raiz)
        errores = (list(errores_lexicos) + list(parser.errores)
                   + validar_reglas(raiz, tokens) + list(errores_semanticos))

        if raiz.hijos:
            self.consola.insert(tk.END, arbol_a_texto(raiz) + "\n")
            self.consola.insert(
                tk.END,
                f"\nNodos: {contar_nodos(raiz)} | "
                f"Profundidad: {profundidad(raiz)}\n",
                "info",
            )
        else:
            self.consola.insert(
                tk.END, "No se pudo construir el arbol de parseo.\n", "error"
            )

        if errores:
            self.consola.insert(tk.END, "\n[ERRORES DETECTADOS DURANTE EL PARSEO]\n", "info")
            self._mostrar_errores(errores)
        else:
            self.consola.insert(
                tk.END, "\nArbol construido sin errores.\n", "success"
            )
        self._marcar_lineas(errores)
