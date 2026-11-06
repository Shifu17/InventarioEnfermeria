"""Paleta y hoja de estilos basada en el azul institucional FAENUS – UAdeC."""
import os
import sys

RECURSOS = (os.path.join(sys._MEIPASS, "app", "recursos") if getattr(sys, "frozen", False)
            else os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos"))

# ------------------------------------------------------------------ temas
# Los nombres se conservan para que el resto del código no cambie: BLANCO es el color de las
# "superficies" (tarjetas, campos) y AZUL el color de acento.
TEMAS = {
    "claro": dict(
        AZUL="#1B4596", AZUL_OSCURO="#122F6B", AZUL_MEDIO="#2D5BB5", AZUL_CLARO="#E8EEF8",
        AZUL_TENUE="#F3F6FB", FONDO="#F6F6F7", BLANCO="#FFFFFF", TEXTO="#1E2A3B", TEXTO_SUAVE="#5E6B7E",
        BORDE="#D9E0EC", ROJO="#C0392B", ROJO_TENUE="#FBE5E3", ROJO_BORDE="#EBC4C0",
        LATERAL="#1B4596", BOTON="#1B4596", BOTON_HOVER="#2D5BB5", REJILLA="#EEF1F6",
        BARRA="#C5CFDF", AVISO_FONDO="#E3F4EA", AVISO_TEXTO="#1E7B46",
        FLECHA="flecha_abajo.svg", FLECHA_INACTIVA="flecha_abajo_gris.svg",
        COLOR_ESTADO={
            "FUNCIONAL": ("#E3F4EA", "#1E7B46"),
            "MAL ESTADO": ("#FBE5E3", "#B3261E"),
            "PENDIENTE DE VALORAR": ("#FFF3D6", "#8A5A00"),
            "EN REPARACIÓN": ("#FFE9D9", "#A14A00"),
            "DADO DE BAJA": ("#ECEDEF", "#4A5161"),
        },
    ),
    "oscuro": dict(
        AZUL="#7EA6FF", AZUL_OSCURO="#DCE6FA", AZUL_MEDIO="#4A78D8", AZUL_CLARO="#26375C",
        AZUL_TENUE="#1B2232", FONDO="#11161F", BLANCO="#192030", TEXTO="#E3E8F2", TEXTO_SUAVE="#9AA6B8",
        BORDE="#2C3850", ROJO="#FF7A6E", ROJO_TENUE="#3A1F22", ROJO_BORDE="#6B3333",
        LATERAL="#0F1E45", BOTON="#2D5BB5", BOTON_HOVER="#3D6CCB", REJILLA="#232C3E",
        BARRA="#3A465E", AVISO_FONDO="#16352A", AVISO_TEXTO="#7FD8A4",
        FLECHA="flecha_abajo_claro.svg", FLECHA_INACTIVA="flecha_abajo_gris_oscuro.svg",
        COLOR_ESTADO={
            "FUNCIONAL": ("#16352A", "#7FD8A4"),
            "MAL ESTADO": ("#3E1D1C", "#FF8A80"),
            "PENDIENTE DE VALORAR": ("#3A2E12", "#F5C66B"),
            "EN REPARACIÓN": ("#3D2716", "#FFAD6B"),
            "DADO DE BAJA": ("#2A303B", "#B5BDCA"),
        },
    ),
}

TEMA = "claro"


def _ruta_recurso(nombre):
    # Qt necesita diagonales normales en las rutas de la hoja de estilos.
    return os.path.join(RECURSOS, nombre).replace(os.sep, "/")


def construir_qss():
    _FLECHA = _ruta_recurso(FLECHA)
    _FLECHA_GRIS = _ruta_recurso(FLECHA_INACTIVA)
    return f"""
* {{ font-family: "Segoe UI", "Arial"; font-size: 10pt; color: {TEXTO}; }}
QMainWindow, QDialog {{ background: {FONDO}; }}

#Sidebar {{ background: {LATERAL}; }}
#Sidebar QLabel {{ color: white; }}
#SidebarTitulo {{ color: #BFD0F0; font-size: 8.5pt; font-weight: 600; letter-spacing: 1px; }}
#ListaAreas {{ background: transparent; border: none; outline: none; font-size: 9pt; font-weight: 600; }}
#ListaAreas::item {{ color: #FFFFFF; font-size: 9pt; font-weight: 600; padding: 3px 10px; border-radius: 7px; margin: 1px 8px; }}
#ListaAreas::item:hover {{ background: rgba(255,255,255,0.10); }}
#ListaAreas::item:selected {{ background: white; color: {LATERAL}; font-weight: 700; }}
#BotonLateral {{ background: rgba(255,255,255,0.12); color: white; border: 1px solid rgba(255,255,255,0.25);
    border-radius: 8px; padding: 8px 10px; text-align: left; }}
#BotonLateral:hover {{ background: rgba(255,255,255,0.22); }}
#BotonLateral:disabled {{ color: rgba(255,255,255,0.45); border-color: rgba(255,255,255,0.12); }}
#EnlaceLateral {{ background: transparent; border: none; color: white; text-decoration: underline;
    font-size: 8pt; padding: 2px 0; }}
#EnlaceLateral:hover {{ color: #BFD0F0; }}
#EnlaceLateral:disabled {{ color: #BFD0F0; text-decoration: none; }}
#Aviso {{ background: {AVISO_FONDO}; color: {AVISO_TEXTO}; border-radius: 12px; padding: 6px 14px; font-weight: 600; }}

#Encabezado {{ background: {BLANCO}; border-bottom: 1px solid {BORDE}; }}
#TituloSeccion {{ font-size: 23pt; font-weight: 800; color: {AZUL_OSCURO}; }}
#Subtitulo {{ color: {TEXTO_SUAVE}; }}

#Buscador {{ background: {AZUL_TENUE}; border: 2px solid {BORDE}; border-radius: 22px;
    padding: 9px 16px 9px 40px; font-size: 11pt; }}
#Buscador:focus {{ border-color: {AZUL}; background: {BLANCO}; }}

QPushButton {{ background: {BLANCO}; border: 1px solid {BORDE}; border-radius: 8px; padding: 8px 14px; }}
QPushButton:hover {{ border-color: {AZUL}; color: {AZUL}; }}
QPushButton#Primario {{ background: {BOTON}; color: white; border: none; font-weight: 600; padding: 9px 18px; }}
QPushButton#Primario:hover {{ background: {BOTON_HOVER}; }}
QPushButton#Peligro {{ color: {ROJO}; border-color: {ROJO_BORDE}; }}
QPushButton#Peligro:hover {{ background: {ROJO_TENUE}; }}
QPushButton:checked {{ background: {AZUL_CLARO}; color: {AZUL}; border-color: {AZUL}; font-weight: 600; }}

QComboBox, QLineEdit, QPlainTextEdit, QSpinBox {{ background: {BLANCO}; border: 1px solid {BORDE}; border-radius: 7px; padding: 6px 8px; }}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{ border: 1px solid {AZUL}; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; border: none; }}
QComboBox {{ padding-right: 34px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 28px;
    border: none; border-left: 1px solid {BORDE}; border-top-right-radius: 7px; border-bottom-right-radius: 7px;
    background: {AZUL_TENUE}; }}
QComboBox::drop-down:hover {{ background: {AZUL_CLARO}; }}
QComboBox::down-arrow {{ image: url("{_FLECHA}"); width: 14px; height: 14px; }}
QComboBox::down-arrow:disabled {{ image: url("{_FLECHA_GRIS}"); }}
QComboBox::down-arrow:on {{ top: 1px; }}
QComboBox QAbstractItemView {{ background: {BLANCO}; color: {TEXTO}; selection-background-color: {AZUL_CLARO}; selection-color: {AZUL}; }}

QListView#Tarjetas {{ background: {FONDO}; border: none; outline: none; }}
QTableView {{ background: {BLANCO}; border: 1px solid {BORDE}; border-radius: 8px; gridline-color: {REJILLA};
    selection-background-color: {AZUL_CLARO}; selection-color: {TEXTO}; alternate-background-color: {AZUL_TENUE}; }}
QHeaderView::section {{ background: {AZUL_CLARO}; color: {AZUL_OSCURO}; font-weight: 600; border: none;
    border-right: 1px solid {BORDE}; padding: 7px; }}

QTabWidget::pane {{ border: 1px solid {BORDE}; border-radius: 8px; background: {BLANCO}; top: -1px; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; color: {TEXTO_SUAVE}; border-bottom: 3px solid transparent; }}
QTabBar::tab:selected {{ color: {AZUL}; border-bottom: 3px solid {AZUL}; font-weight: 600; }}

#Etiqueta {{ color: {TEXTO_SUAVE}; font-size: 9pt; font-weight: 600; }}
#MarcoFoto {{ background: {BLANCO}; border: 2px dashed {BORDE}; border-radius: 12px; }}
#Tarjeta {{ background: {BLANCO}; border: 1px solid {BORDE}; border-radius: 12px; }}
#Chip {{ background: {AZUL_CLARO}; color: {AZUL}; border-radius: 11px; padding: 3px 10px; font-weight: 600; font-size: 9pt; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BARRA}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {AZUL_MEDIO}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BARRA}; border-radius: 4px; min-width: 30px; }}
QToolTip {{ background: {LATERAL}; color: white; border: none; padding: 6px; }}
QMenu {{ background: {BLANCO}; border: 1px solid {BORDE}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 5px; }}
QMenu::item:selected {{ background: {AZUL_CLARO}; color: {AZUL}; }}
QMessageBox QLabel, QInputDialog QLabel {{ color: {TEXTO}; }}
QProgressBar {{ background: {AZUL_TENUE}; border: 1px solid {BORDE}; border-radius: 6px; text-align: center; }}
QProgressBar::chunk {{ background: {BOTON}; border-radius: 5px; }}
"""


def aplicar_tema(nombre):
    """Cambia los colores globales al tema pedido ("claro" u "oscuro") y devuelve la hoja de estilos."""
    global TEMA
    TEMA = nombre if nombre in TEMAS else "claro"
    globals().update(TEMAS[TEMA])
    return construir_qss()


def es_oscuro():
    return TEMA == "oscuro"


QSS = aplicar_tema("claro")
