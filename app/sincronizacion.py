"""Sincroniza la base local con el inventario en línea.

Regla de combinación: para cada registro (equipo, área o borrado) gana la versión con la marca de
tiempo `t` más reciente. Así funciona aunque una computadora haya trabajado sin internet: al volver
la conexión se suben sus cambios y se bajan los de las demás.
"""
import hashlib
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from . import db as BD
from .nube import ARCHIVO_DOC, CARPETA_FOTOS, Conflicto

ESTADO_ARCHIVO = "sincronizacion.json"


def _clave_orden(reg):
    # Desempate determinista (todas las computadoras eligen lo mismo con la misma información).
    return (reg.get("t") or 0, json.dumps(reg, sort_keys=True, ensure_ascii=False))


def combinar(a, b):
    """Combina dos documentos de inventario; gana el registro más reciente de cada clave."""
    regs = dict(a.get("registros", {}))
    for k, v in b.get("registros", {}).items():
        if k not in regs or _clave_orden(v) > _clave_orden(regs[k]):
            regs[k] = v
    ultimo = max(a.get("meta", {}).get("ultimo_folio", 0), b.get("meta", {}).get("ultimo_folio", 0))
    _resolver_folios_repetidos(regs)
    vivos = [v.get("folio") or 0 for k, v in regs.items() if k.startswith("e:") and not v.get("borrado")]
    ultimo = max([ultimo] + vivos)
    return {"formato": 1, "registros": regs, "meta": {"ultimo_folio": ultimo}}


def _resolver_folios_repetidos(regs):
    """Si dos computadoras dieron el mismo folio a equipos distintos, el más nuevo recibe otro folio."""
    por_folio = {}
    for k, v in regs.items():
        if k.startswith("e:") and not v.get("borrado") and v.get("folio"):
            por_folio.setdefault(v["folio"], []).append(k)
    maximo = max(por_folio) if por_folio else 0
    for folio in sorted(por_folio):
        claves = por_folio[folio]
        if len(claves) < 2:
            continue
        claves.sort(key=lambda k: (regs[k].get("creado") or "", k))
        for k in claves[1:]:
            maximo += 1
            r = dict(regs[k])
            r["folio"] = maximo
            r["t"] = (r.get("t") or 0) + 1
            regs[k] = r


def huella(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def fotos_usadas(doc):
    return {v["foto"] for k, v in doc["registros"].items()
            if k.startswith("e:") and not v.get("borrado") and v.get("foto")}


def _leer_estado(carpeta):
    try:
        with open(os.path.join(carpeta, ESTADO_ARCHIVO), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _guardar_estado(carpeta, estado):
    ruta = os.path.join(carpeta, ESTADO_ARCHIVO)
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False)
    os.replace(ruta + ".tmp", ruta)


def sincronizar(nube, db_path=None, fotos_dir=None, carpeta_estado=None, intentos=4):
    """Hace un ciclo completo de sincronización. Devuelve un dict con lo que pasó.

    Lanza nube.SinConexion / nube.AccesoDenegado si no se pudo hablar con GitHub.
    """
    db_path = db_path or BD.DB_PATH
    fotos_dir = fotos_dir or BD.FOTOS_DIR
    carpeta_estado = carpeta_estado or os.path.dirname(db_path)
    os.makedirs(fotos_dir, exist_ok=True)
    estado = _leer_estado(carpeta_estado)
    resultado = {"bajados": 0, "subido": False, "fotos_bajadas": 0, "fotos_subidas": 0}

    for _ in range(intentos):
        cabeza = nube.cabeza()
        con = BD.conectar(db_path)
        try:
            BD.crear_esquema(con)
            local = BD.exportar_doc(con)
        finally:
            con.close()

        # Nada cambió ni aquí ni en línea desde la última vez: no hay nada que hacer.
        if cabeza and cabeza == estado.get("cabeza") and huella(local) == estado.get("huella_local"):
            return resultado

        if cabeza and cabeza == estado.get("cabeza") and "remoto" in estado:
            remoto, arbol_sha, archivos = estado["remoto"], estado["arbol"], estado["archivos"]
        elif cabeza:
            arbol_sha, archivos = nube.arbol(cabeza)
            remoto = (json.loads(nube.blob(archivos[ARCHIVO_DOC]).decode("utf-8"))
                      if ARCHIVO_DOC in archivos else {"formato": 1, "registros": {}, "meta": {}})
        else:
            remoto, arbol_sha, archivos = {"formato": 1, "registros": {}, "meta": {}}, None, {}

        combinado = combinar(local, remoto)

        # 1) Aplicar lo nuevo a la base local (en una transacción, releyendo por si hubo cambios mientras tanto)
        con = BD.conectar(db_path)
        try:
            con.execute("BEGIN IMMEDIATE")
            actual = BD.exportar_doc(con)
            if actual != local:
                # El usuario guardó algo mientras se descargaba: se combina también.
                combinado = combinar(actual, combinado)
            resultado["bajados"] += BD.importar_doc(con, combinado, actual)
            con.commit()
        finally:
            con.close()

        # 2) Bajar fotos que falten aquí (varias a la vez)
        faltan = [n for n in sorted(fotos_usadas(combinado))
                  if not os.path.exists(os.path.join(fotos_dir, n)) and CARPETA_FOTOS + n in archivos]

        def bajar(nombre):
            destino = os.path.join(fotos_dir, nombre)
            contenido = nube.blob(archivos[CARPETA_FOTOS + nombre])
            with open(destino + ".tmp", "wb") as f:
                f.write(contenido)
            os.replace(destino + ".tmp", destino)

        if faltan:
            with ThreadPoolExecutor(max_workers=8) as ex:
                list(ex.map(bajar, faltan))
            resultado["fotos_bajadas"] += len(faltan)

        # 3) Subir si aquí había algo que en línea no estaba
        if combinado != remoto:
            subir = {ARCHIVO_DOC: json.dumps(combinado, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")}
            for nombre in sorted(fotos_usadas(combinado)):
                ruta_local = os.path.join(fotos_dir, nombre)
                if CARPETA_FOTOS + nombre not in archivos and os.path.exists(ruta_local):
                    with open(ruta_local, "rb") as f:
                        subir[CARPETA_FOTOS + nombre] = f.read()
            try:
                mensaje = f"Inventario actualizado desde {os.environ.get('COMPUTERNAME', 'una computadora')} " \
                          f"({datetime.now():%Y-%m-%d %H:%M})"
                cabeza = nube.subir(cabeza, arbol_sha, subir, mensaje)
            except Conflicto:
                estado.pop("cabeza", None)
                continue        # alguien subió al mismo tiempo: se vuelve a combinar
            resultado["subido"] = True
            resultado["fotos_subidas"] += len(subir) - 1
            arbol_sha, archivos = nube.arbol(cabeza)
            remoto = combinado

        estado = {"cabeza": cabeza, "huella_local": huella(combinado), "remoto": remoto,
                  "arbol": arbol_sha, "archivos": archivos,
                  "ultima": datetime.now().isoformat(timespec="seconds")}
        _guardar_estado(carpeta_estado, estado)
        return resultado
    raise Conflicto("Demasiados cambios simultáneos; se reintentará en un momento.")
