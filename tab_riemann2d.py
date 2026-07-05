# -*- coding: utf-8 -*-
"""
tab_riemann2d.py
================
Pestaña 1 de la aplicación: "Suma de Riemann 2D & Antiderivadas".

Contiene:
- Panel de parámetros (función f, función g opcional, límites a/b, n con
  slider+spinbox sincronizados, método, modo Área/Longitud, checkboxes de
  superposición de métodos y área real).
- Gráfico principal (curva + rectángulos), con barra de herramientas de
  zoom/paneo (requisito de la rúbrica).
- Gráfico de convergencia (error vs. n).
- "Pizarra Digital" con el desarrollo simbólico paso a paso (PizarraDigital).
- Historial de los últimos 10 cálculos (clic para restaurar parámetros).
- Botones Calcular / Limpiar / Animar / Exportar.

CORRECCIÓN DE BUG DEL SELECTOR DE MÉTODO:
Todos los controles que afectan el resultado (función, límites, n, método,
modo, checkboxes) están conectados a una única función central,
`recalcular_y_dibujar()`, que SIEMPRE limpia los ejes (ax.clear()) antes de
volver a dibujar y SIEMPRE termina llamando a canvas.draw_idle(). De esta
forma no puede quedar una figura a medio refrescar ni una figura "vieja"
mezclada con la nueva.
"""

import numpy as np
import sympy as sp

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QLabel, QLineEdit,
    QSpinBox, QSlider, QComboBox, QPushButton, QCheckBox, QListWidget,
    QListWidgetItem, QSplitter, QFileDialog, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

import mathcore as mc
from pizarra import PizarraDigital


MAX_HISTORIAL = 10
N_SLIDER_MAX = 200  # tope práctico del slider (rectángulos visibles); el spinbox permite más


