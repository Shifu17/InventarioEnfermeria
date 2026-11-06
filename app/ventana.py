"""Ventana principal del Inventario de Enfermería."""
import os
import re

from PySide6.QtCore import (QEvent, QAbstractTableModel, QModelIndex, QRect, QRectF, QSize, Qt, QTimer)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap,
                           QTextLayout, QKeySequence, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QPushButton, QStackedWidget, QStyle,
                               QStyledItemDelegate, QTableView, QVBoxLayout, QWidget, QButtonGroup)

from . import estilos as E
from .db import Database, FOTOS_DIR, ESTADOS
from .iconos import icono, pixmap
from .ficha import FichaEquipo

import sys as _sys
RECURSOS = (os.path.join(_sys._MEIPASS, "app", "recursos") if getattr(_sys, "frozen", False)
            else os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos"))
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
        ruta = os.path.join(FOTOS_DIR, foto)
        if not os.path.exists(ruta):
            return None
        clave = (foto, os.path.getmtime(ruta), w, h, dpr)
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
            ("area", "Área"), ("marca", "Marca"), ("modelo", "Modelo"), ("serie", "Serie"), ("estado", "Estado")]


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
            return fila.get(campo, "")
        if role == Qt.DecorationRole and campo == "foto":
            return MINIS.obtener(fila.get("foto"), 56, 56, 2.0)
        if role == Qt.ToolTipRole and campo == "descripcion":
            return titulo_corto(fila["descripcion"])
        if role == Qt.ForegroundRole and campo == "estado" and fila.get("estado") in E.COLOR_ESTADO:
            return QColor(E.COLOR_ESTADO[fila["estado"]][1])
        if role == Qt.TextAlignmentRole and campo == "folio":
            return Qt.AlignCenter
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
        p.setBrush(QColor("white"))
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
        p.setBrush(QColor(E.AZUL))
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
        p.drawText(QRectF(x0, r.bottom() - 46, ancho, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(fs).elidedText(mm, Qt.ElideRight, int(ancho)))

        # chip de área
        fc = QFont(opt.font)
        fc.setPointSizeF(7.5)
        fc.setBold(True)
        fmc = QFontMetrics(fc)
        area = fila.get("area") or ""
        w = min(fmc.horizontalAdvance(area) + 18, ancho)
        cr = QRectF(x0, r.bottom() - 26, w, 18)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(E.AZUL_CLARO))
        p.drawRoundedRect(cr, 9, 9)
        p.setFont(fc)
        p.setPen(QColor(E.AZUL))
        p.drawText(cr, Qt.AlignCenter, fmc.elidedText(area, Qt.ElideRight, int(w - 10)))
        p.restore()


