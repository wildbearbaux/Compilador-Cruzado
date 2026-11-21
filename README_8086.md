# Traductor Java → ensamblador 8086 en el IDE

El proyecto esta organizado en el paquete `compilador/`; `main.py` es solo el
punto de entrada que inicia la interfaz. El IDE incluye un **traductor
automatico de un subconjunto de Java a ensamblador 8086**. Desde el codigo que
tengas en el editor genera, en la **misma carpeta del archivo `.java`**:

1. el codigo fuente ensamblador (`Nombre.asm`),
2. el ejecutable de DOS (`Nombre.com`),
3. y lo ejecuta mostrando la salida en la consola del IDE.

El IDE **no necesita instalar nada**: si no encuentra TASM, MASM ni JWasm, usa
el **ensamblador interno** de `compilador/ensamblador8086.py`; y si no esta el
modulo `unicorn`, usa el **interprete 8086 interno** de
`compilador/interprete8086.py`. Cuando hay herramientas externas, las prefiere
automaticamente. La consola indica cual se uso (`ensamblado con ...`,
`ejecutado con ...`).

---

## Estructura del proyecto

```
compilador_completo/
├── main.py                     Punto de entrada (python3 main.py)
├── README_8086.md
├── ejemplos/
└── compilador/
    ├── config.py               Constantes del lenguaje
    ├── lexico.py               Analizador lexico
    ├── sintactico.py           Parser y AST
    ├── semantico.py            Analisis semantico
    ├── reglas.py               Reglas de iterativas anidadas
    ├── arbol.py                Utilidades del AST
    ├── analizador.py           Orquestador de los analisis
    ├── generador8086.py        Traductor Java -> ASM 8086
    ├── interprete_ast.py       Ejecucion de alto nivel del AST
    ├── ensamblador8086.py      Ensamblador interno .COM
    ├── interprete8086.py       CPU virtual de 16 bits
    └── ui/
        ├── ide.py              Ventana principal
        ├── sidebar.py          Explorador de archivos
        ├── busqueda.py         Buscar y reemplazar
        ├── archivos.py         Abrir, guardar y temporales
        └── numeros_linea.py    Numeros de linea del editor
```

---

## Como se usa

Abre un archivo `.java` en el IDE (por ejemplo `ejemplos/BubbleSort8086.java`)
y usa cualquiera de estas opciones:

| Accion | Atajo | Que hace |
|---|---|---|
| **Compiladores → Generar ensamblador 8086 (.asm)** | `Alt+4` | Traduce el editor y escribe `Nombre.asm` junto al `.java`. |
| **Compiladores → Ensamblar y ejecutar 8086** | `Alt+5` | Genera el `.asm`, lo ensambla, crea `Nombre.com` y lo ejecuta. |
| **Ejecutar → Generar y ejecutar 8086** | `Alt+5` | Igual que el anterior. |
| **Ejecutar → Ejecutar Java (javac + java)** | `F5` | Compila y ejecuta el `.java` real para comparar resultados. |
| **Compiladores → Abrir ejemplo 8086 compatible** | — | Abre `ejemplos/BubbleSort8086.java`, que si se traduce. |
| **Compiladores → Diagnostico del traductor 8086** | — | Traduce, ensambla y ejecuta un programa corto (`6 * 7`) para comprobar que todo funciona. |

Antes de compilar, el IDE guarda automaticamente el contenido del editor, de
modo que el `.java`, el `.asm` y el `.com` siempre corresponden al mismo codigo.

Los archivos se crean en la carpeta del archivo abierto:

```
ejemplos/
├── BubbleSort8086.java   <- tu codigo
├── BubbleSort8086.asm    <- generado por el traductor
└── BubbleSort8086.com    <- ejecutable de DOS generado al ensamblar
```

---

## Requisitos

### Para ensamblar (opcional)

**No hace falta nada**: si no hay un ensamblador externo, el IDE usa su
ensamblador interno (Python puro), que entiende exactamente las instrucciones
que genera. Si prefieres el flujo clasico del curso, tambien detecta:

| Herramienta | Instalacion | Como la detecta el IDE |
|---|---|---|
| **TASM 5** | `tasm.exe` y `tlink.exe` en el `PATH` | `tasm archivo.asm /m2` y luego `tlink /t archivo.obj` |
| **MASM 6.11+** | `ml.exe` en el `PATH` | `ml /AT archivo.asm` (genera `.com`) |
| **JWasm** | `jwasm` en el `PATH` | `jwasm -bin -Fo archivo.com archivo.asm` |
| **emu8086** | Abre el `.asm` generado | No se invoca desde el IDE; se usa su boton *Emulate* |

El IDE prueba en ese orden: `tasm`, `ml`, `masm`, `jwasm`. Si ninguno esta
disponible (o falla), genera el `.com` con el ensamblador interno y lo indica
en la consola. En Windows, si quieres usar TASM/MASM, asegurate de que su
carpeta este en el `PATH` o ejecuta el IDE desde una consola donde funcionen.

