"""Ventana principal del Inventario de Enfermería."""
import os
import re

from PySide6.QtCore import (QEvent, QAbstractTableModel, QModelIndex, QObject, QRect, QRectF, QSize, Qt,
                            QThread, QTimer, Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap,
                           QTextLayout, QKeySequence, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QListView, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu, QMessageBox, QProgressDialog, QPushButton,
                               QStackedWidget, QStyle, QStyledItemDelegate, QTableView, QVBoxLayout, QWidget,
                               QButtonGroup)

from . import estilos as E
from . import actualizador
from . import nube as NUBE
from .credencial import token as token_datos
from .sincronizacion import sincronizar
from . import db as BD
from .db import AREA_BAJAS, Database, ESTADOS, formato_costo
from .version import REPO_DATOS, VERSION
from .iconos import icono, pixmap
from .ficha import FichaEquipo

RECURSOS = E.RECURSOS
TODAS = "__TODAS__"


def titulo_corto(texto):
    partes = [p.strip() for p in (texto or "").split("°") if p.strip()]
    vistos, unicas = set(), []
    for p in partes:
        k = re.sub(r"\s+", " ", p).upper()
        if k not in vistos:
            vistos.add(k)
            unicas.append(re.sub(r"\s+", " ", p))
    return " · ".join(unicas) or "(Sin descripción)"


