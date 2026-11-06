import sqlite3

import pytest

from app import db as BD
from app.actualizador import es_mas_nueva, version_tupla
from app.db import AREA_BAJAS, ESTADO_BAJA


def nuevo(base, **kw):
    datos = {"no_inventario": "1", "area": "UCI", "descripcion": "Monitor", "estado": "FUNCIONAL"}
    datos.update(kw)
    eid = base.agregar_equipo(datos)
    return base.obtener(eid)


# ---------------------------------------------------------------- dados de baja
def test_al_dar_de_baja_pasa_al_area_de_bajas_y_regresa(base):
    eq = nuevo(base, area="Quirófano")
    assert eq["area"] == "QUIRÓFANO"
    base.actualizar_equipo(eq["id"], {"estado": ESTADO_BAJA})
    eq = base.obtener(eq["id"])
    assert eq["area"] == AREA_BAJAS
    assert eq["area_anterior"] == "QUIRÓFANO"
    assert base.areas()[-1] == AREA_BAJAS
    # Si se reactiva, vuelve a su área original
    base.actualizar_equipo(eq["id"], {"estado": "FUNCIONAL", "area": AREA_BAJAS})
    eq = base.obtener(eq["id"])
    assert eq["area"] == "QUIRÓFANO"
    assert eq["area_anterior"] is None


def test_alta_directa_como_baja(base):
    eq = nuevo(base, area="uci", estado=ESTADO_BAJA)
    assert eq["area"] == AREA_BAJAS and eq["area_anterior"] == "UCI"


def test_area_de_bajas_siempre_al_final(base):
    nuevo(base, area="A", estado=ESTADO_BAJA)
    base.agregar_area("Z nueva")
    assert base.areas()[-1] == AREA_BAJAS
    assert "Z NUEVA" in base.areas()


# ---------------------------------------------------------------- migración de bases anteriores
def test_migra_base_v1(carpeta):
    con = sqlite3.connect(carpeta / "inventario.db")
    con.executescript("""
        CREATE TABLE areas(nombre TEXT PRIMARY KEY, orden INTEGER);
        CREATE TABLE equipos(id INTEGER PRIMARY KEY AUTOINCREMENT, no_inventario TEXT, area TEXT,
            descripcion TEXT, observaciones TEXT, marca TEXT, modelo TEXT, serie TEXT, estado TEXT DEFAULT '',
            practicas TEXT, resumen TEXT, comentarios TEXT, foto TEXT, creado TEXT, actualizado TEXT);
        INSERT INTO areas VALUES('Simulación', 1), ('UCIN', 2);
        INSERT INTO equipos(no_inventario, area, estado) VALUES('10', 'Simulación', 'FUNCIONAL');
        INSERT INTO equipos(no_inventario, area, estado) VALUES('11', 'UCIN', 'DADO DE BAJA');
    """)
    con.commit()
    con.close()
    d = BD.Database()
    try:
        assert d.areas() == ["SIMULACIÓN", "UCIN", AREA_BAJAS]
        filas = {f["no_inventario"]: f for f in d.buscar()}
        assert filas["10"]["area"] == "SIMULACIÓN" and filas["10"]["folio"] == 1
        assert filas["11"]["area"] == AREA_BAJAS and filas["11"]["area_anterior"] == "UCIN"
        assert filas["11"]["costo"] is None
    finally:
        d.con.close()


# ---------------------------------------------------------------- renombrar áreas
def test_renombrar_area(base):
    eq = nuevo(base, area="Lab 1")
    final = base.renombrar_area("LAB 1", "laboratorio  de simulación")
    assert final == "LABORATORIO DE SIMULACIÓN"
    assert base.obtener(eq["id"])["area"] == final
    assert "LAB 1" not in base.areas() and final in base.areas()


def test_renombrar_actualiza_area_anterior_de_bajas(base):
    eq = nuevo(base, area="LAB", estado=ESTADO_BAJA)
    base.renombrar_area("LAB", "LABORATORIO")
    assert base.obtener(eq["id"])["area_anterior"] == "LABORATORIO"


def test_renombrar_a_area_existente_une(base):
    a = nuevo(base, area="A")
    b = nuevo(base, no_inventario="2", area="B")
    base.renombrar_area("A", "B")
    assert base.obtener(a["id"])["area"] == "B" == base.obtener(b["id"])["area"]
    assert base.areas().count("B") == 1 and "A" not in base.areas()


def test_area_de_bajas_protegida(base):
    nuevo(base, estado=ESTADO_BAJA)
    with pytest.raises(ValueError):
        base.renombrar_area(AREA_BAJAS, "OTRA")
    with pytest.raises(ValueError):
        base.renombrar_area("UCI", AREA_BAJAS)


# ---------------------------------------------------------------- costos
@pytest.mark.parametrize("entrada,esperado", [
    ("$1,234.50", 1234.5), ("1234", 1234.0), (" 99.999 ", 100.0), ("", None), (None, None), (15, 15.0), ("abc", None),
])
def test_a_costo(entrada, esperado):
    assert BD.a_costo(entrada) == esperado


def test_costo_guardado_y_total(base):
    a = nuevo(base, costo="$1,500.00")
    nuevo(base, no_inventario="2", costo=250.25)
    nuevo(base, no_inventario="3")
    assert a["costo"] == 1500.0
    assert base.costo_total() == pytest.approx(1750.25)
    assert base.costo_total("UCI") == pytest.approx(1750.25)
    base.actualizar_equipo(a["id"], {"costo": ""})
    assert base.obtener(a["id"])["costo"] is None
    assert BD.formato_costo(1234.5) == "$1,234.50" and BD.formato_costo(None) == ""


# ---------------------------------------------------------------- recarga cuando otra conexión escribe
def test_detecta_cambios_de_otra_computadora(base, carpeta):
    assert base.hubo_cambios_externos() is False
    nuevo(base)                        # cambio propio: no cuenta como externo
    assert base.hubo_cambios_externos() is False
    otra = BD.Database(str(carpeta / "inventario.db"))   # "otra PC" sobre el mismo archivo
    otra.agregar_equipo({"no_inventario": "99", "area": "UCI"})
    otra.con.close()
    assert base.hubo_cambios_externos() is True
    assert any(f["no_inventario"] == "99" for f in base.buscar())
    assert base.hubo_cambios_externos() is False






# ---------------------------------------------------------------- búsqueda (comportamiento previo intacto)
def test_busqueda_por_lista_y_rango(base):
    for i in range(1, 8):
        nuevo(base, no_inventario=f"X{i}")
    assert [f["folio"] for f in base.buscar("1,3")] == [1, 3]
    assert [f["folio"] for f in base.buscar("2-4")] == [2, 3, 4]
    assert [f["folio"] for f in base.buscar("#5")] == [5]


# ---------------------------------------------------------------- versiones
def test_versiones():
    assert version_tupla("v1.2.10") == (1, 2, 10)
    assert version_tupla("1.1") == (1, 1, 0)
    assert es_mas_nueva("v1.1.1", "1.1.0")
    assert es_mas_nueva("v1.10.0", "1.9.9")
    assert not es_mas_nueva("v1.1.0", "1.1.0")
    assert not es_mas_nueva("v1.0.9", "1.1.0")
