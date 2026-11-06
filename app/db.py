"""Capa de datos: SQLite en una carpeta local o compartida (red, OneDrive, Google Drive…)."""
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime

CONGELADO = getattr(sys, "frozen", False)

AREA_BAJAS = "EQUIPOS DADOS DE BAJA"
ESTADO_BAJA = "DADO DE BAJA"


def _carpeta_local():
    # En el .exe la configuración vive en %LOCALAPPDATA%; desde el código, en la carpeta del proyecto.
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


def configurado():
    """True si el usuario ya eligió dónde guardar los datos (carpeta compartida o solo esta PC)."""
    return "carpeta_datos" in leer_config()


def carpeta_configurada():
    c = leer_config().get("carpeta_datos") or ""
    return c if c and os.path.isdir(c) else CARPETA_LOCAL


DATA_DIR = FOTOS_DIR = DB_PATH = ""


def usar_carpeta(carpeta):
    """Cambia la carpeta de datos activa (base de datos + fotos)."""
    global DATA_DIR, FOTOS_DIR, DB_PATH
    DATA_DIR = os.path.abspath(carpeta)
    FOTOS_DIR = os.path.join(DATA_DIR, "fotos")
    DB_PATH = os.path.join(DATA_DIR, "inventario.db")


usar_carpeta(carpeta_configurada())


def ruta_foto(nombre):
    return os.path.join(FOTOS_DIR, nombre) if nombre else ""


def es_compartida():
    return os.path.normcase(DATA_DIR) != os.path.normcase(os.path.abspath(CARPETA_LOCAL))


def copiar_datos(origen, destino):
    """Copia inventario.db y fotos/ de una carpeta a otra (sin sobrescribir una base existente)."""
    os.makedirs(os.path.join(destino, "fotos"), exist_ok=True)
    db_o = os.path.join(origen, "inventario.db")
    if os.path.exists(db_o) and not os.path.exists(os.path.join(destino, "inventario.db")):
        # Copia consistente aunque la base esté abierta.
        src = sqlite3.connect(db_o)
        dst = sqlite3.connect(os.path.join(destino, "inventario.db"))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
    fotos_o = os.path.join(origen, "fotos")
    if os.path.isdir(fotos_o):
        for a in os.listdir(fotos_o):
            d = os.path.join(destino, "fotos", a)
            if not os.path.exists(d):
                shutil.copy2(os.path.join(fotos_o, a), d)


def preparar_datos():
    os.makedirs(FOTOS_DIR, exist_ok=True)


CAMPOS = ["no_inventario", "area", "descripcion", "observaciones", "marca", "modelo",
          "serie", "estado", "practicas", "resumen", "comentarios", "foto", "costo"]

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


