"""Interprete de alto nivel del AST (try/catch, objetos, Scanner, etc.)."""

from .semantico import normalizar


# ======================================================================
# INTERPRETE DE ALTO NIVEL DEL AST
# ======================================================================

class _SenalReturn(Exception):
    def __init__(self, valor):
        self.valor = valor


class _SenalBreak(Exception):
    pass


class _SenalContinue(Exception):
    pass


class _ExcepcionRuntime(Exception):
    def __init__(self, tipo, mensaje):
        super().__init__(mensaje)
        self.tipo = tipo
        self.mensaje = mensaje

    def __str__(self):
        return f"{self.tipo}: {self.mensaje}" if self.mensaje else self.tipo


class _InstanciaObjeto:
    def __init__(self, nombre_clase):
        self.nombre_clase = nombre_clase
        self.campos = {}


class _ScannerRuntime:
    def __init__(self, proveedor_entrada):
        self.proveedor_entrada = proveedor_entrada
        self.tokens_buffer = []

    def _leer_linea(self):
        return self.proveedor_entrada()

    def _siguiente_token(self):
        while not self.tokens_buffer:
            linea = self._leer_linea()
            if linea is None:
                raise _ExcepcionRuntime("NoSuchElementException", "Entrada cancelada")
            partes = linea.strip().split()
            if partes:
                self.tokens_buffer.extend(partes)
        return self.tokens_buffer.pop(0)

    def nextInt(self):
        tok = self._siguiente_token()
        try:
            return int(tok)
        except ValueError:
            raise _ExcepcionRuntime("InputMismatchException", f"Se esperaba un entero y se recibio '{tok}'")

    def nextLong(self):
        return self.nextInt()

    def nextDouble(self):
        tok = self._siguiente_token()
        try:
            return float(tok)
        except ValueError:
            raise _ExcepcionRuntime("InputMismatchException", f"Se esperaba un decimal y se recibio '{tok}'")

    def nextFloat(self):
        return self.nextDouble()

    def nextBoolean(self):
        tok = self._siguiente_token().lower()
        if tok == "true":
            return True
        if tok == "false":
            return False
        raise _ExcepcionRuntime("InputMismatchException", f"Se esperaba booleano y se recibio '{tok}'")

    def next(self):
        return self._siguiente_token()

    def nextLine(self):
        if self.tokens_buffer:
            resto = " ".join(self.tokens_buffer)
            self.tokens_buffer.clear()
            return resto
        linea = self._leer_linea()
        if linea is None:
            return ""
        return linea

    def close(self):
        pass


