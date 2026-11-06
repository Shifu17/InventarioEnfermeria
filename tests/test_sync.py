"""Sincronización entre computadoras, con un GitHub simulado en memoria."""
import hashlib
import os
import sqlite3

import pytest

from app import db as BD
from app.nube import ARCHIVO_DOC, Conflicto
from app.sincronizacion import combinar, sincronizar


class NubeFalsa:
    """Imita app.nube.Nube: un historial de commits con archivos {ruta: bytes}."""

    def __init__(self):
        self.commits = {}          # sha -> {ruta: sha_blob}
        self.blobs = {}
        self.head = None
        self.conflictos_pendientes = 0
        self.subidas = 0

    def cabeza(self):
        return self.head

    def arbol(self, sha):
        return sha, dict(self.commits[sha])

    def blob(self, sha):
        return self.blobs[sha]

    def subir(self, padre, arbol_base, archivos, mensaje):
        if self.conflictos_pendientes:
            self.conflictos_pendientes -= 1
            raise Conflicto("simulado")
        if padre != self.head:
            raise Conflicto("no es fast-forward")
        arbol = dict(self.commits[padre]) if padre else {}
        for ruta, contenido in archivos.items():
            b = hashlib.sha1(contenido).hexdigest()
            self.blobs[b] = contenido
            arbol[ruta] = b
        sha = hashlib.sha1(repr(sorted(arbol.items())).encode() + str(len(self.commits)).encode()).hexdigest()
        self.commits[sha] = arbol
        self.head = sha
        self.subidas += 1
        return sha


class PC:
    """Una computadora: su propia carpeta de datos."""

    def __init__(self, tmp_path, nombre):
        self.dir = tmp_path / nombre
        (self.dir / "fotos").mkdir(parents=True)
        self.db_path = str(self.dir / "inventario.db")
        BD.usar_carpeta(str(self.dir))
        self.db = BD.Database(self.db_path)

    def usar(self):
        BD.usar_carpeta(str(self.dir))
        return self.db

    def sync(self, nube):
        return sincronizar(nube, self.db_path, str(self.dir / "fotos"), str(self.dir))

    def equipos(self):
        return {f["no_inventario"]: f for f in self.usar().buscar()}


@pytest.fixture
def nube():
    return NubeFalsa()


@pytest.fixture
def pcs(tmp_path):
    yield PC(tmp_path, "a"), PC(tmp_path, "b")
    BD.usar_carpeta(BD.CARPETA_LOCAL)


def test_computadora_nueva_descarga_todo_con_fotos(pcs, nube):
    a, b = pcs
    eid = a.usar().agregar_equipo({"no_inventario": "100", "area": "UCI", "costo": 50})
    (a.dir / "fotos" / "f1.jpg").write_bytes(b"FOTO")
    a.db.actualizar_equipo(eid, {"foto": "f1.jpg"})
    r = a.sync(nube)
    assert r["subido"] and r["fotos_subidas"] == 1
    assert ARCHIVO_DOC in nube.commits[nube.head]

    r = b.sync(nube)
    assert r["bajados"] > 0 and r["fotos_bajadas"] == 1 and not r["subido"]
    eq = b.equipos()["100"]
    assert eq["area"] == "UCI" and eq["costo"] == 50 and eq["foto"] == "f1.jpg"
    assert (b.dir / "fotos" / "f1.jpg").read_bytes() == b"FOTO"
    assert "UCI" in b.usar().areas()


def test_sin_cambios_no_sube_de_nuevo(pcs, nube):
    a, _ = pcs
    a.usar().agregar_equipo({"no_inventario": "1", "area": "UCI"})
    a.sync(nube)
    a.sync(nube)
    a.sync(nube)
    assert nube.subidas == 1


def test_cambios_en_equipos_distintos_se_conservan(pcs, nube):
    a, b = pcs
    ea = a.usar().agregar_equipo({"no_inventario": "1", "area": "UCI"})
    a.usar().agregar_equipo({"no_inventario": "2", "area": "UCI"})
    a.sync(nube)
    b.sync(nube)
    # Las dos trabajan sin conexión sobre equipos distintos
    a.usar().actualizar_equipo(ea, {"marca": "MARCA A"})
    eb = b.equipos()["2"]["id"]
    b.usar().actualizar_equipo(eb, {"marca": "MARCA B"})
    a.sync(nube)
    b.sync(nube)
    a.sync(nube)
    for pc in (a, b):
        e = pc.equipos()
        assert e["1"]["marca"] == "MARCA A" and e["2"]["marca"] == "MARCA B"


def test_mismo_equipo_gana_el_cambio_mas_reciente(pcs, nube):
    a, b = pcs
    ea = a.usar().agregar_equipo({"no_inventario": "1", "area": "UCI"})
    a.sync(nube)
    b.sync(nube)
    eb = b.equipos()["1"]["id"]
    a.usar().actualizar_equipo(ea, {"marca": "VIEJA"})
    b.usar().actualizar_equipo(eb, {"marca": "NUEVA"})
    b.db.con.execute("UPDATE equipos SET t=t+10 WHERE id=?", (eb,))
    b.db.con.commit()
    a.sync(nube)
    b.sync(nube)
    a.sync(nube)
    assert a.equipos()["1"]["marca"] == b.equipos()["1"]["marca"] == "NUEVA"


