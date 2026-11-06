"""Código de acceso al repositorio privado de datos.

Orden de búsqueda: variable de entorno INVENTARIO_TOKEN, config.json ("token") y, en el .exe,
el código que se incrusta al compilar (app/_acceso.py, generado por herramientas/compilar.py y
excluido de git). Se guarda ofuscado solo para que no aparezca como texto plano dentro del .exe.
"""
import base64
import os

_SAL = b"FAENUS-UAdeC-inventario"


def ofuscar(texto):
    datos = texto.encode()
    return base64.b85encode(bytes(b ^ _SAL[i % len(_SAL)] for i, b in enumerate(datos))).decode()


def desofuscar(texto):
    datos = base64.b85decode(texto.encode())
    return bytes(b ^ _SAL[i % len(_SAL)] for i, b in enumerate(datos)).decode()


def token():
    if os.environ.get("INVENTARIO_SIN_NUBE"):
        return ""
    if os.environ.get("INVENTARIO_TOKEN"):
        return os.environ["INVENTARIO_TOKEN"].strip()
    from .db import leer_config
    t = leer_config().get("token")
    if t:
        return t.strip()
    try:
        from ._acceso import ACCESO
        return desofuscar(ACCESO)
    except Exception:
        return ""