class Database:
    def __init__(self, path=None):
        preparar_datos()
        self.path = path or DB_PATH
        self.con = None
        self._abrir()

    # ---- conexión / recarga automática ----
    def _abrir(self):
        if self.con is not None:
            try:
                self.con.close()
            except sqlite3.Error:
                pass
        # timeout alto: en carpetas de red otra PC puede estar escribiendo en ese momento.
        self.con = sqlite3.connect(self.path, timeout=15)
        self.con.row_factory = sqlite3.Row
        # Modo de diario clásico: WAL no funciona bien en carpetas de red ni sincronizadas.
        self.con.execute("PRAGMA journal_mode=DELETE")
        self._migrar()
        self._firma = self._firma_archivo()
        self._version = self._data_version()

    def _firma_archivo(self):
        try:
            st = os.stat(self.path)
            return st.st_mtime_ns, st.st_size
        except OSError:
            return None

    def _data_version(self):
        try:
            return self.con.execute("PRAGMA data_version").fetchone()[0]
        except sqlite3.Error:
            return None

    def _commit(self):
        self.con.commit()
        self._firma = self._firma_archivo()
        self._version = self._data_version()

    def hubo_cambios_externos(self):
        """True si otra computadora (u otro programa) modificó la base desde la última lectura.

        Si el archivo fue reemplazado (p. ej. por OneDrive/Google Drive), se reabre la conexión.
        """
        firma = self._firma_archivo()
        if firma is None:
            return False
        if firma != self._firma:
            self._abrir()
            return True
        v = self._data_version()
        if v != self._version:
            self._version = v
            return True
        return False

    def _migrar(self):
        self.con.executescript(
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
            """
        )
        cols = [r[1] for r in self.con.execute("PRAGMA table_info(equipos)")]
        if "folio" not in cols:
            self.con.execute("ALTER TABLE equipos ADD COLUMN folio INTEGER")
        if "costo" not in cols:
            self.con.execute("ALTER TABLE equipos ADD COLUMN costo REAL")
        if "area_anterior" not in cols:
            self.con.execute("ALTER TABLE equipos ADD COLUMN area_anterior TEXT")
        self.con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_folio ON equipos(folio)")
        # Equipos sin folio (bases anteriores): se numeran en orden de alta.
        for (eid,) in self.con.execute("SELECT id FROM equipos WHERE folio IS NULL ORDER BY id").fetchall():
            self.con.execute("UPDATE equipos SET folio=? WHERE id=?", (self._siguiente_folio(), eid))
        self._areas_en_mayusculas()
        self._mover_bajas()
        if self.con.in_transaction:
            self.con.commit()

    def _areas_en_mayusculas(self):
        """Todas las áreas en mayúsculas (incluye acentos, que UPPER() de SQLite no convierte)."""
        cambio = False
        for (nombre,) in self.con.execute("SELECT nombre FROM areas").fetchall():
            nuevo = normalizar_area(nombre)
            if nuevo != nombre:
                self._renombrar_sin_commit(nombre, nuevo)
                cambio = True
        for (area,) in self.con.execute("SELECT DISTINCT area FROM equipos WHERE area IS NOT NULL").fetchall():
            nuevo = normalizar_area(area)
            if nuevo != area:
                self.con.execute("UPDATE equipos SET area=? WHERE area=?", (nuevo, area))
                cambio = True
        return cambio

    def _mover_bajas(self):
        """Los equipos dados de baja viven siempre en el área de bajas."""
        filas = self.con.execute("SELECT id, area FROM equipos WHERE estado=? AND area IS NOT ?",
                                 (ESTADO_BAJA, AREA_BAJAS)).fetchall()
        for eid, area in filas:
            self.con.execute("UPDATE equipos SET area_anterior=?, area=? WHERE id=?", (area, AREA_BAJAS, eid))
        if filas:
            self._asegurar_area_bajas()
        return bool(filas)

    def _asegurar_area_bajas(self):
        self.con.execute("INSERT OR IGNORE INTO areas(nombre, orden) VALUES(?, 1000000)", (AREA_BAJAS,))

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
        self.con.execute("UPDATE equipos SET folio=? WHERE id=?", (folio, eid))
        r = self.con.execute("SELECT valor FROM meta WHERE clave='ultimo_folio'").fetchone()
        if folio > (int(r[0]) if r else 0):
            self.con.execute("INSERT OR REPLACE INTO meta(clave, valor) VALUES('ultimo_folio', ?)", (str(folio),))
        self._commit()

    def _siguiente_folio(self):
        """Folio único y consecutivo; nunca se reutiliza aunque se elimine un equipo."""
        r = self.con.execute("SELECT valor FROM meta WHERE clave='ultimo_folio'").fetchone()
        maximo = self.con.execute("SELECT COALESCE(MAX(folio),0) FROM equipos").fetchone()[0]
        n = max(int(r[0]) if r else 0, maximo) + 1
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
            self.con.execute("INSERT OR IGNORE INTO areas(nombre, orden) VALUES(?,?)", (nombre, orden))
        self._commit()

    def existe_area(self, nombre):
        nombre = normalizar_area(nombre)
        return bool(self.con.execute("SELECT 1 FROM areas WHERE nombre=?", (nombre,)).fetchone()
                    or self.con.execute("SELECT 1 FROM equipos WHERE area=? LIMIT 1", (nombre,)).fetchone())

    def _renombrar_sin_commit(self, viejo, nuevo):
        fila = self.con.execute("SELECT orden FROM areas WHERE nombre=?", (viejo,)).fetchone()
        destino = self.con.execute("SELECT orden FROM areas WHERE nombre=?", (nuevo,)).fetchone()
        if fila is not None:
            self.con.execute("DELETE FROM areas WHERE nombre=?", (viejo,))
            if destino is None:
                self.con.execute("INSERT INTO areas(nombre, orden) VALUES(?,?)", (nuevo, fila["orden"]))
        elif destino is None:
            orden = self.con.execute("SELECT COALESCE(MAX(orden),0)+1 FROM areas").fetchone()[0]
            self.con.execute("INSERT INTO areas(nombre, orden) VALUES(?,?)", (nuevo, orden))
        self.con.execute("UPDATE equipos SET area=? WHERE area=?", (nuevo, viejo))
        self.con.execute("UPDATE equipos SET area_anterior=? WHERE area_anterior=?", (nuevo, viejo))

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
        return d

    def agregar_equipo(self, datos):
        d = {k: datos.get(k, "") or "" for k in CAMPOS}
        d["costo"] = datos.get("costo")
        d = self._aplicar_reglas(d)
        campos = CAMPOS + (["area_anterior"] if "area_anterior" in d else [])
        now = datetime.now().isoformat(timespec="seconds")
        cur = self.con.execute(
            f"INSERT INTO equipos({','.join(campos)}, folio, creado, actualizado) "
            f"VALUES({','.join('?' * len(campos))}, ?, ?, ?)",
            [d[k] for k in campos] + [self._siguiente_folio(), now, now])
        self._commit()
        return cur.lastrowid

    def actualizar_equipo(self, eid, datos):
        cambios = {k: v for k, v in datos.items() if k in CAMPOS}
        if not cambios:
            return
        if "estado" in cambios or "area" in cambios or "costo" in cambios:
            cambios = self._aplicar_reglas(cambios, self.obtener(eid))
        sets = ", ".join(f"{k}=?" for k in cambios)
        self.con.execute(f"UPDATE equipos SET {sets}, actualizado=? WHERE id=?",
                         list(cambios.values()) + [datetime.now().isoformat(timespec="seconds"), eid])
        self._commit()

    def eliminar_equipo(self, eid):
        eq = self.obtener(eid)
        self.con.execute("DELETE FROM equipos WHERE id=?", (eid,))
        self._commit()
        if eq and eq.get("foto"):
            p = os.path.join(FOTOS_DIR, eq["foto"])
            if os.path.exists(p):
                os.remove(p)
