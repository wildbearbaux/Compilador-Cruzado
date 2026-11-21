"""Interprete de 16 bits en Python puro para ejecutar los .COM generados."""


class ErrorEjecucion(Exception):
    pass


class Interprete8086:
    """Interprete de 16 bits en Python puro, para el .COM generado."""

    MAX_PASOS = 5_000_000
    NOMBRES16 = {0: "ax", 1: "cx", 2: "dx", 3: "bx",
                 4: "sp", 5: "bp", 6: "si", 7: "di"}
    NOMBRES8 = {0: ("ax", 0), 1: ("cx", 0), 2: ("dx", 0), 3: ("bx", 0),
                4: ("ax", 8), 5: ("cx", 8), 6: ("dx", 8), 7: ("bx", 8)}
    NOMBRES_SREG = {0: "es", 1: "cs", 2: "ss", 3: "ds"}

    def __init__(self, ruta_com):
        self.ruta = ruta_com
        self.memoria = bytearray(0x100000)
        self.regs = {nombre: 0 for nombre in
                     ("ax", "cx", "dx", "bx", "sp", "bp", "si", "di")}
        self.segmentos = {"cs": 0, "ds": 0, "es": 0, "ss": 0}
        self.ip = 0
        self.zf = False
        self.sf = False
        self.cf = False
        self.ov = False
        self.salida = []
        self.pasos = 0
        self.terminado = False

    def ejecutar(self):
        with open(self.ruta, "rb") as archivo:
            codigo = archivo.read()
        if len(codigo) > 0xFF00:
            raise ErrorEjecucion("El .COM es demasiado grande")
        segmento = 0x1000
        base = segmento << 4
        self.memoria[base + 0x100:base + 0x100 + len(codigo)] = codigo
        for nombre in self.segmentos:
            self.segmentos[nombre] = segmento
        self.regs["sp"] = 0xFFFE
        self.ip = 0x100
        while not self.terminado:
            if self.pasos >= self.MAX_PASOS:
                raise ErrorEjecucion("Se supero el limite de instrucciones")
            self.pasos += 1
            self._paso()
        return "".join(self.salida)

    def _leer8(self, segmento, desplazamiento):
        return self.memoria[(segmento << 4)
                            + (desplazamiento & 0xFFFF)]

    def _leer16(self, segmento, desplazamiento):
        base = (segmento << 4)
        bajo = self.memoria[base + (desplazamiento & 0xFFFF)]
        alto = self.memoria[base + ((desplazamiento + 1) & 0xFFFF)]
        return bajo | (alto << 8)

    def _escribir8(self, segmento, desplazamiento, valor):
        self.memoria[(segmento << 4) + (desplazamiento & 0xFFFF)] = valor & 0xFF

    def _escribir16(self, segmento, desplazamiento, valor):
        base = (segmento << 4)
        self.memoria[base + (desplazamiento & 0xFFFF)] = valor & 0xFF
        self.memoria[base + ((desplazamiento + 1) & 0xFFFF)] = (valor >> 8) & 0xFF

    def _fetch8(self):
        valor = self._leer8(self.segmentos["cs"], self.ip)
        self.ip = (self.ip + 1) & 0xFFFF
        return valor

    def _fetch16(self):
        valor = self._leer16(self.segmentos["cs"], self.ip)
        self.ip = (self.ip + 2) & 0xFFFF
        return valor

    def _reg16(self, codigo):
        return self.regs[self.NOMBRES16[codigo]]

    def _set_reg16(self, codigo, valor):
        self.regs[self.NOMBRES16[codigo]] = valor & 0xFFFF

    def _reg8(self, codigo):
        registro, desplazamiento = self.NOMBRES8[codigo]
        return (self.regs[registro] >> desplazamiento) & 0xFF

    def _set_reg8(self, codigo, valor):
        registro, desplazamiento = self.NOMBRES8[codigo]
        actual = self.regs[registro]
        if desplazamiento == 0:
            self.regs[registro] = (actual & 0xFF00) | (valor & 0xFF)
        else:
            self.regs[registro] = (actual & 0x00FF) | ((valor & 0xFF) << 8)

    def _modrm(self):
        byte = self._fetch8()
        mod = byte >> 6
        reg = (byte >> 3) & 7
        rm = byte & 7
        if mod == 3:
            return mod, reg, rm, None
        if mod == 0 and rm == 6:
            return mod, reg, rm, self._fetch16()
        if mod == 1:
            desplazamiento = self._fetch8()
            if desplazamiento & 0x80:
                desplazamiento -= 0x100
        elif mod == 2:
            desplazamiento = self._fetch16()
        else:
            desplazamiento = 0
        return mod, reg, rm, desplazamiento

    def _direccion(self, mod, rm, desplazamiento):
        if mod == 0 and rm == 6:
            return self.segmentos["ds"], desplazamiento
        if rm == 7:
            return (self.segmentos["ds"],
                    (self.regs["bx"] + desplazamiento) & 0xFFFF)
        if rm == 4:
            return (self.segmentos["ds"],
                    (self.regs["si"] + desplazamiento) & 0xFFFF)
        if rm == 5:
            return (self.segmentos["ds"],
                    (self.regs["di"] + desplazamiento) & 0xFFFF)
        if rm == 6:
            return (self.segmentos["ss"],
                    (self.regs["bp"] + desplazamiento) & 0xFFFF)
        raise ErrorEjecucion("Direccion no soportada")

    def _leer_rm16(self, mod, rm, desplazamiento):
        if mod == 3:
            return self._reg16(rm)
        segmento, direccion = self._direccion(mod, rm, desplazamiento)
        return self._leer16(segmento, direccion)

    def _escribir_rm16(self, mod, rm, desplazamiento, valor):
        if mod == 3:
            self._set_reg16(rm, valor)
            return
        segmento, direccion = self._direccion(mod, rm, desplazamiento)
        self._escribir16(segmento, direccion, valor)

    def _leer_rm8(self, mod, rm, desplazamiento):
        if mod == 3:
            return self._reg8(rm)
        segmento, direccion = self._direccion(mod, rm, desplazamiento)
        return self._leer8(segmento, direccion)

    def _escribir_rm8(self, mod, rm, desplazamiento, valor):
        if mod == 3:
            self._set_reg8(rm, valor)
            return
        segmento, direccion = self._direccion(mod, rm, desplazamiento)
        self._escribir8(segmento, direccion, valor)

    def _push(self, valor):
        self.regs["sp"] = (self.regs["sp"] - 2) & 0xFFFF
        self._escribir16(self.segmentos["ss"], self.regs["sp"], valor)

    def _pop(self):
        valor = self._leer16(self.segmentos["ss"], self.regs["sp"])
        self.regs["sp"] = (self.regs["sp"] + 2) & 0xFFFF
        return valor

    @staticmethod
    def _con_signo(valor):
        return valor - 0x10000 if valor & 0x8000 else valor

    def _flags_suma(self, a, b, resultado, bits=16):
        mascara = (1 << bits) - 1
        signo = 1 << (bits - 1)
        resultado &= mascara
        self.zf = resultado == 0
        self.sf = bool(resultado & signo)
        self.cf = (a + b) > mascara
        self.ov = bool(((a ^ resultado) & (b ^ resultado) & signo))
        return resultado

    def _flags_resta(self, a, b, resultado, bits=16):
        mascara = (1 << bits) - 1
        signo = 1 << (bits - 1)
        resultado &= mascara
        self.zf = resultado == 0
        self.sf = bool(resultado & signo)
        self.cf = (a & mascara) < (b & mascara)
        self.ov = bool(((a ^ b) & (a ^ resultado) & signo))
        return resultado

    def _flags_logicos(self, resultado, bits=16):
        mascara = (1 << bits) - 1
        signo = 1 << (bits - 1)
        resultado &= mascara
        self.zf = resultado == 0
        self.sf = bool(resultado & signo)
        self.cf = False
        self.ov = False
        return resultado

    def _paso(self):
        op = self._fetch8()
        if op == 0x90:
            return
        if 0x40 <= op <= 0x47:
            self._inc_dec(op & 7, 1)
            return
        if 0x48 <= op <= 0x4F:
            self._inc_dec(op & 7, -1)
            return
        if 0x50 <= op <= 0x57:
            self._push(self._reg16(op & 7))
            return
        if 0x58 <= op <= 0x5F:
            self._set_reg16(op & 7, self._pop())
            return
        if 0x70 <= op <= 0x7F:
            relativo = self._fetch8()
            if relativo & 0x80:
                relativo -= 0x100
            if self._condicion(op):
                self.ip = (self.ip + relativo) & 0xFFFF
            return
        if op in (0x01, 0x03, 0x09, 0x0B, 0x21, 0x23,
                  0x29, 0x2B, 0x31, 0x33, 0x39, 0x3B, 0x85):
            self._aritmetica(op)
            return
        if op in (0x04, 0x05, 0x0C, 0x0D, 0x24, 0x25,
                  0x2C, 0x2D, 0x34, 0x35, 0x3C, 0x3D,
                  0xA8, 0xA9):
            self._acumulador_inmediato(op)
            return
        if op in (0x80, 0x81, 0x82, 0x83):
            self._aritmetica_inmediata(op)
            return
        if op in (0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8E):
            self._mov_registros(op)
            return
        if op in (0xA0, 0xA1, 0xA2, 0xA3):
            self._mov_moffs(op)
            return
        if 0xB0 <= op <= 0xB7:
            self._set_reg8(op & 7, self._fetch8())
            return
        if 0xB8 <= op <= 0xBF:
            self._set_reg16(op & 7, self._fetch16())
            return
        if op == 0xC3:
            self.ip = self._pop()
            return
        if op in (0xC6, 0xC7):
            self._mov_inmediato(op)
            return
        if op == 0xCD:
            self._interrupcion(self._fetch8())
            return
        if op in (0xD0, 0xD1, 0xD2, 0xD3):
            self._desplazar(op)
            return
        if op == 0xE2:
            relativo = self._fetch8()
            if relativo & 0x80:
                relativo -= 0x100
            self.regs["cx"] = (self.regs["cx"] - 1) & 0xFFFF
            if self.regs["cx"] != 0:
                self.ip = (self.ip + relativo) & 0xFFFF
            return
        if op == 0xE8:
            relativo = self._fetch16()
            if relativo & 0x8000:
                relativo -= 0x10000
            self._push(self.ip)
            self.ip = (self.ip + relativo) & 0xFFFF
            return
        if op == 0xE9:
            relativo = self._fetch16()
            if relativo & 0x8000:
                relativo -= 0x10000
            self.ip = (self.ip + relativo) & 0xFFFF
            return
        if op == 0xEB:
            relativo = self._fetch8()
            if relativo & 0x80:
                relativo -= 0x100
            self.ip = (self.ip + relativo) & 0xFFFF
            return
        if op == 0xF7:
            self._grupo3()
            return
        if op == 0x99:
            self.regs["dx"] = 0xFFFF if self.regs["ax"] & 0x8000 else 0
            return
        if op in (0xFA, 0xFB):
            return
        raise ErrorEjecucion(
            f"Instruccion no soportada: {op:#04x} en {self.ip - 1:#06x}")

    def _condicion(self, opcode):
        if opcode == 0x74:
            return self.zf
        if opcode == 0x75:
            return not self.zf
        if opcode == 0x7C:
            return self.sf != self.ov
        if opcode == 0x7D:
            return self.sf == self.ov
        if opcode == 0x7E:
            return self.zf or (self.sf != self.ov)
        if opcode == 0x7F:
            return (not self.zf) and (self.sf == self.ov)
        if opcode == 0x79:
            return not self.sf
        if opcode == 0x78:
            return self.sf
        if opcode == 0x73:
            return not self.cf
        if opcode == 0x72:
            return self.cf
        if opcode == 0x76:
            return self.cf or self.zf
        if opcode == 0x77:
            return (not self.cf) and (not self.zf)
        raise ErrorEjecucion(
            f"Salto condicional no soportado: {opcode:#04x}")

    def _inc_dec(self, codigo, delta):
        valor = self._reg16(codigo)
        cf = self.cf
        if delta > 0:
            resultado = self._flags_suma(valor, 1, valor + 1)
        else:
            resultado = self._flags_resta(valor, 1, valor - 1)
        self.cf = cf
        self._set_reg16(codigo, resultado)

    def _acumulador_inmediato(self, op):
        ancho8 = op in (0x04, 0x0C, 0x24, 0x2C, 0x34, 0x3C, 0xA8)
        if ancho8:
            actual = self._reg8(0)
            inmediato = self._fetch8()
            bits = 8
        else:
            actual = self._reg16(0)
            inmediato = self._fetch16()
            bits = 16
        base = op & 0xFE
        if base == 0x04:
            resultado = self._flags_suma(actual, inmediato,
                                         actual + inmediato, bits)
        elif base == 0x0C:
            resultado = self._flags_logicos(actual | inmediato, bits)
        elif base == 0x24:
            resultado = self._flags_logicos(actual & inmediato, bits)
        elif base == 0x2C:
            resultado = self._flags_resta(actual, inmediato,
                                          actual - inmediato, bits)
        elif base == 0x34:
            resultado = self._flags_logicos(actual ^ inmediato, bits)
        elif base == 0x3C:
            self._flags_resta(actual, inmediato, actual - inmediato, bits)
            return
        elif base == 0xA8:
            self._flags_logicos(actual & inmediato, bits)
            return
        else:
            raise ErrorEjecucion(
                f"Operacion acumulador no soportada: {op:#04x}")
        if ancho8:
            self._set_reg8(0, resultado)
        else:
            self._set_reg16(0, resultado)

    def _aritmetica(self, op):
        mod, reg, rm, disp = self._modrm()
        if op in (0x01, 0x09, 0x21, 0x29, 0x31, 0x39):
            a = self._leer_rm16(mod, rm, disp)
            b = self._reg16(reg)
            destino = (mod, rm, disp)
        else:
            a = self._reg16(reg)
            b = self._leer_rm16(mod, rm, disp)
            destino = ("reg", reg)
        if op in (0x01, 0x03):
            resultado = self._flags_suma(a, b, a + b)
        elif op in (0x29, 0x2B, 0x39, 0x3B):
            resultado = self._flags_resta(a, b, a - b)
        elif op in (0x31, 0x33):
            resultado = self._flags_logicos(a ^ b)
        elif op in (0x21, 0x23):
            resultado = self._flags_logicos(a & b)
        elif op in (0x09, 0x0B):
            resultado = self._flags_logicos(a | b)
        else:
            self._flags_logicos(a & b)
            return
        if op in (0x39, 0x3B):
            return
        if destino[0] == "reg":
            self._set_reg16(reg, resultado)
        else:
            self._escribir_rm16(mod, rm, disp, resultado)

    def _aritmetica_inmediata(self, op):
        mod, reg, rm, disp = self._modrm()
        if op in (0x80, 0x82):
            actual = self._leer_rm8(mod, rm, disp)
            inmediato = self._fetch8()
            if reg == 0:
                resultado = self._flags_suma(actual, inmediato,
                                             actual + inmediato, 8)
            elif reg == 1:
                resultado = self._flags_logicos(actual | inmediato, 8)
            elif reg == 4:
                resultado = self._flags_logicos(actual & inmediato, 8)
            elif reg == 5:
                resultado = self._flags_resta(actual, inmediato,
                                              actual - inmediato, 8)
            elif reg == 6:
                resultado = self._flags_logicos(actual ^ inmediato, 8)
            elif reg == 7:
                self._flags_resta(actual, inmediato, actual - inmediato, 8)
                return
            else:
                raise ErrorEjecucion(f"Grupo 80 no soportado /{reg}")
            self._escribir_rm8(mod, rm, disp, resultado)
            return

        actual = self._leer_rm16(mod, rm, disp)
        inmediato = self._fetch8() if op == 0x83 else self._fetch16()
        if op == 0x83 and inmediato & 0x80:
            inmediato -= 0x100
        inmediato &= 0xFFFF
        if reg == 0:
            resultado = self._flags_suma(actual, inmediato,
                                         actual + inmediato)
        elif reg == 1:
            resultado = self._flags_logicos(actual | inmediato)
        elif reg == 4:
            resultado = self._flags_logicos(actual & inmediato)
        elif reg == 5:
            resultado = self._flags_resta(actual, inmediato,
                                          actual - inmediato)
        elif reg == 6:
            resultado = self._flags_logicos(actual ^ inmediato)
        elif reg == 7:
            self._flags_resta(actual, inmediato, actual - inmediato)
            return
        else:
            raise ErrorEjecucion(f"Grupo 81 no soportado /{reg}")
        self._escribir_rm16(mod, rm, disp, resultado)

    def _mov_registros(self, op):
        mod, reg, rm, disp = self._modrm()
        if op == 0x88:
            self._escribir_rm8(mod, rm, disp, self._reg8(reg))
        elif op == 0x89:
            self._escribir_rm16(mod, rm, disp, self._reg16(reg))
        elif op == 0x8A:
            self._set_reg8(reg, self._leer_rm8(mod, rm, disp))
        elif op == 0x8B:
            self._set_reg16(reg, self._leer_rm16(mod, rm, disp))
        elif op == 0x8C:
            self._escribir_rm16(
                mod, rm, disp, self.segmentos[self.NOMBRES_SREG[reg]])
        elif op == 0x8E:
            nombre = self.NOMBRES_SREG[reg]
            if nombre == "cs":
                raise ErrorEjecucion("No se puede modificar CS")
            self.segmentos[nombre] = self._leer_rm16(mod, rm, disp)

    def _mov_moffs(self, op):
        direccion = self._fetch16()
        if op == 0xA0:
            self._set_reg8(0, self._leer8(self.segmentos["ds"], direccion))
        elif op == 0xA1:
            self._set_reg16(0, self._leer16(self.segmentos["ds"], direccion))
        elif op == 0xA2:
            self._escribir8(self.segmentos["ds"], direccion, self._reg8(0))
        else:
            self._escribir16(self.segmentos["ds"], direccion, self._reg16(0))

    def _mov_inmediato(self, op):
        mod, reg, rm, disp = self._modrm()
        if op == 0xC6:
            self._escribir_rm8(mod, rm, disp, self._fetch8())
        else:
            self._escribir_rm16(mod, rm, disp, self._fetch16())

    def _desplazar(self, op):
        mod, reg, rm, disp = self._modrm()
        ancho8 = op in (0xD0, 0xD2)
        cuenta = (self._reg8(1) & 0x1F) if op in (0xD2, 0xD3) else 1
        if ancho8:
            valor = self._leer_rm8(mod, rm, disp)
            bits = 8
        else:
            valor = self._leer_rm16(mod, rm, disp)
            bits = 16
        mascara = (1 << bits) - 1
        signo = 1 << (bits - 1)
        for _ in range(cuenta):
            if reg == 4:
                self.cf = bool(valor & signo)
                valor = (valor << 1) & mascara
            elif reg == 5:
                self.cf = bool(valor & 1)
                valor >>= 1
            elif reg == 7:
                self.cf = bool(valor & 1)
                valor = (valor >> 1) | (signo if valor & signo else 0)
                valor &= mascara
            else:
                raise ErrorEjecucion(
                    f"Desplazamiento no soportado /{reg}")
        if ancho8:
            self._escribir_rm8(mod, rm, disp, valor)
        else:
            self._escribir_rm16(mod, rm, disp, valor)

    def _grupo3(self):
        mod, reg, rm, disp = self._modrm()
        valor = self._leer_rm16(mod, rm, disp)
        if reg in (0, 1):
            inmediato = self._fetch16()
            self._flags_logicos(valor & inmediato)
        elif reg == 2:
            self._escribir_rm16(mod, rm, disp, (~valor) & 0xFFFF)
        elif reg == 3:
            self._flags_resta(0, valor, -valor)
            self._escribir_rm16(mod, rm, disp, (-valor) & 0xFFFF)
        elif reg == 4:
            producto = self.regs["ax"] * valor
            self.regs["ax"] = producto & 0xFFFF
            self.regs["dx"] = (producto >> 16) & 0xFFFF
            self.cf = self.ov = self.regs["dx"] != 0
        elif reg == 5:
            producto = self._con_signo(self.regs["ax"]) * self._con_signo(valor)
            self.regs["ax"] = producto & 0xFFFF
            self.regs["dx"] = (producto >> 16) & 0xFFFF
            extension = 0xFFFF if self.regs["ax"] & 0x8000 else 0
            self.cf = self.ov = self.regs["dx"] != extension
        elif reg == 6:
            if valor == 0:
                raise ErrorEjecucion("Division por cero")
            dividendo = (self.regs["dx"] << 16) | self.regs["ax"]
            cociente, resto = divmod(dividendo, valor)
            if cociente > 0xFFFF:
                raise ErrorEjecucion("Desbordamiento en la division")
            self.regs["ax"] = cociente
            self.regs["dx"] = resto
        elif reg == 7:
            if valor == 0:
                raise ErrorEjecucion("Division por cero")
            dividendo = (self._con_signo(self.regs["dx"]) << 16) | self.regs["ax"]
            divisor = self._con_signo(valor)
            cociente = int(dividendo / divisor)
            resto = dividendo - cociente * divisor
            if not -32768 <= cociente <= 32767:
                raise ErrorEjecucion("Desbordamiento en la division")
            self.regs["ax"] = cociente & 0xFFFF
            self.regs["dx"] = resto & 0xFFFF
        else:
            raise ErrorEjecucion(f"Grupo F7 no soportado /{reg}")

    def _interrupcion(self, numero):
        if numero == 0x20:
            self.terminado = True
            return
        if numero != 0x21:
            raise ErrorEjecucion(f"Interrupcion no soportada: {numero:#04x}")
        funcion = (self.regs["ax"] >> 8) & 0xFF
        if funcion == 0x4C:
            self.terminado = True
        elif funcion == 0x02:
            byte = self.regs["dx"] & 0xFF
            self.salida.append(bytes([byte]).decode("cp437", errors="replace"))
        elif funcion == 0x09:
            desplazamiento = self.regs["dx"]
            datos = bytearray()
            while True:
                byte = self._leer8(self.segmentos["ds"], desplazamiento)
                if byte == ord("$"):
                    break
                datos.append(byte)
                desplazamiento = (desplazamiento + 1) & 0xFFFF
                if len(datos) > 65535:
                    raise ErrorEjecucion("Cadena sin terminador '$'")
            self.salida.append(datos.decode("cp437", errors="replace"))
        else:
            raise ErrorEjecucion(
                f"Funcion DOS no soportada: AH={funcion:#04x}")
