"""Exportar e importar la base de datos completa (inventario.db + fotos) en un solo archivo .zip.

Sirve para pasar el inventario de una computadora a otra (USB, correo, Drive…) y como respaldo.
"""
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime

from . import db as BD

MARCA = "InventarioEnfermeria"          # archivo de identificación dentro del .zip


class ArchivoNoValido(Exception):
    """El archivo elegido no es un respaldo del inventario."""


def nombre_sugerido():
    return f"Inventario Enfermeria {datetime.now():%Y-%m-%d %H%M}.zip"


def exportar_base(destino, db_path=None, fotos_dir=None):
    """Crea el .zip con la base y las fotos que usa. Devuelve (equipos, fotos) exportados."""
    db_path = db_path or BD.DB_PATH
    fotos_dir = fotos_dir or BD.FOTOS_DIR
    tmp = tempfile.mkdtemp(prefix="inv_exp_")
    try:
        copia = os.path.join(tmp, "inventario.db")
        # Copia consistente aunque la base esté abierta.
        origen = sqlite3.connect(db_path)
        dest = sqlite3.connect(copia)
        with dest:
            origen.backup(dest)
        n_equipos = dest.execute("SELECT COUNT(*) FROM equipos").fetchone()[0]
        fotos = sorted({r[0] for r in dest.execute("SELECT foto FROM equipos WHERE foto IS NOT NULL AND foto<>''")})
        origen.close()
        dest.close()
        parcial = destino + ".tmp"
        n_fotos = 0
        with zipfile.ZipFile(parcial, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(MARCA, f"Respaldo del Inventario de Enfermería · {datetime.now():%Y-%m-%d %H:%M}\n")
            z.write(copia, "inventario.db")
            for f in fotos:
                ruta = os.path.join(fotos_dir, f)
                if os.path.exists(ruta):
                    z.write(ruta, "fotos/" + f, compress_type=zipfile.ZIP_STORED)   # ya vienen comprimidas
                    n_fotos += 1
        os.replace(parcial, destino)
        return n_equipos, n_fotos
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def revisar_archivo(origen):
    """Valida el .zip y devuelve cuántos equipos trae. Lanza ArchivoNoValido si no sirve."""
    try:
        with zipfile.ZipFile(origen) as z:
            nombres = set(z.namelist())
            if "inventario.db" not in nombres:
                raise ArchivoNoValido("El archivo no contiene un inventario (falta inventario.db).")
            for n in nombres:
                if n.startswith("/") or ".." in n.replace("\\", "/").split("/"):
                    raise ArchivoNoValido("El archivo contiene rutas no válidas.")
            tmp = tempfile.mkdtemp(prefix="inv_rev_")
            try:
                z.extract("inventario.db", tmp)
                con = sqlite3.connect(os.path.join(tmp, "inventario.db"))
                try:
                    return con.execute("SELECT COUNT(*) FROM equipos").fetchone()[0]
                finally:
                    con.close()
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    except zipfile.BadZipFile:
        raise ArchivoNoValido("El archivo no es un respaldo .zip válido.") from None
    except sqlite3.DatabaseError:
        raise ArchivoNoValido("La base de datos dentro del archivo está dañada.") from None


def importar_base(origen, db_path=None, fotos_dir=None, carpeta_respaldos=None):
    """Reemplaza la base local por la del .zip. Antes guarda un respaldo de la actual.

    La base debe estar cerrada al llamar. Devuelve (equipos_importados, ruta_del_respaldo_previo).
    """
    db_path = db_path or BD.DB_PATH
    fotos_dir = fotos_dir or BD.FOTOS_DIR
    carpeta_respaldos = carpeta_respaldos or os.path.join(os.path.dirname(db_path), "respaldos")
    n = revisar_archivo(origen)

    previo = None
    if os.path.exists(db_path):
        os.makedirs(carpeta_respaldos, exist_ok=True)
        base = os.path.join(carpeta_respaldos, f"antes de importar {datetime.now():%Y-%m-%d %H%M%S}")
        previo, i = base + ".zip", 2
        # Nombre siempre nuevo: nunca se sobrescribe otro respaldo (ni el archivo que se está importando).
        while os.path.exists(previo) or os.path.abspath(previo) == os.path.abspath(origen):
            previo, i = f"{base} ({i}).zip", i + 1
        exportar_base(previo, db_path, fotos_dir)

    tmp = tempfile.mkdtemp(prefix="inv_imp_", dir=os.path.dirname(db_path))
    try:
        with zipfile.ZipFile(origen) as z:
            z.extract("inventario.db", tmp)
            os.makedirs(fotos_dir, exist_ok=True)
            for info in z.infolist():
                if info.filename.startswith("fotos/") and not info.is_dir():
                    nombre = os.path.basename(info.filename)
                    if nombre:
                        with z.open(info) as fo, open(os.path.join(fotos_dir, nombre), "wb") as fd:
                            shutil.copyfileobj(fo, fd)
        for extra in ("-journal", "-wal", "-shm"):
            if os.path.exists(db_path + extra):
                os.remove(db_path + extra)
        os.replace(os.path.join(tmp, "inventario.db"), db_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return n, previo
