"""Utilidades para formatear, recorrer y medir el arbol de parseo."""


# ======================================================================
# UTILIDADES DEL ARBOL DE PARSEO
# ======================================================================

def _texto_nodo(nodo):
    texto = nodo.etiqueta
    if nodo.valor not in (None, ""):
        if nodo.tipo and str(nodo.valor) != str(nodo.tipo):
            texto += f" ({nodo.valor} : {nodo.tipo})"
        else:
            texto += f" ({nodo.valor})"
    elif nodo.tipo:
        texto += f" (: {nodo.tipo})"
    return texto


def formatear_arbol(nodo, prefijo="", es_ultimo=True, es_raiz=True, lineas=None):
    if lineas is None:
        lineas = []
    if es_raiz:
        lineas.append(_texto_nodo(nodo))
        nuevo_prefijo = ""
    else:
        conector = "└── " if es_ultimo else "├── "
        lineas.append(prefijo + conector + _texto_nodo(nodo))
        nuevo_prefijo = prefijo + ("    " if es_ultimo else "│   ")
    for indice, hijo in enumerate(nodo.hijos):
        formatear_arbol(hijo, nuevo_prefijo, indice == len(nodo.hijos) - 1,
                        False, lineas)
    return lineas


def arbol_a_texto(nodo):
    return "\n".join(formatear_arbol(nodo))


def contar_nodos(nodo):
    return 1 + sum(contar_nodos(hijo) for hijo in nodo.hijos)


def profundidad(nodo):
    if not nodo.hijos:
        return 1
    return 1 + max(profundidad(hijo) for hijo in nodo.hijos)
