# -*- coding: utf-8 -*-
"""
mathcore.py
===========
Núcleo matemático de la aplicación: parser de sintaxis amigable (x^2, sen, ln,
sqrt, e, pi, abs), evaluación numérica segura (vectorizada con NumPy) y las
rutinas de cálculo de Sumas de Riemann, integral exacta (simbólica con SymPy,
con respaldo numérico de alta precisión si la integral no es elemental) y
longitud de arco.

Todo este módulo es independiente de la interfaz gráfica: la GUI (PyQt6) sólo
llama a estas funciones y muestra los resultados.
"""

import re
import numpy as np
import sympy as sp

# ---------------------------------------------------------------------------
# Símbolos globales
# ---------------------------------------------------------------------------
X, Y = sp.symbols('x y', real=True)

# Diccionarios de nombres permitidos dentro de sympify (evita usar eval "pelado"
# sobre texto arbitrario: sympify con locals restringidos es mucho más seguro).
_LOCAL_DICT_1D = {
    'x': X,
    'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan,
    'asin': sp.asin, 'acos': sp.acos, 'atan': sp.atan,
    'sinh': sp.sinh, 'cosh': sp.cosh, 'tanh': sp.tanh,
    'log': sp.log, 'sqrt': sp.sqrt, 'exp': sp.exp,
    'Abs': sp.Abs, 'pi': sp.pi, 'e': sp.E,
}
_LOCAL_DICT_2D = dict(_LOCAL_DICT_1D)
_LOCAL_DICT_2D['y'] = Y


class ErrorSintaxis(Exception):
    """Excepción propia para errores de sintaxis en la función ingresada."""
    pass


def _preprocesar_texto(texto: str) -> str:
    """
    Traduce la sintaxis 'amigable' que pide la rúbrica a sintaxis que SymPy
    puede interpretar:
        ^        -> **
        sen(...) -> sin(...)
        ln(...)  -> log(...)      (logaritmo natural)
        abs(...) -> Abs(...)      (valor absoluto, con mayúscula para SymPy)
    sqrt, exp, pi, e, sin, cos, etc. ya son reconocidos de forma nativa.
    """
    if texto is None:
        raise ErrorSintaxis("La función no puede estar vacía.")
    s = texto.strip()
    if not s:
        raise ErrorSintaxis("La función no puede estar vacía.")

    s = s.replace(' ', '')
    s = s.replace('^', '**')
    # Inserta un asterisco entre un número y una letra (ej. '2x' -> '2*x')
    s = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', s)
    s = re.sub(r'\bsen\(', 'sin(', s)
    s = re.sub(r'\bln\(', 'log(', s)
    s = re.sub(r'\babs\(', 'Abs(', s)
    return s


def parsear_funcion_1d(texto: str) -> sp.Expr:
    """Convierte un texto tipo 'x^2 + sen(x)' en una expresión SymPy de x."""
    s = _preprocesar_texto(texto)
    try:
        expr = sp.sympify(s, locals=_LOCAL_DICT_1D)
    except Exception as ex:
        raise ErrorSintaxis(f"No se pudo interpretar la función: {ex}")
    # Verificamos que no aparezcan símbolos "raros" (protección extra)
    simbolos_permitidos = {X}
    extra = expr.free_symbols - simbolos_permitidos
    if extra:
        raise ErrorSintaxis(
            f"La función sólo puede depender de 'x'. Se detectó: {', '.join(str(s) for s in extra)}"
        )
    return expr


def parsear_funcion_2d(texto: str) -> sp.Expr:
    """Convierte un texto tipo 'x^2 + y^2' en una expresión SymPy de x,y."""
    s = _preprocesar_texto(texto)
    try:
        expr = sp.sympify(s, locals=_LOCAL_DICT_2D)
    except Exception as ex:
        raise ErrorSintaxis(f"No se pudo interpretar la función: {ex}")
    simbolos_permitidos = {X, Y}
    extra = expr.free_symbols - simbolos_permitidos
    if extra:
        raise ErrorSintaxis(
            f"La función sólo puede depender de 'x' e 'y'. Se detectó: {', '.join(str(s) for s in extra)}"
        )
    return expr


def parsear_limite(texto: str) -> float:
    """
    Permite que los límites de integración acepten expresiones simples como
    'pi', '-pi/2', 'sqrt(2)', además de números normales.
    """
    s = _preprocesar_texto(texto) if texto and texto.strip() else texto
    try:
        val = sp.sympify(s, locals={'pi': sp.pi, 'e': sp.E, 'sqrt': sp.sqrt})
        return float(val)
    except Exception:
        raise ErrorSintaxis(f"'{texto}' no es un número válido.")