class InterpreteAST:
    """Ejecuta cualquier programa Java del AST directamente en el IDE."""

    def __init__(self, pedir_entrada_fn=None, al_imprimir_fn=None):
        self.pedir_entrada_fn = pedir_entrada_fn
        self.al_imprimir_fn = al_imprimir_fn
        self.salida = []
        self.clases = {}
        self.metodos_globales = {}
        self.ambitos = [{}]
        self.this_actual = None
        self.pasos = 0
        self.MAX_PASOS = 200_000

    def _tick(self):
        self.pasos += 1
        if self.pasos > self.MAX_PASOS:
            raise _ExcepcionRuntime("RuntimeException", "Limite de iteraciones excedido")

    def _imprimir(self, texto, salto=False):
        s = self._formatear_valor(texto)
        if salto:
            s += "\n"
        self.salida.append(s)
        if self.al_imprimir_fn:
            self.al_imprimir_fn(s)

    def _formatear_valor(self, val):
        if val is None:
            return "null"
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, _ExcepcionRuntime):
            return str(val)
        return str(val)

    def _pedir_entrada(self):
        ultimo_prompt = "".join(self.salida).splitlines()
        prompt = ultimo_prompt[-1] if ultimo_prompt else "Ingresa un valor:"
        if self.pedir_entrada_fn:
            valor = self.pedir_entrada_fn(prompt)
            if valor is not None:
                self._imprimir(str(valor), salto=True)
            return valor
        return "0"

    def _entrar(self):
        self.ambitos.append({})

    def _salir(self):
        self.ambitos.pop()

    def _definir(self, nombre, valor):
        self.ambitos[-1][nombre] = valor

    def _asignar(self, nombre, valor):
        for amb in reversed(self.ambitos):
            if nombre in amb:
                amb[nombre] = valor
                return
        if self.this_actual is not None and nombre in self.this_actual.campos:
            self.this_actual.campos[nombre] = valor
            return
        self.ambitos[-1][nombre] = valor

    def _obtener(self, nombre):
        for amb in reversed(self.ambitos):
            if nombre in amb:
                return amb[nombre]
        if self.this_actual is not None and nombre in self.this_actual.campos:
            return self.this_actual.campos[nombre]
        return None

    def ejecutar(self, raiz):
        main_nodo = None
        clase_main = None
        sueltas = []

        for hijo in raiz.hijos:
            if hijo.etiqueta == "Clase":
                info = self._registrar_clase(hijo)
                if "main" in info["metodos"]:
                    main_nodo = info["metodos"]["main"][0]
                    clase_main = hijo.valor
            elif hijo.etiqueta == "Metodo":
                if hijo.valor == "main":
                    main_nodo = hijo
                else:
                    self.metodos_globales.setdefault(hijo.valor, []).append(hijo)
            elif hijo.etiqueta not in ("Importacion", "Paquete"):
                sueltas.append(hijo)

        try:
            if main_nodo is not None:
                # Si la clase tiene campos estaticos o de instancia y main llama
                # metodos de la clase, creamos una instancia implicita de respaldo
                if clase_main and clase_main in self.clases:
                    self.this_actual = self._crear_instancia_sin_constructor(clase_main)
                self._entrar()
                self._definir("args", [])
                for hijo in main_nodo.hijos:
                    if hijo.etiqueta == "Bloque":
                        self._ejecutar_bloque(hijo)
                self._salir()
            elif sueltas:
                self._entrar()
                for sent in sueltas:
                    self._ejecutar_sentencia(sent)
                self._salir()
        except _SenalReturn:
            pass
        except _ExcepcionRuntime as exc:
            self._imprimir(f"\nExcepcion no capturada -> {exc}", salto=True)

        return "".join(self.salida)

    def _registrar_clase(self, nodo_clase):
        info = {"campos": [], "constructores": [], "metodos": {}}
        for hijo in nodo_clase.hijos:
            if hijo.etiqueta == "Declaracion":
                info["campos"].append(hijo)
            elif hijo.etiqueta == "Metodo":
                es_ctor = False
                for sub in hijo.hijos:
                    if sub.etiqueta == "Tipo" and sub.valor == "constructor":
                        es_ctor = True
                        break
                if es_ctor:
                    info["constructores"].append(hijo)
                else:
                    info["metodos"].setdefault(hijo.valor, []).append(hijo)
        self.clases[nodo_clase.valor] = info
        return info

    def _crear_instancia_sin_constructor(self, nombre_clase):
        inst = _InstanciaObjeto(nombre_clase)
        info = self.clases.get(nombre_clase)
        if info:
            for decl in info["campos"]:
                tipo = normalizar(decl.tipo)
                for var in decl.hijos:
                    if var.etiqueta == "Variable":
                        if var.hijos:
                            inst.campos[var.valor] = self._evaluar(var.hijos[0])
                        else:
                            inst.campos[var.valor] = self._valor_por_defecto(tipo)
        return inst

    def _valor_por_defecto(self, tipo):
        if tipo in ("int", "long", "short", "byte"):
            return 0
        if tipo in ("double", "float"):
            return 0.0
        if tipo == "boolean":
            return False
        if tipo == "char":
            return "\0"
        return None

    def _ejecutar_bloque(self, nodo_bloque):
        self._entrar()
        try:
            for hijo in nodo_bloque.hijos:
                self._ejecutar_sentencia(hijo)
        finally:
            self._salir()

    def _ejecutar_sentencia(self, nodo):
        if nodo is None:
            return
        self._tick()
        et = nodo.etiqueta

        if et == "Bloque":
            self._ejecutar_bloque(nodo)
        elif et == "Declaracion":
            tipo = normalizar(nodo.tipo)
            for var in nodo.hijos:
                if var.etiqueta == "Variable":
                    if var.hijos:
                        val = self._evaluar(var.hijos[0])
                    else:
                        val = self._valor_por_defecto(tipo)
                    self._definir(var.valor, val)
        elif et == "SentenciaExpresion":
            for hijo in nodo.hijos:
                self._evaluar(hijo)
        elif et == "Asignacion":
            self._evaluar(nodo)
        elif et == "Si":
            cond = bool(self._evaluar(nodo.hijos[0].hijos[0]))
            if cond:
                self._ejecutar_sentencia(nodo.hijos[1])
            elif len(nodo.hijos) > 2:
                self._ejecutar_sentencia(nodo.hijos[2])
        elif et == "Mientras":
            while bool(self._evaluar(nodo.hijos[0].hijos[0])):
                self._tick()
                try:
                    self._ejecutar_sentencia(nodo.hijos[1])
                except _SenalContinue:
                    continue
                except _SenalBreak:
                    break
        elif et == "Hacer":
            while True:
                self._tick()
                try:
                    self._ejecutar_sentencia(nodo.hijos[0])
                except _SenalContinue:
                    pass
                except _SenalBreak:
                    break
                if not bool(self._evaluar(nodo.hijos[-1].hijos[0])):
                    break
        elif et == "Para":
            self._entrar()
            try:
                partes = {h.etiqueta: h for h in nodo.hijos}
                init = partes.get("Inicializacion")
                cond = partes.get("Condicion")
                inc = partes.get("Incremento")
                cuerpo = partes.get("Cuerpo")
                if init:
                    for sub in init.hijos:
                        self._ejecutar_sentencia(sub)
                while True:
                    self._tick()
                    if cond and cond.hijos:
                        if not bool(self._evaluar(cond.hijos[0])):
                            break
                    try:
                        if cuerpo:
                            for sub in cuerpo.hijos:
                                self._ejecutar_sentencia(sub)
                    except _SenalContinue:
                        pass
                    except _SenalBreak:
                        break
                    if inc:
                        for sub in inc.hijos:
                            self._ejecutar_sentencia(sub)
            finally:
                self._salir()
        elif et == "Switch":
            val_disc = self._evaluar(nodo.hijos[0].hijos[0])
            coincidio = False
            try:
                for caso in nodo.hijos[1:]:
                    if caso.etiqueta == "Caso":
                        if not coincidio:
                            val_caso = self._evaluar(caso.hijos[0].hijos[0])
                            if val_disc == val_caso:
                                coincidio = True
                        if coincidio:
                            for sent in caso.hijos[1:]:
                                self._ejecutar_sentencia(sent)
                    elif caso.etiqueta == "Default":
                        coincidio = True
                        for sent in caso.hijos:
                            self._ejecutar_sentencia(sent)
            except _SenalBreak:
                pass
        elif et == "Try":
            self._ejecutar_try(nodo)
        elif et == "Lanzar":
            val = self._evaluar(nodo.hijos[0])
            if isinstance(val, _ExcepcionRuntime):
                raise val
            raise _ExcepcionRuntime("Exception", str(val))
        elif et == "Retorno":
            val = self._evaluar(nodo.hijos[0]) if nodo.hijos else None
            raise _SenalReturn(val)
        elif et == "Break":
            raise _SenalBreak()
        elif et == "Continue":
            raise _SenalContinue()
        elif et == "Sincronizado":
            for hijo in nodo.hijos:
                if hijo.etiqueta == "Bloque":
                    self._ejecutar_sentencia(hijo)

    def _ejecutar_try(self, nodo):
        recursos = None
        cuerpo = None
        capturas = []
        cierre = None
        for hijo in nodo.hijos:
            if hijo.etiqueta == "Recursos":
                recursos = hijo
            elif hijo.etiqueta == "Bloque" and cuerpo is None:
                cuerpo = hijo
            elif hijo.etiqueta == "Catch":
                capturas.append(hijo)
            elif hijo.etiqueta == "Finally":
                cierre = hijo

        self._entrar()
        try:
            if recursos is not None:
                for rec in recursos.hijos:
                    self._ejecutar_sentencia(rec)
            if cuerpo is not None:
                self._ejecutar_bloque(cuerpo)
        except _ExcepcionRuntime as exc:
            atrapada = False
            for cap in capturas:
                tipo_cap = cap.tipo or "Exception"
                if tipo_cap in ("Exception", "RuntimeException", "Throwable", exc.tipo):
                    atrapada = True
                    self._entrar()
                    try:
                        self._definir(cap.valor, exc)
                        for hijo in cap.hijos:
                            if hijo.etiqueta == "Bloque":
                                self._ejecutar_bloque(hijo)
                    finally:
                        self._salir()
                    break
            if not atrapada:
                raise
        finally:
            self._salir()
            if cierre is not None:
                for hijo in cierre.hijos:
                    if hijo.etiqueta == "Bloque":
                        self._ejecutar_bloque(hijo)

    def _evaluar(self, nodo):
        if nodo is None:
            return None
        self._tick()
        et = nodo.etiqueta

        if et == "Literal":
            if nodo.tipo == "int":
                return int(nodo.valor)
            if nodo.tipo == "double":
                return float(nodo.valor)
            if nodo.tipo == "boolean":
                return nodo.valor == "true"
            if nodo.tipo == "char":
                txt = nodo.valor[1:-1] if len(nodo.valor) >= 2 else nodo.valor
                return self._unescape(txt)
            if nodo.tipo == "String":
                txt = nodo.valor[1:-1] if len(nodo.valor) >= 2 else nodo.valor
                return self._unescape(txt)
            return None

        if et == "Identificador":
            if nodo.valor == "this":
                return self.this_actual
            return self._obtener(nodo.valor)

        if et == "Agrupacion":
            return self._evaluar(nodo.hijos[0])

        if et == "ListaInicializacion":
            return [self._evaluar(h) for h in nodo.hijos]

        if et == "Nuevo":
            tipo = nodo.valor
            if tipo.endswith("[]"):
                tam = int(self._evaluar(nodo.hijos[0])) if nodo.hijos else 0
                base = tipo[:-2]
                return [self._valor_por_defecto(base) for _ in range(max(0, tam))]
            if tipo == "Scanner":
                return _ScannerRuntime(self._pedir_entrada)
            if tipo in self.clases:
                inst = self._crear_instancia_sin_constructor(tipo)
                args = [self._evaluar(a) for a in nodo.hijos]
                info = self.clases[tipo]
                ctor = None
                for c in info["constructores"]:
                    params = [p for h in c.hijos if h.etiqueta == "Parametros" for p in h.hijos]
                    if len(params) == len(args):
                        ctor = c
                        break
                if ctor is not None:
                    self._invocar_metodo(ctor, args, instancia=inst)
                return inst
            return _InstanciaObjeto(tipo)

        if et == "Indice":
            arr = self._evaluar(nodo.hijos[0])
            idx = int(self._evaluar(nodo.hijos[1]))
            if arr is None:
                raise _ExcepcionRuntime("NullPointerException", "Arreglo nulo")
            if idx < 0 or idx >= len(arr):
                raise _ExcepcionRuntime("ArrayIndexOutOfBoundsException", f"Indice {idx} fuera de rango")
            return arr[idx]

        if et == "Acceso":
            base = self._evaluar(nodo.hijos[0])
            miembro = nodo.valor
            if isinstance(base, list) and miembro == "length":
                return len(base)
            if isinstance(base, _InstanciaObjeto):
                return base.campos.get(miembro)
            return None

        if et == "Asignacion":
            izq, der = nodo.hijos[0], nodo.hijos[1]
            val_der = self._evaluar(der)
            if nodo.valor == "=":
                self._escribir_lvalue(izq, val_der)
                return val_der
            actual = self._evaluar(izq)
            if nodo.valor == "+=":
                nuevo = (str(actual) + str(val_der)) if isinstance(actual, str) else (actual + val_der)
            elif nodo.valor == "-=":
                nuevo = actual - val_der
            elif nodo.valor == "*=":
                nuevo = actual * val_der
            elif nodo.valor == "/=":
                if val_der == 0:
                    raise _ExcepcionRuntime("ArithmeticException", "Division por cero")
                nuevo = int(actual / val_der) if isinstance(actual, int) and isinstance(val_der, int) else (actual / val_der)
            elif nodo.valor == "%=":
                if val_der == 0:
                    raise _ExcepcionRuntime("ArithmeticException", "Modulo por cero")
                nuevo = actual % val_der
            else:
                nuevo = val_der
            self._escribir_lvalue(izq, nuevo)
            return nuevo

        if et == "Unario":
            op = nodo.valor
            if op in ("++", "--"):
                actual = self._evaluar(nodo.hijos[0])
                nuevo = actual + 1 if op == "++" else actual - 1
                self._escribir_lvalue(nodo.hijos[0], nuevo)
                return nuevo
            val = self._evaluar(nodo.hijos[0])
            if op == "-":
                return -val
            if op == "+":
                return +val
            if op == "!":
                return not bool(val)
            if op == "~":
                return ~int(val)
            return val

        if et == "Postfijo":
            actual = self._evaluar(nodo.hijos[0])
            nuevo = actual + 1 if nodo.valor == "++" else actual - 1
            self._escribir_lvalue(nodo.hijos[0], nuevo)
            return actual

        if et == "Operacion":
            op = nodo.valor
            if op == "&&":
                return bool(self._evaluar(nodo.hijos[0])) and bool(self._evaluar(nodo.hijos[1]))
            if op == "||":
                return bool(self._evaluar(nodo.hijos[0])) or bool(self._evaluar(nodo.hijos[1]))
            a = self._evaluar(nodo.hijos[0])
            b = self._evaluar(nodo.hijos[1])
            if op == "+":
                if isinstance(a, str) or isinstance(b, str):
                    return self._formatear_valor(a) + self._formatear_valor(b)
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if b == 0:
                    raise _ExcepcionRuntime("ArithmeticException", "/ by zero")
                if isinstance(a, int) and isinstance(b, int):
                    return int(a / b)
                return a / b
            if op == "%":
                if b == 0:
                    raise _ExcepcionRuntime("ArithmeticException", "/ by zero")
                return a % b
            if op == "<":
                return a < b
            if op == ">":
                return a > b
            if op == "<=":
                return a <= b
            if op == ">=":
                return a >= b
            if op == "==":
                return a == b
            if op == "!=":
                return a != b

        if et == "Llamada":
            return self._evaluar_llamada(nodo)

        return None

    def _escribir_lvalue(self, nodo, valor):
        if nodo.etiqueta == "Identificador":
            self._asignar(nodo.valor, valor)
        elif nodo.etiqueta == "Indice":
            arr = self._evaluar(nodo.hijos[0])
            idx = int(self._evaluar(nodo.hijos[1]))
            arr[idx] = valor
        elif nodo.etiqueta == "Acceso":
            base = self._evaluar(nodo.hijos[0])
            if isinstance(base, _InstanciaObjeto):
                base.campos[nodo.valor] = valor

    def _evaluar_llamada(self, nodo):
        callee = nodo.hijos[0]
        args = [self._evaluar(a) for a in nodo.hijos[1:]]

        if callee.etiqueta == "Identificador":
            nombre = callee.valor
            if nombre in ("println", "print"):
                texto = "".join(self._formatear_valor(a) for a in args)
                self._imprimir(texto, salto=(nombre == "println"))
                return None
            metodo = self._buscar_metodo_callable(nombre, len(args), self.this_actual)
            if metodo is not None:
                return self._invocar_metodo(metodo, args, instancia=self.this_actual)
            return None

        if callee.etiqueta == "Acceso":
            metodo_nombre = callee.valor
            cadena_acceso = self._ruta_acceso(callee)
            if cadena_acceso in ("System.out.println", "System.out.print"):
                texto = "".join(self._formatear_valor(a) for a in args)
                self._imprimir(texto, salto=cadena_acceso.endswith("println"))
                return None
            if cadena_acceso == "System.out.printf" and args:
                fmt = str(args[0])
                try:
                    texto = fmt % tuple(args[1:])
                except Exception:
                    texto = fmt
                self._imprimir(texto, salto=False)
                return None
            if cadena_acceso.startswith("Math."):
                import math
                fn = getattr(math, metodo_nombre, None)
                if fn:
                    return fn(*args)
            if cadena_acceso == "Integer.parseInt" and args:
                try:
                    return int(str(args[0]).strip())
                except ValueError:
                    raise _ExcepcionRuntime("NumberFormatException", f"For input string: \"{args[0]}\"")
            if cadena_acceso == "Double.parseDouble" and args:
                try:
                    return float(str(args[0]).strip())
                except ValueError:
                    raise _ExcepcionRuntime("NumberFormatException", f"For input string: \"{args[0]}\"")

            receptor = self._evaluar(callee.hijos[0])
            if isinstance(receptor, _ScannerRuntime):
                fn = getattr(receptor, metodo_nombre, None)
                if fn:
                    return fn()
                return None
            if isinstance(receptor, str):
                if metodo_nombre == "length":
                    return len(receptor)
                if metodo_nombre == "charAt" and args:
                    return receptor[int(args[0])]
                if metodo_nombre == "equals" and args:
                    return receptor == str(args[0])
                if metodo_nombre == "equalsIgnoreCase" and args:
                    return receptor.lower() == str(args[0]).lower()
                if metodo_nombre == "toUpperCase":
                    return receptor.upper()
                if metodo_nombre == "toLowerCase":
                    return receptor.lower()
                if metodo_nombre == "trim":
                    return receptor.strip()
                return None
            if isinstance(receptor, _InstanciaObjeto):
                metodo = self._buscar_metodo_callable(metodo_nombre, len(args), receptor)
                if metodo is not None:
                    return self._invocar_metodo(metodo, args, instancia=receptor)
            if receptor is None:
                raise _ExcepcionRuntime("NullPointerException", f"Llamada a '{metodo_nombre}' sobre referencia nula")
        return None

    def _ruta_acceso(self, nodo):
        partes = []
        actual = nodo
        while actual.etiqueta == "Acceso":
            partes.append(actual.valor)
            actual = actual.hijos[0]
        if actual.etiqueta == "Identificador":
            partes.append(actual.valor)
        return ".".join(reversed(partes))

    def _buscar_metodo_callable(self, nombre, num_args, instancia):
        if instancia is not None and instancia.nombre_clase in self.clases:
            candidatos = self.clases[instancia.nombre_clase]["metodos"].get(nombre, [])
            for m in candidatos:
                params = [p for h in m.hijos if h.etiqueta == "Parametros" for p in h.hijos]
                if len(params) == num_args:
                    return m
            if candidatos:
                return candidatos[0]
        for info in self.clases.values():
            candidatos = info["metodos"].get(nombre, [])
            for m in candidatos:
                params = [p for h in m.hijos if h.etiqueta == "Parametros" for p in h.hijos]
                if len(params) == num_args:
                    return m
        globales = self.metodos_globales.get(nombre, [])
        if globales:
            return globales[0]
        return None

    def _invocar_metodo(self, nodo_metodo, args, instancia=None):
        anterior_this = self.this_actual
        if instancia is not None:
            self.this_actual = instancia
        self._entrar()
        try:
            params = []
            cuerpo = None
            for hijo in nodo_metodo.hijos:
                if hijo.etiqueta == "Parametros":
                    params = hijo.hijos
                elif hijo.etiqueta == "Bloque":
                    cuerpo = hijo
            for i, p in enumerate(params):
                val = args[i] if i < len(args) else None
                self._definir(p.valor, val)
            if cuerpo is not None:
                self._ejecutar_bloque(cuerpo)
        except _SenalReturn as ret:
            return ret.valor
        finally:
            self._salir()
            self.this_actual = anterior_this
        return None

    @staticmethod
    def _unescape(texto):
        escapes = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "'": "'"}
        res = []
        i = 0
        while i < len(texto):
            if texto[i] == "\\" and i + 1 < len(texto):
                res.append(escapes.get(texto[i + 1], texto[i + 1]))
                i += 2
            else:
                res.append(texto[i])
                i += 1
        return "".join(res)
