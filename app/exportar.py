"""Exporta el inventario a Excel (una hoja por área, con foto)."""
import os
import re
import tempfile

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from PIL import Image

from .db import FOTOS_DIR

COLS = [("folio", "#", 7), ("no_inventario", "No. DE INVENTARIO", 18), ("foto", "FOTO", 22), ("descripcion", "DESCRIPCIÓN", 40),
        ("observaciones", "OBSERVACIONES", 30), ("marca", "MARCA", 16), ("modelo", "MODELO", 14),
        ("serie", "SERIE", 14), ("estado", "ESTADO", 18), ("practicas", "PRÁCTICAS POSIBLES", 60),
        ("resumen", "RESUMEN", 45), ("comentarios", "COMENTARIOS", 35)]


def exportar(db, ruta):
    wb = Workbook()
    wb.remove(wb.active)
    tmp = tempfile.mkdtemp()
    azul = PatternFill("solid", fgColor="1B4596")
    borde = Border(*(Side(style="thin", color="D9E0EC"),) * 4)
    total = 0
    areas = db.areas()
    filas_todas = db.buscar()
    for a in sorted({f["area"] for f in filas_todas} - set(areas)):
        areas.append(a)
    for area in areas:
        filas = [f for f in filas_todas if f["area"] == area]
        nombre = re.sub(r"[\\/*?:\[\]]", "-", area or "SIN ÁREA")[:31] or "SIN ÁREA"
        base, n = nombre, 2
        while nombre in wb.sheetnames:
            nombre = f"{base[:28]}_{n}"
            n += 1
        ws = wb.create_sheet(nombre)
        for c, (_, titulo, ancho) in enumerate(COLS, 1):
            cel = ws.cell(1, c, titulo)
            cel.font = Font(bold=True, color="FFFFFF")
            cel.fill = azul
            cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            ws.column_dimensions[cel.column_letter].width = ancho
        ws.row_dimensions[1].height = 30
        ws.freeze_panes = "A2"
        for r, f in enumerate(filas, 2):
            ws.row_dimensions[r].height = 120
            for c, (campo, _, _) in enumerate(COLS, 1):
                if campo == "foto":
                    continue
                v = f.get(campo, "")
                cel = ws.cell(r, c, int(v) if campo == "no_inventario" and str(v).isdigit() else v)
                cel.alignment = Alignment(vertical="top", wrap_text=True)
                cel.border = borde
            ws.cell(r, 3).border = borde
            if f.get("foto") and os.path.exists(os.path.join(FOTOS_DIR, f["foto"])):
                im = Image.open(os.path.join(FOTOS_DIR, f["foto"]))
                im.thumbnail((300, 300))
                p = os.path.join(tmp, f"{f['id']}.png")
                im.save(p)
                xi = XLImage(p)
                esc = min(150 / xi.width, 150 / xi.height)
                xi.width, xi.height = int(xi.width * esc), int(xi.height * esc)
                ws.add_image(xi, f"C{r}")
            total += 1
    if not wb.sheetnames:
        wb.create_sheet("INVENTARIO")
    wb.save(ruta)
    return total
