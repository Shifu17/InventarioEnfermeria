"""Capa de datos: SQLite en %LOCALAPPDATA%/InventarioEnfermeria de cada computadora.

Para pasar el inventario a otra computadora se exporta/importa completo (ver app/respaldo.py).
Cada equipo conserva un identificador (`uid`) y la marca de tiempo de su último cambio (`t`).
"""
import json
import os
import re
import sqlite3
import sys
import time
import uuid
from datetime import datetime

CONGELADO = getattr(sys, "frozen", False)

AREA_BAJAS = "EQUIPOS DADOS DE BAJA"
ESTADO_BAJA = "DADO DE BAJA"


def _carpeta_local():
    # En el .exe los datos viven en %LOCALAPPDATA%; desde el código, en la carpeta del proyecto.
    if os.environ.get("INVENTARIO_CARPETA_LOCAL"):
        return os.environ["INVENTARIO_CARPETA_LOCAL"]
    if CONGELADO:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "InventarioEnfermeria")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos")


CARPETA_LOCAL = _carpeta_local()
CONFIG_PATH = os.path.join(CARPETA_LOCAL, "config.json")


# ------------------------------------------------------------------ configuración
def leer_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def guardar_config(**cambios):
    cfg = leer_config()
    cfg.update(cambios)
    os.makedirs(CARPETA_LOCAL, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)


DATA_DIR = FOTOS_DIR = DB_PATH = ""


def usar_carpeta(carpeta):
    """Cambia la carpeta de datos activa (base de datos + fotos)."""
    global DATA_DIR, FOTOS_DIR, DB_PATH
    DATA_DIR = os.path.abspath(carpeta)
    FOTOS_DIR = os.path.join(DATA_DIR, "fotos")
    DB_PATH = os.path.join(DATA_DIR, "inventario.db")


usar_carpeta(CARPETA_LOCAL)


def ruta_foto(nombre):
    return os.path.join(FOTOS_DIR, nombre) if nombre else ""


def preparar_datos():
    os.makedirs(FOTOS_DIR, exist_ok=True)


def ahora_ms():
    return int(time.time() * 1000)


CAMPOS = ["no_inventario", "area", "descripcion", "observaciones", "marca", "modelo",
          "serie", "estado", "practicas", "resumen", "comentarios", "foto", "costo"]
# Campos de un equipo que viajan en el inventario en línea
CAMPOS_DOC = CAMPOS + ["folio", "area_anterior", "creado", "actualizado"]

ESTADOS = ["", "FUNCIONAL", "MAL ESTADO", "PENDIENTE DE VALORAR", "EN REPARACIÓN", ESTADO_BAJA]

ETIQUETAS = {
    "no_inventario": "No. de inventario", "area": "Área", "descripcion": "Descripción",
    "observaciones": "Observaciones", "marca": "Marca", "modelo": "Modelo", "serie": "Serie",
    "estado": "Estado", "practicas": "Prácticas posibles", "resumen": "Resumen",
    "comentarios": "Comentarios", "foto": "Foto", "costo": "Costo",
}


def normalizar_area(nombre):
    return re.sub(r"\s+", " ", (nombre or "").strip()).upper()


def a_costo(valor):
    """'$1,234.50' / 1234.5 / '' -> 1234.5 o None."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return round(float(valor), 2)
    t = re.sub(r"[^\d.\-]", "", str(valor).replace(",", ""))
    try:
        return round(float(t), 2) if t else None
    except ValueError:
        return None


def formato_costo(valor):
    return "" if valor is None or valor == "" else f"${float(valor):,.2f}"


# ------------------------------------------------------------------ esquema
def conectar(path):
    # timeout alto por si otra conexión está escribiendo en ese momento.
    con = sqlite3.connect(path, timeout=20)
    con.row_factory = sqlite3.Row
    return con


def crear_esquema(con):
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS areas(
            nombre TEXT PRIMARY KEY, orden INTEGER);
        CREATE TABLE IF NOT EXISTS equipos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            no_inventario TEXT, area TEXT, descripcion TEXT, observaciones TEXT,
            marca TEXT, modelo TEXT, serie TEXT, estado TEXT DEFAULT '',
            practicas TEXT, resumen TEXT, comentarios TEXT, foto TEXT,
            creado TEXT, actualizado TEXT);
        CREATE INDEX IF NOT EXISTS ix_inv ON equipos(no_inventario);
        CREATE TABLE IF NOT EXISTS meta(clave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE IF NOT EXISTS borrados(clave TEXT PRIMARY KEY, t INTEGER);
        """
    )
    cols = [r[1] for r in con.execute("PRAGMA table_info(equipos)")]
    for col, tipo in (("folio", "INTEGER"), ("costo", "REAL"), ("area_anterior", "TEXT"),
                      ("uid", "TEXT"), ("t", "INTEGER DEFAULT 0")):
        if col not in cols:
            con.execute(f"ALTER TABLE equipos ADD COLUMN {col} {tipo}")
    if "t" not in [r[1] for r in con.execute("PRAGMA table_info(areas)")]:
        con.execute("ALTER TABLE areas ADD COLUMN t INTEGER DEFAULT 0")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_folio ON equipos(folio)")