class RiemannTab2D(QWidget):

    def __init__(self, tema_actual: dict, parent=None):
        super().__init__(parent)
        self.tema = tema_actual

        # Estado interno cacheado tras el último cálculo válido (usado por el
        # slider para redibujar rápido sin re-parsear todo desde cero).
        self._expr_f = None
        self._expr_g = None
        self._a = None
        self._b = None
        self._historial = []  # lista de dicts con los parámetros de cada cálculo

        self._construir_ui()
        self._conectar_señales()
        self.aplicar_tema(self.tema)
        self._cargar_valores_por_defecto()
        self.recalcular_y_dibujar(loggear_historial=False)

    # ------------------------------------------------------------------
    # CONSTRUCCIÓN DE LA INTERFAZ
    # ------------------------------------------------------------------
    def _construir_ui(self):
        layout_raiz = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout_raiz.addWidget(splitter)

        # ---------- Columna izquierda: parámetros ----------
        panel_izq = QWidget()
        v_izq = QVBoxLayout(panel_izq)
        v_izq.setContentsMargins(6, 6, 6, 6)

        grupo_func = QGroupBox("Función y límites")
        f_layout = QVBoxLayout(grupo_func)

        f_layout.addWidget(QLabel("f(x) ="))
        self.input_f = QLineEdit()
        self.input_f.setToolTip(
            "Escribe f(x) con sintaxis amigable:\n"
            "  x^2 , sqrt(x) , sen(x) o sin(x) , ln(x) , e^x , pi , abs(x)\n"
            "Ejemplo: -x^2 + 4"
        )
        f_layout.addWidget(self.input_f)

        f_layout.addWidget(QLabel("g(x) = (opcional, área entre curvas; 0 por defecto)"))
        self.input_g = QLineEdit()
        self.input_g.setToolTip("Segunda función opcional para calcular el área ENTRE f(x) y g(x).")
        f_layout.addWidget(self.input_g)

        fila_ab = QHBoxLayout()
        col_a = QVBoxLayout()
        col_a.addWidget(QLabel("Límite inferior a ="))
        self.input_a = QLineEdit()
        self.input_a.setToolTip("Límite inferior de integración. Acepta expresiones como -pi/2, sqrt(2), etc.")
        col_a.addWidget(self.input_a)
        col_b = QVBoxLayout()
        col_b.addWidget(QLabel("Límite superior b ="))
        self.input_b = QLineEdit()
        self.input_b.setToolTip("Límite superior de integración (debe ser mayor que a).")
        col_b.addWidget(self.input_b)
        fila_ab.addLayout(col_a)
        fila_ab.addLayout(col_b)
        f_layout.addLayout(fila_ab)

        v_izq.addWidget(grupo_func)

        grupo_metodo = QGroupBox("Método de evaluación")
        m_layout = QVBoxLayout(grupo_metodo)

        m_layout.addWidget(QLabel("Subintervalos n:"))
        fila_n = QHBoxLayout()
        self.slider_n = QSlider(Qt.Orientation.Horizontal)
        self.slider_n.setMinimum(1)
        self.slider_n.setMaximum(N_SLIDER_MAX)
        self.slider_n.setToolTip("Mueve el slider para ver, EN VIVO, cómo cambian los 3 métodos al variar n.")
        self.spin_n = QSpinBox()
        self.spin_n.setMinimum(1)
        self.spin_n.setMaximum(1_000_000)
        self.spin_n.setToolTip("Cantidad de subintervalos (rectángulos). Debe ser un entero positivo.")
        fila_n.addWidget(self.slider_n, 3)
        fila_n.addWidget(self.spin_n, 1)
        m_layout.addLayout(fila_n)

        m_layout.addWidget(QLabel("Método principal (desglose y convergencia):"))
        self.combo_metodo = QComboBox()
        self.combo_metodo.addItems(["Izquierda", "Derecha", "Punto Medio", "Trapecios"])
        self.combo_metodo.setCurrentText("Punto Medio")
        self.combo_metodo.setToolTip(
            "Método usado para el desarrollo paso a paso y la curva de convergencia.\n"
            "Los 3 métodos base (Izquierda/Derecha/Punto Medio) siempre pueden superponerse en el gráfico."
        )
        m_layout.addWidget(self.combo_metodo)

        self.check_overlay = QCheckBox("Superponer los 3 métodos en tiempo real")
        self.check_overlay.setChecked(True)
        self.check_overlay.setToolTip("Dibuja simultáneamente Izquierda, Derecha y Punto Medio con colores distintos.")
        m_layout.addWidget(self.check_overlay)

        self.combo_modo = QComboBox()
        self.combo_modo.addItems(["Área", "Longitud de Curva"])
        self.combo_modo.setToolTip("Área bajo la curva (Riemann) o longitud de arco de f(x) en [a,b].")
        m_layout.addWidget(QLabel("Modo:"))
        m_layout.addWidget(self.combo_modo)

        self.check_area_real = QCheckBox("Calcular área geométrica real ∫|f(x)-g(x)| dx")
        self.check_area_real.setToolTip("Útil cuando la función cruza el eje X: la integral neta no coincide con el área geométrica.")
        m_layout.addWidget(self.check_area_real)

        v_izq.addWidget(grupo_metodo)

        fila_botones = QHBoxLayout()
        self.btn_calcular = QPushButton("Calcular")
        self.btn_calcular.setToolTip("Ejecuta el cálculo completo y lo guarda en el historial.")
        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.setProperty("rol", "secundario")
        self.btn_limpiar.setToolTip("Restaura todos los campos a sus valores por defecto.")
        fila_botones.addWidget(self.btn_calcular)
        fila_botones.addWidget(self.btn_limpiar)
        v_izq.addLayout(fila_botones)

        fila_botones2 = QHBoxLayout()
        self.btn_animar = QPushButton("▶ Animar")
        self.btn_animar.setProperty("rol", "secundario")
        self.btn_animar.setToolTip("Muestra cómo los rectángulos se agregan uno a uno y la suma converge.")
        self.btn_exportar = QPushButton("Exportar PNG")
        self.btn_exportar.setProperty("rol", "secundario")
        self.btn_exportar.setToolTip("Guarda el gráfico principal como imagen PNG.")
        fila_botones2.addWidget(self.btn_animar)
        fila_botones2.addWidget(self.btn_exportar)
        v_izq.addLayout(fila_botones2)

        self.label_estado = QLabel("")
        self.label_estado.setWordWrap(True)
        v_izq.addWidget(self.label_estado)

        grupo_hist = QGroupBox("Historial (últimos 10 cálculos)")
        h_layout = QVBoxLayout(grupo_hist)
        self.lista_historial = QListWidget()
        self.lista_historial.setToolTip("Haz clic en un cálculo anterior para restaurar sus parámetros.")
        h_layout.addWidget(self.lista_historial)
        v_izq.addWidget(grupo_hist, stretch=1)

        panel_izq.setMinimumWidth(300)
        panel_izq.setMaximumWidth(380)
        splitter.addWidget(panel_izq)

        # ---------- Columna central: gráficos ----------
        panel_centro = QWidget()
        v_centro = QVBoxLayout(panel_centro)
        v_centro.setContentsMargins(6, 6, 6, 6)

        self.fig_principal = Figure(figsize=(6.5, 4.2), dpi=100)
        self.ax_principal = self.fig_principal.add_subplot(111)
        self.canvas_principal = FigureCanvas(self.fig_principal)
        self.toolbar_principal = NavigationToolbar(self.canvas_principal, self)
        v_centro.addWidget(self.toolbar_principal)
        v_centro.addWidget(self.canvas_principal, stretch=3)

        fila_inferior = QHBoxLayout()

        self.fig_conv = Figure(figsize=(3.2, 3.0), dpi=100)
        self.ax_conv = self.fig_conv.add_subplot(111)
        self.canvas_conv = FigureCanvas(self.fig_conv)
        fila_inferior.addWidget(self.canvas_conv, stretch=1)

        self.pizarra = PizarraDigital()
        fila_inferior.addWidget(self.pizarra, stretch=1)

        v_centro.addLayout(fila_inferior, stretch=2)

        splitter.addWidget(panel_centro)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _conectar_señales(self):
        # --- sincronización slider <-> spinbox (con bloqueo de señales para
        # evitar recursión infinita) ---
        self.slider_n.valueChanged.connect(self._slider_a_spin)
        self.spin_n.valueChanged.connect(self._spin_a_slider)

        # --- controles que disparan recálculo EN VIVO (sin loguear historial) ---
        self.slider_n.valueChanged.connect(lambda _v: self.recalcular_y_dibujar())
        self.combo_metodo.currentIndexChanged.connect(lambda _i: self.recalcular_y_dibujar())
        self.combo_modo.currentIndexChanged.connect(lambda _i: self.recalcular_y_dibujar())
        self.check_overlay.stateChanged.connect(lambda _s: self.recalcular_y_dibujar())
        self.check_area_real.stateChanged.connect(lambda _s: self.recalcular_y_dibujar())

        # Los campos de texto (f, g, a, b) sólo recalculan al presionar Enter
        # o al perder el foco, para no re-parsear en cada tecla.
        self.input_f.editingFinished.connect(lambda: self.recalcular_y_dibujar())
        self.input_g.editingFinished.connect(lambda: self.recalcular_y_dibujar())
        self.input_a.editingFinished.connect(lambda: self.recalcular_y_dibujar())
        self.input_b.editingFinished.connect(lambda: self.recalcular_y_dibujar())

        # --- botones ---
        self.btn_calcular.clicked.connect(lambda: self.recalcular_y_dibujar(loggear_historial=True))
        self.btn_limpiar.clicked.connect(self.limpiar_campos)
        self.btn_animar.clicked.connect(self.animar)
        self.btn_exportar.clicked.connect(self.exportar_png)
        self.lista_historial.itemClicked.connect(self.cargar_desde_historial)

    def _slider_a_spin(self, valor):
        if self.spin_n.value() != valor:
            self.spin_n.blockSignals(True)
            self.spin_n.setValue(valor)
            self.spin_n.blockSignals(False)

    def _spin_a_slider(self, valor):
        valor_slider = min(valor, N_SLIDER_MAX)
        if self.slider_n.value() != valor_slider:
            self.slider_n.blockSignals(True)
            self.slider_n.setValue(valor_slider)
            self.slider_n.blockSignals(False)
        if valor != self.spin_n.value():
            return
        self.recalcular_y_dibujar()

    # ------------------------------------------------------------------
    def _cargar_valores_por_defecto(self):
        self.input_f.setText("-x^2 + 4")
        self.input_g.setText("0")
        self.input_a.setText("-2")
        self.input_b.setText("2")
        self.spin_n.setValue(10)
        self.slider_n.setValue(10)
        self.combo_metodo.setCurrentText("Punto Medio")
        self.combo_modo.setCurrentIndex(0)
        self.check_overlay.setChecked(True)
        self.check_area_real.setChecked(False)

    def limpiar_campos(self):
        self._cargar_valores_por_defecto()
        self._mostrar_estado("")
        self.recalcular_y_dibujar(loggear_historial=False)

    # ------------------------------------------------------------------
    # MENSAJES DE ESTADO (errores / advertencias)
    # ------------------------------------------------------------------
    def _mostrar_estado(self, texto, tipo=None):
        self.label_estado.setText(texto)
        self.label_estado.setProperty("rol", tipo if tipo else "")
        self.label_estado.style().unpolish(self.label_estado)
        self.label_estado.style().polish(self.label_estado)

    # ------------------------------------------------------------------
    # NÚCLEO: VALIDAR, CALCULAR Y DIBUJAR TODO
    # ------------------------------------------------------------------
    def recalcular_y_dibujar(self, loggear_historial: bool = False):
        """
        Función central única. TODO control que afecte el resultado llama a
        esta función. Siempre limpia los ejes y siempre refresca los 3
        lienzos al final, evitando el bug de "selector que no refresca".
        """
        texto_f = self.input_f.text()
        texto_g = self.input_g.text() or "0"
        texto_a = self.input_a.text()
        texto_b = self.input_b.text()
        n = self.spin_n.value()
        metodo = self.combo_metodo.currentText()
        modo = self.combo_modo.currentText()
        superponer = self.check_overlay.isChecked()
        calcular_area_real = self.check_area_real.isChecked()

        # ---------- Validaciones ----------
        try:
            expr_f = mc.parsear_funcion_1d(texto_f)
            expr_g = mc.parsear_funcion_1d(texto_g)
        except mc.ErrorSintaxis as ex:
            self._mostrar_estado(f"⚠ Error de sintaxis: {ex}", "error")
            self.pizarra.limpiar()
            return

        try:
            a = mc.parsear_limite(texto_a)
            b = mc.parsear_limite(texto_b)
        except mc.ErrorSintaxis as ex:
            self._mostrar_estado(f"⚠ {ex}", "error")
            return

        if a >= b:
            self._mostrar_estado("⚠ Error: el límite inferior 'a' debe ser menor que 'b'.", "error")
            return
        if n <= 0:
            self._mostrar_estado("⚠ Error: la cantidad de subintervalos debe ser un entero positivo.", "error")
            return

        # A partir de aquí, todo válido: cacheamos para uso del slider/animación
        self._expr_f, self._expr_g, self._a, self._b = expr_f, expr_g, a, b

        f_num = mc.lambdify_1d(expr_f)
        g_num = mc.lambdify_1d(expr_g)
        expr_neta = expr_f - expr_g

        # Chequeo de valores negativos / no evaluables en [a,b]
        muestreo = np.linspace(a, b, 400)
        y_muestra_f = f_num(muestreo)
        advertencias = []
        if np.any(~np.isfinite(y_muestra_f)):
            advertencias.append("La función no se pudo evaluar en algunos puntos del intervalo.")
        elif np.nanmin(y_muestra_f) < -1e-9:
            advertencias.append(
                "⚠️ La función toma valores negativos en el intervalo. "
                "La integral neta no representa el área geométrica real."
            )

        # ---------- Cálculo de los 3 métodos base + trapecios ----------
        resultados = {}
        for m in ("Izquierda", "Derecha", "Punto Medio", "Trapecios"):
            try:
                suma, xs, ys, dx = mc.suma_riemann(lambda v: f_num(v) - g_num(v), a, b, n, m)
                resultados[m] = (suma, xs, ys, dx)
            except Exception:
                resultados[m] = (float("nan"), np.array([]), np.array([]), (b - a) / n)

        suma_principal, xs_p, ys_p, dx_principal = resultados[metodo]

        # ---------- Integral exacta / longitud exacta ----------
        area_real_valor = None
        if modo == "Área":
            valor_exacto, es_simbolico, F_expr = mc.integral_exacta(expr_neta, a, b)
            if calcular_area_real:
                area_real_valor = mc.integral_valor_absoluto(expr_neta, a, b)
        else:
            valor_exacto, es_simbolico = mc.longitud_arco(expr_f, a, b)
            F_expr = None

        error_abs = abs(valor_exacto - suma_principal) if np.isfinite(suma_principal) else float("nan")
        if abs(valor_exacto) > 1e-12:
            error_rel = error_abs / abs(valor_exacto) * 100
        else:
            error_rel = None

        # ---------- Dibujar gráfico principal ----------
        self._dibujar_principal(
            expr_f, expr_g, a, b, n, metodo, modo, superponer, resultados,
            area_real_valor
        )

        # ---------- Dibujar convergencia ----------
        self._dibujar_convergencia(expr_f, expr_g, a, b, n, metodo, modo, valor_exacto)

        # ---------- Dibujar pizarra LaTeX ----------
        self._dibujar_pizarra(
            expr_f, F_expr, a, b, n, dx_principal, suma_principal, valor_exacto,
            error_abs, error_rel, es_simbolico, modo, metodo, area_real_valor
        )

        # ---------- Mensajes de estado ----------
        if advertencias:
            self._mostrar_estado(" / ".join(advertencias), "advertencia")
        else:
            self._mostrar_estado("✔ Cálculo realizado correctamente.", None)

        # ---------- Historial ----------
        if loggear_historial:
            self._agregar_historial(
                texto_f, texto_g, texto_a, texto_b, n, metodo, modo,
                superponer, calcular_area_real, suma_principal, valor_exacto
            )

    # ------------------------------------------------------------------
    def _colores_metodo(self, t):
        return {
            "Izquierda": t["izquierda"],
            "Derecha": t["derecha"],
            "Punto Medio": t["medio"],
            "Trapecios": t["trapecio"],
        }

    def _dibujar_principal(self, expr_f, expr_g, a, b, n, metodo, modo,
                            superponer, resultados, area_real_valor):
        t = self.tema
        ax = self.ax_principal
        ax.clear()  # <- clave para evitar el bug de refresco del selector
        ax.set_facecolor(t["axes_face"])
        self.fig_principal.patch.set_facecolor(t["canvas_face"])

        f_num = mc.lambdify_1d(expr_f)
        g_num = mc.lambdify_1d(expr_g)
        margen = (b - a) * 0.15 if b > a else 1.0
        x_curva = np.linspace(a - margen, b + margen, 800)
        y_f = f_num(x_curva)
        y_g = g_num(x_curva)

        ax.plot(x_curva, y_f, color=t["curva"], linewidth=2.2, label="f(x)")
        if not np.allclose(np.nan_to_num(y_g), 0):
            ax.plot(x_curva, y_g, color=t["curva_g"], linewidth=1.6,
                    linestyle="--", label="g(x)")

        if modo == "Longitud de Curva":
            xs_p = np.linspace(a, b, n + 1)
            ys_p = f_num(xs_p)
            ax.plot(xs_p, ys_p, color=t["trapecio"], linewidth=2.4,
                    marker="o", markersize=4, label="Aproximación poligonal")
        else:
            colores = self._colores_metodo(t)
            metodos_a_dibujar = ["Izquierda", "Derecha", "Punto Medio"] if superponer else [metodo]
            if metodo == "Trapecios" and metodo not in metodos_a_dibujar:
                metodos_a_dibujar.append("Trapecios")

            # NOTA DE RENDIMIENTO: en vez de dibujar un parche Rectangle/fill
            # por cada subintervalo (lento e incluso inutilizable con n grande;
            # p.ej. n=50 000 tardaba ~25 s por método), se construye UNA sola
            # figura vectorizada por método con fill_between(..., step=...).
            # Es matemáticamente idéntico a dibujar los rectángulos uno por
            # uno, pero se renderiza en milisegundos sin importar qué tan
            # grande sea n.
            edges = a + ((b - a) / n) * np.arange(n + 1)  # bordes reales de los n subintervalos

            for m in metodos_a_dibujar:
                suma, xs, ys, dx = resultados[m]
                if xs.size == 0:
                    continue
                color = colores[m]
                if m == "Trapecios":
                    # El "techo" de cada trapecio es la recta entre f(borde_i)
                    # y f(borde_i+1): basta evaluar f y g en los propios
                    # bordes y unir los puntos con líneas rectas normales.
                    y_top = f_num(edges)
                    y_bottom = g_num(edges)
                    ax.fill_between(edges, y_bottom, y_top, facecolor=color,
                                     edgecolor=color, alpha=0.25, linewidth=1.0,
                                     label=f"Trapecios (Σ={suma:.4f})")
                else:
                    # Dentro de cada subintervalo la altura del rectángulo es
                    # CONSTANTE (la evaluada en el punto que dicta el método),
                    # por eso alcanza con dibujar un "escalón" (step='post')
                    # sobre los bordes reales del subintervalo: coincide
                    # exactamente con los rectángulos verdaderos del método.
                    y_f_paso = np.append(f_num(xs), f_num(xs)[-1])
                    y_g_paso = np.append(g_num(xs), g_num(xs)[-1])
                    ax.fill_between(edges, y_g_paso, y_f_paso, step="post",
                                     facecolor=color, alpha=0.35,
                                     edgecolor=color, linewidth=1.0,
                                     label=f"{m} (Σ={suma:.4f})")

        ax.axhline(0, color=t["texto_mpl"], linewidth=0.8, alpha=0.6)
        ax.axvline(0, color=t["texto_mpl"], linewidth=0.8, alpha=0.6)
        ax.grid(True, linestyle="--", alpha=0.4, color=t["grid"])
        ax.tick_params(colors=t["texto_mpl"])
        for spine in ax.spines.values():
            spine.set_color(t["grid"])
        ax.set_xlabel("x", color=t["texto_mpl"])
        ax.set_ylabel("f(x)", color=t["texto_mpl"])

        titulo_extra = ""
        if area_real_valor is not None:
            titulo_extra = f"  |  Área real ∫|f-g|dx ≈ {area_real_valor:.5f}"
        ax.set_title(f"Suma de Riemann — n={n}{titulo_extra}", color=t["texto_mpl"], fontsize=11)
        leg = ax.legend(loc="best", fontsize=8, framealpha=0.85)
        if leg:
            leg.get_frame().set_facecolor(t["panel"])
            for text in leg.get_texts():
                text.set_color(t["texto_mpl"])

        self.canvas_principal.draw_idle()

    def _dibujar_convergencia(self, expr_f, expr_g, a, b, n, metodo, modo, valor_exacto):
        t = self.tema
        ax = self.ax_conv
        ax.clear()
        ax.set_facecolor(t["axes_face"])
        self.fig_conv.patch.set_facecolor(t["canvas_face"])

        f_num = mc.lambdify_1d(expr_f)
        g_num = mc.lambdify_1d(expr_g)

        pasos_n = np.unique(np.linspace(1, max(n, 1), num=min(n, 30), dtype=int))
        errores = []
        for n_paso in pasos_n:
            try:
                if modo == "Área":
                    suma_paso, _, _, _ = mc.suma_riemann(
                        lambda v: f_num(v) - g_num(v), a, b, int(n_paso),
                        metodo if metodo != "Trapecios" else "Trapecios"
                    )
                else:
                    suma_paso = mc.longitud_arco_aproximada(expr_f, a, b, int(n_paso))
                errores.append(abs(valor_exacto - suma_paso))
            except Exception:
                errores.append(np.nan)

        ax.plot(pasos_n, errores, color=t["convergencia"], marker="o",
                markersize=4, linewidth=1.6)
        ax.set_yscale("log") if np.all(np.array(errores) > 0) else None
        ax.set_xlabel("n", color=t["texto_mpl"], fontsize=9)
        ax.set_ylabel("Error absoluto", color=t["texto_mpl"], fontsize=9)
        ax.set_title("Convergencia del error", color=t["texto_mpl"], fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.4, color=t["grid"])
        ax.tick_params(colors=t["texto_mpl"], labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(t["grid"])

        self.canvas_conv.draw_idle()

    def _dibujar_pizarra(self, expr_f, F_expr, a, b, n, dx, suma, valor_exacto,
                          error_abs, error_rel, es_simbolico, modo, metodo,
                          area_real_valor):
        lineas = []
        lineas.append((f"Desarrollo — método: {metodo}  |  modo: {modo}",
                        {"color": "acento", "fontsize": 13.5, "fontweight": "bold", "salto": 0.17}))

        try:
            f_latex = sp.latex(expr_f)
            lineas.append((f"$f(x) = {f_latex}$", {"fontsize": 13, "salto": 0.14}))
        except Exception:
            lineas.append((f"f(x) = {expr_f}", {"fontsize": 13, "salto": 0.14}))

        if modo == "Área":
            if F_expr is not None:
                try:
                    F_latex = sp.latex(F_expr)
                    lineas.append((f"$F(x) = \\int f(x)\\,dx = {F_latex} + C$", {"fontsize": 12.5, "salto": 0.14}))
                except Exception:
                    lineas.append((f"F(x) = {F_expr} + C", {"fontsize": 12.5, "salto": 0.14}))
                try:
                    Fb = float(sp.N(F_expr.subs(mc.X, b)))
                    Fa = float(sp.N(F_expr.subs(mc.X, a)))
                    lineas.append((
                        f"$F({b:.4g}) - F({a:.4g}) = {Fb:.6f} - ({Fa:.6f}) = {valor_exacto:.6f}$",
                        {"fontsize": 12.5, "salto": 0.14}
                    ))
                except Exception:
                    lineas.append((f"F(b) - F(a) = {valor_exacto:.6f}", {"fontsize": 12.5, "salto": 0.14}))
            else:
                lineas.append((
                    f"Integral no elemental: se usó aproximación numérica fina ≈ {valor_exacto:.6f}",
                    {"fontsize": 12, "salto": 0.14}
                ))
        else:
            etiqueta = "exacta (simbólica)" if es_simbolico else "numérica de alta precisión"
            lineas.append((
                f"Longitud de arco ({etiqueta}): $L = \\int_{{{a:.4g}}}^{{{b:.4g}}} \\sqrt{{1+f'(x)^2}}\\,dx = {valor_exacto:.6f}$",
                {"fontsize": 12.3, "salto": 0.16}
            ))

        lineas.append((
            f"$\\Delta x = \\dfrac{{b-a}}{{n}} = \\dfrac{{{b:.4g} - ({a:.4g})}}{{{n}}} = {dx:.6f}$",
            {"fontsize": 12.5, "salto": 0.14}
        ))
        lineas.append((
            f"Suma aproximada (n={n}, {metodo}) = {suma:.6f}",
            {"fontsize": 12.5, "salto": 0.14}
        ))
        if error_rel is not None:
            lineas.append((
                f"Error absoluto = {error_abs:.6f}      Error relativo = {error_rel:.4f} %",
                {"fontsize": 12.2, "salto": 0.14}
            ))
        else:
            lineas.append((
                f"Error absoluto = {error_abs:.6f}      (error relativo no definido: valor exacto ≈ 0)",
                {"fontsize": 11.5, "salto": 0.14}
            ))
        if area_real_valor is not None:
            lineas.append((
                f"Área geométrica real: $\\int |f(x)-g(x)|\\,dx \\approx {area_real_valor:.6f}$",
                {"fontsize": 12.2, "salto": 0.14}
            ))

        self.pizarra.mostrar_lineas(lineas)

    # ------------------------------------------------------------------
    # HISTORIAL
    # ------------------------------------------------------------------
    def _agregar_historial(self, f_txt, g_txt, a_txt, b_txt, n, metodo, modo,
                            overlay, area_real, suma, exacto):
        registro = {
            "f": f_txt, "g": g_txt, "a": a_txt, "b": b_txt, "n": n,
            "metodo": metodo, "modo": modo, "overlay": overlay,
            "area_real": area_real, "suma": suma, "exacto": exacto,
        }
        self._historial.insert(0, registro)
        self._historial = self._historial[:MAX_HISTORIAL]
        self._refrescar_lista_historial()

    def _refrescar_lista_historial(self):
        self.lista_historial.clear()
        for reg in self._historial:
            texto = (f"f(x)={reg['f']}  [{reg['a']},{reg['b']}]  n={reg['n']}  "
                     f"{reg['metodo']}  → Σ={reg['suma']:.4f}")
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, reg)
            self.lista_historial.addItem(item)

    def cargar_desde_historial(self, item: QListWidgetItem):
        reg = item.data(Qt.ItemDataRole.UserRole)
        if not reg:
            return
        self.input_f.setText(reg["f"])
        self.input_g.setText(reg["g"])
        self.input_a.setText(reg["a"])
        self.input_b.setText(reg["b"])
        self.spin_n.setValue(reg["n"])
        self.combo_metodo.setCurrentText(reg["metodo"])
        self.combo_modo.setCurrentText(reg["modo"])
        self.check_overlay.setChecked(reg["overlay"])
        self.check_area_real.setChecked(reg["area_real"])
        self.recalcular_y_dibujar(loggear_historial=False)

    # ------------------------------------------------------------------
    # ANIMACIÓN PROGRESIVA
    # ------------------------------------------------------------------
    def animar(self):
        if self._expr_f is None:
            return
        n_final = self.spin_n.value()
        n_final_anim = min(n_final, 60)  # límite razonable para que la animación sea fluida
        self._anim_n_actual = 1
        self._anim_n_final = n_final_anim
        self.btn_animar.setEnabled(False)
        self._timer_anim = QTimer(self)
        self._timer_anim.timeout.connect(self._paso_animacion)
        self._timer_anim.start(120)

    def _paso_animacion(self):
        t = self.tema
        metodo = self.combo_metodo.currentText()
        if metodo == "Trapecios":
            metodo_anim = "Punto Medio"
        else:
            metodo_anim = metodo
        a, b = self._a, self._b
        expr_f, expr_g = self._expr_f, self._expr_g
        f_num = mc.lambdify_1d(expr_f)
        g_num = mc.lambdify_1d(expr_g)

        n_actual = self._anim_n_actual
        suma, xs, ys, dx = mc.suma_riemann(lambda v: f_num(v) - g_num(v), a, b, n_actual, metodo_anim)

        ax = self.ax_principal
        ax.clear()
        ax.set_facecolor(t["axes_face"])
        self.fig_principal.patch.set_facecolor(t["canvas_face"])
        margen = (b - a) * 0.15
        x_curva = np.linspace(a - margen, b + margen, 400)
        ax.plot(x_curva, f_num(x_curva), color=t["curva"], linewidth=2.0, label="f(x)")

        color = t["medio"]
        if metodo_anim == "Izquierda":
            left = xs
        elif metodo_anim == "Derecha":
            left = xs - dx
        else:
            left = xs - dx / 2
        ax.bar(left, ys, width=dx, align="edge", color=color, alpha=0.4, edgecolor=color)

        ax.axhline(0, color=t["texto_mpl"], linewidth=0.8, alpha=0.6)
        ax.grid(True, linestyle="--", alpha=0.4, color=t["grid"])
        ax.tick_params(colors=t["texto_mpl"])
        for spine in ax.spines.values():
            spine.set_color(t["grid"])
        ax.set_title(f"Animando… n={n_actual}/{self._anim_n_final}  Σ≈{suma:.5f}",
                     color=t["texto_mpl"], fontsize=11)
        self.canvas_principal.draw_idle()

        if n_actual >= self._anim_n_final:
            self._timer_anim.stop()
            self.btn_animar.setEnabled(True)
            self.recalcular_y_dibujar(loggear_historial=False)
        else:
            paso = max(1, self._anim_n_final // 30)
            self._anim_n_actual = min(n_actual + paso, self._anim_n_final)

    # ------------------------------------------------------------------
    # EXPORTAR
    # ------------------------------------------------------------------
    def exportar_png(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar gráfico", "riemann_2d.png", "Imagen PNG (*.png)")
        if ruta:
            try:
                self.fig_principal.savefig(ruta, dpi=150, facecolor=self.fig_principal.get_facecolor())
                QMessageBox.information(self, "Exportado", f"Gráfico guardado en:\n{ruta}")
            except Exception as ex:
                QMessageBox.critical(self, "Error al exportar", str(ex))

    # ------------------------------------------------------------------
    # TEMA (modo oscuro/claro)
    # ------------------------------------------------------------------
    def aplicar_tema(self, tema: dict):
        self.tema = tema
        self.pizarra.aplicar_tema(tema)
        if self._expr_f is not None:
            self.recalcular_y_dibujar(loggear_historial=False)
