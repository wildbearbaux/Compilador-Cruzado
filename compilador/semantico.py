"""Analizador semantico y tabla de simbolos."""

from dataclasses import dataclass


# ======================================================================
# ANALIZADOR SEMANTICO
# ======================================================================

@dataclass
class ErrorSemantico:
    linea: int
    mensaje: str
    tipo: str = "error"
    columna: int = 0


ALIAS = {"Int": "int", "Char": "char", "str": "String", "bool": "boolean"}
NUMERICOS = {"int", "double", "float", "char", "long", "short", "byte"}
ENTEROS = {"int", "char", "long", "short", "byte"}
BUILTINS = {"print", "println", "printf", "scanf", "read", "write"}
RETORNOS_MIEMBRO = {
    "nextInt": "int", "nextDouble": "double", "nextFloat": "float",
    "nextLong": "long", "nextBoolean": "boolean", "nextLine": "String",
    "next": "String", "length": "int", "size": "int", "charAt": "char",
    "equals": "boolean", "equalsIgnoreCase": "boolean",
    "compareTo": "int", "toString": "String", "sqrt": "double",
    "abs": "double", "pow": "double", "random": "double",
    "println": "void", "print": "void", "printf": "void",
}
CLASES_CONOCIDAS = {
    "System", "Math", "String", "Scanner", "Object", "Exception",
    "RuntimeException", "ArithmeticException", "InputMismatchException",
    "ArrayIndexOutOfBoundsException", "NullPointerException", "Throwable",
    "Integer", "Double", "Float", "Boolean", "Character",
    "Thread", "Runnable", "List", "ArrayList", "Map", "HashMap",
}


def normalizar(tipo):
    if not tipo:
        return "desconocido"
    dimensiones = tipo.count("[]")
    base = tipo.replace("[]", "")
    return ALIAS.get(base, base) + "[]" * dimensiones


def compatible(destino, origen):
    destino = normalizar(destino)
    origen = normalizar(origen)
    if destino in ("desconocido", "null") or origen in ("desconocido", "null"):
        return True
    if destino == origen:
        return True
    if destino.endswith("[]") or origen.endswith("[]"):
        return destino == origen
    if destino in ("double", "float") and origen in NUMERICOS:
        return True
    if destino == "int" and origen == "char":
        return True
    if destino == "char" and origen in ENTEROS:
        return True
    return False


def promover(tipo_a, tipo_b):
    tipo_a = normalizar(tipo_a)
    tipo_b = normalizar(tipo_b)
    if "double" in (tipo_a, tipo_b):
        return "double"
    if "float" in (tipo_a, tipo_b):
        return "float"
    if tipo_a in NUMERICOS and tipo_b in NUMERICOS:
        return "int"
    return "desconocido"


class Simbolo:
    def __init__(self, nombre, tipo, linea, categoria="variable",
                 usada=False, inicializada=False):
        self.nombre = nombre
        self.tipo = normalizar(tipo)
        self.linea = linea
        self.categoria = categoria
        self.usada = usada
        self.inicializada = inicializada


class Ambito:
    def __init__(self, padre=None, nombre="global"):
        self.padre = padre
        self.nombre = nombre
        self.simbolos = {}

    def declarar(self, simbolo):
        if simbolo.nombre in self.simbolos:
            return False
        self.simbolos[simbolo.nombre] = simbolo
        return True

    def buscar_local(self, nombre):
        return self.simbolos.get(nombre)

    def buscar(self, nombre):
        ambito = self
        while ambito is not None:
            if nombre in ambito.simbolos:
                return ambito.simbolos[nombre]
            ambito = ambito.padre
        return None


