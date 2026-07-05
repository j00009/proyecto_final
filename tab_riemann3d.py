# -*- coding: utf-8 -*-
"""
tab_riemann3d.py
================
Pestaña 2: "Riemann 3D (Volúmenes)". Adaptación a PyQt6 de la lógica del
script original (superficie translúcida + prismas bar3d), agregando:
- Parser de sintaxis amigable (mismo mathcore que la pestaña 2D).
- Límites de x e y configurables (el script original los tenía fijos).
- Comparación contra un volumen de referencia (numérico muy fino) con
  error absoluto y relativo.
- Pizarra digital con el desglose del cálculo.
- Modo oscuro/claro sincronizado con el resto de la app.
- Validaciones (sintaxis inválida, límites invertidos, n<=0).
"""

import numpy as np
import sympy as sp

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QLabel, QLineEdit,
    QSpinBox, QSlider, QComboBox, QPushButton, QSplitter, QFileDialog,
    QMessageBox
)
from PyQt6.QtCore import Qt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (necesario para projection='3d')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import mathcore as mc
from pizarra import PizarraDigital


class Riemann3DTab(QWidget):

    def __init__(self, tema_actual: dict, parent=None):
        super().__init__(parent)
        self.tema = tema_actual
        self._construir_ui()
        self._conectar_señales()
        self.aplicar_tema(self.tema)
        self._cargar_valores_por_defecto()
        self.recalcular_y_dibujar()

    # ------------------------------------------------------------------
    def _construir_ui(self):
        layout_raiz = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout_raiz.addWidget(splitter)

        panel_izq = QWidget()
        v = QVBoxLayout(panel_izq)

        grupo = QGroupBox("Función y dominio")
        gl = QVBoxLayout(grupo)
        gl.addWidget(QLabel("f(x, y) ="))
        self.input_f = QLineEdit()
        self.input_f.setToolTip(
            "Sintaxis amigable: x^2 + y^2, sen(x)+cos(y), sqrt(x^2+y^2), etc."
        )
        gl.addWidget(self.input_f)

        fila_x = QHBoxLayout()
        col_xa = QVBoxLayout()
        col_xa.addWidget(QLabel("x mínimo:"))
        self.input_xa = QLineEdit()
        col_xa.addWidget(self.input_xa)
        col_xb = QVBoxLayout()
        col_xb.addWidget(QLabel("x máximo:"))
        self.input_xb = QLineEdit()
        col_xb.addWidget(self.input_xb)
        fila_x.addLayout(col_xa)
        fila_x.addLayout(col_xb)
        gl.addLayout(fila_x)

        fila_y = QHBoxLayout()
        col_ya = QVBoxLayout()
        col_ya.addWidget(QLabel("y mínimo:"))
        self.input_ya = QLineEdit()
        col_ya.addWidget(self.input_ya)
        col_yb = QVBoxLayout()
        col_yb.addWidget(QLabel("y máximo:"))
        self.input_yb = QLineEdit()
        col_yb.addWidget(self.input_yb)
        fila_y.addLayout(col_ya)
        fila_y.addLayout(col_yb)
        gl.addLayout(fila_y)

        v.addWidget(grupo)

        grupo2 = QGroupBox("Malla de prismas")
        gl2 = QVBoxLayout(grupo2)
        gl2.addWidget(QLabel("Cuadrícula n × n:"))
        fila_n = QHBoxLayout()
        self.slider_n = QSlider(Qt.Orientation.Horizontal)
        self.slider_n.setMinimum(2)
        self.slider_n.setMaximum(30)
        self.slider_n.setToolTip("Mueve el slider para ver el volumen aproximado EN VIVO.")
        self.spin_n = QSpinBox()
        self.spin_n.setMinimum(2)
        self.spin_n.setMaximum(30)
        fila_n.addWidget(self.slider_n, 3)
        fila_n.addWidget(self.spin_n, 1)
        gl2.addLayout(fila_n)

        gl2.addWidget(QLabel("Punto de evaluación por prisma:"))
        self.combo_punto = QComboBox()
        self.combo_punto.addItems(["Punto Medio", "Esquina inferior izquierda"])
        self.combo_punto.setToolTip("Vértice/punto del sub-rectángulo usado para la altura del prisma.")
        gl2.addWidget(self.combo_punto)

        v.addWidget(grupo2)

        fila_botones = QHBoxLayout()
        self.btn_calcular = QPushButton("Calcular")
        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.setProperty("rol", "secundario")
        fila_botones.addWidget(self.btn_calcular)
        fila_botones.addWidget(self.btn_limpiar)
        v.addLayout(fila_botones)

        self.btn_exportar = QPushButton("Exportar PNG")
        self.btn_exportar.setProperty("rol", "secundario")
        v.addWidget(self.btn_exportar)

        self.label_estado = QLabel("")
        self.label_estado.setWordWrap(True)
        v.addWidget(self.label_estado)
        v.addStretch(1)

        panel_izq.setMinimumWidth(280)
        panel_izq.setMaximumWidth(360)
        splitter.addWidget(panel_izq)

        panel_centro = QWidget()
        vc = QVBoxLayout(panel_centro)
        self.fig_3d = Figure(figsize=(6.5, 5.2), dpi=100)
        self.ax_3d = self.fig_3d.add_subplot(111, projection="3d")
        self.canvas_3d = FigureCanvas(self.fig_3d)
        vc.addWidget(self.canvas_3d, stretch=3)

        self.pizarra = PizarraDigital()
        vc.addWidget(self.pizarra, stretch=1)

        splitter.addWidget(panel_centro)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _conectar_señales(self):
        self.slider_n.valueChanged.connect(self._slider_a_spin)
        self.spin_n.valueChanged.connect(self._spin_a_slider)
        self.slider_n.valueChanged.connect(lambda _v: self.recalcular_y_dibujar())
        self.combo_punto.currentIndexChanged.connect(lambda _i: self.recalcular_y_dibujar())

        self.input_f.editingFinished.connect(self.recalcular_y_dibujar)
        self.input_xa.editingFinished.connect(self.recalcular_y_dibujar)
        self.input_xb.editingFinished.connect(self.recalcular_y_dibujar)
        self.input_ya.editingFinished.connect(self.recalcular_y_dibujar)
        self.input_yb.editingFinished.connect(self.recalcular_y_dibujar)

        self.btn_calcular.clicked.connect(self.recalcular_y_dibujar)
        self.btn_limpiar.clicked.connect(self.limpiar_campos)
        self.btn_exportar.clicked.connect(self.exportar_png)

    def _slider_a_spin(self, valor):
        if self.spin_n.value() != valor:
            self.spin_n.blockSignals(True)
            self.spin_n.setValue(valor)
            self.spin_n.blockSignals(False)

    def _spin_a_slider(self, valor):
        if self.slider_n.value() != valor:
            self.slider_n.blockSignals(True)
            self.slider_n.setValue(valor)
            self.slider_n.blockSignals(False)
        self.recalcular_y_dibujar()

    # ------------------------------------------------------------------
    def _cargar_valores_por_defecto(self):
        self.input_f.setText("sen(x) + cos(y) + 2")
        self.input_xa.setText("-1.5")
        self.input_xb.setText("1.5")
        self.input_ya.setText("-1.5")
        self.input_yb.setText("1.5")
        self.spin_n.setValue(6)
        self.slider_n.setValue(6)
        self.combo_punto.setCurrentIndex(0)

    def limpiar_campos(self):
        self._cargar_valores_por_defecto()
        self.label_estado.setText("")
        self.recalcular_y_dibujar()

    def _mostrar_estado(self, texto, tipo=None):
        self.label_estado.setText(texto)
        self.label_estado.setProperty("rol", tipo if tipo else "")
        self.label_estado.style().unpolish(self.label_estado)
        self.label_estado.style().polish(self.label_estado)

    # ------------------------------------------------------------------
    def recalcular_y_dibujar(self):
        try:
            expr_f = mc.parsear_funcion_2d(self.input_f.text())
        except mc.ErrorSintaxis as ex:
            self._mostrar_estado(f"⚠ Error de sintaxis: {ex}", "error")
            return

        try:
            xa = mc.parsear_limite(self.input_xa.text())
            xb = mc.parsear_limite(self.input_xb.text())
            ya = mc.parsear_limite(self.input_ya.text())
            yb = mc.parsear_limite(self.input_yb.text())
        except mc.ErrorSintaxis as ex:
            self._mostrar_estado(f"⚠ {ex}", "error")
            return

        if xa >= xb or ya >= yb:
            self._mostrar_estado("⚠ Error: los límites mínimos deben ser menores que los máximos.", "error")
            return

        n = self.spin_n.value()
        punto = self.combo_punto.currentText()

        f_num2d = mc.lambdify_2d(expr_f)

        volumen, x_pos, y_pos, dx, dy, alturas = mc.suma_riemann_3d(f_num2d, xa, xb, ya, yb, n, punto)
        volumen_ref = mc.volumen_referencia_3d(f_num2d, xa, xb, ya, yb)
        error_abs = abs(volumen_ref - volumen)
        error_rel = (error_abs / abs(volumen_ref) * 100) if abs(volumen_ref) > 1e-12 else None

        # Advertencia de valores negativos (altura negativa => "resta" volumen)
        advertencia = ""
        if np.nanmin(alturas) < -1e-9:
            advertencia = "⚠️ f(x,y) toma valores negativos en la región: el volumen neto no es un volumen geométrico puro."

        self._dibujar_3d(expr_f, xa, xb, ya, yb, n, x_pos, y_pos, dx, dy, alturas, volumen, f_num2d)
        self._dibujar_pizarra(expr_f, xa, xb, ya, yb, n, dx, dy, volumen, volumen_ref, error_abs, error_rel, punto)

        if advertencia:
            self._mostrar_estado(advertencia, "advertencia")
        else:
            self._mostrar_estado("✔ Cálculo realizado correctamente.", None)

    # ------------------------------------------------------------------
    def _dibujar_3d(self, expr_f, xa, xb, ya, yb, n, x_pos, y_pos, dx, dy, alturas, volumen, f_num2d):
        t = self.tema
        ax = self.ax_3d
        ax.clear()
        self.fig_3d.patch.set_facecolor(t["canvas_face"])
        try:
            ax.set_facecolor(t["axes_face"])
        except Exception:
            pass

        X_mesh, Y_mesh = np.meshgrid(np.linspace(xa, xb, 60), np.linspace(ya, yb, 60))
        Z_mesh = f_num2d(X_mesh, Y_mesh)
        Z_mesh = np.nan_to_num(Z_mesh, nan=0.0)

        ax.plot_surface(X_mesh, Y_mesh, Z_mesh, alpha=0.25, cmap=t["superficie_cmap"], edgecolor="none")

        z_pos = np.zeros_like(x_pos)
        bars_dx = np.ones_like(x_pos) * dx
        bars_dy = np.ones_like(y_pos) * dy
        ax.bar3d(x_pos, y_pos, z_pos, bars_dx, bars_dy, alturas,
                  color=t["trapecio"], alpha=0.55, edgecolor=t["derecha"], shade=True)

        ax.set_title(f"Suma de Riemann 3D — {n}×{n} prismas | Vol. aprox ≈ {volumen:.4f}",
                     color=t["texto_mpl"], fontsize=11)
        ax.set_xlabel("x", color=t["texto_mpl"])
        ax.set_ylabel("y", color=t["texto_mpl"])
        ax.set_zlabel("z = f(x,y)", color=t["texto_mpl"])
        ax.tick_params(colors=t["texto_mpl"])

        max_h = np.max(alturas) if alturas.size else 0
        max_m = np.max(Z_mesh) if Z_mesh.size else 0
        lim_sup = max(max_h, max_m, 0)
        ax.set_zlim(min(0, np.min(alturas) if alturas.size else 0), lim_sup * 1.2 if lim_sup > 0 else 5)

        self.canvas_3d.draw_idle()

    def _dibujar_pizarra(self, expr_f, xa, xb, ya, yb, n, dx, dy, volumen, volumen_ref, error_abs, error_rel, punto):
        lineas = []
        lineas.append(("Desglose del volumen aproximado",
                        {"color": "acento", "fontsize": 13.5, "fontweight": "bold", "salto": 0.17}))
        try:
            f_latex = sp.latex(expr_f)
            lineas.append((f"$f(x,y) = {f_latex}$", {"fontsize": 13, "salto": 0.15}))
        except Exception:
            lineas.append((f"f(x,y) = {expr_f}", {"fontsize": 13, "salto": 0.15}))

        lineas.append((
            f"$\\Delta x = \\dfrac{{{xb:.4g}-({xa:.4g})}}{{{n}}} = {dx:.5f}$"
            f"\\quad\\quad$\\Delta y = \\dfrac{{{yb:.4g}-({ya:.4g})}}{{{n}}} = {dy:.5f}$",
            {"fontsize": 12.2, "salto": 0.15}
        ))
        lineas.append((
            f"Evaluación por prisma: {punto}",
            {"fontsize": 11.5, "salto": 0.14}
        ))
        lineas.append((
            f"$V \\approx \\sum f(x_i,y_i)\\,\\Delta x\\,\\Delta y = {volumen:.6f}$",
            {"fontsize": 12.5, "salto": 0.16}
        ))
        lineas.append((
            f"Volumen de referencia (malla fina 400×400) ≈ {volumen_ref:.6f}",
            {"fontsize": 11.8, "salto": 0.15}
        ))
        if error_rel is not None:
            lineas.append((
                f"Error absoluto = {error_abs:.6f}      Error relativo = {error_rel:.4f} %",
                {"fontsize": 12, "salto": 0.14}
            ))
        else:
            lineas.append((
                f"Error absoluto = {error_abs:.6f}",
                {"fontsize": 12, "salto": 0.14}
            ))

        self.pizarra.mostrar_lineas(lineas)

    # ------------------------------------------------------------------
    def exportar_png(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar gráfico", "riemann_3d.png", "Imagen PNG (*.png)")
        if ruta:
            try:
                self.fig_3d.savefig(ruta, dpi=150, facecolor=self.fig_3d.get_facecolor())
                QMessageBox.information(self, "Exportado", f"Gráfico guardado en:\n{ruta}")
            except Exception as ex:
                QMessageBox.critical(self, "Error al exportar", str(ex))

    # ------------------------------------------------------------------
    def aplicar_tema(self, tema: dict):
        self.tema = tema
        self.pizarra.aplicar_tema(tema)
        self.recalcular_y_dibujar()
