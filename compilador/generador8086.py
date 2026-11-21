"""Traductor de Java a ensamblador 8086."""

from .semantico import normalizar


# ======================================================================
# TRADUCTOR JAVA -> ENSAMBLADOR 8086
# ======================================================================

class ErrorGeneracion(Exception):
    """Error detectado al traducir el arbol de parseo a ensamblador."""

    def __init__(self, linea, mensaje, columna=0):
        super().__init__(mensaje)
        self.linea = linea or 0
        self.columna = columna or 0
        self.mensaje = mensaje
        self.tipo = "error"


class Generador8086:
    """Traduce el AST de Java a codigo ensamblador con sintaxis 8086.

    Soporta:
      - Clases, atributos, constructores y metodos (PROC / ENDP / CALL),
      - Variables de cualquier tipo (int, double, float, String, char,
        boolean, Scanner, objetos),
      - Arreglos con { ... } o new tipo[N],
      - try { ... } catch (...) { ... } finally { ... } y try (recursos),
      - if/else, while, do-while, for, switch/case, break, continue, return, throw,
      - Entrada con Scanner (nextInt, nextDouble, nextLine, next) y salida
        con System.out.print / System.out.println y concatenacion.

    Si el programa usa solo el subconjunto binario de 16 bits, marca
    `es_com_puro = True` para generar un ejecutable .COM real. Si incluye
    construcciones de alto nivel (try/catch, Scanner, clases/metodos, String,
    double, switch, do-while), genera el ensamblador 8086 completo y delega
    la ejecucion directa al interprete del AST.
    """

    TIPOS_ENTEROS = {"int", "char", "short", "byte", "long", "boolean"}

    def __init__(self):
        self.lineas = []
        self.escalares = []
        self.arreglos = []
        self.cadenas = []
        self.cadenas_texto = {}
        self.contador = 0
        self.ambitos = [{}]
        self.etiquetas_break = []
        self.etiquetas_continue = []
        self.etiquetas_catch = []
        self.finales = []
        self.es_com_puro = True
        self.usa_scanner = False
        self.procedimientos = []

    def _marcar_extendido(self):
        self.es_com_puro = False

    def _emitir(self, linea=""):
        self.lineas.append(linea)

    def _etiqueta(self, prefijo="L"):
        self.contador += 1
        return f"{prefijo}{self.contador:04d}"

    def _error(self, nodo, mensaje):
        linea = getattr(nodo, "linea", 0) or 0
        columna = getattr(nodo, "columna", 0) or 0
        raise ErrorGeneracion(linea, mensaje, columna)

    def _entrar(self):
        self.ambitos.append({})

    def _salir(self):
        self.ambitos.pop()

    def _declarar(self, nodo, nombre, simbolo):
        self.ambitos[-1][nombre] = simbolo

    def _buscar(self, nombre):
        for ambito in reversed(self.ambitos):
            if nombre in ambito:
                return ambito[nombre]
        return None

    # ------------------------------------------------------------------
    # Punto de entrada de generacion
    # ------------------------------------------------------------------
    def generar(self, raiz):
        clases, metodos_extra, campos_clase, sentencias_main = self._extraer_estructura(raiz)

        if metodos_extra or campos_clase:
            self._marcar_extendido()

        # Compilamos primero el cuerpo principal en un buffer temporal para
        # determinar si el programa es 100% .COM puro o usa extensiones.
        cuerpo_main = []
        self.lineas = cuerpo_main
        self._entrar()

        for campo in campos_clase:
            self._declaracion(campo, es_global=True)

        for sentencia in sentencias_main:
            self._sentencia(sentencia)

        self._salir()

        # Compilamos metodos auxiliares y constructores como procedimientos 8086
        cuerpo_procs = []
        for metodo in metodos_extra:
            proc_lineas = []
            self.lineas = proc_lineas
            self._compilar_procedimiento(metodo)
            cuerpo_procs.extend(proc_lineas)

        # Ensamblado final del archivo .asm con sintaxis 8086
        self.lineas = []
        self._emitir("; ======================================================")
        self._emitir("; Generado automaticamente por el IDE (Java -> 8086)")
        self._emitir("; Sintaxis compatible con MASM / TASM / emu8086")
        self._emitir("; ======================================================")
        self._emitir("")

        if self.es_com_puro:
            self._emitir("        .model tiny")
            self._emitir("        .code")
            self._emitir("        org 100h")
            self._emitir("")
            self._emitir("inicio:")
            self._emitir("        mov     ax, cs")
            self._emitir("        mov     ds, ax")
            self._emitir("        mov     es, ax")
            self._emitir("")
            self.lineas.extend(cuerpo_main)
            self._emitir("")
            self._emitir("        mov     ax, 4C00h")
            self._emitir("        int     21h")
            self._emitir("")
            self._rutinas()
            self._seccion_datos()
            self._emitir("")
            self._emitir("        end inicio")
        else:
            self._emitir("        .model small")
            self._emitir("        .stack 100h")
            self._emitir("")
            self._emitir("        .data")
            self._seccion_datos(con_comentario=False)
            self._emitir("")
            self._emitir("        .code")
            self._emitir("main PROC")
            self._emitir("        mov     ax, @data")
            self._emitir("        mov     ds, ax")
            self._emitir("        mov     es, ax")
            self._emitir("")
            self.lineas.extend(cuerpo_main)
            self._emitir("")
            self._emitir("        mov     ax, 4C00h")
            self._emitir("        int     21h")
            self._emitir("main ENDP")
            self._emitir("")
            if cuerpo_procs:
                self.lineas.extend(cuerpo_procs)
            self._rutinas()
            self._emitir("        end main")

        return "\n".join(self.lineas) + "\n"

    def _extraer_estructura(self, raiz):
        clases = []
        metodos_extra = []
        campos_clase = []
        metodo_main = None

        def explorar(nodo):
            nonlocal metodo_main
            for hijo in nodo.hijos:
                if hijo.etiqueta == "Clase":
                    clases.append(hijo)
                    explorar(hijo)
                elif hijo.etiqueta == "Metodo":
                    if hijo.valor == "main" and metodo_main is None:
                        metodo_main = hijo
                    else:
                        metodos_extra.append(hijo)
                elif hijo.etiqueta == "Declaracion" and nodo.etiqueta == "Clase":
                    campos_clase.append(hijo)

        explorar(raiz)

        if metodo_main is not None:
            sentencias = []
            for hijo in metodo_main.hijos:
                if hijo.etiqueta == "Bloque":
                    sentencias = hijo.hijos
                    break
            return clases, metodos_extra, campos_clase, sentencias

        sueltas = [h for h in raiz.hijos
                   if h.etiqueta not in ("Clase", "Metodo", "Importacion", "Paquete")]
        if sueltas:
            return clases, metodos_extra, campos_clase, sueltas

        if metodos_extra:
            # Si hay metodos pero no main, usamos el primero como entrada
            primero = metodos_extra.pop(0)
            sentencias = []
            for hijo in primero.hijos:
                if hijo.etiqueta == "Bloque":
                    sentencias = hijo.hijos
                    break
            return clases, metodos_extra, campos_clase, sentencias

        self._error(raiz, "No se encontraron sentencias o metodos para traducir")

    def _compilar_procedimiento(self, metodo):
        nombre = metodo.valor or "subrutina"
        self._emitir(f"; --- Procedimiento: {nombre} ---")
        self._emitir(f"{nombre} PROC")
        self._emitir("        push    bp")
        self._emitir("        mov     bp, sp")
        self._entrar()

        desplazamiento_bp = 4
        for hijo in metodo.hijos:
            if hijo.etiqueta == "Parametros":
                for param in hijo.hijos:
                    self.contador += 1
                    etiqueta_param = f"p_{param.valor}_{self.contador}"
                    self.escalares.append(etiqueta_param)
                    self._declarar(param, param.valor, ("var", etiqueta_param, normalizar(param.tipo)))
                    self._emitir(f"        mov     ax, [bp+{desplazamiento_bp}]")
                    self._emitir(f"        mov     [{etiqueta_param}], ax")
                    desplazamiento_bp += 2
            elif hijo.etiqueta == "Bloque":
                for sent in hijo.hijos:
                    self._sentencia(sent, en_subrutina=True)

        self._salir()
        self._emitir("        pop     bp")
        self._emitir("        ret")
        self._emitir(f"{nombre} ENDP")
        self._emitir("")

    # ------------------------------------------------------------------
    # Datos, cadenas y rutinas 8086
    # ------------------------------------------------------------------
    def _cadena(self, texto):
        if texto not in self.cadenas_texto:
            self.contador += 1
            etiqueta = f"str{self.contador:04d}"
            self.cadenas_texto[texto] = etiqueta
            self.cadenas.append((etiqueta, texto))
        return self.cadenas_texto[texto]

    def _db_texto(self, texto):
        piezas = []
        actual = []
        for caracter in texto:
            codigo = ord(caracter)
            if 32 <= codigo <= 126 and caracter != '"':
                actual.append(caracter)
            else:
                if actual:
                    piezas.append('"' + "".join(actual) + '"')
                    actual = []
                try:
                    byte = caracter.encode("cp437")[0]
                except (UnicodeEncodeError, IndexError):
                    byte = ord("?")
                piezas.append(str(byte))
        if actual:
            piezas.append('"' + "".join(actual) + '"')
        piezas.append("'$'")
        return ", ".join(piezas)

    def _seccion_datos(self, con_comentario=True):
        if con_comentario:
            self._emitir("; ------------------------- datos -------------------------")
        for etiqueta in self.escalares:
            self._emitir(f"        {etiqueta} dw 0")
        for etiqueta, valores in self.arreglos:
            self._emitir(f"        {etiqueta} dw " + ", ".join(str(v) for v in valores))
        for etiqueta, texto in self.cadenas:
            self._emitir(f"        {etiqueta} db {self._db_texto(texto)}")
        if self.usa_scanner:
            self._emitir("        buf_entrada db 64, 0, 64 dup(0)")

    def _rutinas(self):
        self._emitir("; ------------------------ rutinas ------------------------")
        self._emitir("rt_imprimir_numero:")
        self._emitir("        push    ax")
        self._emitir("        push    bx")
        self._emitir("        push    cx")
        self._emitir("        push    dx")
        self._emitir("        test    ax, ax")
        self._emitir("        jns     rt_num_positivo")
        self._emitir("        push    ax")
        self._emitir("        mov     dl, '-'")
        self._emitir("        mov     ah, 02h")
        self._emitir("        int     21h")
        self._emitir("        pop     ax")
        self._emitir("        neg     ax")
        self._emitir("rt_num_positivo:")
        self._emitir("        mov     bx, 10")
        self._emitir("        xor     cx, cx")
        self._emitir("rt_num_dividir:")
        self._emitir("        xor     dx, dx")
        self._emitir("        div     bx")
        self._emitir("        push    dx")
        self._emitir("        inc     cx")
        self._emitir("        test    ax, ax")
        self._emitir("        jnz     rt_num_dividir")
        self._emitir("rt_num_mostrar:")
        self._emitir("        pop     dx")
        self._emitir("        add     dl, '0'")
        self._emitir("        mov     ah, 02h")
        self._emitir("        int     21h")
        self._emitir("        loop    rt_num_mostrar")
        self._emitir("        pop     dx")
        self._emitir("        pop     cx")
        self._emitir("        pop     bx")
        self._emitir("        pop     ax")
        self._emitir("        ret")
        self._emitir("")
        self._emitir("rt_nueva_linea:")
        self._emitir("        push    ax")
        self._emitir("        push    dx")
        self._emitir("        mov     dl, 13")
        self._emitir("        mov     ah, 02h")
        self._emitir("        int     21h")
        self._emitir("        mov     dl, 10")
        self._emitir("        mov     ah, 02h")
        self._emitir("        int     21h")
        self._emitir("        pop     dx")
        self._emitir("        pop     ax")
        self._emitir("        ret")
        self._emitir("")
        if self.usa_scanner:
            self._emitir("rt_leer_entrada:")
            self._emitir("        push    dx")
            self._emitir("        mov     dx, offset buf_entrada")
            self._emitir("        mov     ah, 0Ah")
            self._emitir("        int     21h")
            self._emitir("        call    rt_nueva_linea")
            self._emitir("        xor     ax, ax")
            self._emitir("        mov     al, [buf_entrada+1]")
            self._emitir("        pop     dx")
            self._emitir("        ret")
            self._emitir("")

    # ------------------------------------------------------------------
    # Sentencias
    # ------------------------------------------------------------------
    def _sentencia(self, nodo, en_subrutina=False):
        if nodo is None:
            return
        etiqueta = nodo.etiqueta
        if etiqueta == "Bloque":
            self._entrar()
            for hijo in nodo.hijos:
                self._sentencia(hijo, en_subrutina=en_subrutina)
            self._salir()
        elif etiqueta == "Declaracion":
            self._declaracion(nodo)
        elif etiqueta == "SentenciaExpresion":
            for hijo in nodo.hijos:
                self._expresion(hijo)
        elif etiqueta == "Asignacion":
            self._expresion(nodo)
        elif etiqueta == "Si":
            self._si(nodo, en_subrutina=en_subrutina)
        elif etiqueta == "Mientras":
            self._mientras(nodo, en_subrutina=en_subrutina)
        elif etiqueta == "Hacer":
            self._hacer(nodo, en_subrutina=en_subrutina)
        elif etiqueta == "Para":
            self._para(nodo, en_subrutina=en_subrutina)
        elif etiqueta == "Switch":
            self._switch(nodo, en_subrutina=en_subrutina)
        elif etiqueta == "SentenciaVacia":
            self._emitir("        nop")
        elif etiqueta == "Retorno":
            if nodo.hijos:
                self._expresion(nodo.hijos[0])
            self._emitir_finales(en_subrutina=en_subrutina)
            if en_subrutina:
                self._emitir("        pop     bp")
                self._emitir("        ret")
            else:
                self._emitir("        mov     ax, 4C00h")
                self._emitir("        int     21h")
        elif etiqueta == "Break":
            if self.etiquetas_break:
                self._emitir_finales(en_subrutina=en_subrutina)
                self._emitir(f"        jmp     {self.etiquetas_break[-1]}")
        elif etiqueta == "Continue":
            if self.etiquetas_continue:
                self._emitir_finales(en_subrutina=en_subrutina)
                self._emitir(f"        jmp     {self.etiquetas_continue[-1]}")
        elif etiqueta == "Try":
            self._try(nodo, en_subrutina=en_subrutina)
        elif etiqueta == "Lanzar":
            self._marcar_extendido()
            self._emitir("        ; throw excepcion")
            if nodo.hijos:
                self._expresion(nodo.hijos[0])
            if self.etiquetas_catch:
                self._emitir(f"        jmp     {self.etiquetas_catch[-1]}")
            else:
                self._emitir("        mov     ax, 4C01h")
                self._emitir("        int     21h")
        elif etiqueta == "Sincronizado":
            self._marcar_extendido()
            self._emitir("        ; synchronized")
            for hijo in nodo.hijos:
                if hijo.etiqueta == "Bloque":
                    self._sentencia(hijo, en_subrutina=en_subrutina)
        else:
            self._marcar_extendido()
            self._emitir(f"        ; {etiqueta}")

    def _try(self, nodo, en_subrutina=False):
        """Traduce try { ... } catch (...) { ... } finally { ... } a 8086."""
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

        if capturas or recursos is not None:
            self._marcar_extendido()

        etiqueta_try = self._etiqueta("L_TRY_")
        etiqueta_finally = self._etiqueta("L_FINALLY_")
        etiqueta_fin = self._etiqueta("L_END_TRY_")
        etiquetas_cap = [self._etiqueta("L_CATCH_") for _ in capturas]

        self._emitir(f"{etiqueta_try}: ; inicio bloque try")
        self._entrar()

        if recursos is not None:
            for recurso in recursos.hijos:
                if recurso.etiqueta == "Declaracion":
                    self._declaracion(recurso)

        bloques_final = []
        if cierre is not None:
            bloques_final = [h for h in cierre.hijos if h.etiqueta == "Bloque"]
        self.finales.extend(bloques_final)

        if etiquetas_cap:
            self.etiquetas_catch.append(etiquetas_cap[0])

        if cuerpo is not None:
            self._sentencia(cuerpo, en_subrutina=en_subrutina)

        if etiquetas_cap:
            self.etiquetas_catch.pop()

        if bloques_final:
            del self.finales[-len(bloques_final):]

        self._salir()
        self._emitir(f"        jmp     {etiqueta_finally}")

        for idx, cap in enumerate(capturas):
            self._emitir(f"{etiquetas_cap[idx]}: ; catch ({cap.tipo} {cap.valor})")
            self._entrar()
            self.contador += 1
            etiqueta_exc = f"v_{cap.valor}_{self.contador}"
            self.escalares.append(etiqueta_exc)
            self._declarar(cap, cap.valor, ("var", etiqueta_exc, cap.tipo or "Exception"))
            self._emitir(f"        mov     [{etiqueta_exc}], ax")
            for hijo in cap.hijos:
                if hijo.etiqueta == "Bloque":
                    self._sentencia(hijo, en_subrutina=en_subrutina)
            self._salir()
            self._emitir(f"        jmp     {etiqueta_finally}")

        self._emitir(f"{etiqueta_finally}: ; bloque finally")
        for bloque in bloques_final:
            self._sentencia(bloque, en_subrutina=en_subrutina)
        self._emitir(f"{etiqueta_fin}: ; fin try")

    def _emitir_finales(self, en_subrutina=False):
        pendientes = self.finales
        if not pendientes:
            return
        self.finales = []
        try:
            for bloque in reversed(pendientes):
                self._sentencia(bloque, en_subrutina=en_subrutina)
        finally:
            self.finales = pendientes

    def _declaracion(self, nodo, es_global=False):
        tipo = normalizar(nodo.tipo)
        for variable in nodo.hijos:
            if variable.etiqueta != "Variable":
                continue
            tipo_variable = normalizar(variable.tipo or tipo)
            valor_inicial = variable.hijos[0] if variable.hijos else None
            if tipo_variable.endswith("[]"):
                self._declarar_arreglo(nodo, variable, valor_inicial)
            elif tipo_variable in self.TIPOS_ENTEROS:
                self.contador += 1
                etiqueta_var = f"v_{variable.valor}_{self.contador}"
                self._declarar(nodo, variable.valor,
                               ("var", etiqueta_var, tipo_variable))
                self.escalares.append(etiqueta_var)
                if valor_inicial is not None:
                    self._expresion(valor_inicial)
                    self._emitir(f"        mov     [{etiqueta_var}], ax")
            else:
                # Tipos extendidos: String, double, float, Scanner, objetos
                self._marcar_extendido()
                self.contador += 1
                etiqueta_var = f"v_{variable.valor}_{self.contador}"
                self._declarar(nodo, variable.valor,
                               ("obj", etiqueta_var, tipo_variable))
                self.escalares.append(etiqueta_var)
                self._emitir(f"        ; {tipo_variable} {variable.valor}")
                if valor_inicial is not None:
                    self._expresion(valor_inicial)
                    self._emitir(f"        mov     [{etiqueta_var}], ax")

    def _declarar_arreglo(self, nodo, variable, valor_inicial):
        nombre = variable.valor
        valores = []
        if valor_inicial is not None and valor_inicial.etiqueta == "ListaInicializacion":
            for elemento in valor_inicial.hijos:
                valores.append(self._literal_entero_o_cero(elemento))
        elif valor_inicial is not None and valor_inicial.etiqueta == "Nuevo":
            tamano = 10
            if valor_inicial.hijos:
                tamano = max(1, self._literal_entero_o_cero(valor_inicial.hijos[0], defecto=10))
            valores = [0] * tamano
        else:
            valores = [0] * 10
        self.contador += 1
        etiqueta_arr = f"a_{nombre}_{self.contador}"
        self._declarar(variable, nombre, ("arr", etiqueta_arr, len(valores)))
        self.arreglos.append((etiqueta_arr, valores))

    def _literal_entero_o_cero(self, nodo, defecto=0):
        signo = 1
        while nodo.etiqueta == "Agrupacion":
            nodo = nodo.hijos[0]
        if nodo.etiqueta == "Unario" and nodo.valor in ("-", "+"):
            if nodo.valor == "-":
                signo = -1
            nodo = nodo.hijos[0]
        if nodo.etiqueta == "Literal" and nodo.tipo == "int":
            try:
                return signo * int(nodo.valor)
            except ValueError:
                return defecto
        self._marcar_extendido()
        return defecto

    def _codigo_caracter(self, nodo):
        texto = nodo.valor
        if len(texto) >= 2 and texto[0] == "'" and texto[-1] == "'":
            texto = texto[1:-1]
        texto = self._texto_cadena('"' + texto + '"')
        if len(texto) >= 1:
            return ord(texto[0])
        return 0

    def _tipo_simple(self, nodo):
        if nodo is None:
            return None
        if nodo.etiqueta == "Literal":
            return nodo.tipo
        if nodo.etiqueta == "Agrupacion":
            return self._tipo_simple(nodo.hijos[0])
        if nodo.etiqueta == "Identificador":
            simbolo = self._buscar(nodo.valor)
            if simbolo is not None:
                return simbolo[2]
            return None
        if nodo.etiqueta == "Operacion":
            if nodo.valor in ("<", ">", "<=", ">=", "==", "!=", "&&", "||"):
                return "boolean"
            return "int"
        if nodo.etiqueta == "Unario" and nodo.valor == "!":
            return "boolean"
        if nodo.etiqueta == "Postfijo":
            return "int"
        return None

    def _condicion(self, nodo):
        if nodo is None:
            self._emitir("        xor     ax, ax")
            return
        if nodo.etiqueta == "Condicion":
            if not nodo.hijos:
                self._emitir("        xor     ax, ax")
                return
            self._expresion(nodo.hijos[0])
        else:
            self._expresion(nodo)

    def _si(self, nodo, en_subrutina=False):
        etiqueta_falso = self._etiqueta()
        etiqueta_fin = self._etiqueta()
        self._condicion(nodo.hijos[0])
        self._emitir("        test    ax, ax")
        self._emitir(f"        jz      {etiqueta_falso}")
        self._sentencia(nodo.hijos[1], en_subrutina=en_subrutina)
        if len(nodo.hijos) > 2:
            self._emitir(f"        jmp     {etiqueta_fin}")
        self._emitir(f"{etiqueta_falso}:")
        if len(nodo.hijos) > 2:
            self._sentencia(nodo.hijos[2], en_subrutina=en_subrutina)
            self._emitir(f"{etiqueta_fin}:")

    def _mientras(self, nodo, en_subrutina=False):
        etiqueta_inicio = self._etiqueta()
        etiqueta_fin = self._etiqueta()
        self.etiquetas_break.append(etiqueta_fin)
        self.etiquetas_continue.append(etiqueta_inicio)
        self._emitir(f"{etiqueta_inicio}:")
        self._condicion(nodo.hijos[0])
        self._emitir("        test    ax, ax")
        self._emitir(f"        jz      {etiqueta_fin}")
        self._sentencia(nodo.hijos[1], en_subrutina=en_subrutina)
        self._emitir(f"        jmp     {etiqueta_inicio}")
        self._emitir(f"{etiqueta_fin}:")
        self.etiquetas_continue.pop()
        self.etiquetas_break.pop()

    def _hacer(self, nodo, en_subrutina=False):
        self._marcar_extendido()
        etiqueta_inicio = self._etiqueta()
        etiqueta_cond = self._etiqueta()
        etiqueta_fin = self._etiqueta()
        self.etiquetas_break.append(etiqueta_fin)
        self.etiquetas_continue.append(etiqueta_cond)
        self._emitir(f"{etiqueta_inicio}:")
        self._sentencia(nodo.hijos[0], en_subrutina=en_subrutina)
        self._emitir(f"{etiqueta_cond}:")
        self._condicion(nodo.hijos[-1])
        self._emitir("        test    ax, ax")
        self._emitir(f"        jnz     {etiqueta_inicio}")
        self._emitir(f"{etiqueta_fin}:")
        self.etiquetas_continue.pop()
        self.etiquetas_break.pop()

    def _switch(self, nodo, en_subrutina=False):
        self._marcar_extendido()
        etiqueta_fin = self._etiqueta("L_SW_FIN_")
        self.etiquetas_break.append(etiqueta_fin)
        self._expresion(nodo.hijos[0].hijos[0])
        self._emitir("        push    ax")
        etiquetas_casos = []
        etiqueta_default = None
        for caso in nodo.hijos[1:]:
            if caso.etiqueta == "Caso":
                et = self._etiqueta("L_CASE_")
                etiquetas_casos.append((et, caso))
                self._expresion(caso.hijos[0].hijos[0])
                self._emitir("        mov     bx, ax")
                self._emitir("        pop     ax")
                self._emitir("        push    ax")
                self._emitir("        cmp     ax, bx")
                self._emitir(f"        je      {et}")
            elif caso.etiqueta == "Default":
                etiqueta_default = self._etiqueta("L_DEF_")
                etiquetas_casos.append((etiqueta_default, caso))
        self._emitir("        pop     ax")
        self._emitir(f"        jmp     {etiqueta_default or etiqueta_fin}")
        for et, caso in etiquetas_casos:
            self._emitir(f"{et}:")
            self._emitir("        pop     ax")
            self._emitir("        push    ax")
            inicio_sents = 1 if caso.etiqueta == "Caso" else 0
            for sent in caso.hijos[inicio_sents:]:
                self._sentencia(sent, en_subrutina=en_subrutina)
        self._emitir(f"{etiqueta_fin}:")
        self._emitir("        pop     ax")
        self.etiquetas_break.pop()

    def _para(self, nodo, en_subrutina=False):
        self._entrar()
        inicializacion = condicion = incremento = cuerpo = None
        for hijo in nodo.hijos:
            if hijo.etiqueta == "Inicializacion":
                inicializacion = hijo
            elif hijo.etiqueta == "Condicion":
                condicion = hijo
            elif hijo.etiqueta == "Incremento":
                incremento = hijo
            elif hijo.etiqueta == "Cuerpo":
                cuerpo = hijo

        if inicializacion is not None:
            for sub in inicializacion.hijos:
                if sub.etiqueta == "Declaracion":
                    self._sentencia(sub, en_subrutina=en_subrutina)
                else:
                    self._expresion(sub)

        etiqueta_inicio = self._etiqueta()
        etiqueta_incremento = self._etiqueta()
        etiqueta_fin = self._etiqueta()
        self.etiquetas_break.append(etiqueta_fin)
        self.etiquetas_continue.append(etiqueta_incremento)
        self._emitir(f"{etiqueta_inicio}:")
        if condicion is not None and condicion.hijos:
            self._condicion(condicion)
            self._emitir("        test    ax, ax")
            self._emitir(f"        jz      {etiqueta_fin}")
        if cuerpo is not None:
            for sub in cuerpo.hijos:
                self._sentencia(sub, en_subrutina=en_subrutina)
        self._emitir(f"{etiqueta_incremento}:")
        if incremento is not None:
            for sub in incremento.hijos:
                if sub.etiqueta == "Declaracion":
                    self._sentencia(sub, en_subrutina=en_subrutina)
                else:
                    self._expresion(sub)
        self._emitir(f"        jmp     {etiqueta_inicio}")
        self._emitir(f"{etiqueta_fin}:")
        self.etiquetas_continue.pop()
        self.etiquetas_break.pop()
        self._salir()

    # ------------------------------------------------------------------
    # Expresiones (el resultado queda en AX)
    # ------------------------------------------------------------------
    def _expresion(self, nodo):
        if nodo is None:
            self._emitir("        xor     ax, ax")
            return
        etiqueta = nodo.etiqueta
        if etiqueta == "Literal":
            if nodo.tipo == "int":
                val = int(nodo.valor) & 0xFFFF
                self._emitir(f"        mov     ax, {val}")
            elif nodo.tipo == "double":
                self._marcar_extendido()
                try:
                    val = int(float(nodo.valor)) & 0xFFFF
                except ValueError:
                    val = 0
                self._emitir(f"        mov     ax, {val} ; literal decimal {nodo.valor}")
            elif nodo.tipo == "char":
                self._emitir(f"        mov     ax, {self._codigo_caracter(nodo)}")
            elif nodo.tipo == "boolean":
                self._emitir(
                    "        mov     ax, "
                    + ("1" if nodo.valor == "true" else "0")
                )
            elif nodo.tipo == "String":
                self._marcar_extendido()
                et = self._cadena(self._texto_cadena(nodo.valor))
                self._emitir(f"        mov     ax, offset {et}")
            else:
                self._emitir("        xor     ax, ax")
        elif etiqueta == "Identificador":
            simbolo = self._buscar(nodo.valor)
            if simbolo is None:
                self._marcar_extendido()
                self.contador += 1
                et_auto = f"v_{nodo.valor}_{self.contador}"
                self.escalares.append(et_auto)
                simbolo = ("var", et_auto, "int")
                self._declarar(nodo, nodo.valor, simbolo)
            if simbolo[0] == "arr":
                self._emitir(f"        mov     ax, offset {simbolo[1]}")
            else:
                self._emitir(f"        mov     ax, [{simbolo[1]}]")
        elif etiqueta == "Agrupacion":
            self._expresion(nodo.hijos[0])
        elif etiqueta == "Indice":
            self._cargar_lvalue(nodo)
        elif etiqueta == "Acceso":
            self._acceso(nodo)
        elif etiqueta == "Operacion":
            self._operacion(nodo)
        elif etiqueta == "Unario":
            self._unario(nodo)
        elif etiqueta == "Postfijo":
            self._unario_incdec(nodo.hijos[0], nodo.valor)
        elif etiqueta == "Asignacion":
            self._asignacion(nodo)
        elif etiqueta == "Llamada":
            self._llamada(nodo)
        elif etiqueta == "Nuevo":
            self._marcar_extendido()
            tipo_obj = nodo.valor or "Objeto"
            self._emitir(f"        ; new {tipo_obj}()")
            for arg in reversed(nodo.hijos):
                self._expresion(arg)
                self._emitir("        push    ax")
            if tipo_obj == "Scanner":
                self.usa_scanner = True
                self._emitir("        mov     ax, offset buf_entrada")
            else:
                self._emitir(f"        call    {tipo_obj}")
            if nodo.hijos and tipo_obj != "Scanner":
                self._emitir(f"        add     sp, {len(nodo.hijos) * 2}")
        elif etiqueta == "ListaInicializacion":
            self._marcar_extendido()
            self._emitir("        xor     ax, ax")
        else:
            self._marcar_extendido()
            self._emitir(f"        xor     ax, ax ; {etiqueta}")

    def _acceso(self, nodo):
        base = nodo.hijos[0]
        if nodo.valor == "length" and base.etiqueta == "Identificador":
            simbolo = self._buscar(base.valor)
            if simbolo and simbolo[0] == "arr":
                self._emitir(f"        mov     ax, {simbolo[2]}")
                return
        self._marcar_extendido()
        simbolo = self._buscar(nodo.valor)
        if simbolo is not None:
            self._emitir(f"        mov     ax, [{simbolo[1]}] ; .{nodo.valor}")
        else:
            self._emitir(f"        xor     ax, ax ; .{nodo.valor}")

    def _cargar_lvalue(self, nodo):
        if nodo.etiqueta == "Identificador":
            simbolo = self._buscar(nodo.valor)
            if simbolo is None:
                self._marcar_extendido()
                self.contador += 1
                et_auto = f"v_{nodo.valor}_{self.contador}"
                self.escalares.append(et_auto)
                simbolo = ("var", et_auto, "int")
                self._declarar(nodo, nodo.valor, simbolo)
            self._emitir(f"        mov     ax, [{simbolo[1]}]")
            return
        if nodo.etiqueta == "Indice":
            base, indice = nodo.hijos
            simbolo = self._buscar(base.valor) if base.etiqueta == "Identificador" else None
            if simbolo is None or simbolo[0] != "arr":
                self._marcar_extendido()
                self._emitir("        xor     ax, ax")
                return
            self._expresion(indice)
            self._emitir("        mov     bx, ax")
            self._emitir("        shl     bx, 1")
            self._emitir(f"        mov     ax, {simbolo[1]}[bx]")
            return
        if nodo.etiqueta == "Acceso":
            self._acceso(nodo)
            return
        self._marcar_extendido()
        self._emitir("        xor     ax, ax")

    def _guardar(self, nodo):
        if nodo.etiqueta == "Identificador":
            simbolo = self._buscar(nodo.valor)
            if simbolo is None:
                self._marcar_extendido()
                self.contador += 1
                et_auto = f"v_{nodo.valor}_{self.contador}"
                self.escalares.append(et_auto)
                simbolo = ("var", et_auto, "int")
                self._declarar(nodo, nodo.valor, simbolo)
            self._emitir(f"        mov     [{simbolo[1]}], ax")
            return
        if nodo.etiqueta == "Indice":
            base, indice = nodo.hijos
            simbolo = self._buscar(base.valor) if base.etiqueta == "Identificador" else None
            if simbolo is None or simbolo[0] != "arr":
                self._marcar_extendido()
                return
            self._emitir("        push    ax")
            self._expresion(indice)
            self._emitir("        mov     bx, ax")
            self._emitir("        shl     bx, 1")
            self._emitir("        pop     ax")
            self._emitir(f"        mov     {simbolo[1]}[bx], ax")
            return
        if nodo.etiqueta == "Acceso":
            self._marcar_extendido()
            simbolo = self._buscar(nodo.valor)
            if simbolo is not None:
                self._emitir(f"        mov     [{simbolo[1]}], ax ; .{nodo.valor}")
            return
        self._marcar_extendido()

    def _asignacion(self, nodo):
        destino = nodo.hijos[0]
        valor = nodo.hijos[1]
        if nodo.valor == "=":
            self._expresion(valor)
            self._guardar(destino)
            return
        operaciones = {"+=": "add", "-=": "sub", "*=": "imul"}
        if nodo.valor not in operaciones:
            self._marcar_extendido()
            self._cargar_lvalue(destino)
            self._emitir("        push    ax")
            self._expresion(valor)
            self._emitir("        mov     bx, ax")
            self._emitir("        pop     ax")
            self._emitir("        cwd")
            self._emitir("        idiv    bx")
            if nodo.valor == "%=":
                self._emitir("        mov     ax, dx")
            self._guardar(destino)
            return
        self._cargar_lvalue(destino)
        self._emitir("        push    ax")
        self._expresion(valor)
        self._emitir("        mov     bx, ax")
        self._emitir("        pop     ax")
        if nodo.valor == "*=":
            self._emitir("        imul    bx")
        else:
            self._emitir(f"        {operaciones[nodo.valor]}     ax, bx")
        self._guardar(destino)

    def _operacion(self, nodo):
        izquierda, derecha = nodo.hijos
        operador = nodo.valor
        if operador == "+" and self._contiene_cadena(nodo):
            self._marcar_extendido()
            self._expresion(izquierda)
            self._emitir("        push    ax")
            self._expresion(derecha)
            self._emitir("        mov     bx, ax")
            self._emitir("        pop     ax ; concatenacion String")
            return

        self._expresion(izquierda)
        self._emitir("        push    ax")
        self._expresion(derecha)
        self._emitir("        mov     bx, ax")
        self._emitir("        pop     ax")

        if operador == "+":
            self._emitir("        add     ax, bx")
        elif operador == "-":
            self._emitir("        sub     ax, bx")
        elif operador == "*":
            self._emitir("        imul    bx")
        elif operador in ("/", "%"):
            self._emitir("        cwd")
            self._emitir("        idiv    bx")
            if operador == "%":
                self._emitir("        mov     ax, dx")
        elif operador in ("<", ">", "<=", ">=", "==", "!="):
            saltos = {"<": "jl", ">": "jg", "<=": "jle", ">=": "jge",
                      "==": "je", "!=": "jne"}
            etiqueta_verdadero = self._etiqueta()
            etiqueta_fin = self._etiqueta()
            self._emitir("        cmp     ax, bx")
            self._emitir(f"        {saltos[operador]}      {etiqueta_verdadero}")
            self._emitir("        xor     ax, ax")
            self._emitir(f"        jmp     {etiqueta_fin}")
            self._emitir(f"{etiqueta_verdadero}:")
            self._emitir("        mov     ax, 1")
            self._emitir(f"{etiqueta_fin}:")
        elif operador in ("&&", "||"):
            etiqueta_fin = self._etiqueta()
            if operador == "&&":
                etiqueta_falso = self._etiqueta()
                self._emitir("        test    ax, ax")
                self._emitir(f"        jz      {etiqueta_falso}")
                self._emitir("        test    bx, bx")
                self._emitir(f"        jz      {etiqueta_falso}")
                self._emitir("        mov     ax, 1")
                self._emitir(f"        jmp     {etiqueta_fin}")
                self._emitir(f"{etiqueta_falso}:")
                self._emitir("        xor     ax, ax")
            else:
                etiqueta_verdadero = self._etiqueta()
                self._emitir("        test    ax, ax")
                self._emitir(f"        jnz     {etiqueta_verdadero}")
                self._emitir("        test    bx, bx")
                self._emitir(f"        jnz     {etiqueta_verdadero}")
                self._emitir("        xor     ax, ax")
                self._emitir(f"        jmp     {etiqueta_fin}")
                self._emitir(f"{etiqueta_verdadero}:")
                self._emitir("        mov     ax, 1")
            self._emitir(f"{etiqueta_fin}:")
        else:
            self._marcar_extendido()

    def _unario(self, nodo):
        operador = nodo.valor
        if operador in ("++", "--"):
            self._unario_incdec(nodo.hijos[0], operador)
            return
        self._expresion(nodo.hijos[0])
        if operador == "-":
            self._emitir("        neg     ax")
        elif operador == "~":
            self._emitir("        not     ax")
        elif operador == "+":
            pass
        elif operador == "!":
            etiqueta_verdadero = self._etiqueta()
            etiqueta_fin = self._etiqueta()
            self._emitir("        cmp     ax, 0")
            self._emitir(f"        je      {etiqueta_verdadero}")
            self._emitir("        xor     ax, ax")
            self._emitir(f"        jmp     {etiqueta_fin}")
            self._emitir(f"{etiqueta_verdadero}:")
            self._emitir("        mov     ax, 1")
            self._emitir(f"{etiqueta_fin}:")
        else:
            self._marcar_extendido()

    def _unario_incdec(self, destino, operador):
        self._cargar_lvalue(destino)
        self._emitir("        inc     ax" if operador == "++" else "        dec     ax")
        self._guardar(destino)

    # ------------------------------------------------------------------
    # Llamadas (impresion, Scanner, metodos de usuario)
    # ------------------------------------------------------------------
    def _nombre_llamada(self, callee):
        partes = []
        while callee.etiqueta == "Acceso":
            partes.append(callee.valor)
            callee = callee.hijos[0]
        if callee.etiqueta == "Identificador":
            partes.append(callee.valor)
        return ".".join(reversed(partes))

    def _llamada(self, nodo):
        nombre = self._nombre_llamada(nodo.hijos[0])
        argumentos = nodo.hijos[1:]
        permitidas_salida = ("System.out.print", "System.out.println", "print", "println")
        if nombre in permitidas_salida:
            con_salto = nombre.endswith("println")
            if not argumentos:
                if con_salto:
                    self._emitir("        call    rt_nueva_linea")
                return
            for arg in argumentos:
                partes = self._partes_concatenacion(arg)
                if partes is not None:
                    for parte in partes:
                        self._imprimir_parte(parte)
                else:
                    self._imprimir_parte(arg)
            if con_salto:
                self._emitir("        call    rt_nueva_linea")
            return

        # Llamada extendida (Scanner, metodos de clase/objeto, Math, etc.)
        self._marcar_extendido()
        metodo_corto = nombre.split(".")[-1]
        if metodo_corto in ("nextInt", "nextDouble", "nextFloat", "nextLong", "nextBoolean", "nextLine", "next"):
            self.usa_scanner = True
            self._emitir(f"        ; llamada {nombre}()")
            self._emitir("        call    rt_leer_entrada")
            return

        self._emitir(f"        ; llamada a metodo {nombre}()")
        for arg in reversed(argumentos):
            self._expresion(arg)
            self._emitir("        push    ax")
        self._emitir(f"        call    {metodo_corto}")
        if argumentos:
            self._emitir(f"        add     sp, {len(argumentos) * 2}")

    def _partes_concatenacion(self, nodo):
        if not self._contiene_cadena(nodo):
            return None
        partes = []
        self._aplanar_suma(nodo, partes)
        return partes

    def _contiene_cadena(self, nodo):
        if nodo.etiqueta == "Literal":
            return nodo.tipo == "String"
        if nodo.etiqueta == "Agrupacion":
            return self._contiene_cadena(nodo.hijos[0])
        if nodo.etiqueta == "Operacion" and nodo.valor == "+":
            return (self._contiene_cadena(nodo.hijos[0])
                    or self._contiene_cadena(nodo.hijos[1]))
        if nodo.etiqueta == "Identificador":
            sim = self._buscar(nodo.valor)
            if sim and sim[2] == "String":
                return True
        return False

    def _aplanar_suma(self, nodo, partes):
        while nodo.etiqueta == "Agrupacion":
            nodo = nodo.hijos[0]
        if (nodo.etiqueta == "Operacion" and nodo.valor == "+"
                and self._contiene_cadena(nodo)):
            self._aplanar_suma(nodo.hijos[0], partes)
            self._aplanar_suma(nodo.hijos[1], partes)
        else:
            partes.append(nodo)

    def _imprimir_parte(self, nodo):
        if nodo.etiqueta == "Literal" and nodo.tipo == "String":
            self._imprimir_cadena(self._texto_cadena(nodo.valor))
            return
        tipo = self._tipo_simple(nodo)
        if tipo == "char":
            self._expresion(nodo)
            self._emitir("        mov     dl, al")
            self._emitir("        mov     ah, 02h")
            self._emitir("        int     21h")
        elif tipo == "boolean":
            self._imprimir_booleano(nodo)
        elif tipo == "String":
            self._expresion(nodo)
            self._emitir("        mov     dx, ax")
            self._emitir("        mov     ah, 09h")
            self._emitir("        int     21h")
        else:
            self._expresion(nodo)
            self._emitir("        call    rt_imprimir_numero")

    def _imprimir_cadena(self, texto):
        piezas = texto.split("$")
        for indice, pieza in enumerate(piezas):
            if pieza:
                etiqueta = self._cadena(pieza)
                self._emitir(f"        mov     dx, offset {etiqueta}")
                self._emitir("        mov     ah, 09h")
                self._emitir("        int     21h")
            if indice < len(piezas) - 1:
                self._emitir("        mov     dl, '$'")
                self._emitir("        mov     ah, 02h")
                self._emitir("        int     21h")

    def _imprimir_booleano(self, nodo):
        self._expresion(nodo)
        etiqueta_falso = self._etiqueta()
        etiqueta_fin = self._etiqueta()
        self._emitir("        test    ax, ax")
        self._emitir(f"        jz      {etiqueta_falso}")
        self._emitir(f"        mov     dx, offset {self._cadena('true')}")
        self._emitir(f"        jmp     {etiqueta_fin}")
        self._emitir(f"{etiqueta_falso}:")
        self._emitir(f"        mov     dx, offset {self._cadena('false')}")
        self._emitir(f"{etiqueta_fin}:")
        self._emitir("        mov     ah, 09h")
        self._emitir("        int     21h")

    def _texto_cadena(self, valor):
        if len(valor) >= 2 and valor.startswith('"') and valor.endswith('"'):
            valor = valor[1:-1]
        escapes = {"n": "\n", "t": "\t", "r": "\r", '"': '"',
                   "\\": "\\", "'": "'"}
        salida = []
        i = 0
        while i < len(valor):
            caracter = valor[i]
            if caracter == "\\" and i + 1 < len(valor):
                salida.append(escapes.get(valor[i + 1], valor[i + 1]))
                i += 2
            else:
                salida.append(caracter)
                i += 1
        return "".join(salida)
