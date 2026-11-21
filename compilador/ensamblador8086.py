"""Ensamblador interno de 8086 para generar ejecutables .COM."""

import re


# ======================================================================
# ENSAMBLADOR INTERNO 8086 (.COM)
# ======================================================================

class ErrorEnsamblado(Exception):
    def __init__(self, linea, mensaje):
        super().__init__(mensaje)
        self.linea = linea or 0
        self.mensaje = mensaje


class EnsambladorInterno8086:
    """Ensamblador de respaldo, escrito en Python puro."""

    REG16 = {"ax": 0, "cx": 1, "dx": 2, "bx": 3,
             "sp": 4, "bp": 5, "si": 6, "di": 7}
    REG8 = {"al": 0, "cl": 1, "dl": 2, "bl": 3,
            "ah": 4, "ch": 5, "dh": 6, "bh": 7}
    SREG = {"es": 0, "cs": 1, "ss": 2, "ds": 3}
    BASE_RM = {"bx": 7, "si": 4, "di": 5, "bp": 6}
    CONDICIONALES = {
        "jo": 0x70, "jno": 0x71, "jb": 0x72, "jc": 0x72, "jnae": 0x72,
        "jae": 0x73, "jnb": 0x73, "jnc": 0x73, "je": 0x74, "jz": 0x74,
        "jne": 0x75, "jnz": 0x75, "jbe": 0x76, "jna": 0x76,
        "ja": 0x77, "jnbe": 0x77, "js": 0x78, "jns": 0x79,
        "jp": 0x7A, "jpe": 0x7A, "jnp": 0x7B, "jpo": 0x7B,
        "jl": 0x7C, "jnge": 0x7C, "jge": 0x7D, "jnl": 0x7D,
        "jle": 0x7E, "jng": 0x7E, "jg": 0x7F, "jnle": 0x7F,
    }
    INVERSOS = {
        0x70: 0x71, 0x71: 0x70, 0x72: 0x73, 0x73: 0x72,
        0x74: 0x75, 0x75: 0x74, 0x76: 0x77, 0x77: 0x76,
        0x78: 0x79, 0x79: 0x78, 0x7A: 0x7B, 0x7B: 0x7A,
        0x7C: 0x7D, 0x7D: 0x7C, 0x7E: 0x7F, 0x7F: 0x7E,
    }

    def ensamblar(self, texto):
        items = self._analizar(texto)
        expandidas = set()
        for _ in range(len(items) + 2):
            direcciones, etiquetas = self._disposicion(items, expandidas)
            nuevas = set()
            for indice, item in enumerate(items):
                if item[0] != "ins" or indice in expandidas:
                    continue
                if item[1] not in self.CONDICIONALES:
                    continue
                destino = self._etiqueta(etiquetas, item[2][0], item[3])
                relativo = destino - (direcciones[indice] + 2)
                if not -128 <= relativo <= 127:
                    nuevas.add(indice)
            if not nuevas:
                break
            expandidas |= nuevas
        else:
            raise ErrorEnsamblado(0, "No se pudieron resolver los saltos")

        direcciones, etiquetas = self._disposicion(items, expandidas)
        datos = bytearray()
        for indice, item in enumerate(items):
            if item[0] == "data":
                datos.extend(item[1])
            elif item[0] == "ins":
                datos.extend(self._codificar(
                    item[1], item[2], item[3], etiquetas,
                    direcciones[indice], indice in expandidas))
        return bytes(datos)

    def _analizar(self, texto):
        items = []
        numero_linea = 0
        for linea in texto.splitlines():
            numero_linea += 1
            limpia = self._sin_comentario(linea).strip()
            if not limpia:
                continue
            while True:
                coincidencia = re.match(
                    r"^([A-Za-z_]\w*):\s*(.*)$", limpia)
                if not coincidencia:
                    break
                items.append(("label", coincidencia.group(1)))
                limpia = coincidencia.group(2).strip()
                if not limpia:
                    break
            if not limpia:
                continue
            partes = limpia.split(None, 1)
            mnem = partes[0].lower()
            resto = partes[1].strip() if len(partes) > 1 else ""
            if (resto and mnem not in ("db", "dw")
                    and resto.split(None, 1)[0].lower() in ("db", "dw")):
                items.append(("label", partes[0]))
                partes = resto.split(None, 1)
                mnem = partes[0].lower()
                resto = partes[1].strip() if len(partes) > 1 else ""
            if mnem in (".model", ".code", ".stack", ".data", "end"):
                continue
            if mnem == "org":
                if self._numero(resto, numero_linea) != 0x100:
                    raise ErrorEnsamblado(
                        numero_linea, "Solo se soporta 'org 100h'")
                continue
            if mnem in ("db", "dw"):
                items.append(("data", self._datos(mnem, resto, numero_linea)))
                continue
            operandos = [self._operando(pieza, numero_linea)
                         for pieza in self._dividir(resto)]
            items.append(("ins", mnem, operandos, numero_linea))
        return items

    @staticmethod
    def _sin_comentario(linea):
        fuera = []
        comilla = None
        for caracter in linea:
            if comilla is not None:
                fuera.append(caracter)
                if caracter == comilla:
                    comilla = None
            elif caracter in "\"'":
                comilla = caracter
                fuera.append(caracter)
            elif caracter == ";":
                break
            else:
                fuera.append(caracter)
        return "".join(fuera)

    @staticmethod
    def _dividir(texto):
        partes = []
        actual = []
        comilla = None
        corchetes = 0
        for caracter in texto:
            if comilla is not None:
                actual.append(caracter)
                if caracter == comilla:
                    comilla = None
                continue
            if caracter in "\"'":
                comilla = caracter
                actual.append(caracter)
            elif caracter == "[":
                corchetes += 1
                actual.append(caracter)
            elif caracter == "]":
                corchetes -= 1
                actual.append(caracter)
            elif caracter == "," and corchetes == 0:
                partes.append("".join(actual).strip())
                actual = []
            else:
                actual.append(caracter)
        partes.append("".join(actual).strip())
        return [parte for parte in partes if parte]

    def _numero(self, texto, linea):
        valor = texto.strip()
        if len(valor) >= 2 and valor[0] == "'" and valor[-1] == "'":
            interior = valor[1:-1]
            if len(interior) != 1:
                raise ErrorEnsamblado(
                    linea, f"Caracter no valido: {texto}")
            return ord(interior)
        try:
            if valor.lower().endswith("h"):
                return int(valor[:-1], 16)
            if valor.lower().startswith("0x"):
                return int(valor, 16)
            return int(valor, 10)
        except ValueError:
            raise ErrorEnsamblado(linea, f"Numero no valido: {texto}")

    def _datos(self, mnem, texto, linea):
        datos = bytearray()
        for pieza in self._dividir(texto):
            if (len(pieza) >= 2 and pieza.startswith('"')
                    and pieza.endswith('"')):
                for caracter in pieza[1:-1]:
                    codigo = ord(caracter)
                    if codigo > 255:
                        raise ErrorEnsamblado(
                            linea, f"Caracter no soportado: {caracter!r}")
                    datos.append(codigo)
                continue
            valor = self._numero(pieza, linea)
            if mnem == "db":
                datos.append(valor & 0xFF)
            else:
                datos.extend((valor & 0xFF, (valor >> 8) & 0xFF))
        return bytes(datos)

    def _operando(self, texto, linea):
        valor = texto.strip()
        bajo = valor.lower()
        if bajo in self.REG16:
            return ("r16", self.REG16[bajo])
        if bajo in self.REG8:
            return ("r8", self.REG8[bajo])
        if bajo in self.SREG:
            return ("sreg", self.SREG[bajo])
        if bajo.startswith("offset "):
            nombre = valor[7:].strip()
            if not re.fullmatch(r"[A-Za-z_]\w*", nombre):
                raise ErrorEnsamblado(linea, f"Etiqueta no valida: {nombre}")
            return ("offset", nombre)
        if valor.startswith("["):
            return self._memoria(valor, linea)
        coincidencia = re.fullmatch(r"([A-Za-z_]\w*)\s*\[(.+)\]", valor)
        if coincidencia:
            base = coincidencia.group(2).strip().lower()
            if base not in self.BASE_RM:
                raise ErrorEnsamblado(
                    linea, f"Registro base no soportado: {base}")
            return ("mem", coincidencia.group(1), base)
        if re.fullmatch(r"[A-Za-z_]\w*", valor):
            return ("label", valor)
        return ("imm", self._numero(valor, linea))

    def _memoria(self, texto, linea):
        interior = texto[1:-1].strip()
        if re.fullmatch(r"[A-Za-z_]\w*", interior):
            return ("mem", interior, None)
        coincidencia = re.fullmatch(
            r"([A-Za-z_]\w*)\s*\+\s*(bx|si|di|bp)",
            interior, re.IGNORECASE)
        if coincidencia:
            return ("mem", coincidencia.group(1),
                    coincidencia.group(2).lower())
        coincidencia = re.fullmatch(r"(bx|si|di|bp)", interior,
                                    re.IGNORECASE)
        if coincidencia:
            return ("mem", None, coincidencia.group(1).lower())
        raise ErrorEnsamblado(linea, f"Direccion no soportada: {texto}")

    def _etiqueta(self, etiquetas, operando, linea):
        if operando[0] != "label":
            raise ErrorEnsamblado(linea, "Se esperaba una etiqueta")
        if etiquetas is None:
            return 0
        if operando[1] not in etiquetas:
            raise ErrorEnsamblado(
                linea, f"Etiqueta no definida: {operando[1]}")
        return etiquetas[operando[1]]

    def _disposicion(self, items, expandidas):
        direccion = 0x100
        direcciones = []
        etiquetas = {}
        for indice, item in enumerate(items):
            direcciones.append(direccion)
            if item[0] == "label":
                etiquetas[item[1]] = direccion
            elif item[0] == "data":
                direccion += len(item[1])
            elif item[0] == "ins":
                direccion += len(self._codificar(
                    item[1], item[2], item[3], None, 0,
                    indice in expandidas))
        return direcciones, etiquetas

    @staticmethod
    def _modrm(mod, reg, rm):
        return bytes([((mod & 3) << 6) | ((reg & 7) << 3) | (rm & 7)])

    @staticmethod
    def _inm16(valor):
        return (valor & 0xFFFF).to_bytes(2, "little")

    def _mem_campos(self, operando, etiquetas, linea):
        _, nombre, base = operando
        desplazamiento = 0
        if nombre is not None:
            if etiquetas is None:
                pass
            elif nombre not in etiquetas:
                raise ErrorEnsamblado(
                    linea, f"Etiqueta no definida: {nombre}")
            else:
                desplazamiento = etiquetas[nombre]
        if base is None:
            return 0, 6, self._inm16(desplazamiento)
        return 2, self.BASE_RM[base], self._inm16(desplazamiento)

    def _dir(self, nombre, etiquetas, linea):
        if etiquetas is None:
            return b"\x00\x00"
        if nombre not in etiquetas:
            raise ErrorEnsamblado(linea, f"Etiqueta no definida: {nombre}")
        return self._inm16(etiquetas[nombre])

    @staticmethod
    def _error(linea, mensaje):
        raise ErrorEnsamblado(linea, mensaje)

    def _codificar(self, mnem, ops, linea, etiquetas, direccion, expandida):
        if mnem == "mov":
            if len(ops) != 2:
                self._error(linea, "'mov' necesita dos operandos")
            destino, origen = ops
            if destino[0] == "r16":
                if origen[0] == "imm":
                    return bytes([0xB8 + destino[1]]) + self._inm16(origen[1])
                if origen[0] == "offset":
                    return (bytes([0xB8 + destino[1]])
                            + self._dir(origen[1], etiquetas, linea))
                if origen[0] == "r16":
                    return bytes([0x89]) + self._modrm(3, origen[1], destino[1])
                if origen[0] == "sreg":
                    return bytes([0x8C]) + self._modrm(3, origen[1], destino[1])
                if origen[0] == "mem":
                    mod, rm, disp = self._mem_campos(origen, etiquetas, linea)
                    if destino[1] == 0 and mod == 0:
                        return bytes([0xA1]) + disp
                    return (bytes([0x8B]) + self._modrm(mod, destino[1], rm)
                            + disp)
            elif destino[0] == "r8":
                if origen[0] == "imm":
                    return bytes([0xB0 + destino[1], origen[1] & 0xFF])
                if origen[0] == "r8":
                    return bytes([0x88]) + self._modrm(3, origen[1], destino[1])
            elif destino[0] == "sreg":
                if origen[0] == "r16":
                    return bytes([0x8E]) + self._modrm(3, origen[1], destino[1])
            elif destino[0] == "mem":
                mod, rm, disp = self._mem_campos(destino, etiquetas, linea)
                if origen[0] == "r16":
                    if origen[1] == 0 and mod == 0:
                        return bytes([0xA3]) + disp
                    return (bytes([0x89]) + self._modrm(mod, origen[1], rm)
                            + disp)
                if origen[0] == "imm":
                    return (bytes([0xC7]) + self._modrm(mod, 0, rm) + disp
                            + self._inm16(origen[1]))
            self._error(linea, f"'mov' no soportado: {mnem} {ops}")

        grupo = {
            "add": (0x01, 0x03, 0), "or": (0x09, 0x0B, 1),
            "and": (0x21, 0x23, 4), "sub": (0x29, 0x2B, 5),
            "xor": (0x31, 0x33, 6), "cmp": (0x39, 0x3B, 7),
            "test": (0x85, 0x85, 0),
        }
        if mnem in grupo:
            if len(ops) != 2:
                self._error(linea, f"'{mnem}' necesita dos operandos")
            rm_r, r_rm, extension = grupo[mnem]
            destino, origen = ops
            if destino[0] == "r16" and origen[0] == "r16":
                return (bytes([r_rm])
                        + self._modrm(3, destino[1], origen[1]))
            if destino[0] == "r8" and origen[0] == "imm":
                return bytes([0x80]) + self._modrm(3, extension, destino[1]) \
                    + bytes([origen[1] & 0xFF])
            if destino[0] == "r16" and origen[0] == "imm":
                if mnem == "cmp":
                    return bytes([0x3D]) + self._inm16(origen[1])
                if mnem == "test":
                    return (bytes([0xF7, 0xC0 | destino[1]])
                            + self._inm16(origen[1]))
                return (bytes([0x81])
                        + self._modrm(3, extension, destino[1])
                        + self._inm16(origen[1]))
            if destino[0] == "mem" and origen[0] == "imm":
                mod, rm, disp = self._mem_campos(destino, etiquetas, linea)
                return (bytes([0x81]) + self._modrm(mod, extension, rm)
                        + disp + self._inm16(origen[1]))
            self._error(linea, f"'{mnem}' no soportado: {ops}")

        if mnem in ("inc", "dec"):
            if len(ops) == 1 and ops[0][0] == "r16":
                return bytes([(0x40 if mnem == "inc" else 0x48) + ops[0][1]])
            self._error(linea, f"'{mnem}' no soportado")

        if mnem in ("push", "pop"):
            if len(ops) == 1 and ops[0][0] == "r16":
                return bytes([(0x50 if mnem == "push" else 0x58) + ops[0][1]])
            self._error(linea, f"'{mnem}' no soportado")

        extensiones = {"not": 2, "neg": 3, "mul": 4, "imul": 5,
                       "div": 6, "idiv": 7}
        if mnem in extensiones:
            if len(ops) == 1 and ops[0][0] == "r16":
                return bytes([0xF7]) + self._modrm(3, extensiones[mnem],
                                                  ops[0][1])
            self._error(linea, f"'{mnem}' no soportado")

        if mnem == "cwd":
            return b"\x99"
        if mnem == "nop":
            return b"\x90"
        if mnem == "ret":
            return b"\xC3"

        if mnem in ("shl", "sal", "shr", "sar"):
            desplazamientos = {"shl": 4, "sal": 4, "shr": 5, "sar": 7}
            if len(ops) != 2 or ops[0][0] != "r16":
                self._error(linea, f"'{mnem}' no soportado")
            extension = desplazamientos[mnem]
            if ops[1][0] == "imm" and ops[1][1] == 1:
                return bytes([0xD1]) + self._modrm(3, extension, ops[0][1])
            if ops[1][0] == "r8" and ops[1][1] == 1:
                return bytes([0xD3]) + self._modrm(3, extension, ops[0][1])
            self._error(linea, f"'{mnem}' no soportado: {ops}")

        if mnem == "jmp":
            destino = self._etiqueta(etiquetas, ops[0], linea)
            return bytes([0xE9]) + self._inm16(destino - (direccion + 3))
        if mnem in self.CONDICIONALES:
            destino = self._etiqueta(etiquetas, ops[0], linea)
            opcode = self.CONDICIONALES[mnem]
            if not expandida:
                relativo = destino - (direccion + 2)
                if etiquetas is not None and not -128 <= relativo <= 127:
                    self._error(linea, "Salto corto fuera de rango")
                return bytes([opcode, relativo & 0xFF])
            relativo = destino - (direccion + 5)
            return (bytes([self.INVERSOS[opcode], 0x03, 0xE9])
                    + self._inm16(relativo))
        if mnem == "loop":
            destino = self._etiqueta(etiquetas, ops[0], linea)
            relativo = destino - (direccion + 2)
            if etiquetas is not None and not -128 <= relativo <= 127:
                self._error(linea, "'loop' fuera de rango")
            return bytes([0xE2, relativo & 0xFF])
        if mnem == "call":
            destino = self._etiqueta(etiquetas, ops[0], linea)
            return bytes([0xE8]) + self._inm16(destino - (direccion + 3))
        if mnem == "int":
            if len(ops) != 1 or ops[0][0] != "imm":
                self._error(linea, "'int' necesita un numero")
            return bytes([0xCD, ops[0][1] & 0xFF])

        self._error(linea, f"Instruccion no soportada: {mnem}")