# ---------------------------------------------------------------------------
# Evaluación numérica segura (envuelve lambdify para blindar contra escalares,
# NaN, división por cero, dominios inválidos, etc.)
# ---------------------------------------------------------------------------

def lambdify_1d(expr: sp.Expr):
    """Devuelve f(x_array) -> y_array (NumPy), robusta ante errores puntuales."""
    f_raw = sp.lambdify(X, expr, modules=['numpy'])

    def f_seguro(xs):
        xs = np.atleast_1d(np.asarray(xs, dtype=float))
        with np.errstate(all='ignore'):
            try:
                ys = f_raw(xs)
            except Exception:
                ys = np.full_like(xs, np.nan)
        ys = np.asarray(ys, dtype=float)
        if ys.shape != xs.shape:
            # La expresión es constante (p. ej. f(x)=5): lambdify devuelve escalar
            try:
                val = float(ys)
            except Exception:
                val = np.nan
            ys = np.full_like(xs, val)
        return ys
    return f_seguro


def lambdify_2d(expr: sp.Expr):
    """Devuelve f(X_mesh, Y_mesh) -> Z_mesh (NumPy), robusta ante errores."""
    f_raw = sp.lambdify((X, Y), expr, modules=['numpy'])

    def f_seguro(xs, ys):
        xs = np.asarray(xs, dtype=float)
        ys = np.asarray(ys, dtype=float)
        with np.errstate(all='ignore'):
            try:
                zs = f_raw(xs, ys)
            except Exception:
                zs = np.full(np.broadcast(xs, ys).shape, np.nan)
        zs = np.asarray(zs, dtype=float)
        if zs.shape != xs.shape:
            try:
                val = float(zs)
            except Exception:
                val = np.nan
            zs = np.full(xs.shape, val)
        return zs
    return f_seguro


# ---------------------------------------------------------------------------
# Sumas de Riemann (1D)
# ---------------------------------------------------------------------------

def puntos_metodo(a, b, n, metodo):
    """Devuelve las abscisas c_i usadas por cada método, y el ancho dx."""
    dx = (b - a) / n
    if metodo == 'Izquierda':
        xs = a + dx * np.arange(n)
    elif metodo == 'Derecha':
        xs = a + dx * np.arange(1, n + 1)
    elif metodo == 'Punto Medio':
        xs = a + dx * (np.arange(n) + 0.5)
    elif metodo == 'Trapecios':
        xs = a + dx * np.arange(n + 1)
    else:
        raise ValueError(f"Método desconocido: {metodo}")
    return xs, dx


def suma_riemann(f_num, a, b, n, metodo):
    """
    Calcula la suma de Riemann (o la regla de trapecios) para f_num en [a,b]
    con n subintervalos. Devuelve (suma, xs_usados, ys_usados, dx).
    """
    xs, dx = puntos_metodo(a, b, n, metodo)
    ys = f_num(xs)
    if metodo == 'Trapecios':
        suma = float(dx * (np.nansum(ys) - 0.5 * ys[0] - 0.5 * ys[-1]))
    else:
        suma = float(np.nansum(ys) * dx)
    return suma, xs, ys, dx


# ---------------------------------------------------------------------------
# Integral exacta (simbólica, con respaldo numérico fino)
# ---------------------------------------------------------------------------

def integral_exacta(expr_neta: sp.Expr, a: float, b: float):
    """
    Intenta calcular la integral definida de forma SIMBÓLICA con SymPy.
    Si el resultado no es elemental (contiene una Integral sin resolver) o es
    complejo, recurre a una aproximación numérica de altísima precisión
    (suma de punto medio con n=200000) como respaldo.

    Devuelve: (valor_float, es_simbolico: bool, F_expr o None)
    """
    F = None
    try:
        F = sp.integrate(expr_neta, X)
        if F.has(sp.Integral):
            raise ValueError("Resultado no elemental (integral sin resolver).")
        valor_sym = F.subs(X, b) - F.subs(X, a)
        valor_c = complex(sp.N(valor_sym))
        if abs(valor_c.imag) > 1e-6:
            raise ValueError("El resultado simbólico es complejo.")
        return float(valor_c.real), True, F
    except Exception:
        f_num = lambdify_1d(expr_neta)
        n_fino = 200_000
        dx = (b - a) / n_fino
        xs = a + dx * (np.arange(n_fino) + 0.5)
        ys = f_num(xs)
        valor = float(np.nansum(ys) * dx)
        return valor, False, F


