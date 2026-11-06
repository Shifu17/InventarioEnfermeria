"""Pruebas de la interfaz sin pantalla (Qt offscreen)."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.db import AREA_BAJAS, ESTADO_BAJA


@pytest.fixture(scope="module")
def qapp():
    from app.estilos import QSS
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(QSS)
    return app


@pytest.fixture
def ventana(qapp, carpeta, monkeypatch):
    from app import ventana as V
    monkeypatch.setattr(V.VentanaPrincipal, "buscar_actualizaciones", lambda self, silencioso=False: None)
    v = V.VentanaPrincipal()
    v.resize(1300, 800)
    v.show()
    qapp.processEvents()
    yield v
    v.vigilante.stop()
    v.close()
    v.db.con.close()


def test_ficha_baja_mueve_area(ventana, qapp):
    from app.ficha import FichaEquipo
    eid = ventana.db.agregar_equipo({"no_inventario": "123", "area": "UCI", "estado": "FUNCIONAL"})
    dlg = FichaEquipo(ventana.db, eid, parent=ventana)
    i = dlg.c_estado.findData(ESTADO_BAJA)
    dlg.c_estado.setCurrentIndex(i)
    assert dlg.c_area.currentText() == AREA_BAJAS and not dlg.c_area.isEnabled()
    dlg.c_estado.setCurrentIndex(dlg.c_estado.findData("FUNCIONAL"))
    assert dlg.c_area.currentText() == "UCI" and dlg.c_area.isEnabled()
    dlg.c_estado.setCurrentIndex(i)
    dlg.e_costo.setText("2500")
    dlg._formatear_costo()
    assert dlg.e_costo.text() == "$2,500.00"
    dlg.guardar()
    eq = ventana.db.obtener(eid)
    assert eq["area"] == AREA_BAJAS and eq["costo"] == 2500.0 and eq["area_anterior"] == "UCI"
    dlg.limpiar()
    dlg.deleteLater()


def test_areas_en_mayusculas_y_bajas_al_final(ventana):
    ventana.db.agregar_equipo({"no_inventario": "1", "area": "quirófano"})
    ventana.db.agregar_equipo({"no_inventario": "2", "area": "uci", "estado": ESTADO_BAJA})
    ventana.cargar_areas()
    textos = [ventana.lista_areas.item(i).text() for i in range(ventana.lista_areas.count())]
    assert textos[0].startswith("TODAS LAS ÁREAS")
    assert textos[-1].startswith(AREA_BAJAS)
    assert all(t == t.upper() for t in textos)


def test_renombrar_desde_ventana(ventana, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    ventana.db.agregar_equipo({"no_inventario": "1", "area": "LAB"})
    ventana.cargar_areas()
    item = next(ventana.lista_areas.item(i) for i in range(ventana.lista_areas.count())
                if ventana.lista_areas.item(i).data(Qt.UserRole) == "LAB")
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("laboratorio", True))
    ventana.renombrar_area(item)
    assert ventana.area_actual == "LABORATORIO"
    assert ventana.lbl_titulo.text() == "LABORATORIO"


def test_recarga_automatica(ventana, carpeta, qapp):
    from app import db as BD
    otra = BD.Database(str(carpeta / "inventario.db"))
    otra.agregar_equipo({"no_inventario": "777", "area": "NUEVA"})
    otra.con.close()
    ventana._revisar_cambios_externos()
    assert any(f["no_inventario"] == "777" for f in ventana.modelo.filas)
    assert ventana.lbl_aviso.isVisibleTo(ventana)


def test_columna_costo_y_flecha_combobox(ventana, qapp):
    from app import ventana as V
    import os
    from app import estilos as E
    QSS, _FLECHA = E.construir_qss(), E._ruta_recurso(E.FLECHA)
    ventana.db.agregar_equipo({"no_inventario": "1", "area": "UCI", "costo": 1234.5})
    ventana.refrescar()
    col = [c for c, _ in V.COLUMNAS].index("costo")
    assert ventana.modelo.data(ventana.modelo.index(0, col)) == "$1,234.50"
    assert "valor $1,234.50" in ventana.lbl_sub.text()
    assert os.path.exists(_FLECHA) and "down-arrow" in QSS


def test_exportar_excel(ventana, tmp_path):
    from openpyxl import load_workbook
    from app.exportar import exportar
    ventana.db.agregar_equipo({"no_inventario": "1", "area": "UCI", "costo": 100})
    ventana.db.agregar_equipo({"no_inventario": "2", "area": "UCI", "costo": 50})
    ruta = tmp_path / "x.xlsx"
    assert exportar(ventana.db, str(ruta)) == 2
    ws = load_workbook(ruta)["UCI"]
    encabezados = [c.value for c in ws[1]]
    assert "COSTO (MXN)" in encabezados
    col = encabezados.index("COSTO (MXN)") + 1
    assert ws.cell(4, col).value.startswith("=SUM(")


def test_modo_oscuro(ventana, qapp):
    from app import db as BD
    from app import estilos as E
    assert not E.es_oscuro()
    ventana.alternar_tema()
    try:
        assert E.es_oscuro() and E.FONDO == E.TEMAS["oscuro"]["FONDO"]
        assert E.TEMAS["oscuro"]["FONDO"] in qapp.styleSheet()
        assert BD.leer_config()["tema"] == "oscuro"
        assert ventana.btn_tema.text().strip() == "Modo claro"
        qapp.processEvents()
        ventana.grab()          # pinta tarjetas con los colores oscuros sin errores
    finally:
        ventana.alternar_tema()
    assert not E.es_oscuro() and BD.leer_config()["tema"] == "claro"
