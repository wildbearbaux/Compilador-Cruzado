"""Analizador sintactico y construccion del arbol de parseo (AST)."""

from dataclasses import dataclass

from .lexico import Token


# ======================================================================
# ANALIZADOR SINTACTICO (PARSER)
# ======================================================================

# Construye un arbol de parseo (AST) para un subconjunto de Java adaptado al
# proyecto: clases, metodos, variables, asignaciones, if/else, for, while,
# try/catch/finally, return, llamadas y expresiones con precedencia.



@dataclass
class ErrorSintactico:
    linea: int
    columna: int
    mensaje: str
    tipo: str = "error"


class Nodo:
    """Nodo generico del arbol de parseo."""

    __slots__ = ("etiqueta", "valor", "linea", "columna", "tipo", "hijos")

    def __init__(self, etiqueta, valor=None, linea=None, columna=None, tipo=None):
        self.etiqueta = etiqueta
        self.valor = valor
        self.linea = linea
        self.columna = columna
        self.tipo = tipo
        self.hijos = []

    def agregar(self, hijo):
        if hijo is not None:
            self.hijos.append(hijo)
        return self

    def __repr__(self):
        return f"Nodo({self.etiqueta!r}, {self.valor!r}, hijos={len(self.hijos)})"


MODIFICADORES = {
    "public", "private", "protected", "static", "final", "abstract",
    "native", "synchronized", "transient", "volatile", "strictfp",
}