### Para ejecutar el `.com` dentro del IDE (opcional)

**No hace falta nada**: el IDE incluye un interprete 8086 en Python que ejecuta
el `.com` y muestra su salida en la consola.

* Si tienes `unicorn` instalado (`python3 -m pip install unicorn`), lo usa
  preferentemente.
* Sin `unicorn`, usa el interprete interno.
* Si hubiera un `.exe` (por ejemplo generado por MASM sin `/AT`) y hay
  **DOSBox** (`dosbox`, `dosbox-x` o `dosbox-staging`) en el `PATH`, lo abre en
  DOSBox.

---

## Subconjunto de Java soportado

El traductor trabaja sobre el arbol de parseo del propio IDE, asi que primero
debe pasar el analisis lexico y sintactico. Despues acepta:

### Estructura
* Una clase con `public static void main(String[] args)`.
* Tambien acepta sentencias sueltas (estilo script) si no hay `main`.
* Declaraciones y sentencias dentro de `main` o de bloques `{ ... }`.

### Variables
* Tipos enteros de 16 bits: `int`, `short`, `byte`, `char`, `long`, `boolean`.
* Declaracion con o sin valor inicial: `int x;`, `int x = 5;`.
* `char` y `boolean` con sus literales de Java: `char c = 'a';`,
  `boolean ok = true;`.
* Asignaciones `=`, `+=`, `-=`, `*=`.
* `++` y `--` como sentencia o prefijo/postfijo en expresiones.

### Arreglos
* `int[] a = {1, 2, 3};`
* `int[] a = new int[10];` (el tamano debe ser una **constante entera**).
* Lectura y escritura con indices: `a[i]`, `a[i + 1] = x;`.
* `.length` sobre un arreglo: `a.length`.
* Los indices pueden ser expresiones (`a[i * 2 + 1]`), pero solo sobre una
  variable de arreglo (no sobre otra expresion).

### Control
* `if` / `else` (incluidos `else if` anidados).
* `while`.
* `for` clasico: `for (i = 0; i < n; i++)` o `for (int i = 0; ...)`.
* `break` y `continue` dentro de `while` o `for`.
* `return;` y `return expresion;` dentro de `main` (termina el programa).

### Expresiones
* `+  -  *  /  %` con enteros.
* Comparaciones `<  >  <=  >=  ==  !=`.
* Logicos `&&  ||  !` con cortocircuito.
* Parentesis y signos unarios `-`, `+`, `~`.

### Entrada/salida
* `System.out.print(...)` y `System.out.println(...)`.
* Un solo argumento por llamada.
* Se admite: enteros, variables enteras, elementos de arreglo, caracteres,
  booleanos y **cadenas literales** (`"texto"`).
* Se admite **concatenar con `+`** dentro de `print`/`println`, por ejemplo
  `System.out.println("Resultado: " + total);`.
* `System.out.println()` sin argumentos escribe solo el salto de linea.
* Los caracteres se imprimen como caracter (`'A'` → `A`) y los booleanos como
  `true` / `false`, igual que en Java.
* Las cadenas admiten acentos y simbolos; un `$` dentro del texto se imprime
  correctamente (el generador parte la cadena porque `INT 21h/AH=09h` termina
  en `$`).

---

## Lo que NO esta soportado

El traductor muestra un error con **linea y columna** (y no escribe el `.asm`)
cuando encuentra algo fuera del subconjunto, junto con una **sugerencia** y el
ejemplo que si funciona. En particular:

* Otros metodos ademas de `main` y llamadas a funciones (`foo()`,
  `calc.sumar()`), constructores y objetos.
* Entrada por teclado (`Scanner`, `System.in`).
* Arreglos multidimensionales y arreglos de otros tipos.
* `new int[n]` con tamano variable (solo constantes).
* `double`, `float` y literales decimales.
* Casts explicitos como `(char) (c + 1)`.
* `switch`, `do-while`, `try/catch`.
* Metodos de `String` (`length()`, `charAt()`, `equals()`, ...).
* Recursividad y funciones.

Ejemplos de errores que veras en la consola del IDE:

```
Linea 3, Col 9 -> Error: Llamada no soportada 'foo()'
Linea 26, Col 9 -> Error: Sentencia no soportada por el traductor: Try
Linea 4, Col 27 -> Error: Se esperaba una constante entera
```

---

## Como funciona el codigo generado

* Se genera un programa **`.COM` de DOS** con `.model tiny`, `org 100h`, para
  que funcione en MASM, TASM, JWasm y emu8086 sin enlazador especial.
* Las expresiones se evaluan con `AX` como acumulador y la pila para los
  operandos; las comparaciones y los logicos dejan `0` o `1` en `AX`.
* Cada variable, arreglo, cadena y etiqueta recibe un nombre unico
  (`v_x_3`, `a_datos_7`, `str0002`, `L0014`) para no chocar con palabras
  reservadas ni con nombres del usuario.
