"""Migra inventario.xlsx (con fotos colocadas dentro de celda) a SQLite + carpeta de fotos.
Uso: python herramientas/migrar_excel.py ruta/inventario.xlsx
"""
import io, os, re, sys, sqlite3, zipfile, posixpath
import xml.etree.ElementTree as ET
from openpyxl import load_workbook
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from app.db import Database, FOTOS_DIR, DB_PATH

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "rd": "http://schemas.microsoft.com/office/spreadsheetml/2017/richdata",
    "rvr": "http://schemas.microsoft.com/office/spreadsheetml/2022/richvaluerel",
}
CAMPOS = {
    "NO. DE INVENTARIO": "no_inventario", "DESCRIPCIÓN": "descripcion", "DESCRIPCION": "descripcion",
    "OBSERVACIONES": "observaciones", "MARCA": "marca", "MODELO": "modelo", "SERIE": "serie",
    "PRÁCTICAS POSIBLES": "practicas", "PRACTICAS POSIBLES": "practicas", "RESUMEN": "resumen",
    "COMENTARIOS": "comentarios", "FOTO": "foto",
}


def _rels(z, path):
    d = posixpath.dirname(path)
    rp = posixpath.join(d, "_rels", posixpath.basename(path) + ".rels")
    if rp not in z.namelist():
        return {}
    root = ET.fromstring(z.read(rp))
    return {r.get("Id"): posixpath.normpath(posixpath.join(d, r.get("Target"))) for r in root}


def mapa_imagenes(z):
    """Devuelve {(hoja, 'C2'): ruta_media} para imágenes colocadas en celda."""
    if "xl/metadata.xml" not in z.namelist():
        return {}
    meta = ET.fromstring(z.read("xl/metadata.xml"))
    fm = [int(e.get("i")) for e in meta.iter(f"{{{NS['rd']}}}rvb")]  # bk -> rich value idx
    vm_list = []  # valueMetadata bk -> futureMetadata index
    vmeta = meta.find("m:valueMetadata", NS)
    if vmeta is not None:
        for bk in vmeta.findall("m:bk", NS):
            rc = bk.find("m:rc", NS)
            vm_list.append(int(rc.get("v")))
    rv = ET.fromstring(z.read("xl/richData/rdrichvalue.xml"))
    rv_rel = [int(e.findall("rd:v", NS)[0].text) for e in rv.findall("rd:rv", NS)]
    relxml = ET.fromstring(z.read("xl/richData/richValueRel.xml"))
    rids = [e.get(f"{{{NS['r']}}}id") for e in relxml]
    relmap = _rels(z, "xl/richData/richValueRel.xml")

    wb = ET.fromstring(z.read("xl/workbook.xml"))
    wbrels = _rels(z, "xl/workbook.xml")
    out = {}
    for sh in wb.find("m:sheets", NS):
        name = sh.get("name")
        path = wbrels[sh.get(f"{{{NS['r']}}}id")]
        root = ET.fromstring(z.read(path))
        for c in root.iter(f"{{{NS['m']}}}c"):
            vm = c.get("vm")
            if vm is None:
                continue
            fidx = vm_list[int(vm) - 1] if vm_list else int(vm) - 1
            rvi = fm[fidx]
            media = relmap[rids[rv_rel[rvi]]]
            out[(name, c.get("r"))] = media
    return out


def guardar_foto(z, media, destino):
    img = Image.open(io.BytesIO(z.read(media)))
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    img.save(destino, "JPEG", quality=90)


def migrar(xlsx):
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    for f in os.listdir(FOTOS_DIR):
        os.remove(os.path.join(FOTOS_DIR, f))
    db = Database()
    z = zipfile.ZipFile(xlsx)
    imgs = mapa_imagenes(z)
    wb = load_workbook(xlsx)
    total = fotos = 0
    for ws in wb:
        db.agregar_area(ws.title.strip().upper())
        hdr_row, cols = None, {}
        for row in ws.iter_rows(min_row=1, max_row=10):
            for c in row:
                if isinstance(c.value, str) and "INVENTARIO" in c.value.upper():
                    hdr_row = c.row
            if hdr_row:
                for c in row:
                    k = str(c.value or "").strip().upper()
                    if k in CAMPOS:
                        cols[CAMPOS[k]] = c.column_letter
                    elif k:
                        cols.setdefault("_extra", []).append((k, c.column_letter))
                break
        if not hdr_row:
            continue
        for r in range(hdr_row + 1, ws.max_row + 1):
            val = lambda campo: ws[f"{cols[campo]}{r}"].value if campo in cols else None
            datos = {}
            for campo in ("no_inventario", "descripcion", "observaciones", "marca", "modelo",
                          "serie", "practicas", "resumen", "comentarios"):
                v = val(campo)
                if v is None or (isinstance(v, str) and v.startswith("#")):
                    v = ""
                if isinstance(v, float) and v.is_integer():
                    v = int(v)
                datos[campo] = str(v).strip()
            for k, letra in cols.get("_extra", []):
                v = ws[f"{letra}{r}"].value
                if v not in (None, ""):
                    datos["comentarios"] = (datos["comentarios"] + f"\n{k}: {v}").strip()
            foto_media = imgs.get((ws.title, f"{cols.get('foto', 'C')}{r}"))
            if not any(datos.values()) and not foto_media:
                continue
            datos["area"] = ws.title.strip().upper()
            todo = " ".join(datos.values()).upper()
            for clave in ("MAL ESTADO", "PENDIENTE DE VALORAR", "EN REPARACIÓN", "DADO DE BAJA"):
                if re.search(r"\b" + clave + r"\b", todo):
                    datos["estado"] = clave
                    break
            eid = db.agregar_equipo(datos)
            total += 1
            if foto_media:
                nombre = f"equipo_{eid}.jpg"
                guardar_foto(z, foto_media, os.path.join(FOTOS_DIR, nombre))
                db.actualizar_equipo(eid, {"foto": nombre})
                fotos += 1
    print(f"Migrados {total} equipos, {fotos} fotos.")
    return total, fotos


if __name__ == "__main__":
    migrar(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "inventario.xlsx"))
