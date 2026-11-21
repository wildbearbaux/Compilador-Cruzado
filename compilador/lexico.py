"""Analizador lexico del lenguaje."""

from dataclasses import dataclass

from .config import (
    BOOLEANOS,
    DELIMITADORES,
    ESCRITURA_CORRECTA,
    NULOS,
    OPERADORES,
    RESERVADAS,
    TIPOS,
)


# ======================================================================
# ANALIZADOR LEXICO
# ======================================================================

# Convierte el texto fuente en una lista de tokens con linea, columna y
# desplazamiento (offset), y reporta los errores lexicos encontrados.


@dataclass
class Token:
    tipo: str
    valor: str
    linea: int
    columna: int
    offset: int = 0


@dataclass
class ErrorLexico:
    linea: int
    columna: int
    mensaje: str
    tipo: str = "error"


def tokenize(codigo):
    """Devuelve (tokens, errores). El ultimo token siempre es EOF."""
    tokens = []
    errores = []
    n = len(codigo)
    i = 0
    linea = 1
    columna = 1

    def avanzar():
        nonlocal i, linea, columna
        if i >= n:
            return
        c = codigo[i]
        i += 1
        if c == "\n":
            linea += 1
            columna = 1
        else:
            columna += 1

    def agregar(tipo, valor, lin, col, offset):
        tokens.append(Token(tipo, valor, lin, col, offset))

    def error(lin, col, mensaje):
        errores.append(ErrorLexico(lin, col, mensaje))

    while i < n:
        c = codigo[i]

        # Espacios en blanco
        if c in " \t\r\f\v":
            avanzar()
            continue

        # Salto de linea
        if c == "\n":
            avanzar()
            continue

        # Comentarios de linea
        if codigo.startswith("//", i):
            while i < n and codigo[i] != "\n":
                avanzar()
            continue

        # Comentarios de bloque
        if codigo.startswith("/*", i):
            lin_ini, col_ini = linea, columna
            avanzar()
            avanzar()
            cerrado = False
            while i < n:
                if codigo.startswith("*/", i):
                    avanzar()
                    avanzar()
                    cerrado = True
                    break
                avanzar()
            if not cerrado:
                error(lin_ini, col_ini, "Comentario de bloque sin cerrar (falta '*/')")
            continue

        # Cadenas de texto
        if c == '"':
            lin_ini, col_ini, offset = linea, columna, i
            avanzar()
            cerrada = False
            while i < n:
                actual = codigo[i]
                if actual == "\\":
                    avanzar()
                    if i < n:
                        avanzar()
                elif actual == '"':
                    avanzar()
                    cerrada = True
                    break
                elif actual == "\n":
                    break
                else:
                    avanzar()
            valor = codigo[offset:i]
            if not cerrada:
                error(lin_ini, col_ini, "Cadena de texto sin cerrar (falta '\"')")
            agregar("CADENA", valor, lin_ini, col_ini, offset)
            continue

        # Caracteres
        if c == "'":
            lin_ini, col_ini, offset = linea, columna, i
            avanzar()
            cerrada = False
            while i < n:
                actual = codigo[i]
                if actual == "\\":
                    avanzar()
                    if i < n:
                        avanzar()
                elif actual == "'":
                    avanzar()
                    cerrada = True
                    break
                elif actual == "\n":
                    break
                else:
                    avanzar()
            valor = codigo[offset:i]
            if not cerrada:
                error(lin_ini, col_ini, "Caracter sin cerrar (falta \"'\")")
            agregar("CARACTER", valor, lin_ini, col_ini, offset)
            continue

        # Numeros enteros y decimales
        if c.isdigit():
            lin_ini, col_ini, offset = linea, columna, i
            while i < n and codigo[i].isdigit():
                avanzar()
            es_decimal = False
            if i + 1 < n and codigo[i] == "." and codigo[i + 1].isdigit():
                es_decimal = True
                avanzar()
                while i < n and codigo[i].isdigit():
                    avanzar()
            if i < n and codigo[i] in "eE":
                k = i + 1
                if k < n and codigo[k] in "+-":
                    k += 1
                if k < n and codigo[k].isdigit():
                    es_decimal = True
                    while i < k:
                        avanzar()
                    while i < n and codigo[i].isdigit():
                        avanzar()
            # Un numero seguido de letras es un identificador invalido (2q)
            if i < n and (codigo[i].isalpha() or codigo[i] == "_"):
                while i < n and (codigo[i].isalnum() or codigo[i] == "_"):
                    avanzar()
                valor = codigo[offset:i]
                error(lin_ini, col_ini,
                      f"Identificador no valido '{valor}': no puede iniciar con un numero")
                agregar("IDENTIFICADOR_INVALIDO", valor, lin_ini, col_ini, offset)
            else:
                valor = codigo[offset:i]
                agregar("DECIMAL" if es_decimal else "ENTERO",
                        valor, lin_ini, col_ini, offset)
            continue

        # Identificadores y palabras reservadas
        if c.isalpha() or c == "_":
            lin_ini, col_ini, offset = linea, columna, i
            while i < n and (codigo[i].isalnum() or codigo[i] == "_"):
                avanzar()
            valor = codigo[offset:i]
            correcta = ESCRITURA_CORRECTA.get(valor.lower())
            if (correcta is not None and valor != correcta
                    and valor not in TIPOS):
                error(lin_ini, col_ini,
                      f"'{valor}' no es una palabra reservada; en Java se "
                      f"escribe '{correcta}'")
                valor = correcta
            if valor in TIPOS:
                tipo = "TIPO"
            elif valor in BOOLEANOS:
                tipo = "BOOLEANO"
            elif valor in NULOS:
                tipo = "NULO"
            elif valor in RESERVADAS:
                tipo = "RESERVADA"
            else:
                tipo = "IDENTIFICADOR"
            agregar(tipo, valor, lin_ini, col_ini, offset)
            continue

        # Delimitadores
        if c in DELIMITADORES:
            agregar("DELIMITADOR", c, linea, columna, i)
            avanzar()
            continue

        # Operadores (se prueba primero el de mayor longitud)
        encontrado = False
        for op in OPERADORES:
            if codigo.startswith(op, i):
                agregar("OPERADOR", op, linea, columna, i)
                for _ in range(len(op)):
                    avanzar()
                encontrado = True
                break
        if encontrado:
            continue

        # Caracter desconocido
        error(linea, columna, f"Caracter no reconocido '{c}'")
        agregar("DESCONOCIDO", c, linea, columna, i)
        avanzar()

    tokens.append(Token("EOF", "", linea, columna, i))
    return tokens, errores
