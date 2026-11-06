"""Ficha de equipo: ver, editar, agregar, cambiar foto y eliminar."""
import os
import time
import weakref

from PIL import Image, ImageOps
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QGuiApplication, QFontMetricsF, QIntValidator
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QTabWidget,
                               QVBoxLayout, QWidget)

from . import estilos as E
from .db import ESTADOS, FOTOS_DIR
from .iconos import icono

EXT_IMG = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".tif", ".tiff", ".jfif")


def guardar_imagen(origen, eid):
    """Copia una imagen a la carpeta de fotos (corrige rotación y la optimiza)."""
    img = Image.open(origen)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1600, 1600))
    nombre = f"equipo_{eid}_{int(time.time())}.jpg"
    img.save(os.path.join(FOTOS_DIR, nombre), "JPEG", quality=90)
    return nombre


class CampoFolio(QLineEdit):
    """Campo de folio: solo números enteros positivos."""
    def __init__(self):
        super().__init__()
        self.setValidator(QIntValidator(1, 9999999, self))
        self.setPlaceholderText("#")

    def value(self):
        return int(self.text()) if self.text().isdigit() else 0

    def setValue(self, n):
        self.setText(str(n))


# ------------------------------------------------------------------ visor
class VisorFoto(QDialog):
    def __init__(self, ruta, titulo, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.pm = QPixmap(ruta)
        scr = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(int(scr.width() * 0.75), int(scr.height() * 0.85))
        self.setStyleSheet("background:#0F1B33;")
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        self.lbl = QLabel(alignment=Qt.AlignCenter)
        v.addWidget(self.lbl)

    def resizeEvent(self, ev):
        dpr = self.devicePixelRatioF()
        s = self.lbl.size() * dpr
        pm = self.pm.scaled(s, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        self.lbl.setPixmap(pm)
        super().resizeEvent(ev)

    def mousePressEvent(self, ev):
        self.accept()


# ------------------------------------------------------------------ marco de foto (acepta arrastrar y soltar)
class MarcoFoto(QLabel):
    def __init__(self, ficha):
        super().__init__()
        self._ficha = weakref.ref(ficha)
        self.setObjectName("MarcoFoto")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(QSize(400, 360))
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Clic para ampliar · Arrastra aquí una imagen para cambiarla")
        self._pm = None

    def poner(self, ruta):
        self._pm = QPixmap(ruta) if ruta and os.path.exists(ruta) else None
        if self._pm and not self._pm.isNull():
            self.setStyleSheet(f"#MarcoFoto {{ border: 1px solid {E.BORDE}; border-style: solid; }}")
        else:
            self._pm = None
            self.setStyleSheet("")
        self._render()

    def _render(self):
        if self._pm:
            dpr = self.devicePixelRatioF()
            pm = self._pm.scaled((self.size() - QSize(20, 20)) * dpr, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            self.setPixmap(pm)
        else:
            self.setPixmap(QPixmap())
            self.setText("📷\n\nSin foto\n\nHaz clic en «Cambiar foto»\no arrastra una imagen aquí")
            self.setStyleSheet(f"#MarcoFoto {{ color: {E.TEXTO_SUAVE}; font-size: 10.5pt; }}")

    def resizeEvent(self, ev):
        self._render()
        super().resizeEvent(ev)

    def mousePressEvent(self, ev):
        if self._pm:
            self._ficha().ampliar_foto()
        else:
            self._ficha().cambiar_foto()

    def dragEnterEvent(self, ev):
        urls = ev.mimeData().urls()
        if urls and urls[0].toLocalFile().lower().endswith(EXT_IMG):
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        self._ficha().establecer_foto(ev.mimeData().urls()[0].toLocalFile())


# ------------------------------------------------------------------ ficha
class FichaEquipo(QDialog):
    def __init__(self, db, eid=None, area_inicial=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.eid = eid
        self.datos = db.obtener(eid) if eid else {}
        self.foto_nueva = None          # ruta de imagen seleccionada, pendiente de guardar
        self.quitar_foto = False
        self.area_final = None

        self.setWindowTitle("Editar equipo" if eid else "Agregar equipo")
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # banda superior
        banda = QFrame()
        banda.setStyleSheet(f"background:{E.AZUL};")
        hb = QHBoxLayout(banda)
        hb.setContentsMargins(26, 16, 26, 16)
        cruz = QLabel()
        cruz.setPixmap(icono("cruz", "#FFFFFF", 26).pixmap(26, 26))
        hb.addWidget(cruz)
        self.lbl_cab = QLabel()
        self.lbl_cab.setStyleSheet("color:white; font-size:14pt; font-weight:700;")
        hb.addWidget(self.lbl_cab, 1)
        if eid:
            hb.addWidget(QLabel(f"Última actualización: {(self.datos.get('actualizado') or '').replace('T', ' ')}",
                                styleSheet="color:#C9D6F0; font-size:9pt;"))
        raiz.addWidget(banda)

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(24, 20, 24, 12)
        cuerpo.setSpacing(22)

        # --- columna foto
        colf = QVBoxLayout()
        colf.setSpacing(10)
        self.marco = MarcoFoto(self)
        colf.addWidget(self.marco, 1)
        bf = QHBoxLayout()
        b1 = QPushButton("  Cambiar foto")
        b1.setIcon(icono("camara", E.AZUL, 18))
        b1.clicked.connect(self.cambiar_foto)
        self.b_ampliar = QPushButton("  Ampliar")
        self.b_ampliar.setIcon(icono("ampliar", E.AZUL, 18))
        self.b_ampliar.clicked.connect(self.ampliar_foto)
        self.b_quitar = QPushButton("Quitar foto", objectName="Peligro")
        self.b_quitar.clicked.connect(self._quitar_foto)
        for b in (b1, self.b_ampliar, self.b_quitar):
            b.setCursor(Qt.PointingHandCursor)
            bf.addWidget(b)
        colf.addLayout(bf)
        wf = QWidget()
        wf.setLayout(colf)
        wf.setFixedWidth(430)
        cuerpo.addWidget(wf)

        # --- columna datos
        cold = QVBoxLayout()
        cold.setSpacing(12)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(4)

        def etiqueta(t):
            return QLabel(t.upper(), objectName="Etiqueta")

        self.s_folio = CampoFolio()
        self.s_folio.setToolTip("Número único del equipo. Puedes cambiarlo; no se permite repetir.")
        self.s_folio.setStyleSheet(f"font-weight:700; color:{E.AZUL};")
        self.e_inv = QLineEdit()
        self.e_inv.setPlaceholderText("Ej. 260401454")
        self.c_area = QComboBox()
        self.c_area.setEditable(True)
        self.c_area.addItems(db.areas())
        self.c_estado = QComboBox()
        self.c_estado.setEditable(True)
        for e in ESTADOS:
            self.c_estado.addItem(e if e else "(Sin especificar)", e)
        self.e_marca, self.e_modelo, self.e_serie = QLineEdit(), QLineEdit(), QLineEdit()

        g.addWidget(etiqueta("Folio único"), 0, 0)
        g.addWidget(etiqueta("No. de inventario"), 0, 1)
        g.addWidget(etiqueta("Área"), 0, 2)
        g.addWidget(etiqueta("Estado"), 0, 3)
        g.addWidget(self.s_folio, 1, 0)
        g.addWidget(self.e_inv, 1, 1)
        g.addWidget(self.c_area, 1, 2)
        g.addWidget(self.c_estado, 1, 3)
        g.addWidget(etiqueta("Marca"), 2, 0, 1, 2)
        g.addWidget(etiqueta("Modelo"), 2, 2)
        g.addWidget(etiqueta("Serie"), 2, 3)
        g.addWidget(self.e_marca, 3, 0, 1, 2)
        g.addWidget(self.e_modelo, 3, 2)
        g.addWidget(self.e_serie, 3, 3)
        g.setColumnStretch(0, 1)
        for c in (1, 2, 3):
            g.setColumnStretch(c, 2)
        g.setRowMinimumHeight(2, 26)
        cold.addLayout(g)

        cold.addWidget(etiqueta("Descripción"))
        self.t_desc = QPlainTextEdit()
        self.t_desc.setFixedHeight(70)
        cold.addWidget(self.t_desc)
        cold.addWidget(etiqueta("Observaciones"))
        self.t_obs = QPlainTextEdit()
        self.t_obs.setFixedHeight(56)
        cold.addWidget(self.t_obs)

        self.tabs = QTabWidget()
        self.t_prac, self.t_res, self.t_com = QPlainTextEdit(), QPlainTextEdit(), QPlainTextEdit()
        for t, nombre in ((self.t_prac, "Prácticas posibles"), (self.t_res, "Resumen"), (self.t_com, "Comentarios")):
            t.setStyleSheet("border:none;")
            t.setTabStopDistance(QFontMetricsF(t.font()).horizontalAdvance(" ") * 6)
            self.tabs.addTab(t, nombre)
        cold.addWidget(self.tabs, 1)
        cuerpo.addLayout(cold, 1)
        raiz.addLayout(cuerpo, 1)

        # --- botones
        pie = QHBoxLayout()
        pie.setContentsMargins(24, 6, 24, 18)
        if eid:
            be = QPushButton("  Eliminar equipo", objectName="Peligro")
            be.setIcon(icono("basura", E.ROJO, 18))
            be.clicked.connect(self.eliminar)
            pie.addWidget(be)
        pie.addStretch(1)
        bc = QPushButton("Cancelar")
        bc.clicked.connect(self.reject)
        bg = QPushButton("  Guardar cambios" if eid else "  Agregar al inventario", objectName="Primario")
        bg.setIcon(icono("guardar", "#FFFFFF", 18))
        bg.setDefault(True)
        bg.clicked.connect(self.guardar)
        for b in (bc, bg):
            b.setCursor(Qt.PointingHandCursor)
            pie.addWidget(b)
        raiz.addLayout(pie)

        self._llenar(area_inicial)

    # ---------- carga
    def _llenar(self, area_inicial):
        d = self.datos
        self.s_folio.setValue(d.get("folio") or self.db.proximo_folio())
        self.e_inv.setText(d.get("no_inventario", ""))
        self.c_area.setCurrentText(d.get("area") or area_inicial or "")
        est = d.get("estado", "")
        i = self.c_estado.findData(est)
        if i >= 0:
            self.c_estado.setCurrentIndex(i)
        else:
            self.c_estado.setCurrentText(est)
        self.e_marca.setText(d.get("marca", ""))
        self.e_modelo.setText(d.get("modelo", ""))
        self.e_serie.setText(d.get("serie", ""))
        self.t_desc.setPlainText(d.get("descripcion", ""))
        self.t_obs.setPlainText(d.get("observaciones", ""))
        self.t_prac.setPlainText(d.get("practicas", ""))
        self.t_res.setPlainText(d.get("resumen", ""))
        self.t_com.setPlainText(d.get("comentarios", ""))
        self._actualizar_cabecera()
        self.e_inv.textChanged.connect(self._actualizar_cabecera)
        self.s_folio.textChanged.connect(self._actualizar_cabecera)
        self._mostrar_foto()

    def _actualizar_cabecera(self):
        no = self.e_inv.text().strip()
        if self.eid:
            self.lbl_cab.setText(f"Equipo #{self.s_folio.text()}   ·   No. de inventario {no or 'S/N'}")
        else:
            self.lbl_cab.setText(f"Nuevo equipo #{self.s_folio.text()}{('   ·   No. ' + no) if no else ''}")

    def _ruta_foto_actual(self):
        if self.foto_nueva:
            return self.foto_nueva
        if self.quitar_foto or not self.datos.get("foto"):
            return None
        return os.path.join(FOTOS_DIR, self.datos["foto"])

    def _mostrar_foto(self):
        ruta = self._ruta_foto_actual()
        self.marco.poner(ruta)
        hay = bool(ruta)
        self.b_ampliar.setEnabled(hay)
        self.b_quitar.setEnabled(hay)

    # ---------- foto
    def cambiar_foto(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Seleccionar foto del equipo", "",
                                              "Imágenes (*.jpg *.jpeg *.png *.bmp *.webp *.gif *.tif *.tiff *.jfif)")
        if ruta:
            self.establecer_foto(ruta)

    def establecer_foto(self, ruta):
        try:
            Image.open(ruta).verify()
        except Exception:
            QMessageBox.warning(self, "Imagen no válida", "El archivo seleccionado no es una imagen válida.")
            return
        self.foto_nueva = ruta
        self.quitar_foto = False
        self._mostrar_foto()

    def _quitar_foto(self):
        self.foto_nueva = None
        self.quitar_foto = True
        self._mostrar_foto()

    def ampliar_foto(self):
        ruta = self._ruta_foto_actual()
        if ruta:
            visor = VisorFoto(ruta, f"Foto · No. {self.e_inv.text() or 'S/N'}", self)
            visor.exec()
            visor.deleteLater()

    def limpiar(self):
        """Corta conexiones y referencias antes de destruir la ficha."""
        try:
            self.e_inv.textChanged.disconnect()
            self.s_folio.textChanged.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.marco._pm = None

    # ---------- guardar / eliminar
    def _estado(self):
        t = self.c_estado.currentText().strip()
        return "" if t in ("", "(Sin especificar)") else t.upper()

    def guardar(self):
        datos = {
            "no_inventario": self.e_inv.text().strip(),
            "area": self.c_area.currentText().strip().upper(),
            "estado": self._estado(),
            "marca": self.e_marca.text().strip(),
            "modelo": self.e_modelo.text().strip(),
            "serie": self.e_serie.text().strip(),
            "descripcion": self.t_desc.toPlainText().strip(),
            "observaciones": self.t_obs.toPlainText().strip(),
            "practicas": self.t_prac.toPlainText().strip(),
            "resumen": self.t_res.toPlainText().strip(),
            "comentarios": self.t_com.toPlainText().strip(),
        }
        if not datos["no_inventario"] and not datos["descripcion"]:
            QMessageBox.warning(self, "Faltan datos", "Escribe al menos el número de inventario o la descripción.")
            return
        if not datos["area"]:
            QMessageBox.warning(self, "Faltan datos", "Selecciona o escribe el área.")
            return
        folio = self.s_folio.value()
        if folio < 1:
            QMessageBox.warning(self, "Folio", "Escribe un folio válido (número mayor a 0).")
            self.s_folio.setFocus()
            return
        if self.db.folio_en_uso(folio, self.eid):
            QMessageBox.warning(self, "Folio repetido",
                                f"El folio #{folio} ya lo tiene otro equipo.\nElige un número distinto.")
            self.s_folio.setFocus()
            return
        if self.db.existe_inventario(datos["no_inventario"], self.eid):
            r = QMessageBox.question(self, "Número repetido",
                                     f"Ya existe otro equipo con el No. {datos['no_inventario']}.\n¿Guardar de todos modos?")
            if r != QMessageBox.Yes:
                return

        self.db.agregar_area(datos["area"])
        if self.eid:
            self.db.actualizar_equipo(self.eid, datos)
        else:
            self.eid = self.db.agregar_equipo(datos)
        self.db.cambiar_folio(self.eid, folio)

        foto_vieja = self.datos.get("foto")
        if self.foto_nueva:
            try:
                nombre = guardar_imagen(self.foto_nueva, self.eid)
            except Exception as ex:
                QMessageBox.warning(self, "Foto", f"No se pudo guardar la foto:\n{ex}")
            else:
                self.db.actualizar_equipo(self.eid, {"foto": nombre})
                self._borrar_archivo(foto_vieja)
        elif self.quitar_foto:
            self.db.actualizar_equipo(self.eid, {"foto": ""})
            self._borrar_archivo(foto_vieja)

        self.area_final = datos["area"]
        self.accept()

    @staticmethod
    def _borrar_archivo(nombre):
        if nombre:
            p = os.path.join(FOTOS_DIR, nombre)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

    def eliminar(self):
        r = QMessageBox.question(self, "Eliminar equipo",
                                 f"¿Eliminar definitivamente el equipo No. {self.e_inv.text() or 'S/N'}?\n"
                                 "Esta acción no se puede deshacer.")
        if r == QMessageBox.Yes:
            self.db.eliminar_equipo(self.eid)
            self.area_final = self.datos.get("area")
            self.accept()
