"""Elegir dónde vive la base de datos: una carpeta compartida entre computadoras o solo esta PC."""
import os
import sqlite3

from PySide6.QtWidgets import QFileDialog, QMessageBox

from . import db as BD

SUBCARPETA = "InventarioEnfermeria"


def contar_equipos(carpeta):
    ruta = os.path.join(carpeta, "inventario.db")
    if not os.path.exists(ruta):
        return None
    try:
        con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True, timeout=5)
        try:
            return con.execute("SELECT COUNT(*) FROM equipos").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return 0


def _destino_para(elegida):
    """Si la carpeta elegida ya tiene un inventario se usa tal cual; si no, se crea una subcarpeta propia."""
    if os.path.exists(os.path.join(elegida, "inventario.db")):
        return elegida
    if os.path.basename(os.path.normpath(elegida)).lower() == SUBCARPETA.lower():
        return elegida
    sub = os.path.join(elegida, SUBCARPETA)
    return sub


def elegir_carpeta_compartida(parent):
    """Pide la carpeta compartida, ofrece copiar el inventario actual y la deja activa.

    Devuelve True si se cambió la carpeta.
    """
    inicio = BD.DATA_DIR if BD.es_compartida() else os.path.expanduser("~")
    elegida = QFileDialog.getExistingDirectory(
        parent, "Elige la carpeta compartida (red, OneDrive, Google Drive…)", inicio)
    if not elegida:
        return False
    destino = _destino_para(elegida)
    try:
        os.makedirs(os.path.join(destino, "fotos"), exist_ok=True)
        prueba = os.path.join(destino, ".prueba_escritura")
        with open(prueba, "w") as f:
            f.write("ok")
        os.remove(prueba)
    except OSError as ex:
        QMessageBox.warning(parent, "Carpeta no válida",
                            f"No se puede guardar en esa carpeta:\n{destino}\n\n{ex}")
        return False

    n_destino = contar_equipos(destino)
    origen = BD.DATA_DIR
    n_origen = contar_equipos(origen) if os.path.normcase(origen) != os.path.normcase(destino) else None

    if n_destino is not None:
        QMessageBox.information(
            parent, "Inventario compartido encontrado",
            f"En esa carpeta ya hay un inventario con {n_destino} equipos.\n"
            "Desde ahora este programa usará ese inventario compartido.")
    elif n_origen:
        r = QMessageBox.question(
            parent, "Copiar inventario",
            f"La carpeta compartida está vacía.\n\n¿Copiar ahí tu inventario actual ({n_origen} equipos y sus fotos)?\n"
            "Si eliges «No», el inventario compartido empezará vacío.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if r == QMessageBox.Yes:
            try:
                BD.copiar_datos(origen, destino)
            except (OSError, sqlite3.Error) as ex:
                QMessageBox.critical(parent, "Error al copiar", f"No se pudo copiar el inventario:\n{ex}")
                return False
    BD.guardar_config(carpeta_datos=destino)
    BD.usar_carpeta(destino)
    return True


def usar_solo_esta_pc():
    BD.guardar_config(carpeta_datos="")
    BD.usar_carpeta(BD.CARPETA_LOCAL)


def configurar_primera_vez(parent=None):
    """Primera vez que se abre el programa en esta computadora."""
    caja = QMessageBox(parent)
    caja.setWindowTitle("Base de datos del inventario")
    caja.setIcon(QMessageBox.Question)
    caja.setText("<b>¿Dónde quieres guardar el inventario?</b>")
    caja.setInformativeText(
        "Para que varias computadoras vean y editen el mismo inventario, elige una "
        "<b>carpeta compartida</b> (carpeta de red, OneDrive o Google Drive). "
        "El programa la abrirá automáticamente cada vez y se actualizará solo cuando "
        "otra computadora guarde cambios.<br><br>"
        "Puedes cambiarlo después con el botón «Base de datos compartida».")
    b_comp = caja.addButton("Usar carpeta compartida…", QMessageBox.AcceptRole)
    b_local = caja.addButton("Solo en esta computadora", QMessageBox.RejectRole)
    caja.setDefaultButton(b_comp)
    while True:
        caja.exec()
        if caja.clickedButton() is b_comp:
            if elegir_carpeta_compartida(parent):
                return
            continue
        usar_solo_esta_pc()
        return


def verificar_carpeta(parent=None):
    """Si la carpeta compartida no está disponible (sin red, unidad desconectada…), lo avisa.

    Devuelve False si el usuario decide salir.
    """
    cfg = BD.leer_config()
    carpeta = cfg.get("carpeta_datos") or ""
    while carpeta and not os.path.isdir(carpeta):
        caja = QMessageBox(parent)
        caja.setWindowTitle("Carpeta compartida no disponible")
        caja.setIcon(QMessageBox.Warning)
        caja.setText(f"No se encuentra la carpeta compartida del inventario:\n{carpeta}")
        caja.setInformativeText("Revisa la conexión a la red o que OneDrive / Google Drive estén abiertos.")
        b_re = caja.addButton("Reintentar", QMessageBox.AcceptRole)
        b_otra = caja.addButton("Elegir otra carpeta…", QMessageBox.ActionRole)
        b_salir = caja.addButton("Salir", QMessageBox.RejectRole)
        caja.setDefaultButton(b_re)
        caja.exec()
        if caja.clickedButton() is b_salir:
            return False
        if caja.clickedButton() is b_otra:
            BD.usar_carpeta(BD.CARPETA_LOCAL)
            if elegir_carpeta_compartida(parent):
                return True
        carpeta = BD.leer_config().get("carpeta_datos") or ""
    BD.usar_carpeta(BD.carpeta_configurada())
    return True
