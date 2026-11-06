import os
import sys
import tempfile

# Configuración aislada: nunca toca los datos reales de la computadora.
os.environ["INVENTARIO_CARPETA_LOCAL"] = tempfile.mkdtemp(prefix="inv_test_local_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from app import db as BD  # noqa: E402


@pytest.fixture
def carpeta(tmp_path):
    BD.usar_carpeta(str(tmp_path))
    yield tmp_path
    BD.usar_carpeta(BD.CARPETA_LOCAL)


@pytest.fixture
def base(carpeta):
    d = BD.Database()
    yield d
    d.con.close()


@pytest.fixture
def qapp_y_ventana(carpeta, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from app import ventana as V
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(V.VentanaPrincipal, "buscar_actualizaciones", lambda self, silencioso=False: None)
    v = V.VentanaPrincipal()
    yield v
    v.vigilante.stop()
    v.close()
    v.db.con.close()
