"""Paquete del compilador Java -> ensamblador 8086.

Modulos principales:
    config          Constantes del lenguaje.
    lexico          Analizador lexico (tokens y errores).
    sintactico      Parser y AST.
    semantico       Analisis semantico y tabla de simbolos.
    reglas          Validacion de estructuras iterativas anidadas.
    arbol           Utilidades para imprimir y medir el AST.
    analizador      Orquestador de los analisis del IDE.
    generador8086   Traduccion del AST a ensamblador 8086.
    interprete_ast  Ejecucion de alto nivel del AST.
    ensamblador8086 Ensamblador interno .COM.
    interprete8086  CPU virtual de 16 bits.
    ui              Componentes de la interfaz Tkinter.
"""
