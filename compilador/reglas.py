"""Reglas de estructuras iterativas anidadas."""

from .sintactico import ErrorSintactico


# ======================================================================
# REGLAS DE ESTRUCTURAS ITERATIVAS ANIDADAS
# ======================================================================

COMPARADORES = {"<", ">", "<=", ">=", "==", "!="}
CONSTANTES = {"int", "double", "char"}


class ValidadorReglas:
    def __init__(self):
        self.errores = []
        self._vistos = set()

    def validar(self, raiz, tokens=None):
        self._recorrer(raiz, ())
        return self.errores

    def _agregar(self, nodo, mensaje, tipo="error"):
        linea = nodo.linea or 0
        columna = nodo.columna or 0
        clave = (linea, mensaje)
        if clave in self._vistos:
            return
        self._vistos.add(clave)
        self.errores.append(ErrorSintactico(linea, columna, mensaje, tipo))

    def _recorrer(self, nodo, externas):
        etiqueta = nodo.etiqueta

        if etiqueta == "Mientras":
            self._regla_while(nodo)
        elif etiqueta == "Hacer":
            self._regla_do(nodo)
        elif etiqueta == "Para":
            externas = externas + tuple(self._regla_for(nodo, externas))
        elif etiqueta == "Si":
            self._regla_if(nodo)
        elif etiqueta == "Switch":
            self._regla_switch(nodo)
        elif etiqueta == "Sincronizado":
            self._regla_synchronized(nodo)
        elif etiqueta == "Try":
            self._regla_try(nodo)

        for hijo in nodo.hijos:
            self._recorrer(hijo, externas)

    def _condicion_valida(self, condicion, estructura):
        if condicion is None or not condicion.hijos:
            self._agregar(condicion, f"Falta la condicion del '{estructura}'")
            return False
        expr = condicion.hijos[0]
        if (expr.etiqueta == "Operacion" and expr.valor in COMPARADORES
                and expr.hijos[0].etiqueta == "Identificador"
                and expr.hijos[1].etiqueta == "Literal"
                and expr.hijos[1].tipo in CONSTANTES):
            return True
        self._agregar(
            condicion,
            f"La condicion del '{estructura}' debe tener la forma "
            f"<variable><operador><constante> (ej. x < 5)",
        )
        return False

    def _cuerpo_con_llaves(self, nodo, cuerpo, estructura):
        if cuerpo is None:
            return
        if cuerpo.etiqueta != "Bloque":
            self._agregar(
                nodo,
                f"El cuerpo del '{estructura}' debe ir entre llaves '{{ }}'",
            )

    def _regla_while(self, nodo):
        condicion = nodo.hijos[0] if nodo.hijos else None
        cuerpo = nodo.hijos[1] if len(nodo.hijos) > 1 else None
        valida = self._condicion_valida(condicion, "while")
        self._cuerpo_con_llaves(nodo, cuerpo, "while")
        if valida and cuerpo is not None:
            variable = condicion.hijos[0].hijos[0].valor
            if not self._modifica(cuerpo, variable):
                self._agregar(
                    nodo,
                    f"Posible ciclo infinito: '{variable}' no se modifica "
                    f"dentro del while",
                    "warning",
                )

    def _regla_do(self, nodo):
        if not nodo.hijos:
            return
        cuerpo = nodo.hijos[0]
        condicion = nodo.hijos[-1]
        self._cuerpo_con_llaves(nodo, cuerpo, "do")
        valida = self._condicion_valida(condicion, "do-while")
        if valida:
            variable = condicion.hijos[0].hijos[0].valor
            if not self._modifica(cuerpo, variable):
                self._agregar(
                    nodo,
                    f"Posible ciclo infinito: '{variable}' no se modifica "
                    f"dentro del do-while",
                    "warning",
                )

    def _regla_for(self, nodo, externas=()):
        if nodo.valor == "for (postfijo)":
            self._agregar(
                nodo,
                "Sintaxis incorrecta: 'for' debe escribirse antes de los "
                "parentesis: for (init; condicion; incremento) { ... }",
            )
        partes = {h.etiqueta: h for h in nodo.hijos}
        inicializacion = partes.get("Inicializacion")
        condicion = partes.get("Condicion")
        incremento = partes.get("Incremento")
        cuerpo = partes.get("Cuerpo")

        if inicializacion is not None and not inicializacion.hijos:
            self._agregar(nodo, "Falta la inicializacion en el 'for'")
        valida = self._condicion_valida(condicion, "for")
        if incremento is not None and not incremento.hijos:
            self._agregar(nodo, "Falta el incremento en el 'for' (ej. x++)")
        if cuerpo is not None and cuerpo.hijos:
            self._cuerpo_con_llaves(nodo, cuerpo.hijos[0], "for")

        declaradas = []
        for parte in (inicializacion, incremento):
            if parte is not None:
                declaradas += self._variables_declaradas(parte)
        for nombre in declaradas:
            if nombre in externas:
                self._agregar(
                    nodo,
                    f"La variable '{nombre}' ya esta declarada en un 'for' "
                    f"externo; use otro nombre en el ciclo anidado",
                )

        if valida and incremento is not None and incremento.hijos:
            expr = condicion.hijos[0]
            variable, operador = expr.hijos[0].valor, expr.valor
            if not self._modifica(incremento, variable):
                self._agregar(
                    nodo,
                    f"Posible ciclo infinito: el incremento del 'for' no "
                    f"modifica '{variable}', que es la variable de la condicion",
                    "warning",
                )
            else:
                direccion = self._direccion(incremento, variable)
                if (operador in ("<", "<=") and direccion < 0) or \
                   (operador in (">", ">=") and direccion > 0):
                    self._agregar(
                        nodo,
                        f"Posible ciclo infinito: '{variable}' se "
                        f"{'decrementa' if direccion < 0 else 'incrementa'} "
                        f"pero la condicion usa '{operador}'",
                        "warning",
                    )
        return declaradas

    def _variables_declaradas(self, contenedor):
        nombres = []
        for hijo in contenedor.hijos:
            if hijo.etiqueta == "Declaracion":
                nombres += [v.valor for v in hijo.hijos
                            if v.etiqueta == "Variable"]
        return nombres

    def _direccion(self, nodo, variable):
        if (nodo.etiqueta in ("Unario", "Postfijo")
                and nodo.valor in ("++", "--")
                and nodo.hijos[0].etiqueta == "Identificador"
                and nodo.hijos[0].valor == variable):
            return 1 if nodo.valor == "++" else -1
        if (nodo.etiqueta == "Asignacion" and nodo.valor in ("+=", "-=")
                and nodo.hijos[0].etiqueta == "Identificador"
                and nodo.hijos[0].valor == variable):
            return 1 if nodo.valor == "+=" else -1
        for hijo in nodo.hijos:
            direccion = self._direccion(hijo, variable)
            if direccion:
                return direccion
        return 0

    def _regla_if(self, nodo):
        condicion = nodo.hijos[0] if nodo.hijos else None
        self._condicion_valida(condicion, "if")
        if len(nodo.hijos) > 1:
            self._cuerpo_con_llaves(nodo, nodo.hijos[1], "if")
        if len(nodo.hijos) > 2:
            alterno = nodo.hijos[2]
            if alterno.etiqueta not in ("Bloque", "Si"):
                self._agregar(
                    nodo, "El cuerpo del 'else' debe ir entre llaves '{ }'"
                )

    def _regla_switch(self, nodo):
        discriminante = nodo.hijos[0] if nodo.hijos else None
        if (discriminante is None or not discriminante.hijos
                or discriminante.hijos[0].etiqueta != "Identificador"):
            self._agregar(
                nodo if discriminante is None else discriminante,
                "El 'switch' debe tener la forma switch (<variable>) { ... }",
            )
        tiene_default = False
        for caso in nodo.hijos[1:]:
            if caso.etiqueta == "Default":
                tiene_default = True
            elif caso.etiqueta == "Caso":
                valor = caso.hijos[0].hijos[0] if caso.hijos and caso.hijos[0].hijos else None
                if valor is None or valor.etiqueta != "Literal":
                    self._agregar(
                        caso, "El 'case' debe ir seguido de una constante "
                              "(ej. case 1:)")
        if not tiene_default:
            self._agregar(nodo, "El 'switch' no tiene caso 'default'",
                          "warning")

    def _regla_synchronized(self, nodo):
        condicion = nodo.hijos[0] if nodo.hijos else None
        if (condicion is None or not condicion.hijos
                or condicion.hijos[0].etiqueta != "Identificador"):
            self._agregar(
                nodo, "El 'synchronized' debe tener la forma "
                      "synchronized (<variable>) { ... }")

    def _regla_try(self, nodo):
        for hijo in nodo.hijos:
            if hijo.etiqueta == "Catch" and not hijo.valor:
                self._agregar(
                    hijo, "El 'catch' debe tener la forma "
                          "catch (<Tipo> <variable>) { ... }")

    def _modifica(self, nodo, variable):
        if nodo.etiqueta == "Asignacion":
            izq = nodo.hijos[0]
            if izq.etiqueta == "Identificador" and izq.valor == variable:
                return True
        if nodo.etiqueta in ("Unario", "Postfijo") and nodo.valor in ("++", "--"):
            objetivo = nodo.hijos[0]
            if objetivo.etiqueta == "Identificador" and objetivo.valor == variable:
                return True
        return any(self._modifica(h, variable) for h in nodo.hijos)


def validar_reglas(raiz, tokens=None):
    return ValidadorReglas().validar(raiz, tokens)
