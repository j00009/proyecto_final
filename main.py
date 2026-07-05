# -*- coding: utf-8 -*-
"""
main.py
=======
Punto de entrada de la aplicación. Crea la ventana principal con el
QTabWidget de 2 pestañas y el botón de modo oscuro/claro que se propaga a
toda la interfaz y a todos los lienzos de Matplotlib (curva, convergencia y
pizarra LaTeX) de ambas pestañas, evitando que algún texto quede invisible
al cambiar de tema.

Ejecutar con:  python3 main.py
"""

import sys
from PyQt6.QtWidgets import QMainWindow, QApplication, QTabWidget, QToolBar, QPushButton, QLabel
from PyQt6.QtCore import Qt

from temas import TEMA_CLARO, TEMA_OSCURO, generar_qss
from tab_riemann2d import RiemannTab2D
from tab_riemann3d import Riemann3DTab


class VentanaPrincipal(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visualizador de la Suma de Riemann y Antiderivadas")
        self.resize(1440, 900)

        self.modo_oscuro = False
        self.tema_actual = TEMA_CLARO

        self._construir_toolbar()

        self.tabs = QTabWidget()
        self.tab1 = RiemannTab2D(self.tema_actual)
        self.tab2 = Riemann3DTab(self.tema_actual)
        self.tabs.addTab(self.tab1, "Suma de Riemann 2D && Antiderivadas")
        self.tabs.addTab(self.tab2, "Riemann 3D (Volúmenes)")
        self.setCentralWidget(self.tabs)

        self._aplicar_tema_global()

    # ------------------------------------------------------------------
    def _construir_toolbar(self):
        toolbar = QToolBar("Preferencias")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        titulo = QLabel("  📐 Suma de Riemann y Antiderivadas")
        titulo.setStyleSheet("font-size: 15px; font-weight: 700;")
        toolbar.addWidget(titulo)

        # Empuja el botón de tema a la derecha
        spacer = QLabel()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(), spacer.sizePolicy().verticalPolicy())
        toolbar.addWidget(spacer)

        self.btn_tema = QPushButton("🌙 Modo Oscuro")
        self.btn_tema.setToolTip("Alterna entre modo claro y modo oscuro en toda la aplicación.")
        self.btn_tema.clicked.connect(self.alternar_tema)
        toolbar.addWidget(self.btn_tema)

    # ------------------------------------------------------------------
    def alternar_tema(self):
        self.modo_oscuro = not self.modo_oscuro
        self.tema_actual = TEMA_OSCURO if self.modo_oscuro else TEMA_CLARO
        self.btn_tema.setText("☀ Modo Claro" if self.modo_oscuro else "🌙 Modo Oscuro")
        self._aplicar_tema_global()

    def _aplicar_tema_global(self):
        app = QApplication.instance()
        app.setStyleSheet(generar_qss(self.tema_actual))
        # Propaga el tema a cada pestaña, que a su vez redibuja sus 3 lienzos
        # (principal, convergencia/superficie y pizarra LaTeX) con los nuevos
        # colores, evitando texto invisible sobre el nuevo fondo.
        self.tab1.aplicar_tema(self.tema_actual)
        self.tab2.aplicar_tema(self.tema_actual)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
