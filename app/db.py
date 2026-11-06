"""Capa de datos: SQLite local."""
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime

CONGELADO = getattr(sys, "frozen", False)


def _data_dir():
    # En el .exe los datos viven en %LOCALAPPDATA%; desde el código, en la carpeta del proyecto.
    if CONGELADO:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "InventarioEnfermeria")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos")


DATA_DIR = _data_dir()
FOTOS_DIR = os.path.join(DATA_DIR, "fotos")
DB_PATH = os.path.join(DATA_DIR, "inventario.db")


def preparar_datos():
    """Primera ejecución del .exe: copia el inventario inicial que viene incluido."""
    if CONGELADO and not os.path.exists(DB_PATH):
        semilla = os.path.join(getattr(sys, "_MEIPASS", ""), "datos_iniciales")
        if os.path.isdir(semilla):
            for raiz, _, archivos in os.walk(semilla):
                destino = os.path.join(DATA_DIR, os.path.relpath(raiz, semilla))
                os.makedirs(destino, exist_ok=True)
                for a in archivos:
                    with open(os.path.join(raiz, a), "rb") as fo, open(os.path.join(destino, a), "wb") as fd:
                        shutil.copyfileobj(fo, fd)
    os.makedirs(FOTOS_DIR, exist_ok=True)


CAMPOS = ["no_inventario", "area", "descripcion", "observaciones", "marca", "modelo",
          "serie", "estado", "practicas", "resumen", "comentarios", "foto"]

ESTADOS = ["", "FUNCIONAL", "MAL ESTADO", "PENDIENTE DE VALORAR", "EN REPARACIÓN", "DADO DE BAJA"]

ETIQUETAS = {
    "no_inventario": "No. de inventario", "area": "Área", "descripcion": "Descripción",
    "observaciones": "Observaciones", "marca": "Marca", "modelo": "Modelo", "serie": "Serie",
    "estado": "Estado", "practicas": "Prácticas posibles", "resumen": "Resumen",
    "comentarios": "Comentarios", "foto": "Foto",
}


class Database:
    def __init__(self, path=DB_PATH):
        preparar_datos()
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
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
        self.con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_folio ON equipos(folio)")
        # Equipos sin folio (bases anteriores): se numeran en orden de alta.
        for (eid,) in self.con.execute("SELECT id FROM equipos WHERE folio IS NULL ORDER BY id").fetchall():
            self.con.execute("UPDATE equipos SET folio=? WHERE id=?", (self._siguiente_folio(), eid))
        self.con.commit()

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
        self.con.commit()

    def _siguiente_folio(self):
        """Folio único y consecutivo; nunca se reutiliza aunque se elimine un equipo."""
        r = self.con.execute("SELECT valor FROM meta WHERE clave='ultimo_folio'").fetchone()
        maximo = self.con.execute("SELECT COALESCE(MAX(folio),0) FROM equipos").fetchone()[0]
        n = max(int(r[0]) if r else 0, maximo) + 1
        self.con.execute("INSERT OR REPLACE INTO meta(clave, valor) VALUES('ultimo_folio', ?)", (str(n),))
        return n

    # ---- áreas ----
    def areas(self):
        return [r["nombre"] for r in self.con.execute("SELECT nombre FROM areas ORDER BY orden, nombre")]

    def agregar_area(self, nombre):
        nombre = nombre.strip().upper()
        if not nombre:
            return
        orden = self.con.execute("SELECT COALESCE(MAX(orden),0)+1 FROM areas").fetchone()[0]
        self.con.execute("INSERT OR IGNORE INTO areas(nombre, orden) VALUES(?,?)", (nombre, orden))
        self.con.commit()

    def conteo_por_area(self):
        return {r[0]: r[1] for r in self.con.execute("SELECT area, COUNT(*) FROM equipos GROUP BY area")}

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
            if len(rangos) == 1 and rangos[0][0] == rangos[0][1]:
                # Un solo número: también coincidencias parciales de inventario o serie.
                conds.append("(no_inventario LIKE ? OR serie LIKE ?)")
                args += [f"%{rangos[0][0]}%"] * 2
            orden = " ORDER BY folio"
            if len(rangos) == 1 and rangos[0][0] == rangos[0][1]:
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

    def agregar_equipo(self, datos):
        d = {k: datos.get(k, "") or "" for k in CAMPOS}
        now = datetime.now().isoformat(timespec="seconds")
        cur = self.con.execute(
            f"INSERT INTO equipos({','.join(CAMPOS)}, folio, creado, actualizado) "
            f"VALUES({','.join('?' * len(CAMPOS))}, ?, ?, ?)",
            [d[k] for k in CAMPOS] + [self._siguiente_folio(), now, now])
        self.con.commit()
        return cur.lastrowid

    def actualizar_equipo(self, eid, datos):
        cambios = {k: v for k, v in datos.items() if k in CAMPOS}
        if not cambios:
            return
        sets = ", ".join(f"{k}=?" for k in cambios)
        self.con.execute(f"UPDATE equipos SET {sets}, actualizado=? WHERE id=?",
                         list(cambios.values()) + [datetime.now().isoformat(timespec="seconds"), eid])
        self.con.commit()

    def eliminar_equipo(self, eid):
        eq = self.obtener(eid)
        self.con.execute("DELETE FROM equipos WHERE id=?", (eid,))
        self.con.commit()
        if eq and eq.get("foto"):
            p = os.path.join(FOTOS_DIR, eq["foto"])
            if os.path.exists(p):
                os.remove(p)
