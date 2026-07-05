# -*- coding: utf-8 -*-
"""
temas.py
========
Definición centralizada de la paleta "Modo Claro" y "Modo Oscuro" y del
generador de hoja de estilos (QSS) para toda la aplicación PyQt6.

Mantener los colores en un solo lugar permite que, al presionar el botón de
alternar tema, TODOS los widgets (paneles, botones, listas) y TODOS los
lienzos de Matplotlib (gráfico principal, convergencia y "pizarra" LaTeX)
cambien de forma coherente y ningún texto quede invisible sobre su fondo.
"""

TEMA_CLARO = {
    "bg": "#f2f4fb",            # Fondo general de la ventana
    "panel": "#ffffff",         # Fondo de tarjetas / paneles
    "panel_alt": "#eef0f9",     # Fondo alterno (inputs)
    "texto": "#1f2233",         # Texto principal
    "subtexto": "#5b5f77",      # Texto secundario / ayuda
    "borde": "#d7dbee",         # Bordes de tarjetas e inputs
    "acento": "#4f46e5",        # Color de acento (botones principales)
    "acento_hover": "#4338ca",
    "peligro": "#dc2626",       # Rojo para errores
    "advertencia": "#b45309",   # Ámbar para advertencias
    "exito": "#15803d",         # Verde para OK
    # Colores específicos de Matplotlib:
    "canvas_face": "#ffffff",   # Fondo de la figura completa
    "axes_face": "#ffffff",     # Fondo del área de dibujo (ax)
    "grid": "#d7dbee",
    "texto_mpl": "#1f2233",
    "curva": "#1d4ed8",
    "curva_g": "#7c3aed",
    "izquierda": "#2563eb",     # Azul
    "derecha": "#dc2626",       # Rojo
    "medio": "#16a34a",         # Verde
    "trapecio": "#ea580c",      # Naranja
    "convergencia": "#dc2626",
    "superficie_cmap": "coolwarm",
}

TEMA_OSCURO = {
    "bg": "#12131c",
    "panel": "#1b1d2b",
    "panel_alt": "#232538",
    "texto": "#eef0fb",
    "subtexto": "#a3a7c2",
    "borde": "#2f3350",
    "acento": "#818cf8",
    "acento_hover": "#6366f1",
    "peligro": "#f87171",
    "advertencia": "#fbbf24",
    "exito": "#4ade80",
    "canvas_face": "#1b1d2b",
    "axes_face": "#1b1d2b",
    "grid": "#3a3d5c",
    "texto_mpl": "#eef0fb",
    "curva": "#93c5fd",
    "curva_g": "#c4b5fd",
    "izquierda": "#60a5fa",
    "derecha": "#f87171",
    "medio": "#4ade80",
    "trapecio": "#fb923c",
    "convergencia": "#f87171",
    "superficie_cmap": "plasma",
}


def generar_qss(t: dict) -> str:
    """Genera la hoja de estilos (QSS) de toda la app a partir de un tema."""
    return f"""
    QWidget {{
        background-color: {t['bg']};
        color: {t['texto']};
        font-family: 'Segoe UI', 'Ubuntu', sans-serif;
        font-size: 13px;
    }}
    QMainWindow {{
        background-color: {t['bg']};
    }}
    QGroupBox {{
        background-color: {t['panel']};
        border: 1px solid {t['borde']};
        border-radius: 10px;
        margin-top: 14px;
        padding: 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {t['acento']};
    }}
    QLabel {{
        background: transparent;
        color: {t['texto']};
    }}
    QLabel[rol="subtitulo"] {{
        color: {t['subtexto']};
        font-size: 11px;
    }}
    QLabel[rol="error"] {{
        color: {t['peligro']};
        font-weight: 600;
    }}
    QLabel[rol="advertencia"] {{
        color: {t['advertencia']};
        font-weight: 600;
    }}
    QLineEdit, QSpinBox, QComboBox, QDoubleSpinBox {{
        background-color: {t['panel_alt']};
        border: 1px solid {t['borde']};
        border-radius: 6px;
        padding: 5px 8px;
        color: {t['texto']};
        selection-background-color: {t['acento']};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border: 1px solid {t['acento']};
    }}
    QComboBox QAbstractItemView {{
        background-color: {t['panel_alt']};
        color: {t['texto']};
        selection-background-color: {t['acento']};
    }}
    QPushButton {{
        background-color: {t['acento']};
        color: white;
        border: none;
        border-radius: 7px;
        padding: 7px 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {t['acento_hover']};
    }}
    QPushButton:disabled {{
        background-color: {t['borde']};
        color: {t['subtexto']};
    }}
    QPushButton[rol="secundario"] {{
        background-color: {t['panel_alt']};
        color: {t['texto']};
        border: 1px solid {t['borde']};
    }}
    QPushButton[rol="secundario"]:hover {{
        background-color: {t['borde']};
    }}
    QCheckBox {{
        spacing: 8px;
    }}
    QListWidget {{
        background-color: {t['panel']};
        border: 1px solid {t['borde']};
        border-radius: 8px;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 6px;
        border-radius: 6px;
    }}
    QListWidget::item:selected {{
        background-color: {t['acento']};
        color: white;
    }}
    QTabWidget::pane {{
        border: 1px solid {t['borde']};
        border-radius: 10px;
        background-color: {t['bg']};
    }}
    QTabBar::tab {{
        background: {t['panel']};
        color: {t['texto']};
        padding: 9px 20px;
        margin-right: 4px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {t['acento']};
        color: white;
    }}
    QSlider::groove:horizontal {{
        height: 6px;
        background: {t['borde']};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {t['acento']};
        width: 16px;
        margin: -6px 0;
        border-radius: 8px;
    }}
    QToolTip {{
        background-color: {t['panel_alt']};
        color: {t['texto']};
        border: 1px solid {t['acento']};
        padding: 4px;
        border-radius: 4px;
    }}
    QScrollBar:vertical {{
        background: {t['panel']};
        width: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {t['borde']};
        border-radius: 5px;
    }}
    """
