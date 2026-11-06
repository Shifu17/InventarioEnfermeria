"""Inventario de Enfermería · FAENUS UAdeC — punto de entrada."""
import os
import sys
import traceback
from datetime import datetime

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from app import estilos
from app.db import leer_config
from app.ventana import RECURSOS, VentanaPrincipal


def _manejar_error(tipo, valor, tb):
    """Evita que el programa se cierre sin aviso: muestra el error y lo guarda en un log."""
    texto = "".join(traceback.format_exception(tipo, valor, tb))
    try:
        from app.db import CARPETA_LOCAL
        os.makedirs(CARPETA_LOCAL, exist_ok=True)
        with open(os.path.join(CARPETA_LOCAL, "errores.log"), "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} ---\n{texto}")
    except Exception:
        pass
    try:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Ocurrió un error",
                             f"Se produjo un error inesperado, pero tus datos están a salvo.\n\n{valor}")
    except Exception:
        return


def main():
    sys.excepthook = _manejar_error
    try:
        # Si el programa llegara a cerrarse de golpe, deja el rastro en errores.log.
        import faulthandler
        from app.db import CARPETA_LOCAL
        os.makedirs(CARPETA_LOCAL, exist_ok=True)
        global _log_fallos
        _log_fallos = open(os.path.join(CARPETA_LOCAL, "errores.log"), "a", encoding="utf-8")
        faulthandler.enable(_log_fallos)
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("faenus.inventario.enfermeria")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Inventario de Enfermería")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(estilos.aplicar_tema(leer_config().get("tema", "claro")))
    app.setWindowIcon(QIcon(os.path.join(RECURSOS, "icono.ico")))
    v = VentanaPrincipal()
    v.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