# ------------------------------------------------------------------ caché de miniaturas
class Miniaturas:
    def __init__(self):
        self._cache = {}

    def obtener(self, foto, w, h, dpr=1.0):
        if not foto:
            return None
        ruta = BD.ruta_foto(foto)
        if not os.path.exists(ruta):
            return None
        clave = (ruta, os.path.getmtime(ruta), w, h, dpr)
        if clave not in self._cache:
            if len(self._cache) > 300:
                self._cache.clear()
            pm = QPixmap(ruta)
            if pm.isNull():
                return None
            pm = pm.scaled(int(w * dpr), int(h * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            self._cache[clave] = pm
        return self._cache[clave]


MINIS = Miniaturas()


# ------------------------------------------------------------------ modelo
COLUMNAS = [("folio", "#"), ("foto", "Foto"), ("no_inventario", "No. inventario"), ("descripcion", "Descripción"),
            ("area", "Área"), ("marca", "Marca"), ("modelo", "Modelo"), ("serie", "Serie"), ("estado", "Estado"), ("costo", "Costo")]


class ModeloEquipos(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.filas = []

    def cargar(self, filas):
        self.beginResetModel()
        self.filas = filas
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.filas)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNAS)

    def headerData(self, s, o, role=Qt.DisplayRole):
        if o == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNAS[s][1]

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        fila = self.filas[idx.row()]
        campo = COLUMNAS[idx.column()][0]
        if role == Qt.UserRole:
            return fila
        if role == Qt.DisplayRole:
            if campo == "foto":
                return ""
            if campo == "folio":
                return f"#{fila.get('folio') or ''}"
            if campo == "descripcion":
                return titulo_corto(fila["descripcion"])
            if campo == "costo":
                return formato_costo(fila.get("costo"))
            return fila.get(campo, "")
        if role == Qt.DecorationRole and campo == "foto":
            return MINIS.obtener(fila.get("foto"), 56, 56, 2.0)
        if role == Qt.ToolTipRole and campo == "descripcion":
            return titulo_corto(fila["descripcion"])
        if role == Qt.ForegroundRole and campo == "estado" and fila.get("estado") in E.COLOR_ESTADO:
            return QColor(E.COLOR_ESTADO[fila["estado"]][1])
        if role == Qt.TextAlignmentRole and campo == "folio":
            return Qt.AlignCenter
        if role == Qt.TextAlignmentRole and campo == "costo":
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.ForegroundRole and campo == "folio":
            return QColor(E.AZUL)
        if role == Qt.FontRole and campo in ("folio", "no_inventario", "estado"):
            f = QFont()
            f.setBold(True)
            return f


# ------------------------------------------------------------------ tarjeta (delegate)
ANCHO_T, ALTO_T, ALTO_FOTO = 232, 300, 168


def _lineas_elididas(texto, fuente, ancho, max_lineas):
    fm = QFontMetrics(fuente)
    layout = QTextLayout(texto, fuente)
    layout.beginLayout()
    lineas = []
    while True:
        ln = layout.createLine()
        if not ln.isValid():
            break
        ln.setLineWidth(ancho)
        lineas.append(texto[ln.textStart(): ln.textStart() + ln.textLength()])
    layout.endLayout()
    if len(lineas) > max_lineas:
        resto = "".join(lineas[max_lineas - 1:])
        lineas = lineas[:max_lineas - 1] + [fm.elidedText(resto, Qt.ElideRight, ancho)]
    return [l.strip() for l in lineas]


class DelegadoTarjeta(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.escudo = QPixmap(os.path.join(RECURSOS, "escudo.png"))

    def sizeHint(self, opt, idx):
        g = self.parent().gridSize()
        return g if g.isValid() else QSize(ANCHO_T + 16, ALTO_T + 16)

    def paint(self, p, opt, idx):
        fila = idx.data(Qt.UserRole)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(opt.rect).adjusted(8, 8, -8, -8)
        hover = opt.state & QStyle.State_MouseOver
        sel = opt.state & QStyle.State_Selected

        # sombra suave
        for i, a in ((4, 10), (2, 18)):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(18, 47, 107, a if not hover else a + 12))
            p.drawRoundedRect(r.adjusted(-i / 2, i / 2, i / 2, i), 12, 12)
        p.setBrush(QColor(E.BLANCO))
        p.setPen(QPen(QColor(E.AZUL if (hover or sel) else E.BORDE), 2 if sel else 1))
        p.drawRoundedRect(r, 12, 12)

        # foto
        rf = QRectF(r.x() + 1, r.y() + 1, r.width() - 2, ALTO_FOTO)
        clip = QPainterPath()
        clip.setFillRule(Qt.WindingFill)
        clip.addRoundedRect(rf, 11, 11)
        clip.addRect(QRectF(rf.x(), rf.y() + 20, rf.width(), rf.height() - 20))
        p.save()
        p.setClipPath(clip.simplified())
        p.fillRect(rf, QColor(E.AZUL_TENUE))
        dpr = p.device().devicePixelRatioF() if p.device() else 1.0
        pm = MINIS.obtener(fila.get("foto"), int(rf.width() - 12), int(rf.height() - 12), dpr)
        if pm:
            sz = pm.size() / pm.devicePixelRatio()
            x = rf.x() + (rf.width() - sz.width()) / 2
            y = rf.y() + (rf.height() - sz.height()) / 2
            p.drawPixmap(int(x), int(y), pm)
        else:
            p.setOpacity(0.18)
            esc = self.escudo.scaled(90, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(int(rf.center().x() - esc.width() / 2), int(rf.center().y() - esc.height() / 2 - 8), esc)
            p.setOpacity(1)
            f = QFont(opt.font)
            f.setPointSizeF(8.5)
            p.setFont(f)
            p.setPen(QColor(E.TEXTO_SUAVE))
            p.drawText(QRectF(rf.x(), rf.bottom() - 28, rf.width(), 20), Qt.AlignCenter, "Sin foto")
        p.restore()
        p.setPen(QColor(E.BORDE))
        p.drawLine(int(rf.x()), int(rf.bottom()), int(rf.right()), int(rf.bottom()))

        # folio (esquina superior izquierda de la foto)
        ff = QFont(opt.font)
        ff.setPointSizeF(9)
        ff.setBold(True)
        txt_f = f"#{fila.get('folio', '')}"
        wf = QFontMetrics(ff).horizontalAdvance(txt_f) + 16
        rfo = QRectF(r.x() + 10, r.y() + 10, wf, 22)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(E.BOTON))
        p.drawRoundedRect(rfo, 11, 11)
        p.setFont(ff)
        p.setPen(QColor("white"))
        p.drawText(rfo, Qt.AlignCenter, txt_f)

        x0 = r.x() + 14
        ancho = r.width() - 28
        y = rf.bottom() + 12

        # número de inventario + estado
        f = QFont(opt.font)
        f.setPointSizeF(10.5)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(E.AZUL))
        no = fila.get("no_inventario") or "S/N"
        p.drawText(QRectF(x0, y, ancho, 20), Qt.AlignLeft | Qt.AlignVCenter, f"No. {no}")
        estado = fila.get("estado") or ""
        if estado in E.COLOR_ESTADO:
            fb = QFont(opt.font)
            fb.setPointSizeF(7.5)
            fb.setBold(True)
            fmb = QFontMetrics(fb)
            txt = estado if len(estado) < 14 else estado.split()[0]
            w = fmb.horizontalAdvance(txt) + 14
            br = QRectF(r.right() - 12 - w, y + 1, w, 18)
            fondo, color = E.COLOR_ESTADO[estado]
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(fondo))
            p.drawRoundedRect(br, 9, 9)
            p.setFont(fb)
            p.setPen(QColor(color))
            p.drawText(br, Qt.AlignCenter, txt)
        y += 24

        # descripción (2 líneas)
        fd = QFont(opt.font)
        fd.setPointSizeF(9.5)
        fd.setBold(True)
        p.setFont(fd)
        p.setPen(QColor(E.TEXTO))
        lh = QFontMetrics(fd).height()
        for ln in _lineas_elididas(titulo_corto(fila.get("descripcion")), fd, ancho, 2):
            p.drawText(QRectF(x0, y, ancho, lh), Qt.AlignLeft | Qt.AlignVCenter, ln)
            y += lh

        # marca / modelo
        fs = QFont(opt.font)
        fs.setPointSizeF(8.5)
        p.setFont(fs)
        p.setPen(QColor(E.TEXTO_SUAVE))
        mm = " · ".join(v for v in (fila.get("marca"), fila.get("modelo")) if v) or "—"
        costo = formato_costo(fila.get("costo"))
        w_costo = 0
        if costo:
            fcos = QFont(fs)
            fcos.setBold(True)
            w_costo = QFontMetrics(fcos).horizontalAdvance(costo) + 8
            p.setFont(fcos)
            p.setPen(QColor(E.AZUL_OSCURO))
            p.drawText(QRectF(x0, r.bottom() - 46, ancho, 16), Qt.AlignRight | Qt.AlignVCenter, costo)
            p.setFont(fs)
            p.setPen(QColor(E.TEXTO_SUAVE))
        p.drawText(QRectF(x0, r.bottom() - 46, ancho - w_costo, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(fs).elidedText(mm, Qt.ElideRight, int(ancho - w_costo)))

        # chip de área
        fc = QFont(opt.font)
        fc.setPointSizeF(7.5)
        fc.setBold(True)
        fmc = QFontMetrics(fc)
        area = fila.get("area") or ""
        w = min(fmc.horizontalAdvance(area) + 18, ancho)
        cr = QRectF(x0, r.bottom() - 26, w, 18)
        p.setPen(Qt.NoPen)
        baja = area == AREA_BAJAS
        p.setBrush(QColor(E.COLOR_ESTADO["DADO DE BAJA"][0] if baja else E.AZUL_CLARO))
        p.drawRoundedRect(cr, 9, 9)
        p.setFont(fc)
        p.setPen(QColor(E.COLOR_ESTADO["DADO DE BAJA"][1] if baja else E.AZUL))
        p.drawText(cr, Qt.AlignCenter, fmc.elidedText(area, Qt.ElideRight, int(w - 10)))
        p.restore()


# ------------------------------------------------------------------ consulta de actualizaciones (hilo aparte)
class _BuscadorActualizacion(QObject):
    listo = Signal(object, str)

    def ejecutar(self):
        try:
            self.listo.emit(actualizador.buscar_actualizacion(), "")
        except Exception as ex:
            self.listo.emit(None, str(ex) or ex.__class__.__name__)


class _Sincronizador(QObject):
    terminado = Signal(object, str)

    def __init__(self, nube):
        super().__init__()
        self.nube = nube

    def ejecutar(self):
        try:
            self.terminado.emit(sincronizar(self.nube), "")
        except NUBE.AccesoDenegado as ex:
            self.terminado.emit(None, f"acceso:{ex}")
        except Exception as ex:
            self.terminado.emit(None, str(ex) or ex.__class__.__name__)


# ------------------------------------------------------------------ ventana
class VentanaPrincipal(QMainWindow):
    _pedir_sync = Signal()

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.area_actual = TODAS
        self._cambios_pendientes = False
        self._hilo_act = None
        self.setWindowTitle(f"Inventario de Enfermería · FAENUS UAdeC   ·   v{VERSION}")
        self.resize(1360, 840)
        self.setMinimumSize(1000, 640)

        central = QWidget()
        self.setCentralWidget(central)
        raiz = QHBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._barra_lateral())

        derecha = QVBoxLayout()
        derecha.setContentsMargins(0, 0, 0, 0)
        derecha.setSpacing(0)
        derecha.addWidget(self._encabezado())
        derecha.addWidget(self._contenido(), 1)
        cont = QWidget()
        cont.setLayout(derecha)
        raiz.addWidget(cont, 1)

        self.temporizador = QTimer(self, singleShot=True, interval=180)
        self.temporizador.timeout.connect(self.refrescar)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.buscador.setFocus(), self.buscador.selectAll()))
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.nuevo_equipo)
        QShortcut(QKeySequence("Esc"), self.buscador, activated=lambda: self.buscador.clear())

        self.cargar_areas()
        self.refrescar()

        # Recarga automática: revisa cada pocos segundos si otra computadora guardó cambios.
        self.vigilante = QTimer(self, interval=3000)
        self.vigilante.timeout.connect(self._revisar_cambios_externos)
        self.vigilante.start()
        self._iniciar_sincronizacion()
        # Busca actualizaciones en GitHub poco después de abrir (sin estorbar el arranque).
        QTimer.singleShot(4000, lambda: self.buscar_actualizaciones(silencioso=True))

    # ---------- construcción
    def _barra_lateral(self):
        lat = QFrame(objectName="Sidebar")
        lat.setFixedWidth(285)
        v = QVBoxLayout(lat)
        v.setContentsMargins(0, 22, 0, 18)
        v.setSpacing(6)

        escudos = QHBoxLayout()
        escudos.setContentsMargins(18, 0, 18, 0)
        escudos.setSpacing(0)
        escudos.addStretch(1)
        for i, archivo in enumerate(("uadec_blanco.png", "escudo_blanco.png")):
            if i:
                escudos.addSpacing(48)   # separación entre los dos logos
            lbl = QLabel()
            pm = QPixmap(os.path.join(RECURSOS, archivo)).scaledToHeight(78 * 2, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(2)
            lbl.setPixmap(pm)
            escudos.addWidget(lbl, 0, Qt.AlignVCenter)
        escudos.addStretch(1)
        v.addLayout(escudos)

        fac = QLabel("FACULTAD DE ENFERMERÍA\nY NUTRICIÓN")
        fac.setAlignment(Qt.AlignCenter)
        fac.setStyleSheet("color:white; font-weight:700; font-size:9.5pt; margin-top:14px;")
        v.addWidget(fac)
        sub = QLabel("Inventario de Enfermería")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#BFD0F0; font-size:8.5pt;")
        v.addWidget(sub)

        linea = QFrame()
        linea.setFixedHeight(1)
        linea.setStyleSheet("background: rgba(255,255,255,0.18); margin: 12px 18px;")
        v.addWidget(linea)

        t = QLabel("ÁREAS", objectName="SidebarTitulo")
        t.setContentsMargins(22, 4, 0, 4)
        v.addWidget(t)

        self.lista_areas = QListWidget(objectName="ListaAreas")
        self.lista_areas.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.lista_areas.currentItemChanged.connect(self._area_cambiada)
        self.lista_areas.itemDoubleClicked.connect(lambda it: self.renombrar_area(it))
        self.lista_areas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lista_areas.customContextMenuRequested.connect(self._menu_area)
        self.lista_areas.setToolTip("Doble clic o clic derecho sobre un área para cambiarle el nombre")
        v.addWidget(self.lista_areas, 1)

        def boton(txt, ic, fn, tip=""):
            b = QPushButton(txt, objectName="BotonLateral")
            b.setIcon(icono(ic, "#FFFFFF", 18))
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            return b

        caja = QVBoxLayout()
        caja.setContentsMargins(14, 8, 14, 0)
        caja.setSpacing(8)
        fila_areas = QHBoxLayout()
        fila_areas.setSpacing(8)
        fila_areas.addWidget(boton("  Nueva área", "mas", self.nueva_area))
        self.btn_renombrar = boton("  Renombrar", "editar", lambda: self.renombrar_area(),
                                   "Cambiar el nombre del área seleccionada")
        fila_areas.addWidget(self.btn_renombrar)
        caja.addLayout(fila_areas)
        caja.addWidget(boton("  Exportar a Excel", "excel", self.exportar_excel))
        self.btn_sync = boton("  Sincronizar ahora", "nube", lambda: self.sincronizar_ahora(manual=True),
                              "Subir y descargar los cambios del inventario en línea")
        caja.addWidget(self.btn_sync)
        caja.addWidget(boton("  Abrir carpeta de datos", "carpeta", self.abrir_datos))
        self.btn_tema = boton("", "luna", self.alternar_tema)
        caja.addWidget(self.btn_tema)
        self._rotular_boton_tema()
        v.addLayout(caja)

        pie = QHBoxLayout()
        pie.setContentsMargins(22, 10, 14, 0)
        self.lbl_datos = QLabel(styleSheet="color:#BFD0F0; font-size:8pt;")
        self.lbl_datos.setWordWrap(True)
        pie.addWidget(self.lbl_datos, 1)
        v.addLayout(pie)
        pie2 = QHBoxLayout()
        pie2.setContentsMargins(22, 2, 14, 0)
        ver = QLabel(f"Versión {VERSION}", styleSheet="color:#BFD0F0; font-size:8pt;")
        pie2.addWidget(ver)
        pie2.addStretch(1)
        self.btn_act = QPushButton("Buscar actualizaciones", objectName="EnlaceLateral")
        self.btn_act.setCursor(Qt.PointingHandCursor)
        self.btn_act.clicked.connect(lambda: self.buscar_actualizaciones(silencioso=False))
        pie2.addWidget(self.btn_act)
        v.addLayout(pie2)
        return lat

    def _encabezado(self):
        enc = QFrame(objectName="Encabezado")
        v = QVBoxLayout(enc)
        v.setContentsMargins(28, 20, 28, 16)
        v.setSpacing(12)

        fila1 = QHBoxLayout()
        tit = QVBoxLayout()
        tit.setSpacing(0)
        self.lbl_titulo = QLabel("TODAS LAS ÁREAS", objectName="TituloSeccion")
        self.lbl_sub = QLabel("", objectName="Subtitulo")
        tit.addWidget(self.lbl_titulo)
        tit.addWidget(self.lbl_sub)
        fila1.addLayout(tit, 1)
        self.lbl_aviso = QLabel(objectName="Aviso")
        self.lbl_aviso.hide()
        fila1.addWidget(self.lbl_aviso, 0, Qt.AlignVCenter)
        fila1.addSpacing(12)

        self.btn_nuevo = QPushButton("  Agregar equipo", objectName="Primario")
        self.btn_nuevo.setIcon(icono("mas", "#FFFFFF", 18))
        self.btn_nuevo.setCursor(Qt.PointingHandCursor)
        self.btn_nuevo.clicked.connect(self.nuevo_equipo)
        fila1.addWidget(self.btn_nuevo, 0, Qt.AlignVCenter)
        v.addLayout(fila1)

        fila2 = QHBoxLayout()
        fila2.setSpacing(10)
        cont_busq = QWidget()
        cb = QHBoxLayout(cont_busq)
        cb.setContentsMargins(0, 0, 0, 0)
        self.buscador = QLineEdit(objectName="Buscador")
        self.buscador.setPlaceholderText("Buscar por nombre, # folio, No. de inventario, marca o serie…   Varios: 1,2,3  ·  Rango: 1-10")
        self.buscador.setClearButtonEnabled(True)
        self.buscador.textChanged.connect(lambda: self.temporizador.start())
        self.buscador.returnPressed.connect(self._enter_busqueda)
        cb.addWidget(self.buscador)
        lupa = QLabel(self.buscador)
        self._lupa = lupa
        lupa.setPixmap(pixmap("buscar", E.AZUL, 18))
        lupa.move(15, 12)
        lupa.setAttribute(Qt.WA_TransparentForMouseEvents)
        fila2.addWidget(cont_busq, 1)

        self.filtro_estado = QComboBox()
        self.filtro_estado.addItem("Todos los estados", "")
        for e in ESTADOS[1:]:
            self.filtro_estado.addItem(e.capitalize(), e)
        self.filtro_estado.addItem("Sin foto", "__SINFOTO__")
        self.filtro_estado.setMinimumWidth(190)
        self.filtro_estado.currentIndexChanged.connect(self.refrescar)
        fila2.addWidget(self.filtro_estado)

        self.grupo_vista = QButtonGroup(self)
        for i, (ic, tip) in enumerate((("cuadricula", "Vista de tarjetas"), ("lista", "Vista de tabla"))):
            b = QPushButton()
            b.setIcon(icono(ic, E.AZUL, 18))
            b.setProperty("icono", ic)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setFixedSize(42, 40)
            b.setCursor(Qt.PointingHandCursor)
            self.grupo_vista.addButton(b, i)
            fila2.addWidget(b)
        self.grupo_vista.button(0).setChecked(True)
        self.grupo_vista.idClicked.connect(lambda i: self.pila.setCurrentIndex(i))
        v.addLayout(fila2)
        return enc

    def _contenido(self):
        self.modelo = ModeloEquipos()
        self.pila = QStackedWidget()

        self.vista_tarjetas = QListView(objectName="Tarjetas")
        self.vista_tarjetas.setModel(self.modelo)
        self.vista_tarjetas.setViewMode(QListView.IconMode)
        self.vista_tarjetas.setResizeMode(QListView.Adjust)
        self.vista_tarjetas.setMovement(QListView.Static)
        self.vista_tarjetas.setUniformItemSizes(True)
        self.vista_tarjetas.setSpacing(0)
        self.vista_tarjetas.setMouseTracking(True)
        self.vista_tarjetas.setSelectionMode(QAbstractItemView.SingleSelection)
        self.vista_tarjetas.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.vista_tarjetas.verticalScrollBar().setSingleStep(24)
        self.vista_tarjetas.setItemDelegate(DelegadoTarjeta(self.vista_tarjetas))
        self.vista_tarjetas.setContentsMargins(16, 16, 16, 16)
        self.vista_tarjetas.setViewportMargins(14, 12, 6, 12)
        self.vista_tarjetas.clicked.connect(self.abrir_ficha)
        self.vista_tarjetas.setCursor(Qt.PointingHandCursor)
        self._viewport = self.vista_tarjetas.viewport()
        self._viewport.installEventFilter(self)

        self.tabla = QTableView()
        self.tabla.setModel(self.modelo)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(64)
        self.tabla.setIconSize(QSize(56, 56))
        self.tabla.setShowGrid(False)
        self.tabla.setWordWrap(True)
        h = self.tabla.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        for col, w in ((0, 60), (1, 76), (2, 120), (4, 140), (5, 120), (6, 110), (7, 120), (8, 160), (9, 110)):
            self.tabla.setColumnWidth(col, w)
        self.tabla.clicked.connect(self.abrir_ficha)
        envoltura = QWidget()
        ev = QVBoxLayout(envoltura)
        ev.setContentsMargins(24, 18, 24, 18)
        ev.addWidget(self.tabla)

        self.vacio = QLabel()
        self.vacio.setAlignment(Qt.AlignCenter)
        self.vacio.setStyleSheet(f"color:{E.TEXTO_SUAVE}; font-size:12pt;")

        self.pila.addWidget(self.vista_tarjetas)
        self.pila.addWidget(envoltura)
        self.pila.addWidget(self.vacio)
        return self.pila

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Resize and obj is getattr(self, "_viewport", None):
            disp = obj.width() - 24
            cols = max(1, disp // (ANCHO_T + 16))
            ancho = min(disp // cols, ANCHO_T + 90)
            self.vista_tarjetas.setGridSize(QSize(ancho, ALTO_T + 16))
        return super().eventFilter(obj, ev)

    # ---------- datos
    def cargar_areas(self, seleccionar=None):
        seleccionar = seleccionar or self.area_actual
        self.lista_areas.blockSignals(True)
        self.lista_areas.clear()
        conteo = self.db.conteo_por_area()
        total = sum(conteo.values())
        it = QListWidgetItem(f"TODAS LAS ÁREAS   ({total})")
        it.setData(Qt.UserRole, TODAS)
        self.lista_areas.addItem(it)
        areas = self.db.areas()
        for a in sorted(set(conteo) - set(areas)):
            if a:
                areas.append(a)
        if AREA_BAJAS in areas:
            areas.remove(AREA_BAJAS)
            areas.append(AREA_BAJAS)
        actual = it
        for a in areas:
            item = QListWidgetItem(f"{a.upper()}   ({conteo.get(a, 0)})")
            item.setData(Qt.UserRole, a)
            if a == AREA_BAJAS:
                item.setIcon(icono("basura", "#BFD0F0", 16))
                item.setToolTip("Aquí se mueven solos los equipos con estado «Dado de baja»")
            self.lista_areas.addItem(item)
            if a == seleccionar:
                actual = item
        self.lista_areas.setCurrentItem(actual)
        self.lista_areas.blockSignals(False)
        self.area_actual = actual.data(Qt.UserRole)
        self._actualizar_botones_area()

    def _area_cambiada(self, item, _prev=None):
        if item:
            self.area_actual = item.data(Qt.UserRole)
            self._actualizar_botones_area()
            self.refrescar()

    def _actualizar_botones_area(self):
        if hasattr(self, "btn_renombrar"):
            self.btn_renombrar.setEnabled(self.area_actual not in (TODAS, AREA_BAJAS))


    def refrescar(self):
        area = None if self.area_actual == TODAS else self.area_actual
        filas = self.db.buscar(self.buscador.text().strip(), area)
        filtro = self.filtro_estado.currentData()
        if filtro == "__SINFOTO__":
            filas = [f for f in filas if not f.get("foto")]
        elif filtro:
            filas = [f for f in filas if f.get("estado") == filtro]
        self.modelo.cargar(filas)

        self.lbl_titulo.setText("TODAS LAS ÁREAS" if area is None else area)
        con_foto = sum(1 for f in filas if f.get("foto"))
        atencion = sum(1 for f in filas if f.get("estado") in ("MAL ESTADO", "PENDIENTE DE VALORAR", "EN REPARACIÓN"))
        partes = [f"{len(filas)} equipo{'s' if len(filas) != 1 else ''}", f"{con_foto} con foto"]
        valor = sum(f.get("costo") or 0 for f in filas)
        if valor:
            partes.append(f"valor {formato_costo(valor)}")
        if atencion:
            partes.append(f"{atencion} requieren atención")
        if self.buscador.text().strip():
            partes.append(f"resultados para «{self.buscador.text().strip()}»")
        self.lbl_sub.setText("  ·  ".join(partes))

        if not filas:
            self.vacio.setText("No se encontraron equipos.\nPrueba con otra palabra o número de inventario.")
            self.pila.setCurrentIndex(2)
        else:
            self.pila.setCurrentIndex(self.grupo_vista.checkedId())

    def _enter_busqueda(self):
        self.temporizador.stop()
        self.refrescar()
        if self.modelo.rowCount() == 1:
            self.abrir_ficha(self.modelo.index(0, 0))

    # ---------- acciones
    def abrir_ficha(self, idx):
        if idx.isValid():
            fila = self.modelo.data(self.modelo.index(idx.row(), 0), Qt.UserRole)
            # Se abre después del clic para no anidar el diálogo dentro del evento del ratón.
            QTimer.singleShot(0, lambda eid=fila["id"]: self._abrir_ficha_id(eid))

    def _abrir_ficha_id(self, eid):
        if getattr(self, "_ficha_abierta", False):
            return
        self._ficha_abierta = True
        try:
            if not self.db.obtener(eid):
                self.refrescar()
                return
            self._ejecutar_ficha(FichaEquipo(self.db, eid, parent=self))
        finally:
            self._ficha_abierta = False

    def nuevo_equipo(self):
        if getattr(self, "_ficha_abierta", False):
            return
        self._ficha_abierta = True
        try:
            area = None if self.area_actual == TODAS else self.area_actual
            self._ejecutar_ficha(FichaEquipo(self.db, None, area_inicial=area, parent=self))
        finally:
            self._ficha_abierta = False

    def _ejecutar_ficha(self, dlg):
        try:
            ok = dlg.exec()
            area = dlg.area_final
        finally:
            dlg.limpiar()
            dlg.deleteLater()
        if ok or self._cambios_pendientes:
            self._tras_cambio(area)

    def _tras_cambio(self, area):
        self._cambios_pendientes = False
        self._programar_sync()
        self.cargar_areas(self.area_actual)
        self.refrescar()

    def nueva_area(self):
        nombre, ok = QInputDialog.getText(self, "Nueva área", "Nombre del área:")
        if ok and nombre.strip():
            self.db.agregar_area(nombre)
            self.area_actual = BD.normalizar_area(nombre)
            self.cargar_areas()
            self.refrescar()
            self._programar_sync()

    def _menu_area(self, pos):
        item = self.lista_areas.itemAt(pos)
        if not item or item.data(Qt.UserRole) in (TODAS, AREA_BAJAS):
            return
        menu = QMenu(self)
        accion = menu.addAction(icono("editar", E.AZUL, 16), "Cambiar nombre del área…")
        if menu.exec(self.lista_areas.viewport().mapToGlobal(pos)) is accion:
            self.renombrar_area(item)

    def renombrar_area(self, item=None):
        item = item or self.lista_areas.currentItem()
        if not item:
            return
        viejo = item.data(Qt.UserRole)
        if viejo == TODAS:
            return
        if viejo == AREA_BAJAS:
            QMessageBox.information(self, "Área protegida",
                                    "El área de equipos dados de baja la administra el programa "
                                    "y no se puede renombrar.")
            return
        nuevo, ok = QInputDialog.getText(self, "Cambiar nombre del área",
                                         f"Nuevo nombre para «{viejo}»:", text=viejo)
        nuevo = BD.normalizar_area(nuevo)
        if not ok or not nuevo or nuevo == viejo:
            return
        if nuevo == AREA_BAJAS:
            QMessageBox.warning(self, "Nombre reservado", "Ese nombre está reservado para los equipos dados de baja.")
            return
        if self.db.existe_area(nuevo):
            r = QMessageBox.question(self, "El área ya existe",
                                     f"Ya existe un área llamada «{nuevo}».\n"
                                     f"¿Unir «{viejo}» con ella? Todos sus equipos pasarán a «{nuevo}».")
            if r != QMessageBox.Yes:
                return
        self.area_actual = self.db.renombrar_area(viejo, nuevo)
        self.cargar_areas()
        self.refrescar()
        self._programar_sync()

    def exportar_excel(self):
        from .exportar import exportar
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar inventario", "inventario_enfermeria.xlsx",
                                              "Excel (*.xlsx)")
        if not ruta:
            return
        self.setCursor(Qt.WaitCursor)
        try:
            n = exportar(self.db, ruta)
        except Exception as ex:
            self.unsetCursor()
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{ex}")
            return
        self.unsetCursor()
        QMessageBox.information(self, "Exportado", f"Se exportaron {n} equipos a:\n{ruta}")

    def abrir_datos(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(BD.DATA_DIR))

    # ---------- modo oscuro
    def _rotular_boton_tema(self):
        oscuro = E.es_oscuro()
        self.btn_tema.setText("  Modo claro" if oscuro else "  Modo oscuro")
        self.btn_tema.setIcon(icono("sol" if oscuro else "luna", "#FFFFFF", 18))
        self.btn_tema.setToolTip("Cambiar entre el tema claro y el oscuro")

    def alternar_tema(self):
        nuevo = "claro" if E.es_oscuro() else "oscuro"
        QApplication.instance().setStyleSheet(E.aplicar_tema(nuevo))
        BD.guardar_config(tema=nuevo)
        self._rotular_boton_tema()
        self._lupa.setPixmap(pixmap("buscar", E.AZUL, 18))
        for b in self.grupo_vista.buttons():
            b.setIcon(icono(b.property("icono"), E.AZUL, 18))
        self.vacio.setStyleSheet(f"color:{E.TEXTO_SUAVE}; font-size:12pt;")
        self.modelo.cargar(self.modelo.filas)       # recolorea estados y folios de la tabla
        self.vista_tarjetas.viewport().update()

    # ---------- sincronización con el inventario en línea
    def _iniciar_sincronizacion(self):
        self._sync_en_curso = False
        self._sync_pendiente = False
        self._sync_manual = False
        tk = token_datos()
        self._nube = NUBE.Nube(REPO_DATOS, tk) if tk else None
        if not self._nube:
            self._estado_sync("Sin código de acceso: el inventario solo se guarda en esta computadora", error=True)
            self.btn_sync.setEnabled(False)
            return
        self._hilo_sync = QThread(self)
        self._trab_sync = _Sincronizador(self._nube)
        self._trab_sync.moveToThread(self._hilo_sync)
        self._pedir_sync.connect(self._trab_sync.ejecutar)
        self._trab_sync.terminado.connect(self._fin_sync)
        self._hilo_sync.start()
        self._reloj_sync = QTimer(self, interval=20000)       # revisa cambios en línea cada 20 s
        self._reloj_sync.timeout.connect(self.sincronizar_ahora)
        self._reloj_sync.start()
        self._retraso_sync = QTimer(self, singleShot=True, interval=1500)
        self._retraso_sync.timeout.connect(self.sincronizar_ahora)
        self._estado_sync("Conectando con el inventario en línea…")
        QTimer.singleShot(300, self.sincronizar_ahora)

    def _programar_sync(self):
        if getattr(self, "_nube", None):
            self._retraso_sync.start()

    def sincronizar_ahora(self, manual=False):
        if not getattr(self, "_nube", None):
            return
        self._sync_manual = self._sync_manual or manual
        if self._sync_en_curso:
            self._sync_pendiente = True
            return
        self._sync_en_curso = True
        self.btn_sync.setEnabled(False)
        if manual:
            self._estado_sync("Sincronizando…")
        self._pedir_sync.emit()

    def _fin_sync(self, resultado, error):
        self._sync_en_curso = False
        self.btn_sync.setEnabled(True)
        manual, self._sync_manual = self._sync_manual, False
        if error:
            if error.startswith("acceso:"):
                self._estado_sync("El código de acceso al inventario en línea no es válido", error=True)
                if manual:
                    QMessageBox.warning(self, "Inventario en línea", error[7:])
            else:
                self._estado_sync("Sin internet: los cambios se guardan aquí y se subirán después", error=True)
                if manual:
                    QMessageBox.warning(self, "Inventario en línea",
                                        f"No se pudo sincronizar. Revisa la conexión a internet.\n\n{error}")
        else:
            from datetime import datetime
            self._estado_sync(f"Inventario en línea sincronizado · {datetime.now():%H:%M}")
            self._revisar_cambios_externos()
        if self._sync_pendiente:
            self._sync_pendiente = False
            QTimer.singleShot(200, self.sincronizar_ahora)

    def _estado_sync(self, texto, error=False):
        self.lbl_datos.setText(("⚠  " if error else "☁  ") + texto)
        self.lbl_datos.setStyleSheet(f"color:{'#FFD38A' if error else '#BFD0F0'}; font-size:8pt;")
        self.lbl_datos.setToolTip(f"Copia local: {BD.DB_PATH}\nEn línea: github.com/{REPO_DATOS}")

    def closeEvent(self, ev):
        self.vigilante.stop()
        if getattr(self, "_nube", None):
            self._reloj_sync.stop()
            self._retraso_sync.stop()
            self._hilo_sync.quit()
            self._hilo_sync.wait(20000)
            # Último intento de subir lo pendiente antes de cerrar (rápido si no hay cambios).
            self.setCursor(Qt.WaitCursor)
            try:
                self._nube.timeout = 10
                sincronizar(self._nube)
            except Exception:
                pass
            self.unsetCursor()
        super().closeEvent(ev)

    def _revisar_cambios_externos(self):
        if getattr(self, "_ficha_abierta", False) or QApplication.activeModalWidget():
            # No se refresca con una ficha o un diálogo abiertos; se hará al cerrarlos.
            try:
                self._cambios_pendientes = self.db.hubo_cambios_externos() or self._cambios_pendientes
            except Exception:
                pass
            return
        try:
            cambio = self.db.hubo_cambios_externos() or self._cambios_pendientes
        except Exception:
            return   # base ocupada por el sincronizador: se reintenta en el siguiente ciclo
        if cambio:
            self._cambios_pendientes = False
            self.cargar_areas(self.area_actual)
            self.refrescar()
            self.lbl_aviso.setText("↻  Inventario actualizado")
            self.lbl_aviso.show()
            QTimer.singleShot(5000, self.lbl_aviso.hide)

    # ---------- actualizaciones desde GitHub
    def buscar_actualizaciones(self, silencioso=False):
        if self._hilo_act is not None:
            return
        self.btn_act.setEnabled(False)
        self.btn_act.setText("Buscando…")
        self._hilo_act = QThread(self)
        self._trab_act = _BuscadorActualizacion()
        self._trab_act.moveToThread(self._hilo_act)
        self._hilo_act.started.connect(self._trab_act.ejecutar)
        self._trab_act.listo.connect(lambda info, error: self._resultado_actualizacion(info, error, silencioso))
        self._trab_act.listo.connect(self._hilo_act.quit)
        self._hilo_act.finished.connect(self._fin_hilo_act)
        self._hilo_act.start()

    def _fin_hilo_act(self):
        self._hilo_act.deleteLater()
        self._trab_act.deleteLater()
        self._hilo_act = None
        self.btn_act.setEnabled(True)
        self.btn_act.setText("Buscar actualizaciones")

    def _resultado_actualizacion(self, info, error, silencioso):
        if error:
            if not silencioso:
                QMessageBox.warning(self, "Actualizaciones",
                                    f"No se pudo consultar si hay una versión nueva.\nRevisa la conexión a internet.\n\n{error}")
            return
        if not info:
            if not silencioso:
                QMessageBox.information(self, "Actualizaciones", f"Ya tienes la versión más reciente ({VERSION}).")
            return
        notas = info.get("notas") or ""
        if len(notas) > 900:
            notas = notas[:900] + "…"
        caja = QMessageBox(self)
        caja.setWindowTitle("Actualización disponible")
        caja.setIcon(QMessageBox.Information)
        caja.setText(f"<b>Hay una versión nueva: {info['version']}</b><br>Tienes la {VERSION}.")
        caja.setInformativeText("Tus datos no se modifican al actualizar.\n\n" + notas if notas
                                else "Tus datos no se modifican al actualizar.")
        b_si = caja.addButton("Actualizar ahora", QMessageBox.AcceptRole)
        caja.addButton("Más tarde", QMessageBox.RejectRole)
        caja.setDefaultButton(b_si)
        caja.exec()
        if caja.clickedButton() is not b_si:
            return
        if not actualizador.puede_actualizarse():
            QMessageBox.information(self, "Actualizaciones",
                                    "Estás usando el programa desde el código fuente.\n"
                                    "Para actualizar descarga los cambios con «git pull».")
            return
        prog = QProgressDialog("Descargando actualización…", None, 0, 100, self)
        prog.setWindowTitle("Actualizando")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)

        def avance(hecho, total):
            if total:
                prog.setValue(int(hecho * 100 / total))
            QApplication.processEvents()

        try:
            nuevo = actualizador.descargar(info, avance)
        except Exception as ex:
            prog.close()
            QMessageBox.critical(self, "Actualización", f"No se pudo descargar la actualización:\n{ex}")
            return
        prog.close()
        try:
            actualizador.instalar_y_reiniciar(nuevo)
        except Exception as ex:
            QMessageBox.critical(self, "Actualización", f"No se pudo instalar la actualización:\n{ex}")
            return
        QMessageBox.information(self, "Actualización",
                                "El programa se cerrará y se abrirá de nuevo ya actualizado.")
        QApplication.quit()

    def keyPressEvent(self, ev):
        vista = self.vista_tarjetas if self.pila.currentIndex() == 0 else self.tabla
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and vista.currentIndex().isValid():
            self.abrir_ficha(vista.currentIndex())
            return
        super().keyPressEvent(ev)
