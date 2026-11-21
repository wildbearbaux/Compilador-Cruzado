"""Constantes de configuracion del lenguaje y del IDE."""

# ======================================================================
# CONFIGURACION
# ======================================================================

RESERVADAS_JAVA = [
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", 
    "class", "const", "continue", "default", "do", "double", "else", "enum", 
    "extends", "final", "finally", "float", "for", "goto", "if", "implements", 
    "import", "instanceof", "int", "interface", "long", "native", "new", "package", 
    "private", "protected", "public", "return", "short", "static", "strictfp", 
    "super", "switch", "synchronized", "this", "throw", "throws", "transient", 
    "try", "void", "volatile", "while", "true", "false", "null", 
    "String", "System", "out", "println", "print", "Scanner", "Exception", 
    "Object", "Math", "Thread", "Runnable", "List", "ArrayList", "Map", "HashMap",
    "str", "bool", "Int", "Char", "main"
]

EXTENSION = '.txt'


# Tipos de dato aceptados por el lenguaje (incluye los alias del proyecto).
TIPOS = {
    "int", "Int", "double", "float", "String", "str", "char", "Char",
    "boolean", "bool", "void", "long", "short", "byte",
}

# Palabras reservadas reales del lenguaje (no nombres de librerias).
RESERVADAS = {
    "abstract", "assert", "break", "case", "catch", "class", "const",
    "continue", "default", "do", "else", "enum", "extends", "final",
    "finally", "for", "goto", "if", "implements", "import", "instanceof",
    "interface", "native", "new", "package", "private", "protected",
    "public", "return", "static", "strictfp", "super", "switch",
    "synchronized", "this", "throw", "throws", "transient", "try",
    "volatile", "while",
}

BOOLEANOS = {"true", "false"}
NULOS = {"null"}

# Operadores ordenados de mayor a menor longitud para que el emparejamiento
# sea correcto (por ejemplo, '==' antes que '=').
OPERADORES = sorted(
    [
        "<<=", ">>=", ">>>", "===", "!==", "==", "!=", "<=", ">=", "++",
        "--", "+=", "-=", "*=", "/=", "%=", "&&", "||", "->", "::", "<<",
        ">>", "+", "-", "*", "/", "%", "=", "<", ">", "!", "&", "|", "^",
        "~", "?", ":", "@",
    ],
    key=len,
    reverse=True,
)

DELIMITADORES = set("(){}[];,.")

# Java distingue mayusculas: 'If', 'WHILE' o 'Class' no son palabras
# reservadas. Se mapea la forma en minusculas a la escritura correcta para
# avisar del error y, aun asi, seguir analizando como si estuviera bien.
ESCRITURA_CORRECTA = {
    palabra.lower(): palabra
    for palabra in (
        set(RESERVADAS) | BOOLEANOS | NULOS
        | {"int", "double", "float", "char", "boolean", "long", "short",
           "byte", "void", "String"}
    )
}
