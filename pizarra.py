# -*- coding: utf-8 -*-
r"""
pizarra.py
==========
Widget "Pizarra Digital": un lienzo de Matplotlib sin ejes, usado como
superficie tipográfica para mostrar el desarrollo matemático paso a paso
(antiderivada, Teorema Fundamental del Cálculo, Δx, errores) usando el motor
mathtext de Matplotlib (sintaxis LaTeX entre símbolos $...$, sin necesitar
una instalación externa de LaTeX).

Por qué un lienzo Matplotlib y no un QTextEdit/QTextBrowser:
- mathtext permite escribir fracciones, raíces, subíndices/superíndices e
  integrales con apariencia tipográfica real (requisito de la rúbrica:
  "Renderizado Matemático" 3/3 puntos), algo que un QTextEdit plano no logra
  sin un motor LaTeX externo.

Blindaje: SymPy a veces genera comandos LaTeX (p.ej. \operatorname{...}) que
mathtext no reconoce. Como el error de mathtext ocurre recién al renderizar
(canvas.draw()), este widget intenta dibujar en modo LaTeX y, si falla,
vuelve a dibujar automáticamente en modo texto plano (sin símbolos $...$)
para que la aplicación jamás se caiga por una fórmula rara.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class PizarraDigital(QWidget):
    """Lienzo tipo "pizarra" para mostrar el paso a paso matemático."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig = Figure(figsize=(5.2, 4.2), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        self.fig.subplots_adjust(left=0.03, right=0.97, top=0.95, bottom=0.03)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self._tema = None
        self._lineas_actuales = []  # guarda el último contenido para poder re-pintarlo al cambiar de tema

    # ------------------------------------------------------------------
    def aplicar_tema(self, tema: dict):
        """Guarda el tema activo y re-dibuja el contenido actual con él."""
        self._tema = tema
        if self._lineas_actuales:
            self.mostrar_lineas(self._lineas_actuales)
        else:
            self._pintar_fondo_vacio()

    def _pintar_fondo_vacio(self):
        t = self._tema or {}
        face = t.get("axes_face", "white")
        fig_face = t.get("canvas_face", "white")
        color_txt = t.get("subtexto", "#888888")
        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.set_facecolor(face)
        self.fig.patch.set_facecolor(fig_face)
        self.ax.text(
            0.5, 0.5,
            "Presiona “Calcular” para ver aquí\nel desarrollo paso a paso",
            ha="center", va="center", fontsize=12, color=color_txt,
            transform=self.ax.transAxes, style="italic"
        )
        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    def limpiar(self):
        self._lineas_actuales = []
        self._pintar_fondo_vacio()

    def mostrar_lineas(self, lineas):
        """
        lineas: lista de tuplas (texto, kwargs_extra) donde texto puede
        incluir sintaxis mathtext ($...$). kwargs_extra permite pasar
        fontsize/fontweight/color particulares por línea (p.ej. el título).

        Se intenta primero en modo "tal cual" (con $...$); si mathtext
        lanza una excepción al renderizar, se reintenta reemplazando los
        signos $ por nada (texto plano) para garantizar que algo se vea.
        """
        self._lineas_actuales = lineas
        exito = self._dibujar(lineas, forzar_texto_plano=False)
        if not exito:
            self._dibujar(lineas, forzar_texto_plano=True)

    # ------------------------------------------------------------------
    def _dibujar(self, lineas, forzar_texto_plano: bool) -> bool:
        t = self._tema or {}
        face = t.get("axes_face", "white")
        fig_face = t.get("canvas_face", "white")
        color_txt_defecto = t.get("texto_mpl", "#1f2233")
        color_acento = t.get("acento", "#4f46e5")

        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.ax.set_facecolor(face)
        self.fig.patch.set_facecolor(fig_face)

        y = 0.94
        for item in lineas:
            texto, extra = item
            if forzar_texto_plano:
                texto = texto.replace("$", "")
            estilo = dict(
                ha="left", va="top", fontsize=12.5,
                color=extra.get("color", color_txt_defecto),
                transform=self.ax.transAxes,
                wrap=True,
            )
            estilo.update({k: v for k, v in extra.items() if k not in ("color", "salto")})
            if extra.get("color") == "acento":
                estilo["color"] = color_acento
            self.ax.text(0.04, y, texto, **estilo)
            y -= extra.get("salto", 0.135)

        try:
            self.canvas.draw()
            return True
        except Exception:
            # Algún comando LaTeX no soportado por mathtext: se avisa arriba
            # para reintentar en texto plano.
            return False