ASIGNACIONES = {"=", "+=", "-=", "*=", "/=", "%="}
LITERALES = {"ENTERO", "DECIMAL", "CADENA", "CARACTER", "BOOLEANO", "NULO"}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.errores = []

    # ------------------------------------------------------------------
    # Utilidades del flujo de tokens
    # ------------------------------------------------------------------
    def actual(self):
        return self.tokens[self.pos]

    def token(self, k=0):
        indice = self.pos + k
        if indice >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[indice]

    def es(self, valor):
        return self.actual().valor == valor

    def es_eof(self):
        return self.actual().tipo == "EOF"

    def avanzar(self):
        tok = self.actual()
        if tok.tipo != "EOF":
            self.pos += 1
        return tok

    def aceptar(self, valor):
        if self.es(valor):
            return self.avanzar()
        return None

    def error(self, mensaje, token=None):
        tok = token if token is not None else self.actual()
        if self.errores:
            ultimo = self.errores[-1]
            if (ultimo.linea == tok.linea and ultimo.columna == tok.columna
                    and ultimo.mensaje == mensaje):
                return
        self.errores.append(ErrorSintactico(tok.linea, tok.columna, mensaje))

    def describir(self, tok=None):
        tok = tok if tok is not None else self.actual()
        if tok.tipo == "EOF":
            return "fin de archivo"
        if tok.valor == "":
            return tok.tipo
        return tok.valor

    def esperar(self, valor, mensaje=None):
        if self.es(valor):
            return self.avanzar()
        self.error(mensaje or f"Se esperaba '{valor}' y se encontro '{self.describir()}'")
        return None

    def esperar_punto_coma(self, mensaje):
        """Consume ';' o reporta el error al final del token anterior."""
        if self.es(";"):
            self.avanzar()
            return True
        anterior = self.tokens[self.pos - 1] if self.pos > 0 else self.actual()
        self.error(mensaje, anterior)
        return False

    def es_identificador(self, tok=None):
        tok = tok if tok is not None else self.actual()
        return tok.tipo in ("IDENTIFICADOR", "IDENTIFICADOR_INVALIDO")

    def esperar_identificador(self, descripcion="un identificador"):
        tok = self.actual()
        if self.es_identificador(tok):
            return self.avanzar()
        self.error(f"Se esperaba {descripcion} y se encontro '{self.describir()}'")
        return self._token_falso("IDENTIFICADOR")

    def _token_falso(self, tipo, valor=""):
        tok = self.actual()
        return Token(tipo, valor, tok.linea, tok.columna, tok.offset)

    def sincronizar_sentencia(self):
        """Avanza hasta un punto seguro: ';' o '}'."""
        while not self.es_eof() and not self.es(";") and not self.es("}"):
            self.avanzar()
        if self.es(";"):
            self.avanzar()

    def sincronizar_miembro(self):
        """Avanza hasta el cierre de la clase o el inicio de otro miembro."""
        while not self.es_eof() and not self.es("}") and not self.es(";"):
            self.avanzar()
        if self.es(";"):
            self.avanzar()

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------
    def parse(self):
        raiz = Nodo("Programa")
        while not self.es_eof():
            inicio = self.pos
            self._elemento_global(raiz)
            if self.pos == inicio:
                self.avanzar()
        return raiz

    def _elemento_global(self, raiz):
        mods, anots = self._prefijos()
        if self.es("import") or self.es("package"):
            self._declaracion_externa(raiz)
            return
        if self.es("class") or self.es("interface") or self.es("enum"):
            raiz.agregar(self.clase(mods, anots))
            return
        if self._inicio_metodo():
            raiz.agregar(self.metodo(mods, anots, en_clase=False))
            return
        if self._inicio_declaracion():
            raiz.agregar(self.declaracion())
            return
        # Codigo a nivel global (estilo script): sentencias sueltas.
        if not self.es_eof() and not self.es("}"):
            raiz.agregar(self.sentencia())
            return
        self.error(f"Se esperaba una clase o una funcion y se encontro '{self.describir()}'")
        self.sincronizar_miembro()

    def _declaracion_externa(self, raiz):
        tok = self.actual()
        palabra = tok.valor
        self.avanzar()
        if palabra == "import" and self.es("static"):
            self.avanzar()
        partes = []
        while not self.es_eof() and not self.es(";"):
            partes.append(self.avanzar().valor)
        self.esperar(";")
        etiqueta = "Importacion" if palabra == "import" else "Paquete"
        raiz.agregar(Nodo(etiqueta, "".join(partes), tok.linea, tok.columna))

    # ------------------------------------------------------------------
    # Prefijos: anotaciones y modificadores
    # ------------------------------------------------------------------
    def _prefijos(self):
        mods = []
        anots = []
        while True:
            if self.es("@"):
                self.avanzar()
                nombre = self.esperar_identificador("el nombre de la anotacion")
                anots.append(nombre.valor)
                if self.es("("):
                    self._saltar_parentesis()
            elif (self.actual().valor in MODIFICADORES
                  and not (self.actual().valor == "synchronized"
                           and self.token(1).valor == "(")):
                mods.append(self.avanzar().valor)
            else:
                break
        return mods, anots

    def _saltar_parentesis(self):
        if not self.es("("):
            return
        nivel = 0
        while not self.es_eof():
            if self.es("("):
                nivel += 1
            elif self.es(")"):
                nivel -= 1
                if nivel == 0:
                    self.avanzar()
                    return
            self.avanzar()

    def _agregar_prefijos(self, nodo, mods, anots):
        if mods:
            nodo.agregar(Nodo("Modificadores", " ".join(mods), nodo.linea, nodo.columna))
        if anots:
            nodo.agregar(Nodo("Anotaciones", " ".join(anots), nodo.linea, nodo.columna))

    # ------------------------------------------------------------------
    # Clases y miembros
    # ------------------------------------------------------------------
    def clase(self, mods=None, anots=None):
        mods = mods or []
        anots = anots or []
        tok = self.actual()
        if tok.valor in ("class", "interface", "enum"):
            self.avanzar()
        else:
            self.esperar("class")
        nombre = self.esperar_identificador("el nombre de la clase")
        nodo = Nodo("Clase", nombre.valor, tok.linea, tok.columna)
        self._agregar_prefijos(nodo, mods, anots)
        if self.aceptar("extends"):
            padre = self.esperar_identificador("el nombre de la clase padre")
            nodo.agregar(Nodo("Extiende", padre.valor, padre.linea, padre.columna))
        if self.aceptar("implements"):
            interfaces = [self.esperar_identificador("el nombre de la interfaz").valor]
            while self.aceptar(","):
                interfaces.append(self.esperar_identificador("el nombre de la interfaz").valor)
            nodo.agregar(Nodo("Implementa", ", ".join(interfaces), tok.linea, tok.columna))
        self.esperar("{")
        while not self.es_eof() and not self.es("}"):
            inicio = self.pos
            self._miembro_clase(nodo)
            if self.pos == inicio:
                self.avanzar()
        self.esperar("}")
        return nodo

    def _miembro_clase(self, clase):
        mods, anots = self._prefijos()
        if self.es("class") or self.es("interface") or self.es("enum"):
            clase.agregar(self.clase(mods, anots))
            return
        if self._inicio_metodo():
            clase.agregar(self.metodo(mods, anots, en_clase=True))
            return
        if self._inicio_declaracion():
            clase.agregar(self.declaracion())
            return
        if self.es(";"):
            self.avanzar()
            return
        self.error(f"Se esperaba un metodo o una declaracion y se encontro '{self.describir()}'")
        self.sincronizar_miembro()

    def _inicio_metodo(self):
        k = 0
        if self.es_identificador(self.token(k)) and self.token(k + 1).valor == "(":
            return True
        if (self.token(k).tipo == "TIPO" or self.token(k).valor == "void"
                or self.es_identificador(self.token(k))):
            j = k + 1
            while self.token(j).valor == "[" and self.token(j + 1).valor == "]":
                j += 2
            if self.es_identificador(self.token(j)) and self.token(j + 1).valor == "(":
                return True
        return False

    def _inicio_declaracion(self):
        if self.token(0).tipo == "TIPO":
            j = 1
            while self.token(j).valor == "[" and self.token(j + 1).valor == "]":
                j += 2
            return self.es_identificador(self.token(j))
        # Tipo objeto: Scanner sc = ...
        if self.es_identificador(self.token(0)) and self.es_identificador(self.token(1)):
            return True
        return False

    def metodo(self, mods=None, anots=None, en_clase=True):
        mods = mods or []
        anots = anots or []
        inicio = self.actual()
        if en_clase and self.es_identificador(self.actual()) and self.token(1).valor == "(":
            tipo = Nodo("Tipo", "constructor", inicio.linea, inicio.columna)
        elif not en_clase and self.es_identificador(self.actual()) and self.token(1).valor == "(":
            tipo = Nodo("Tipo", "void", inicio.linea, inicio.columna)
        elif self.es("void"):
            tok = self.avanzar()
            tipo = Nodo("Tipo", "void", tok.linea, tok.columna)
        elif self.token(0).tipo == "TIPO" or self.es_identificador(self.token(0)):
            tipo = self.tipo()
        else:
            self.error("Se esperaba un tipo de retorno")
            tipo = Nodo("Tipo", "desconocido", inicio.linea, inicio.columna)
        nombre = self.esperar_identificador("el nombre del metodo")
        nodo = Nodo("Metodo", nombre.valor, nombre.linea, nombre.columna)
        self._agregar_prefijos(nodo, mods, anots)
        nodo.agregar(tipo)
        self.esperar("(")
        parametros = Nodo("Parametros", linea=nombre.linea, columna=nombre.columna)
        if not self.es(")"):
            parametros.agregar(self.parametro())
            while self.aceptar(","):
                parametros.agregar(self.parametro())
        self.esperar(")")
        nodo.agregar(parametros)
        if self.aceptar("throws"):
            self.esperar_identificador("el tipo de excepcion")
            while self.aceptar(","):
                self.esperar_identificador("el tipo de excepcion")
        if self.es("{"):
            nodo.agregar(self.bloque())
        elif self.es(";"):
            self.avanzar()
        else:
            self.error(f"Se esperaba '{{' para el cuerpo del metodo '{nombre.valor}'")
        return nodo

    def parametro(self):
        tipo = self.tipo()
        nombre = self.esperar_identificador("el nombre del parametro")
        while self.es("[" ) and self.token(1).valor == "]":
            self.avanzar()
            self.avanzar()
            tipo.valor += "[]"
        nodo = Nodo("Parametro", nombre.valor, nombre.linea, nombre.columna, tipo=tipo.valor)
        nodo.agregar(tipo)
        return nodo

    def tipo(self):
        tok = self.actual()
        if tok.tipo == "TIPO" or tok.valor == "void":
            self.avanzar()
            base = tok.valor
        elif self.es_identificador(tok):
            self.avanzar()
            base = tok.valor
        else:
            self.error(f"Se esperaba un tipo de dato y se encontro '{self.describir()}'")
            base = "desconocido"
        nodo = Nodo("Tipo", base, tok.linea, tok.columna)
        while self.es("[") and self.token(1).valor == "]":
            self.avanzar()
            self.avanzar()
            nodo.valor += "[]"
        return nodo

    # ------------------------------------------------------------------
    # Sentencias
    # ------------------------------------------------------------------
    def bloque(self):
        nodo = Nodo("Bloque", linea=self.actual().linea, columna=self.actual().columna)
        if not self.esperar("{"):
            return nodo
        while not self.es_eof() and not self.es("}"):
            inicio = self.pos
            nodo.agregar(self.sentencia())
            if self.pos == inicio:
                self.avanzar()
        self.esperar("}")
        return nodo

    def sentencia(self):
        if self.es("{"):
            return self.bloque()
        if self.es("if"):
            return self.si()
        if self.es("for"):
            return self.para()
        if self.es("while"):
            return self.mientras()
        if self.es("do"):
            return self.hacer()
        if self.es("switch"):
            return self.switch()
        if self.es("return"):
            return self.retorno()
        if self.es("try"):
            return self.intentar()
        if self.es("synchronized") and self.token(1).valor == "(":
            return self.sincronizado()
        if self.es("throw"):
            return self.lanzar()
        if self.es("break") or self.es("continue"):
            tok = self.avanzar()
            self.esperar_punto_coma(f"Falta ';' despues de '{tok.valor}'")
            return Nodo("Break" if tok.valor == "break" else "Continue",
                        tok.valor, tok.linea, tok.columna)
        if self.es(";"):
            tok = self.avanzar()
            return Nodo("SentenciaVacia", ";", tok.linea, tok.columna)
        if self._es_for_postfijo():
            return self.para_postfijo()
        if self._inicio_declaracion():
            return self.declaracion()
        inicio = self.actual()
        expr = self.expresion()
        self.esperar_punto_coma("Falta ';' al final de la instruccion")
        nodo = Nodo("SentenciaExpresion", linea=inicio.linea, columna=inicio.columna)
        nodo.agregar(expr)
        return nodo

    def declaracion(self, consumir_pc=True):
        tipo = self.tipo()
        nodo = Nodo("Declaracion", tipo.valor, tipo.linea, tipo.columna, tipo=tipo.valor)
        nodo.agregar(tipo)
        while True:
            nombre = self.esperar_identificador("el nombre de la variable")
            variable = Nodo("Variable", nombre.valor, nombre.linea, nombre.columna,
                           tipo=tipo.valor)
            if self.aceptar("="):
                if self.es("{"):
                    variable.agregar(self.lista_inicializacion())
                else:
                    variable.agregar(self.expresion())
            nodo.agregar(variable)
            if not self.aceptar(","):
                break
        if consumir_pc:
            self.esperar_punto_coma("Falta ';' al final de la declaracion")
        return nodo

    def lista_inicializacion(self):
        tok = self.actual()
        nodo = Nodo("ListaInicializacion", linea=tok.linea, columna=tok.columna)
        self.esperar("{")
        if not self.es("}"):
            nodo.agregar(self.expresion())
            while self.aceptar(","):
                nodo.agregar(self.expresion())
        self.esperar("}")
        return nodo

    def si(self):
        tok = self.esperar("if")
        nodo = Nodo("Si", "if", tok.linea if tok else None, tok.columna if tok else None)
        self.esperar("(")
        condicion = Nodo("Condicion", linea=self.actual().linea,
                         columna=self.actual().columna)
        condicion.agregar(self.expresion())
        nodo.agregar(condicion)
        self.esperar(")")
        nodo.agregar(self.sentencia())
        if self.aceptar("else"):
            nodo.agregar(self.sentencia())
        return nodo

    def mientras(self):
        tok = self.esperar("while")
        nodo = Nodo("Mientras", "while", tok.linea if tok else None, tok.columna if tok else None)
        self.esperar("(")
        condicion = Nodo("Condicion", linea=self.actual().linea,
                         columna=self.actual().columna)
        condicion.agregar(self.expresion())
        nodo.agregar(condicion)
        self.esperar(")")
        nodo.agregar(self.sentencia())
        return nodo

    def hacer(self):
        tok = self.esperar("do")
        nodo = Nodo("Hacer", "do", tok.linea if tok else None, tok.columna if tok else None)
        nodo.agregar(self.sentencia())
        self.esperar("while")
        self.esperar("(")
        condicion = Nodo("Condicion", linea=self.actual().linea,
                         columna=self.actual().columna)
        condicion.agregar(self.expresion())
        nodo.agregar(condicion)
        self.esperar(")")
        self.esperar_punto_coma("Falta ';' despues de 'while'")
        return nodo

    def switch(self):
        tok = self.esperar("switch")
        nodo = Nodo("Switch", "switch", tok.linea if tok else None,
                    tok.columna if tok else None)
        self.esperar("(")
        discriminante = Nodo("Discriminante", linea=self.actual().linea,
                             columna=self.actual().columna)
        discriminante.agregar(self.expresion())
        nodo.agregar(discriminante)
        self.esperar(")")
        self.esperar("{")
        while not self.es_eof() and not self.es("}"):
            if self.es("case"):
                etiqueta = self.avanzar()
                caso = Nodo("Caso", "case", etiqueta.linea, etiqueta.columna)
                valor = Nodo("ValorCaso", linea=self.actual().linea,
                             columna=self.actual().columna)
                valor.agregar(self.expresion())
                caso.agregar(valor)
                self.esperar(":")
                self._sentencias_caso(caso)
                nodo.agregar(caso)
            elif self.es("default"):
                etiqueta = self.avanzar()
                caso = Nodo("Default", "default", etiqueta.linea, etiqueta.columna)
                self.esperar(":")
                self._sentencias_caso(caso)
                nodo.agregar(caso)
            else:
                self.error(f"Se esperaba 'case' o 'default' y se encontro '{self.describir()}'")
                self.sincronizar_sentencia()
        self.esperar("}")
        return nodo

    def _sentencias_caso(self, caso):
        while (not self.es_eof() and not self.es("case")
               and not self.es("default") and not self.es("}")):
            inicio = self.pos
            caso.agregar(self.sentencia())
            if self.pos == inicio:
                self.avanzar()

    def para(self):
        tok = self.esperar("for")
        nodo = Nodo("Para", "for", tok.linea if tok else None, tok.columna if tok else None)
        self.esperar("(")
        nodo.agregar(self._inicializacion_for())
        self.esperar(";")
        nodo.agregar(self._condicion_for())
        self.esperar(";")
        nodo.agregar(self._incremento_for())
        self.esperar(")")
        nodo.agregar(Nodo("Cuerpo").agregar(self.sentencia()))
        return nodo

    def para_postfijo(self):
        """Soporta la variante del proyecto: (init; cond; inc) for { ... }"""
        tok = self.actual()
        nodo = Nodo("Para", "for (postfijo)", tok.linea, tok.columna)
        self.esperar("(")
        nodo.agregar(self._inicializacion_for())
        self.esperar(";")
        nodo.agregar(self._condicion_for())
        self.esperar(";")
        nodo.agregar(self._incremento_for())
        self.esperar(")")
        self.esperar("for")
        nodo.agregar(Nodo("Cuerpo").agregar(self.sentencia()))
        return nodo

    def _inicializacion_for(self):
        contenedor = Nodo("Inicializacion", linea=self.actual().linea,
                          columna=self.actual().columna)
        if not self.es(";"):
            if self._inicio_declaracion():
                contenedor.agregar(self.declaracion(consumir_pc=False))
            else:
                contenedor.agregar(self.expresion())
        return contenedor

    def _condicion_for(self):
        contenedor = Nodo("Condicion", linea=self.actual().linea,
                          columna=self.actual().columna)
        if not self.es(";"):
            contenedor.agregar(self.expresion())
        return contenedor

    def _incremento_for(self):
        contenedor = Nodo("Incremento", linea=self.actual().linea,
                          columna=self.actual().columna)
        if not self.es(")"):
            if self._inicio_declaracion():
                contenedor.agregar(self.declaracion(consumir_pc=False))
            else:
                contenedor.agregar(self.expresion())
        return contenedor

    def _es_for_postfijo(self):
        if not self.es("("):
            return False
        nivel = 0
        k = self.pos
        while k < len(self.tokens):
            valor = self.tokens[k].valor
            if valor == "(":
                nivel += 1
            elif valor == ")":
                nivel -= 1
                if nivel == 0:
                    return k + 1 < len(self.tokens) and self.tokens[k + 1].valor == "for"
            elif self.tokens[k].tipo == "EOF":
                return False
            k += 1
        return False

    def _recursos_try(self):
        """try (Tipo var = expr; ...) -> nodo con las declaraciones de recursos."""
        tok = self.esperar("(")
        recursos = Nodo("Recursos", "try-with-resources",
                        tok.linea if tok else None, tok.columna if tok else None)
        while not self.es_eof() and not self.es(")"):
            inicio = self.pos
            if self._inicio_declaracion():
                recursos.agregar(self.declaracion(consumir_pc=False))
            else:
                self.error(
                    "Se esperaba una declaracion de recurso en el 'try' "
                    f"y se encontro '{self.describir()}'"
                )
            self.aceptar(";")
            if self.pos == inicio:
                self.avanzar()
        self.esperar(")")
        return recursos

    def intentar(self):
        """try { } catch (Tipo e) { } finally { } / try (Recursos) { }"""
        tok = self.esperar("try")
        nodo = Nodo("Try", "try", tok.linea if tok else None,
                    tok.columna if tok else None)
        tiene_recursos = False
        if self.es("("):
            tiene_recursos = True
            nodo.agregar(self._recursos_try())
        nodo.agregar(self.bloque())
        hay_cierre = False
        while self.es("catch"):
            c = self.avanzar()
            captura = Nodo("Catch", "", c.linea, c.columna)
            self.esperar("(")
            tipo = self.tipo()
            while self.aceptar("|"):
                self.tipo()
            nombre = self.esperar_identificador("el nombre de la excepcion")
            captura.valor = nombre.valor
            captura.tipo = tipo.valor
            captura.agregar(tipo)
            self.esperar(")")
            captura.agregar(self.bloque())
            nodo.agregar(captura)
            hay_cierre = True
        if self.es("finally"):
            f = self.avanzar()
            fin = Nodo("Finally", "finally", f.linea, f.columna)
            fin.agregar(self.bloque())
            nodo.agregar(fin)
            hay_cierre = True
        if not hay_cierre and not tiene_recursos:
            self.error("'try' requiere al menos un 'catch' o un 'finally'", tok)
        return nodo

    def sincronizado(self):
        """synchronized (objeto) { ... }"""
        tok = self.esperar("synchronized")
        nodo = Nodo("Sincronizado", "synchronized", tok.linea, tok.columna)
        self.esperar("(")
        condicion = Nodo("Condicion", linea=self.actual().linea,
                         columna=self.actual().columna)
        condicion.agregar(self.expresion())
        nodo.agregar(condicion)
        self.esperar(")")
        nodo.agregar(self.bloque())
        return nodo

    def lanzar(self):
        tok = self.esperar("throw")
        nodo = Nodo("Lanzar", "throw", tok.linea, tok.columna)
        nodo.agregar(self.expresion())
        self.esperar_punto_coma("Falta ';' despues de 'throw'")
        return nodo

    def retorno(self):
        tok = self.esperar("return")
        nodo = Nodo("Retorno", "return", tok.linea if tok else None,
                    tok.columna if tok else None)
        if not self.es(";"):
            nodo.agregar(self.expresion())
        self.esperar_punto_coma("Falta ';' despues de 'return'")
        return nodo

    # ------------------------------------------------------------------
    # Expresiones (precedencia de mayor a menor)
    # ------------------------------------------------------------------
    def expresion(self):
        return self.asignacion()

    def asignacion(self):
        izquierda = self.logica_o()
        if self.actual().valor in ASIGNACIONES:
            op = self.avanzar()
            derecha = self.asignacion()
            nodo = Nodo("Asignacion", op.valor, op.linea, op.columna)
            nodo.agregar(izquierda)
            nodo.agregar(derecha)
            return nodo
        return izquierda

    def _binario(self, siguiente, operadores):
        izquierda = siguiente()
        while self.actual().valor in operadores:
            op = self.avanzar()
            derecha = siguiente()
            nodo = Nodo("Operacion", op.valor, op.linea, op.columna)
            nodo.agregar(izquierda)
            nodo.agregar(derecha)
            izquierda = nodo
        return izquierda

    def logica_o(self):
        return self._binario(self.logica_y, {"||"})

    def logica_y(self):
        return self._binario(self.igualdad, {"&&"})

    def igualdad(self):
        return self._binario(self.comparacion, {"==", "!="})

    def comparacion(self):
        return self._binario(self.suma, {"<", ">", "<=", ">="})

    def suma(self):
        return self._binario(self.multiplicacion, {"+", "-"})

    def multiplicacion(self):
        return self._binario(self.unario, {"*", "/", "%"})

    def unario(self):
        if self.actual().valor in {"!", "-", "+", "++", "--", "~"}:
            op = self.avanzar()
            nodo = Nodo("Unario", op.valor, op.linea, op.columna)
            nodo.agregar(self.unario())
            return nodo
        return self.postfijo()

    def postfijo(self):
        base = self.primario()
        while True:
            if self.es("("):
                argumentos = self.argumentos()
                nombre = base.valor if base.etiqueta == "Identificador" else ""
                nodo = Nodo("Llamada", nombre, base.linea, base.columna)
                nodo.agregar(base)
                for arg in argumentos:
                    nodo.agregar(arg)
                base = nodo
            elif self.es("."):
                punto = self.avanzar()
                nombre = self.esperar_identificador("el nombre del miembro")
                nodo = Nodo("Acceso", nombre.valor, punto.linea, punto.columna)
                nodo.agregar(base)
                base = nodo
            elif self.es("["):
                corchete = self.avanzar()
                nodo = Nodo("Indice", linea=corchete.linea, columna=corchete.columna)
                nodo.agregar(base)
                nodo.agregar(self.expresion())
                self.esperar("]")
                base = nodo
            elif self.actual().valor in ("++", "--"):
                op = self.avanzar()
                nodo = Nodo("Postfijo", op.valor, op.linea, op.columna)
                nodo.agregar(base)
                base = nodo
            else:
                break
        return base

    def argumentos(self):
        argumentos = []
        self.esperar("(")
        if not self.es(")"):
            argumentos.append(self.expresion())
            while self.aceptar(","):
                argumentos.append(self.expresion())
        self.esperar(")")
        return argumentos

    def primario(self):
        tok = self.actual()
        if tok.tipo in LITERALES:
            self.avanzar()
            tipos = {
                "ENTERO": "int",
                "DECIMAL": "double",
                "CADENA": "String",
                "CARACTER": "char",
                "BOOLEANO": "boolean",
                "NULO": "null",
            }
            return Nodo("Literal", tok.valor, tok.linea, tok.columna,
                        tipo=tipos.get(tok.tipo))
        if self.es_identificador(tok):
            self.avanzar()
            return Nodo("Identificador", tok.valor, tok.linea, tok.columna)
        if tok.valor in ("this", "super"):
            self.avanzar()
            return Nodo("Identificador", tok.valor, tok.linea, tok.columna)
        if tok.valor == "(":
            self.avanzar()
            nodo = Nodo("Agrupacion", "()", tok.linea, tok.columna)
            nodo.agregar(self.expresion())
            self.esperar(")")
            return nodo
        if tok.valor == "new":
            self.avanzar()
            tipo = self.tipo()
            nodo = Nodo("Nuevo", tipo.valor, tok.linea, tok.columna, tipo=tipo.valor)
            if self.es("["):
                self.avanzar()
                nodo.agregar(self.expresion())
                self.esperar("]")
                nodo.valor = tipo.valor + "[]"
                nodo.tipo = nodo.valor
            elif self.es("("):
                for arg in self.argumentos():
                    nodo.agregar(arg)
            return nodo
        if tok.tipo == "TIPO":
            self.avanzar()
            return Nodo("Tipo", tok.valor, tok.linea, tok.columna)
        self.error(f"Token inesperado '{self.describir()}' en una expresion")
        if tok.valor not in (";", ")", "}", "]", ","):
            self.avanzar()
        return Nodo("Error", tok.valor, tok.linea, tok.columna)