* Se incluyen rutinas internas para imprimir enteros con signo
  (`rt_imprimir_numero`) y saltos de linea (`rt_nueva_linea`), usando solo
  `INT 21h` (`AH=09h`, `AH=02h`, `AH=4Ch`).
* Los datos (variables, arreglos y cadenas) se emiten al final, despues del
  codigo, para que el `.COM` se cargue y ejecute directamente en `100h`.

Fragmento tipico:

```asm
        mov     ax, [v_i_3]
        push    ax
        mov     ax, [v_n_2]
        push    ax
        mov     ax, 1
        mov     bx, ax
        pop     ax
        sub     ax, bx
        mov     bx, ax
        pop     ax
        cmp     ax, bx
        jl      L0006
        xor     ax, ax
        jmp     L0007
L0006:
        mov     ax, 1
L0007:
        test    ax, ax
        jz      L0005
```

---

## Ejemplos incluidos

### Calculadora8086

`ejemplos/Calculadora8086.java` usa solo el subconjunto soportado (aritmetica,
`for`, `while`, `break`, `continue`, arreglos y concatenacion en `println`).
Salida identica con Java, con el interprete interno y con `unicorn`:

```
Calculadora 8086
Suma: 55
Resta: 41
Producto: 336
Division: 6
Resto: 6
Suma de pares hasta 30: 26
Factorial de 6: 720
```

### BubbleSort8086

`ejemplos/BubbleSort8086.java` ordena un arreglo con el metodo de la burbuja:

```java
public class BubbleSort8086 {
    public static void main(String[] args) {
        int[] arreglo = {45, 12, 78, 3, 23, 90, 8, 56, 1, 34};
        int n = 10;
        int i = 0;
        while (i < n - 1) {
            int j = 0;
            while (j < n - 1 - i) {
                if (arreglo[j] > arreglo[j + 1]) {
                    int temporal = arreglo[j];
                    arreglo[j] = arreglo[j + 1];
                    arreglo[j + 1] = temporal;
                }
                j++;
            }
            i++;
        }
        ...
    }
}
```

Salida identica con Java y con el ejecutable 8086:

```
Arreglo ordenado:
1
3
8
12
23
34
45
56
78
90
```

Los archivos `BubbleSort8086.asm` (231 lineas) y `BubbleSort8086.com`
(439 bytes con el ensamblador interno, 434 con JWasm) incluidos se generaron
con este traductor y ensamblan sin advertencias ni errores. El `.com` funciona
igual con el interprete interno y con `unicorn`/DOSBox.

---

## Verificacion realizada

* El ejemplo de burbuja y otros cinco programas (matematicas, `for` anidados,
  `else if`, caracteres/booleanos y saltos largos) producen **exactamente la
  misma salida** al ejecutarse con `javac`/`java` y con el `.com` generado.
* Se verifico el ensamblador interno contra JWasm: los `.com` internos y los
  de JWasm dan la misma salida (y el interprete interno ejecuta ambos), con
  `0 warnings, 0 errors` en JWasm.
* Se probo tambien una cadena con acentos, `$`, `%` y comillas: la salida
  coincide con Java tanto en el interprete interno como en `unicorn`.
* `Calculadora8086` verifica ademas `break`, `continue`, concatenacion en
  `print`/`println` y arreglos: la salida coincide exactamente con Java.
* Se probaron los caminos de error: llamada no soportada, `try`, tamano de
  arreglo no constante y programa sin `main`; en todos el IDE informa la
  linea/columna, muestra una sugerencia y **no** escribe el `.asm`.
* La prueba de interfaz completa se ejecuto **sin TASM/MASM/JWasm, sin DOSBox
  y sin `unicorn`**: Alt+5 genero el `.asm`, el `.com` y mostro la salida
  ordenada, usando solo el ensamblador y el interprete internos.
* El menu **Compiladores → Diagnostico del traductor 8086** traduce, ensambla
  y ejecuta `6 * 7` en memoria y confirma que el circuito completo funciona.

---

## Nota sobre `for.java`

Si abres `ejemplos/for.java` y pulsas Alt+5, veras:

```
Linea 26, Col 9 -> Error: Sentencia no soportada por el traductor: Try
El traductor 8086 no puede convertir este programa:
  Sentencia no soportada por el traductor: Try (linea 26, columna 9)
Sugerencia: No se admite try/catch/finally ni try-with-resources. ...
```

El problema **no es el ensamblador**: es que ese programa usa `try/catch`,
`Scanner`, objetos, atributos, constructores y metodos propios, que estan fuera
del subconjunto traducible. Ademas, como Java, tampoco es valido: declara la
clase `CalculadoraBasica` en un archivo llamado `for.java` (el nombre debe
coincidir) y usa `System.util.System.in`, que no existe (deberia ser
`System.in`).

Para ver el flujo completo funcionando, abre
`ejemplos/BubbleSort8086.java` o `ejemplos/Calculadora8086.java` (o usa
**Compiladores → Abrir ejemplo 8086 compatible**) y pulsa `Alt+5`.
`ejemplos/while.java` esta vacio.