class Database:
    def __init__(self, path=None):
        preparar_datos()
        self.path = path or DB_PATH
        self.con = None
        self._abrir()

    # ---- conexión / detección de cambios hechos por otra conexión ----
    def _abrir(self):
        if self.con is not None:
            try:
                self.con.close()
            except sqlite3.Error:
                pass
        self.con = conectar(self.path)
        self._migrar()
        self._version = self._data_version()

    def _data_version(self):
        try:
            return self.con.execute("PRAGMA data_version").fetchone()[0]
        except sqlite3.Error:
            return None

    def _commit(self):
        self.con.commit()
        self._version = self._data_version()

    def hubo_cambios_externos(self):
        """True si otra conexión modificó la base desde la última lectura."""
        v = self._data_version()
        if v != self._version:
            self._version = v
            return True
        return False

    def _migrar(self):
        crear_esquema(self.con)
        # Equipos sin folio (bases anteriores): se numeran en orden de alta.
        for (eid,) in self.con.execute("SELECT id FROM equipos WHERE folio IS NULL ORDER BY id").fetchall():
            self.con.execute("UPDATE equipos SET folio=? WHERE id=?", (self._siguiente_folio(), eid))
        # Identificador global. Los equipos que ya existían usan su folio, así dos computadoras que
        # partieron del mismo inventario reconocen que se trata del mismo equipo.
        self.con.execute("UPDATE equipos SET uid='folio-' || folio WHERE uid IS NULL")
        self.con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_uid ON equipos(uid)")
        self._areas_en_mayusculas()
        self._mover_bajas()
        if self.con.in_transaction:
            self.con.commit()

    def _areas_en_mayusculas(self):
        """Todas las áreas en mayúsculas (incluye acentos, que UPPER() de SQLite no convierte)."""
        for (nombre,) in self.con.execute("SELECT nombre FROM areas").fetchall():
            nuevo = normalizar_area(nombre)
            if nuevo != nombre:
                self._renombrar_sin_commit(nombre, nuevo)
        for (area,) in self.con.execute("SELECT DISTINCT area FROM equipos WHERE area IS NOT NULL").fetchall():
            nuevo = normalizar_area(area)
            if nuevo != area:
                self.con.execute("UPDATE equipos SET area=?, t=? WHERE area=?", (nuevo, ahora_ms(), area))

    def _mover_bajas(self):
        """Los equipos dados de baja viven siempre en el área de bajas."""
        filas = self.con.execute("SELECT id, area FROM equipos WHERE estado=? AND area IS NOT ?",
                                 (ESTADO_BAJA, AREA_BAJAS)).fetchall()
        for eid, area in filas:
            self.con.execute("UPDATE equipos SET area_anterior=?, area=?, t=? WHERE id=?",
                             (area, AREA_BAJAS, ahora_ms(), eid))
        if filas:
            self._asegurar_area_bajas()

    def _asegurar_area_bajas(self):
        self._insertar_area(AREA_BAJAS, 1000000)

    def _insertar_area(self, nombre, orden):
        if self.con.execute("SELECT 1 FROM areas WHERE nombre=?", (nombre,)).fetchone():
            return
        self.con.execute("INSERT INTO areas(nombre, orden, t) VALUES(?,?,?)", (nombre, orden, ahora_ms()))
        self.con.execute("DELETE FROM borrados WHERE clave=?", ("a:" + nombre,))

    # ---- folios ----
    def proximo_folio(self):
        """Folio que se asignaría al siguiente equipo (sin reservarlo)."""
        r = self.con.execute("SELECT valor FROM meta WHERE clave='ultimo_folio'").fetchone()
        maximo = self.con.execute("SELECT COALESCE(MAX(folio),0) FROM equipos").fetchone()[0]
        return max(int(r[0]) if r else 0, maximo) + 1

    def folio_en_uso(self, folio, excluir_id=None):
        r = self.con.execute("SELECT folio FROM equipos WHERE folio=? AND id IS NOT ?", (folio, excluir_id)).fetchone()
        return r is not None

    def cambiar_folio(self, eid, folio):
        actual = self.con.execute("SELECT folio FROM equipos WHERE id=?", (eid,)).fetchone()
        if actual is not None and actual[0] != folio:
            self.con.execute("UPDATE equipos SET folio=?, t=? WHERE id=?", (folio, ahora_ms(), eid))
        r = self.con.execute("SELECT valor FROM meta WHERE clave='ultimo_folio'").fetchone()
        if folio > (int(r[0]) if r else 0):
            self.con.execute("INSERT OR REPLACE INTO meta(clave, valor) VALUES('ultimo_folio', ?)", (str(folio),))
        self._commit()

    def _siguiente_folio(self):
        """Folio único y consecutivo; nunca se reutiliza aunque se elimine un equipo."""
        n = self.proximo_folio()
        self.con.execute("INSERT OR REPLACE INTO meta(clave, valor) VALUES('ultimo_folio', ?)", (str(n),))
        return n

    # ---- áreas ----
    def areas(self):
        """Áreas en su orden; la de equipos dados de baja siempre al final."""
        nombres = [r["nombre"] for r in self.con.execute("SELECT nombre FROM areas ORDER BY orden, nombre")]
        if AREA_BAJAS in nombres:
            nombres.remove(AREA_BAJAS)
            nombres.append(AREA_BAJAS)
        return nombres

    def agregar_area(self, nombre):
        nombre = normalizar_area(nombre)
        if not nombre:
            return
        if nombre == AREA_BAJAS:
            self._asegurar_area_bajas()
        else:
            orden = self.con.execute(
                "SELECT COALESCE(MAX(orden),0)+1 FROM areas WHERE nombre<>?", (AREA_BAJAS,)).fetchone()[0]
            self._insertar_area(nombre, orden)
        self._commit()

    def existe_area(self, nombre):
        nombre = normalizar_area(nombre)
        return bool(self.con.execute("SELECT 1 FROM areas WHERE nombre=?", (nombre,)).fetchone()
                    or self.con.execute("SELECT 1 FROM equipos WHERE area=? LIMIT 1", (nombre,)).fetchone())

    def _renombrar_sin_commit(self, viejo, nuevo):
        t = ahora_ms()
        fila = self.con.execute("SELECT orden FROM areas WHERE nombre=?", (viejo,)).fetchone()
        if fila is not None:
            self.con.execute("DELETE FROM areas WHERE nombre=?", (viejo,))
            self.con.execute("INSERT OR REPLACE INTO borrados(clave, t) VALUES(?,?)", ("a:" + viejo, t))
            self._insertar_area(nuevo, fila["orden"])
        else:
            orden = self.con.execute("SELECT COALESCE(MAX(orden),0)+1 FROM areas").fetchone()[0]
            self._insertar_area(nuevo, orden)
        self.con.execute("UPDATE equipos SET area=?, t=? WHERE area=?", (nuevo, t, viejo))
        self.con.execute("UPDATE equipos SET area_anterior=?, t=? WHERE area_anterior=?", (nuevo, t, viejo))

    def renombrar_area(self, viejo, nuevo):
        """Cambia el nombre de un área (si el nuevo ya existe, se unen). Devuelve el nombre final."""
        nuevo = normalizar_area(nuevo)
        if not nuevo or not viejo or nuevo == viejo:
            return viejo
        if AREA_BAJAS in (viejo, nuevo):
            raise ValueError("El área de equipos dados de baja no se puede renombrar ni usar como destino.")
        self._renombrar_sin_commit(viejo, nuevo)
        self._commit()
        return nuevo

    def conteo_por_area(self):
        return {r[0]: r[1] for r in self.con.execute("SELECT area, COUNT(*) FROM equipos GROUP BY area")}

    def costo_total(self, area=None):
        if area:
            r = self.con.execute("SELECT COALESCE(SUM(costo),0) FROM equipos WHERE area=?", (area,)).fetchone()
        else:
            r = self.con.execute("SELECT COALESCE(SUM(costo),0) FROM equipos").fetchone()
        return r[0]

    # ---- equipos ----
    @staticmethod
    def interpretar_numeros(texto):
        """'1,2,5-8' -> [(1,1),(2,2),(5,8)]; None si el texto no es una lista/rango de números."""
        t = texto.replace(" ", "")
        if not t or not re.fullmatch(r"\d+(-\d+)?([,;]\d+(-\d+)?)*", t):
            return None
        rangos = []
        for parte in re.split(r"[,;]", t):
            a, _, b = parte.partition("-")
            a, b = int(a), int(b or a)
            rangos.append((min(a, b), max(a, b)))
        return rangos

    def buscar(self, texto="", area=None):
        sql = "SELECT * FROM equipos WHERE 1=1"
        args = []
        if area:
            sql += " AND area=?"
            args.append(area)
        rangos = self.interpretar_numeros(texto)
        if rangos:
            conds = []
            for a, b in rangos:
                conds.append("(folio BETWEEN ? AND ?)")
                args += [a, b]
                conds.append("(no_inventario GLOB '[0-9]*' AND CAST(no_inventario AS INTEGER) BETWEEN ? AND ?)")
                args += [a, b]
            orden = " ORDER BY folio"
            if len(rangos) == 1 and rangos[0][0] == rangos[0][1]:
                # Un solo número: también coincidencias parciales de inventario o serie.
                conds.append("(no_inventario LIKE ? OR serie LIKE ?)")
                args += [f"%{rangos[0][0]}%"] * 2
                orden = " ORDER BY (folio = ?) DESC, folio"
                args.append(rangos[0][0])
            sql += " AND (" + " OR ".join(conds) + ")" + orden
            return [dict(r) for r in self.con.execute(sql, args)]
        for palabra in texto.split():
            p = f"%{palabra}%"
            sql += (" AND (CAST(folio AS TEXT)=? OR no_inventario LIKE ? OR descripcion LIKE ?"
                    " OR observaciones LIKE ? OR marca LIKE ? OR modelo LIKE ? OR serie LIKE ?"
                    " OR area LIKE ? OR estado LIKE ? OR comentarios LIKE ?)")
            args += [palabra.lstrip("#")] + [p] * 9
        sql += " ORDER BY folio"
        return [dict(r) for r in self.con.execute(sql, args)]

    def obtener(self, eid):
        r = self.con.execute("SELECT * FROM equipos WHERE id=?", (eid,)).fetchone()
        return dict(r) if r else None

    def existe_inventario(self, no_inv, excluir_id=None):
        if not no_inv:
            return False
        r = self.con.execute("SELECT id FROM equipos WHERE no_inventario=? AND id IS NOT ?",
                             (no_inv, excluir_id)).fetchone()
        return r is not None

    def _aplicar_reglas(self, d, previo=None):
        """Áreas en mayúsculas, costo numérico y traslado automático de los equipos dados de baja."""
        if "area" in d:
            d["area"] = normalizar_area(d["area"])
        if "costo" in d:
            d["costo"] = a_costo(d["costo"])
        previo = previo or {}
        estado = d.get("estado", previo.get("estado"))
        area = d.get("area", previo.get("area"))
        if estado == ESTADO_BAJA:
            if area != AREA_BAJAS:
                d["area_anterior"] = area
                d["area"] = AREA_BAJAS
            elif previo.get("area") and previo["area"] != AREA_BAJAS:
                d["area_anterior"] = previo["area"]
            self._asegurar_area_bajas()
        elif area == AREA_BAJAS:
            # Deja de estar dado de baja: regresa a su área anterior (si se conoce).
            anterior = previo.get("area_anterior") or d.get("area_anterior")
            if anterior and anterior != AREA_BAJAS:
                d["area"] = anterior
                self.agregar_area(anterior)
            d["area_anterior"] = None
        if d.get("area") and d["area"] != AREA_BAJAS:
            orden = self.con.execute(
                "SELECT COALESCE(MAX(orden),0)+1 FROM areas WHERE nombre<>?", (AREA_BAJAS,)).fetchone()[0]
            self._insertar_area(d["area"], orden)
        return d

    def agregar_equipo(self, datos):
        d = {k: datos.get(k, "") or "" for k in CAMPOS}
        d["costo"] = datos.get("costo")
        d = self._aplicar_reglas(d)
        campos = CAMPOS + (["area_anterior"] if "area_anterior" in d else [])
        now = datetime.now().isoformat(timespec="seconds")
        cur = self.con.execute(
            f"INSERT INTO equipos({','.join(campos)}, folio, creado, actualizado, uid, t) "
            f"VALUES({','.join('?' * len(campos))}, ?, ?, ?, ?, ?)",
            [d[k] for k in campos] + [self._siguiente_folio(), now, now, uuid.uuid4().hex, ahora_ms()])
        self._commit()
        return cur.lastrowid

    def actualizar_equipo(self, eid, datos):
        cambios = {k: v for k, v in datos.items() if k in CAMPOS}
        if not cambios:
            return
        if "estado" in cambios or "area" in cambios or "costo" in cambios:
            cambios = self._aplicar_reglas(cambios, self.obtener(eid))
        sets = ", ".join(f"{k}=?" for k in cambios)
        self.con.execute(f"UPDATE equipos SET {sets}, actualizado=?, t=? WHERE id=?",
                         list(cambios.values()) + [datetime.now().isoformat(timespec="seconds"), ahora_ms(), eid])
        self._commit()

    def eliminar_equipo(self, eid):
        eq = self.obtener(eid)
        self.con.execute("DELETE FROM equipos WHERE id=?", (eid,))
        if eq and eq.get("uid"):
            self.con.execute("INSERT OR REPLACE INTO borrados(clave, t) VALUES(?,?)", ("e:" + eq["uid"], ahora_ms()))
        self._commit()
        if eq and eq.get("foto"):
            p = os.path.join(FOTOS_DIR, eq["foto"])
            if os.path.exists(p):
                os.remove(p)
