"""Paleta y hoja de estilos basada en el azul institucional FAENUS – UAdeC."""

AZUL = "#1B4596"          # azul del logo
AZUL_OSCURO = "#122F6B"
AZUL_MEDIO = "#2D5BB5"
AZUL_CLARO = "#E8EEF8"
AZUL_TENUE = "#F3F6FB"
FONDO = "#F6F6F7"         # gris del fondo del logo
BLANCO = "#FFFFFF"
TEXTO = "#1E2A3B"
TEXTO_SUAVE = "#5E6B7E"
BORDE = "#D9E0EC"
ROJO = "#C0392B"

COLOR_ESTADO = {
    "FUNCIONAL": ("#E3F4EA", "#1E7B46"),
    "MAL ESTADO": ("#FBE5E3", "#B3261E"),
    "PENDIENTE DE VALORAR": ("#FFF3D6", "#8A5A00"),
    "EN REPARACIÓN": ("#FFE9D9", "#A14A00"),
    "DADO DE BAJA": ("#ECEDEF", "#4A5161"),
}

QSS = f"""
* {{ font-family: "Segoe UI", "Arial"; font-size: 10pt; color: {TEXTO}; }}
QMainWindow, QDialog {{ background: {FONDO}; }}

#Sidebar {{ background: {AZUL}; }}
#Sidebar QLabel {{ color: white; }}
#SidebarTitulo {{ color: #BFD0F0; font-size: 8.5pt; font-weight: 600; letter-spacing: 1px; }}
#ListaAreas {{ background: transparent; border: none; outline: none; font-size: 12pt; font-weight: 700; }}
#ListaAreas::item {{ color: #FFFFFF; font-size: 11.5pt; font-weight: 700; padding: 10px 12px; border-radius: 8px; margin: 1px 8px; }}
#ListaAreas::item:hover {{ background: rgba(255,255,255,0.10); }}
#ListaAreas::item:selected {{ background: white; color: {AZUL}; font-weight: 800; }}
#BotonLateral {{ background: rgba(255,255,255,0.12); color: white; border: 1px solid rgba(255,255,255,0.25);
    border-radius: 8px; padding: 8px 10px; text-align: left; }}
#BotonLateral:hover {{ background: rgba(255,255,255,0.22); }}

#Encabezado {{ background: {BLANCO}; border-bottom: 1px solid {BORDE}; }}
#TituloSeccion {{ font-size: 23pt; font-weight: 800; color: {AZUL_OSCURO}; }}
#Subtitulo {{ color: {TEXTO_SUAVE}; }}

#Buscador {{ background: {AZUL_TENUE}; border: 2px solid {BORDE}; border-radius: 22px;
    padding: 9px 16px 9px 40px; font-size: 11pt; }}
#Buscador:focus {{ border-color: {AZUL}; background: white; }}

QPushButton {{ background: white; border: 1px solid {BORDE}; border-radius: 8px; padding: 8px 14px; }}
QPushButton:hover {{ border-color: {AZUL}; color: {AZUL}; }}
QPushButton#Primario {{ background: {AZUL}; color: white; border: none; font-weight: 600; padding: 9px 18px; }}
QPushButton#Primario:hover {{ background: {AZUL_MEDIO}; }}
QPushButton#Peligro {{ color: {ROJO}; border-color: #EBC4C0; }}
QPushButton#Peligro:hover {{ background: #FBE5E3; }}
QPushButton:checked {{ background: {AZUL_CLARO}; color: {AZUL}; border-color: {AZUL}; font-weight: 600; }}

QComboBox, QLineEdit, QPlainTextEdit, QSpinBox {{ background: white; border: 1px solid {BORDE}; border-radius: 7px; padding: 6px 8px; }}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{ border: 1px solid {AZUL}; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; border: none; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: white; selection-background-color: {AZUL_CLARO}; selection-color: {AZUL}; }}

QListView#Tarjetas {{ background: {FONDO}; border: none; outline: none; }}
QTableView {{ background: white; border: 1px solid {BORDE}; border-radius: 8px; gridline-color: #EEF1F6;
    selection-background-color: {AZUL_CLARO}; selection-color: {TEXTO}; alternate-background-color: {AZUL_TENUE}; }}
QHeaderView::section {{ background: {AZUL_CLARO}; color: {AZUL_OSCURO}; font-weight: 600; border: none;
    border-right: 1px solid {BORDE}; padding: 7px; }}

QTabWidget::pane {{ border: 1px solid {BORDE}; border-radius: 8px; background: white; top: -1px; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; color: {TEXTO_SUAVE}; border-bottom: 3px solid transparent; }}
QTabBar::tab:selected {{ color: {AZUL}; border-bottom: 3px solid {AZUL}; font-weight: 600; }}

#Etiqueta {{ color: {TEXTO_SUAVE}; font-size: 9pt; font-weight: 600; }}
#MarcoFoto {{ background: white; border: 2px dashed {BORDE}; border-radius: 12px; }}
#Tarjeta {{ background: white; border: 1px solid {BORDE}; border-radius: 12px; }}
#Chip {{ background: {AZUL_CLARO}; color: {AZUL}; border-radius: 11px; padding: 3px 10px; font-weight: 600; font-size: 9pt; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C5CFDF; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {AZUL_MEDIO}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #C5CFDF; border-radius: 4px; min-width: 30px; }}
QToolTip {{ background: {AZUL_OSCURO}; color: white; border: none; padding: 6px; }}
"""