# ------------------------------------------------------------------ ventana
class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.area_actual = TODAS
        self.setWindowTitle("Inventario de Enfermería · FAENUS UAdeC")
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

    # ---------- construcción
    def _barra_lateral(self):
        lat = QFrame(objectName="Sidebar")
        lat.setFixedWidth(285)
        v = QVBoxLayout(lat)
        v.setContentsMargins(0, 22, 0, 18)
        v.setSpacing(6)

        escudos = QHBoxLayout()
        escudos.setSpacing(14)
        escudos.addStretch(1)
        for archivo in ("uadec_blanco.png", "escudo_blanco.png"):
            lbl = QLabel()
            pm = QPixmap(os.path.join(RECURSOS, archivo)).scaledToHeight(84 * 2, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(2)
            lbl.setPixmap(pm)
            escudos.addWidget(lbl, 0, Qt.AlignVCenter)
        escudos.addStretch(1)
        v.addLayout(escudos)

        fac = QLabel("FACULTAD DE ENFERMERÍA\nY NUTRICIÓN")
        fac.setAlignment(Qt.AlignCenter)
        fac.setStyleSheet("color:white; font-weight:800; font-size:13.5pt; margin-top:12px;")
        v.addWidget(fac)
        sub = QLabel("Inventario de Enfermería")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#BFD0F0; font-size:10.5pt;")
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
        v.addWidget(self.lista_areas, 1)

        caja = QVBoxLayout()
        caja.setContentsMargins(14, 8, 14, 0)
        caja.setSpacing(8)
        for txt, ic, fn in (("  Nueva área", "mas", self.nueva_area),
                            ("  Exportar a Excel", "excel", self.exportar_excel),
                            ("  Abrir carpeta de datos", "carpeta", self.abrir_datos)):
            b = QPushButton(txt, objectName="BotonLateral")
            b.setIcon(icono(ic, "#FFFFFF", 18))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            caja.addWidget(b)
        v.addLayout(caja)
        return lat

    def _encabezado(self):
        enc = QFrame(objectName="Encabezado")
        v = QVBoxLayout(enc)
        v.setContentsMargins(28, 20, 28, 16)
        v.setSpacing(12)

        fila1 = QHBoxLayout()
        tit = QVBoxLayout()
        tit.setSpacing(0)
        self.lbl_titulo = QLabel("Todas las áreas", objectName="TituloSeccion")
        self.lbl_sub = QLabel("", objectName="Subtitulo")
        tit.addWidget(self.lbl_titulo)
        tit.addWidget(self.lbl_sub)
        fila1.addLayout(tit, 1)

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
        for col, w in ((0, 60), (1, 76), (2, 120), (4, 140), (5, 120), (6, 110), (7, 120), (8, 160)):
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
        it = QListWidgetItem(f"Todas las áreas   ({total})")
        it.setData(Qt.UserRole, TODAS)
        self.lista_areas.addItem(it)
        areas = self.db.areas()
        for a in sorted(set(conteo) - set(areas)):
            if a:
                areas.append(a)
        actual = it
        for a in areas:
            item = QListWidgetItem(f"{a}   ({conteo.get(a, 0)})")
            item.setData(Qt.UserRole, a)
            self.lista_areas.addItem(item)
            if a == seleccionar:
                actual = item
        self.lista_areas.setCurrentItem(actual)
        self.lista_areas.blockSignals(False)

    def _area_cambiada(self, item, _prev=None):
        if item:
            self.area_actual = item.data(Qt.UserRole)
            self.refrescar()

    def refrescar(self):
        area = None if self.area_actual == TODAS else self.area_actual
        filas = self.db.buscar(self.buscador.text().strip(), area)
        filtro = self.filtro_estado.currentData()
        if filtro == "__SINFOTO__":
            filas = [f for f in filas if not f.get("foto")]
        elif filtro:
            filas = [f for f in filas if f.get("estado") == filtro]
        self.modelo.cargar(filas)

        self.lbl_titulo.setText("Todas las áreas" if area is None else area)
        con_foto = sum(1 for f in filas if f.get("foto"))
        atencion = sum(1 for f in filas if f.get("estado") in ("MAL ESTADO", "PENDIENTE DE VALORAR", "EN REPARACIÓN"))
        partes = [f"{len(filas)} equipo{'s' if len(filas) != 1 else ''}", f"{con_foto} con foto"]
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
        if ok:
            self._tras_cambio(area)

    def _tras_cambio(self, area):
        self.cargar_areas(self.area_actual)
        self.refrescar()

    def nueva_area(self):
        nombre, ok = QInputDialog.getText(self, "Nueva área", "Nombre del área:")
        if ok and nombre.strip():
            self.db.agregar_area(nombre)
            self.area_actual = nombre.strip().upper()
            self.cargar_areas()
            self.refrescar()

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
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(FOTOS_DIR)))

    def keyPressEvent(self, ev):
        vista = self.vista_tarjetas if self.pila.currentIndex() == 0 else self.tabla
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and vista.currentIndex().isValid():
            self.abrir_ficha(vista.currentIndex())
            return
        super().keyPressEvent(ev)
