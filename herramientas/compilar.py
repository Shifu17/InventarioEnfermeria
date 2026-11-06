"""Compila dist/InventarioEnfermeria.exe con el código de acceso al inventario en línea incrustado.

El código se lee de la variable INVENTARIO_TOKEN o del archivo token_datos.txt (junto a este proyecto,
excluido de git). Se escribe ofuscado en app/_acceso.py solo durante la compilación y se borra al terminar.
"""
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app.credencial import ofuscar  # noqa: E402


def main():
    token = os.environ.get("INVENTARIO_TOKEN", "").strip()
    archivo = os.path.join(RAIZ, "token_datos.txt")
    if not token and os.path.exists(archivo):
        token = open(archivo, encoding="utf-8").read().strip()
    if not token:
        sys.exit("Falta el código de acceso: crea token_datos.txt o define INVENTARIO_TOKEN.")
    acceso = os.path.join(RAIZ, "app", "_acceso.py")
    with open(acceso, "w", encoding="utf-8") as f:
        f.write(f'ACCESO = "{ofuscar(token)}"\n')
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                        os.path.join(RAIZ, "InventarioEnfermeria.spec")], cwd=RAIZ, check=True)
    finally:
        os.remove(acceso)
    print("\nListo:", os.path.join(RAIZ, "dist", "InventarioEnfermeria.exe"))


if __name__ == "__main__":
    main()
