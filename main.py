"""Punto de entrada del IDE con compilador Java -> ensamblador 8086.

La implementacion esta organizada en el paquete `compilador/`:
lexer, parser, analizador semantico, reglas de estructuras iterativas,
utilidades del arbol, componentes de la interfaz, traductor/ejecutor 8086
y el orquestador de analisis.

Ejecutar con:

    python3 main.py
"""

import tkinter as tk

from compilador.ui.ide import IDECompilador


def main():
    root = tk.Tk()
    IDECompilador(root)
    root.mainloop()


if __name__ == "__main__":
    main()
