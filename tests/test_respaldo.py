"""Exportar la base en una computadora e importarla en otra."""
import os
import zipfile

import pytest

from app import db as BD
from app import respaldo


def _pc(tmp_path, nombre):
    d = tmp_path / nombre
    (d / "fotos").mkdir(parents=True)
    BD.usar_carpeta(str(d))
    return d, BD.Database()


@pytest.fixture(autouse=True)
def _restaurar():
    yield
    BD.usar_carpeta(BD.CARPETA_LOCAL)


def test_exportar_e_importar_en_otra_computadora(tmp_path):
    a, db_a = _pc(tmp_path, "a")
    eid = db_a.agregar_equipo({"no_inventario": "100", "area": "UCI", "costo": 1500, "estado": "FUNCIONAL"})
    (a / "fotos" / "f1.jpg").write_bytes(b"FOTO-1")
    (a / "fotos" / "huerfana.jpg").write_bytes(b"NO SE USA")
    db_a.actualizar_equipo(eid, {"foto": "f1.jpg"})
    db_a.agregar_equipo({"no_inventario": "101", "area": "QUIRÓFANO", "estado": "DADO DE BAJA"})
    zip_path = str(tmp_path / "respaldo.zip")
    assert respaldo.exportar_base(zip_path) == (2, 1)
    db_a.con.close()
    with zipfile.ZipFile(zip_path) as z:
        assert set(z.namelist()) == {respaldo.MARCA, "inventario.db", "fotos/f1.jpg"}

    b, db_b = _pc(tmp_path, "b")
    db_b.agregar_equipo({"no_inventario": "VIEJO", "area": "OTRA"})
    db_b.con.close()
    assert respaldo.revisar_archivo(zip_path) == 2
    n, previo = respaldo.importar_base(zip_path)
    assert n == 2 and previo and os.path.exists(previo)

    db_b = BD.Database()
    equipos = {f["no_inventario"]: f for f in db_b.buscar()}
    assert set(equipos) == {"100", "101"}
    assert equipos["100"]["costo"] == 1500 and equipos["100"]["foto"] == "f1.jpg"
    assert equipos["101"]["area"] == BD.AREA_BAJAS
    assert (b / "fotos" / "f1.jpg").read_bytes() == b"FOTO-1"
    assert db_b.areas()[-1] == BD.AREA_BAJAS
    db_b.con.close()

    # El respaldo automático permite volver al inventario anterior
    respaldo.importar_base(previo)
    db_b = BD.Database()
    assert [f["no_inventario"] for f in db_b.buscar()] == ["VIEJO"]
    db_b.con.close()


@pytest.mark.parametrize("contenido", [b"no soy un zip", None])
def test_archivo_no_valido(tmp_path, contenido):
    ruta = tmp_path / "x.zip"
    if contenido is None:
        with zipfile.ZipFile(ruta, "w") as z:
            z.writestr("otra_cosa.txt", "hola")
    else:
        ruta.write_bytes(contenido)
    with pytest.raises(respaldo.ArchivoNoValido):
        respaldo.revisar_archivo(str(ruta))


def test_rechaza_rutas_peligrosas(tmp_path):
    a, db_a = _pc(tmp_path, "a")
    db_a.con.close()
    ruta = tmp_path / "malo.zip"
    with zipfile.ZipFile(ruta, "w") as z:
        z.write(a / "inventario.db", "inventario.db")
        z.writestr("../../fuera.txt", "x")
    with pytest.raises(respaldo.ArchivoNoValido):
        respaldo.revisar_archivo(str(ruta))


def test_botones_de_la_ventana(qapp_y_ventana, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    v = qapp_y_ventana
    v.db.agregar_equipo({"no_inventario": "7", "area": "UCI"})
    destino = str(tmp_path / "exportado.zip")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (destino, ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (destino, ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    v.exportar_base()
    assert os.path.exists(destino)
    v.db.agregar_equipo({"no_inventario": "8", "area": "UCI"})
    v.refrescar()
    assert v.modelo.rowCount() == 2
    v.importar_base()
    assert [f["no_inventario"] for f in v.modelo.filas] == ["7"]
    assert "1 equipo" in v.lbl_datos.text()