def integral_valor_absoluto(expr_neta: sp.Expr, a: float, b: float):
    """
    Área geométrica real: integral de |f(x)| en [a,b].
    Se calcula numéricamente (muy fina) para evitar problemas con los puntos
    donde la función cambia de signo (raíces no siempre triviales de hallar
    simbólicamente).
    """
    f_num = lambdify_1d(expr_neta)
    n_fino = 200_000
    dx = (b - a) / n_fino
    xs = a + dx * (np.arange(n_fino) + 0.5)
    ys = np.abs(f_num(xs))
    return float(np.nansum(ys) * dx)


def longitud_arco(expr_f: sp.Expr, a: float, b: float):
    """
    Longitud de arco de f(x) en [a,b]: integral de sqrt(1 + f'(x)^2).
    Intenta resolverlo simbólicamente; si no es elemental, usa una
    aproximación numérica fina (poligonal con muchos segmentos).
    Devuelve (valor_float, es_simbolico: bool).
    """
    try:
        df = sp.diff(expr_f, X)
        integrando = sp.sqrt(1 + df**2)
        F = sp.integrate(integrando, X)
        if F.has(sp.Integral):
            raise ValueError("No elemental")
        valor_sym = F.subs(X, b) - F.subs(X, a)
        valor_c = complex(sp.N(valor_sym))
        if abs(valor_c.imag) > 1e-6:
            raise ValueError("Complejo")
        return float(valor_c.real), True
    except Exception:
        f_num = lambdify_1d(expr_f)
        n_fino = 200_000
        xs = np.linspace(a, b, n_fino + 1)
        ys = f_num(xs)
        dxs = np.diff(xs)
        dys = np.diff(ys)
        segmentos = np.sqrt(dxs**2 + dys**2)
        return float(np.nansum(segmentos)), False


def longitud_arco_aproximada(expr_f: sp.Expr, a: float, b: float, n: int):
    """Aproximación poligonal de la longitud de arco con n segmentos (para
    comparar contra el valor exacto y mostrar convergencia)."""
    f_num = lambdify_1d(expr_f)
    xs = np.linspace(a, b, n + 1)
    ys = f_num(xs)
    dxs = np.diff(xs)
    dys = np.diff(ys)
    segmentos = np.sqrt(dxs**2 + dys**2)
    return float(np.nansum(segmentos))


# ---------------------------------------------------------------------------
# Suma de Riemann 3D (volúmenes) - basada en la lógica del script original
# ---------------------------------------------------------------------------

def suma_riemann_3d(f_num2d, xa, xb, ya, yb, n, punto='Punto Medio'):
    """
    Aproxima el volumen bajo z=f(x,y) sobre el rectángulo [xa,xb]x[ya,yb]
    usando un grid de n x n prismas.
    punto: 'Punto Medio' o 'Esquina inferior izquierda'.
    Devuelve: volumen, x_pos, y_pos, dx, dy, alturas (para graficar bar3d).
    """
    dx = (xb - xa) / n
    dy = (yb - ya) / n

    x_pos, y_pos = np.meshgrid(
        np.linspace(xa, xb - dx, n),
        np.linspace(ya, yb - dy, n)
    )
    x_pos = x_pos.ravel()
    y_pos = y_pos.ravel()

    if punto == 'Punto Medio':
        ex = x_pos + dx / 2
        ey = y_pos + dy / 2
    else:  # Esquina inferior izquierda
        ex = x_pos
        ey = y_pos

    alturas = f_num2d(ex, ey)
    alturas = np.nan_to_num(alturas, nan=0.0)

    volumen = float(np.sum(alturas * dx * dy))
    return volumen, x_pos, y_pos, dx, dy, alturas


def volumen_referencia_3d(f_num2d, xa, xb, ya, yb, n_fino=400):
    """Aproximación numérica muy fina (regla del punto medio 2D) usada como
    'volumen de referencia' para calcular el error del volumen aproximado."""
    dx = (xb - xa) / n_fino
    dy = (yb - ya) / n_fino
    xs = xa + dx * (np.arange(n_fino) + 0.5)
    ys = ya + dy * (np.arange(n_fino) + 0.5)
    XX, YY = np.meshgrid(xs, ys)
    ZZ = f_num2d(XX, YY)
    ZZ = np.nan_to_num(ZZ, nan=0.0)
    return float(np.sum(ZZ) * dx * dy)


def a_mathtext(expr: sp.Expr) -> str:
    """
    Convierte una expresión SymPy a una cadena LaTeX compatible con el motor
    'mathtext' interno de Matplotlib (no requiere instalación de LaTeX).
    Si algo no es soportado por mathtext, se captura en la capa de dibujo.
    """
    return sp.latex(expr)