def test_borrado_se_propaga_y_no_revive(pcs, nube):
    a, b = pcs
    ea = a.usar().agregar_equipo({"no_inventario": "1", "area": "UCI"})
    a.sync(nube)
    b.sync(nube)
    a.usar().eliminar_equipo(ea)
    a.sync(nube)
    b.sync(nube)
    assert "1" not in b.equipos()
    b.sync(nube)
    a.sync(nube)
    assert "1" not in a.equipos()


def test_renombrar_area_se_propaga(pcs, nube):
    a, b = pcs
    a.usar().agregar_equipo({"no_inventario": "1", "area": "LAB"})
    a.sync(nube)
    b.sync(nube)
    b.usar().renombrar_area("LAB", "LABORATORIO")
    b.sync(nube)
    a.sync(nube)
    assert a.usar().areas() == ["LABORATORIO"]
    assert a.equipos()["1"]["area"] == "LABORATORIO"


def test_dos_altas_sin_conexion_con_el_mismo_folio(pcs, nube):
    a, b = pcs
    a.usar().agregar_equipo({"no_inventario": "BASE", "area": "UCI"})
    a.sync(nube)
    b.sync(nube)
    a.usar().agregar_equipo({"no_inventario": "DE-A", "area": "UCI"})     # folio 2 en A
    b.usar().agregar_equipo({"no_inventario": "DE-B", "area": "UCI"})     # folio 2 en B
    a.sync(nube)
    b.sync(nube)
    a.sync(nube)
    fa, fb = a.equipos(), b.equipos()
    assert set(fa) == set(fb) == {"BASE", "DE-A", "DE-B"}
    folios = sorted(f["folio"] for f in fa.values())
    assert folios == [1, 2, 3]
    assert {k: v["folio"] for k, v in fa.items()} == {k: v["folio"] for k, v in fb.items()}
    assert a.usar().proximo_folio() == 4


def test_reintenta_si_otra_pc_sube_al_mismo_tiempo(pcs, nube):
    a, _ = pcs
    a.usar().agregar_equipo({"no_inventario": "1", "area": "UCI"})
    nube.conflictos_pendientes = 2
    assert a.sync(nube)["subido"]


def test_dos_pcs_con_el_inventario_viejo_no_duplican(tmp_path, nube):
    """Dos computadoras que usaban la v1.0 con el mismo inventario inicial (sin identificador)."""
    for nombre in ("a", "b"):
        d = tmp_path / nombre
        (d / "fotos").mkdir(parents=True)
        con = sqlite3.connect(d / "inventario.db")
        con.executescript("""
            CREATE TABLE areas(nombre TEXT PRIMARY KEY, orden INTEGER);
            CREATE TABLE equipos(id INTEGER PRIMARY KEY AUTOINCREMENT, no_inventario TEXT, area TEXT,
                descripcion TEXT, observaciones TEXT, marca TEXT, modelo TEXT, serie TEXT, estado TEXT DEFAULT '',
                practicas TEXT, resumen TEXT, comentarios TEXT, foto TEXT, creado TEXT, actualizado TEXT,
                folio INTEGER);
            CREATE TABLE meta(clave TEXT PRIMARY KEY, valor TEXT);
            INSERT INTO areas VALUES('UCIN', 1);
            INSERT INTO equipos(no_inventario, area, folio) VALUES('10', 'UCIN', 1), ('11', 'UCIN', 2);
        """)
        con.commit()
        con.close()
    try:
        for nombre in ("a", "b", "a"):
            BD.usar_carpeta(str(tmp_path / nombre))
            BD.Database().con.close()
            sincronizar(nube, str(tmp_path / nombre / "inventario.db"), str(tmp_path / nombre / "fotos"),
                        str(tmp_path / nombre))
        for nombre in ("a", "b"):
            con = sqlite3.connect(tmp_path / nombre / "inventario.db")
            assert con.execute("SELECT COUNT(*) FROM equipos").fetchone()[0] == 2
            con.close()
    finally:
        BD.usar_carpeta(BD.CARPETA_LOCAL)


def test_combinar_es_simetrico():
    a = {"registros": {"e:1": {"t": 5, "marca": "A"}, "a:X": {"t": 1, "orden": 1}}, "meta": {"ultimo_folio": 3}}
    b = {"registros": {"e:1": {"t": 7, "marca": "B"}, "a:X": {"borrado": True, "t": 2}}, "meta": {"ultimo_folio": 1}}
    assert combinar(a, b) == combinar(b, a)
    assert combinar(a, b)["registros"]["e:1"]["marca"] == "B"
    assert combinar(a, b)["registros"]["a:X"]["borrado"]