class AnalizadorSemantico:
    def __init__(self):
        self.errores = []
        self.ambito_global = Ambito(None, "global")
        self.metodos = {}
        self.clase_actual = None
        self.metodo_actual = None
        self.en_ciclo = 0
        self.en_switch = 0
        self.simbolos = []
        self.declarando_campo = False

    def analizar(self, raiz):
        self._registrar_metodos(raiz)
        for hijo in raiz.hijos:
            self.visitar(hijo, self.ambito_global)
        self._revisar_no_usadas()
        return self.errores

    def error(self, linea, mensaje):
        self.errores.append(ErrorSemantico(linea, mensaje, "error"))

    def advertencia(self, linea, mensaje):
        self.errores.append(ErrorSemantico(linea, mensaje, "warning"))

    def _registrar_metodos(self, nodo):
        if nodo.etiqueta == "Programa":
            for hijo in nodo.hijos:
                self._registrar_metodos(hijo)
        elif nodo.etiqueta == "Clase":
            for hijo in nodo.hijos:
                if hijo.etiqueta == "Metodo":
                    self._registrar_metodo(hijo)
                elif hijo.etiqueta == "Clase":
                    self._registrar_metodos(hijo)
        elif nodo.etiqueta == "Metodo":
            self._registrar_metodo(nodo)

    def _registrar_metodo(self, metodo):
        retorno = self._tipo_retorno(metodo)
        parametros = self._tipos_parametros(metodo)
        self.metodos.setdefault(metodo.valor, []).append((retorno, parametros, metodo))

    def _tipo_retorno(self, metodo):
        for hijo in metodo.hijos:
            if hijo.etiqueta == "Tipo":
                return normalizar(hijo.valor)
        return "desconocido"

    def _tipos_parametros(self, metodo):
        tipos = []
        for hijo in metodo.hijos:
            if hijo.etiqueta == "Parametros":
                for parametro in hijo.hijos:
                    tipos.append(normalizar(parametro.tipo))
        return tipos

    def visitar(self, nodo, ambito):
        if nodo is None:
            return "desconocido"
        metodo = getattr(self, "_visitar_" + nodo.etiqueta, None)
        if metodo is not None:
            return metodo(nodo, ambito)
        for hijo in nodo.hijos:
            self.visitar(hijo, ambito)
        return "desconocido"

    def _visitar_Programa(self, nodo, ambito):
        for hijo in nodo.hijos:
            self.visitar(hijo, ambito)
        return "programa"

    def _visitar_Literal(self, nodo, ambito):
        return nodo.tipo

    def _visitar_Tipo(self, nodo, ambito):
        return nodo.valor

    def _visitar_Agrupacion(self, nodo, ambito):
        tipo = "desconocido"
        for hijo in nodo.hijos:
            tipo = self.visitar(hijo, ambito)
        return tipo

    def _visitar_Condicion(self, nodo, ambito):
        tipo = "desconocido"
        for hijo in nodo.hijos:
            tipo = self.visitar(hijo, ambito)
        return tipo

    def _visitar_Inicializacion(self, nodo, ambito):
        tipo = "desconocido"
        for hijo in nodo.hijos:
            tipo = self.visitar(hijo, ambito)
        return tipo

    def _visitar_Incremento(self, nodo, ambito):
        tipo = "desconocido"
        for hijo in nodo.hijos:
            tipo = self.visitar(hijo, ambito)
        return tipo

    def _visitar_Cuerpo(self, nodo, ambito):
        tipo = "desconocido"
        for hijo in nodo.hijos:
            tipo = self.visitar(hijo, ambito)
        return tipo

    def _visitar_Clase(self, nodo, ambito):
        ambito_clase = Ambito(ambito, f"clase {nodo.valor}")
        anterior = self.clase_actual
        self.clase_actual = nodo.valor
        for hijo in nodo.hijos:
            if hijo.etiqueta in ("Modificadores", "Anotaciones", "Extiende", "Implementa"):
                continue
            self.declarando_campo = hijo.etiqueta == "Declaracion"
            self.visitar(hijo, ambito_clase)
            self.declarando_campo = False
        self.clase_actual = anterior
        return nodo.valor

    def _visitar_Metodo(self, nodo, ambito):
        ambito_metodo = Ambito(ambito, f"metodo {nodo.valor}")
        anterior_metodo = self.metodo_actual
        anterior_ciclo = self.en_ciclo
        anterior_switch = self.en_switch
        self.metodo_actual = (nodo.valor, self._tipo_retorno(nodo))
        self.en_ciclo = 0
        self.en_switch = 0
        cuerpo = None
        for hijo in nodo.hijos:
            if hijo.etiqueta == "Parametros":
                for parametro in hijo.hijos:
                    self._declarar_parametro(parametro, ambito_metodo)
            elif hijo.etiqueta == "Bloque":
                cuerpo = hijo
                self.visitar(hijo, ambito_metodo)
        retorno = self._tipo_retorno(nodo)
        if retorno not in ("void", "constructor", "desconocido") and cuerpo is not None:
            if not self._contiene_retorno(cuerpo):
                self.advertencia(
                    nodo.linea,
                    f"El metodo '{nodo.valor}' declara retorno '{retorno}' pero no retorna ningun valor",
                )
        self.metodo_actual = anterior_metodo
        self.en_ciclo = anterior_ciclo
        self.en_switch = anterior_switch
        return retorno

    def _declarar_parametro(self, parametro, ambito):
        simbolo = Simbolo(parametro.valor, parametro.tipo, parametro.linea,
                          "parametro", usada=True, inicializada=True)
        if not ambito.declarar(simbolo):
            self.advertencia(parametro.linea,
                             f"Parametro duplicado '{parametro.valor}'")
        else:
            self.simbolos.append(simbolo)

    def _visitar_Bloque(self, nodo, ambito):
        ambito_bloque = Ambito(ambito, "bloque")
        for hijo in nodo.hijos:
            self.visitar(hijo, ambito_bloque)
        return "bloque"

    def _visitar_Declaracion(self, nodo, ambito):
        tipo = normalizar(nodo.tipo)
        for variable in nodo.hijos:
            if variable.etiqueta != "Variable":
                continue
            nombre = variable.valor
            if not nombre or nombre[0].isdigit():
                self.error(variable.linea,
                           f"Nombre de variable no valido '{nombre}': no puede iniciar con un numero")
                continue
            tipo_inicial = None
            if variable.hijos:
                tipo_inicial = self.visitar(variable.hijos[0], ambito)
                if variable.hijos[0].etiqueta == "ListaInicializacion":
                    tipo_inicial = tipo
                if not compatible(tipo, tipo_inicial):
                    self.error(
                        variable.linea,
                        f"No se puede asignar un valor de tipo '{tipo_inicial}' "
                        f"a la variable '{nombre}' de tipo '{tipo}'",
                    )
            simbolo = Simbolo(nombre, tipo, variable.linea,
                              "campo" if self.declarando_campo else "variable",
                              inicializada=bool(variable.hijos))
            anterior = ambito.buscar_local(nombre)
            if not ambito.declarar(simbolo):
                tipo_anterior = anterior.tipo if anterior else "desconocido"
                self.advertencia(
                    variable.linea,
                    f"Ambiguedad: '{nombre}' ya fue declarada como '{tipo_anterior}' "
                    f"(se redeclara como '{tipo}')",
                )
            else:
                self.simbolos.append(simbolo)
        return tipo

    def _visitar_Variable(self, nodo, ambito):
        for hijo in nodo.hijos:
            self.visitar(hijo, ambito)
        return nodo.tipo

    def _visitar_Parametro(self, nodo, ambito):
        for hijo in nodo.hijos:
            self.visitar(hijo, ambito)
        return nodo.tipo

    def _visitar_Asignacion(self, nodo, ambito):
        izquierda, derecha = nodo.hijos[0], nodo.hijos[1]
        tipo_derecha = self.visitar(derecha, ambito)
        tipo_izquierda = self._tipo_lvalue(izquierda, ambito)
        if nodo.valor == "=":
            if not compatible(tipo_izquierda, tipo_derecha):
                self.error(
                    nodo.linea,
                    f"No se puede asignar un valor de tipo '{tipo_derecha}' "
                    f"a una variable de tipo '{tipo_izquierda}'",
                )
        else:
            if tipo_izquierda not in NUMERICOS and tipo_izquierda != "desconocido":
                self.error(nodo.linea,
                           f"El operador '{nodo.valor}' requiere un operando numerico")
            if tipo_derecha not in NUMERICOS and tipo_derecha != "desconocido":
                self.error(nodo.linea,
                           f"El operador '{nodo.valor}' requiere un valor numerico")
        if izquierda.etiqueta == "Identificador":
            simbolo = ambito.buscar(izquierda.valor)
            if simbolo is not None:
                simbolo.inicializada = True
        return tipo_izquierda

    def _tipo_lvalue(self, nodo, ambito):
        if nodo.etiqueta == "Identificador":
            simbolo = ambito.buscar(nodo.valor)
            if simbolo is None:
                if nodo.valor in CLASES_CONOCIDAS:
                    return nodo.valor
                self.error(nodo.linea, f"Variable no declarada '{nodo.valor}'")
                return "desconocido"
            simbolo.usada = True
            return simbolo.tipo
        if nodo.etiqueta == "Indice":
            tipo = self.visitar(nodo.hijos[0], ambito)
            self.visitar(nodo.hijos[1], ambito)
            if tipo.endswith("[]"):
                return tipo[:-2]
            return "desconocido"
        if nodo.etiqueta == "Acceso":
            self.visitar(nodo.hijos[0], ambito)
            return "desconocido"
        return self.visitar(nodo, ambito)

    def _visitar_Operacion(self, nodo, ambito):
        izquierda, derecha = nodo.hijos[0], nodo.hijos[1]
        tipo_izquierda = self.visitar(izquierda, ambito)
        tipo_derecha = self.visitar(derecha, ambito)
        op = nodo.valor
        if op == "+" and ("String" in (tipo_izquierda, tipo_derecha)):
            return "String"
        if op in ("+", "-", "*", "/", "%"):
            if (tipo_izquierda not in NUMERICOS and tipo_izquierda != "desconocido") or \
               (tipo_derecha not in NUMERICOS and tipo_derecha != "desconocido"):
                self.error(
                    nodo.linea,
                    f"El operador '{op}' no es aplicable a '{tipo_izquierda}' y '{tipo_derecha}'",
                )
                return "desconocido"
            if op == "/" and self._es_cero(derecha):
                self.advertencia(nodo.linea, "Division por cero")
            return promover(tipo_izquierda, tipo_derecha)
        if op in ("<", ">", "<=", ">="):
            validos = NUMERICOS | {"String", "char"}
            if (tipo_izquierda not in validos and tipo_izquierda != "desconocido") or \
               (tipo_derecha not in validos and tipo_derecha != "desconocido"):
                self.error(
                    nodo.linea,
                    f"No se pueden comparar '{tipo_izquierda}' y '{tipo_derecha}' con '{op}'",
                )
            return "boolean"
        if op in ("==", "!="):
            return "boolean"
        if op in ("&&", "||"):
            if (tipo_izquierda not in ("boolean", "desconocido")
                    or tipo_derecha not in ("boolean", "desconocido")):
                self.error(
                    nodo.linea,
                    f"El operador '{op}' requiere operandos booleanos, "
                    f"se obtuvo '{tipo_izquierda}' y '{tipo_derecha}'",
                )
            return "boolean"
        return "desconocido"

    def _es_cero(self, nodo):
        return nodo.etiqueta == "Literal" and nodo.valor in ("0", "0.0")

    def _visitar_Unario(self, nodo, ambito):
        tipo = self.visitar(nodo.hijos[0], ambito)
        op = nodo.valor
        if op == "!":
            if tipo not in ("boolean", "desconocido"):
                self.error(nodo.linea, f"El operador '!' requiere un valor booleano, se obtuvo '{tipo}'")
            return "boolean"
        if op in ("+", "-", "~"):
            if tipo not in NUMERICOS and tipo != "desconocido":
                self.error(nodo.linea, f"El operador '{op}' requiere un valor numerico")
            return tipo
        if op in ("++", "--"):
            tipo_lvalue = self._tipo_lvalue(nodo.hijos[0], ambito)
            if tipo_lvalue not in NUMERICOS and tipo_lvalue != "desconocido":
                self.error(nodo.linea, f"El operador '{op}' requiere una variable numerica")
            return tipo_lvalue
        return tipo

    def _visitar_Postfijo(self, nodo, ambito):
        tipo = self._tipo_lvalue(nodo.hijos[0], ambito)
        if tipo not in NUMERICOS and tipo != "desconocido":
            self.error(nodo.linea, f"El operador '{nodo.valor}' requiere una variable numerica")
        return tipo

    def _visitar_Identificador(self, nodo, ambito):
        if nodo.valor in ("this", "super"):
            return self.clase_actual or "desconocido"
        simbolo = ambito.buscar(nodo.valor)
        if simbolo is None:
            if nodo.valor in CLASES_CONOCIDAS:
                return nodo.valor
            self.error(nodo.linea, f"Variable no declarada '{nodo.valor}'")
            return "desconocido"
        simbolo.usada = True
        return simbolo.tipo

    def _visitar_Llamada(self, nodo, ambito):
        if not nodo.hijos:
            return "desconocido"
        callee = nodo.hijos[0]
        argumentos = nodo.hijos[1:]
        if callee.etiqueta == "Identificador":
            nombre = callee.valor
            if nombre in ("this", "super"):
                for argumento in argumentos:
                    self.visitar(argumento, ambito)
                return "void"
            if nombre in BUILTINS:
                for argumento in argumentos:
                    self.visitar(argumento, ambito)
                return "void"
            firmas = self.metodos.get(nombre)
            if not firmas:
                self.error(nodo.linea, f"Metodo no declarado '{nombre}'")
                for argumento in argumentos:
                    self.visitar(argumento, ambito)
                return "desconocido"
            retorno, parametros, _ = firmas[0]
            if len(argumentos) != len(parametros):
                self.error(
                    nodo.linea,
                    f"El metodo '{nombre}' espera {len(parametros)} argumento(s) "
                    f"y recibio {len(argumentos)}",
                )
            for indice, argumento in enumerate(argumentos):
                tipo_argumento = self.visitar(argumento, ambito)
                if indice < len(parametros) and not compatible(parametros[indice], tipo_argumento):
                    self.error(
                        argumento.linea,
                        f"Argumento {indice + 1} de '{nombre}': se esperaba "
                        f"'{parametros[indice]}' y se recibio '{tipo_argumento}'",
                    )
            return retorno
        if callee.etiqueta == "Acceso":
            base = callee.hijos[0]
            if not (base.etiqueta == "Identificador"
                    and base.valor in CLASES_CONOCIDAS):
                self.visitar(base, ambito)
            for argumento in argumentos:
                self.visitar(argumento, ambito)
            return RETORNOS_MIEMBRO.get(callee.valor, "desconocido")
        self.visitar(callee, ambito)
        for argumento in argumentos:
            self.visitar(argumento, ambito)
        return "desconocido"

    def _visitar_Acceso(self, nodo, ambito):
        base = nodo.hijos[0]
        if base.etiqueta == "Identificador" and base.valor in CLASES_CONOCIDAS:
            return "desconocido"
        self.visitar(base, ambito)
        return "desconocido"

    def _visitar_Nuevo(self, nodo, ambito):
        for argumento in nodo.hijos:
            self.visitar(argumento, ambito)
        return normalizar(nodo.valor)

    def _visitar_Indice(self, nodo, ambito):
        tipo = self.visitar(nodo.hijos[0], ambito)
        self.visitar(nodo.hijos[1], ambito)
        if tipo.endswith("[]"):
            return tipo[:-2]
        return "desconocido"

    def _visitar_Retorno(self, nodo, ambito):
        if self.metodo_actual is None:
            self.error(nodo.linea, "'return' solo puede usarse dentro de una funcion")
            for hijo in nodo.hijos:
                self.visitar(hijo, ambito)
            return "desconocido"
        retorno = self.metodo_actual[1] if self.metodo_actual else "desconocido"
        if not nodo.hijos:
            if retorno not in ("void", "constructor", "desconocido"):
                self.error(nodo.linea,
                           f"El metodo '{self.metodo_actual[0]}' debe retornar un valor de tipo '{retorno}'")
            return retorno
        tipo = self.visitar(nodo.hijos[0], ambito)
        if retorno in ("void", "constructor"):
            self.error(nodo.linea,
                       f"El metodo '{self.metodo_actual[0]}' no puede retornar un valor")
        elif not compatible(retorno, tipo):
            self.error(nodo.linea,
                       f"Tipo de retorno incompatible: se esperaba '{retorno}' y se obtuvo '{tipo}'")
        return tipo

    def _visitar_Si(self, nodo, ambito):
        condicion = nodo.hijos[0]
        tipo = self.visitar(condicion, ambito)
        self._verificar_condicion(tipo, "if", condicion.linea)
        for hijo in nodo.hijos[1:]:
            self.visitar(hijo, ambito)
        return "si"

    def _visitar_Mientras(self, nodo, ambito):
        condicion = nodo.hijos[0]
        tipo = self.visitar(condicion, ambito)
        self._verificar_condicion(tipo, "while", condicion.linea)
        self.en_ciclo += 1
        for hijo in nodo.hijos[1:]:
            self.visitar(hijo, ambito)
        self.en_ciclo -= 1
        return "mientras"

    def _visitar_Hacer(self, nodo, ambito):
        self.en_ciclo += 1
        for hijo in nodo.hijos[:-1]:
            self.visitar(hijo, ambito)
        self.en_ciclo -= 1
        condicion = nodo.hijos[-1]
        tipo = self.visitar(condicion, ambito)
        self._verificar_condicion(tipo, "do-while", condicion.linea)
        return "hacer"

    def _visitar_Para(self, nodo, ambito):
        ambito_for = Ambito(ambito, "for")
        incremento = None
        for hijo in nodo.hijos:
            if hijo.etiqueta == "Incremento":
                incremento = hijo
        incremento_visitado = False
        if incremento is not None and any(
                sub.etiqueta == "Declaracion" for sub in incremento.hijos):
            self.visitar(incremento, ambito_for)
            incremento_visitado = True
        for hijo in nodo.hijos:
            if incremento_visitado and hijo is incremento:
                continue
            if hijo.etiqueta == "Condicion":
                tipo = self.visitar(hijo, ambito_for)
                self._verificar_condicion(tipo, "for", hijo.linea)
            elif hijo.etiqueta == "Cuerpo":
                self.en_ciclo += 1
                self.visitar(hijo, ambito_for)
                self.en_ciclo -= 1
            else:
                self.visitar(hijo, ambito_for)
        return "para"

    def _verificar_condicion(self, tipo, estructura, linea):
        if tipo not in ("boolean", "desconocido"):
            self.error(linea,
                       f"La condicion del '{estructura}' debe ser booleana, se obtuvo '{tipo}'")

    def _visitar_Discriminante(self, nodo, ambito):
        tipo = "desconocido"
        for hijo in nodo.hijos:
            tipo = self.visitar(hijo, ambito)
        return tipo

    def _visitar_ValorCaso(self, nodo, ambito):
        tipo = "desconocido"
        for hijo in nodo.hijos:
            tipo = self.visitar(hijo, ambito)
        return tipo

    def _clave_caso(self, nodo):
        if nodo.hijos and nodo.hijos[0].etiqueta in ("Literal", "Identificador"):
            return nodo.hijos[0].valor
        return None

    def _visitar_Switch(self, nodo, ambito):
        discriminante = nodo.hijos[0]
        tipo = self.visitar(discriminante, ambito)
        self.en_switch += 1
        vistos = set()
        for caso in nodo.hijos[1:]:
            if caso.etiqueta == "Caso":
                valor = caso.hijos[0]
                tipo_valor = self.visitar(valor, ambito)
                if not compatible(tipo, tipo_valor):
                    self.error(
                        caso.linea,
                        f"El valor de 'case' de tipo '{tipo_valor}' no es compatible "
                        f"con el switch de tipo '{tipo}'",
                    )
                clave = self._clave_caso(valor)
                if clave is not None:
                    if clave in vistos:
                        self.advertencia(caso.linea,
                                         f"Valor de 'case' duplicado: {clave}")
                    vistos.add(clave)
                for sentencia in caso.hijos[1:]:
                    self.visitar(sentencia, ambito)
            elif caso.etiqueta == "Default":
                for sentencia in caso.hijos:
                    self.visitar(sentencia, ambito)
        self.en_switch -= 1
        return "switch"

    def _visitar_Try(self, nodo, ambito):
        ambito_try = Ambito(ambito, "try")
        for hijo in nodo.hijos:
            if hijo.etiqueta == "Recursos":
                for recurso in hijo.hijos:
                    self.visitar(recurso, ambito_try)
            elif hijo.etiqueta == "Bloque":
                self.visitar(hijo, ambito_try)
            elif hijo.etiqueta == "Catch":
                self.visitar(hijo, ambito)
            elif hijo.etiqueta == "Finally":
                self.visitar(hijo, ambito)
        return "try"

    def _visitar_Catch(self, nodo, ambito):
        ambito_catch = Ambito(ambito, "catch")
        ambito_catch.declarar(Simbolo(nodo.valor, nodo.tipo, nodo.linea,
                                      "parametro", usada=True, inicializada=True))
        for hijo in nodo.hijos:
            if hijo.etiqueta == "Bloque":
                self.visitar(hijo, ambito_catch)
        return "catch"

    def _visitar_Break(self, nodo, ambito):
        if self.en_ciclo == 0 and self.en_switch == 0:
            self.error(nodo.linea, f"'{nodo.valor}' solo puede usarse dentro de un ciclo o un switch")
        return "void"

    def _visitar_Continue(self, nodo, ambito):
        if self.en_ciclo == 0:
            self.error(nodo.linea, "'continue' solo puede usarse dentro de un ciclo")
        return "void"

    def _visitar_SentenciaExpresion(self, nodo, ambito):
        for hijo in nodo.hijos:
            self.visitar(hijo, ambito)
        return "void"

    def _visitar_ListaInicializacion(self, nodo, ambito):
        for hijo in nodo.hijos:
            self.visitar(hijo, ambito)
        return "lista"

    def _contiene_retorno(self, nodo):
        if nodo.etiqueta == "Retorno":
            return True
        if nodo.etiqueta in ("Metodo", "Clase"):
            return False
        return any(self._contiene_retorno(hijo) for hijo in nodo.hijos)

    def _revisar_no_usadas(self):
        for simbolo in self.simbolos:
            if simbolo.categoria == "variable" and not simbolo.usada:
                self.advertencia(
                    simbolo.linea,
                    f"Variable '{simbolo.nombre}' declarada pero no utilizada",
                )
