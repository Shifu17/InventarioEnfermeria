"""Actualización automática desde las versiones (releases) publicadas en GitHub."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from .version import NOMBRE_EXE, REPO, VERSION

API = f"https://api.github.com/repos/{REPO}/releases/latest"
AGENTE = f"InventarioEnfermeria/{VERSION}"


def version_tupla(texto):
    """'v1.2.10' -> (1, 2, 10). Ignora sufijos como '-beta'."""
    nums = re.findall(r"\d+", (texto or "").split("-")[0])
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def es_mas_nueva(remota, local=VERSION):
    return version_tupla(remota) > version_tupla(local)


def _pedir(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def buscar_actualizacion():
    """Devuelve dict(version, notas, url, tamano, sha256) si hay una versión más nueva; si no, None.

    Lanza una excepción si no se pudo consultar GitHub (sin internet, etc.).
    """
    with _pedir(API) as r:
        rel = json.load(r)
    if rel.get("draft") or rel.get("prerelease"):
        return None
    etiqueta = rel.get("tag_name", "")
    if not es_mas_nueva(etiqueta):
        return None
    for a in rel.get("assets", []):
        if a.get("name", "").lower() == NOMBRE_EXE.lower():
            digest = a.get("digest") or ""
            return {
                "version": etiqueta.lstrip("vV"),
                "notas": (rel.get("body") or "").strip(),
                "url": a["browser_download_url"],
                "tamano": a.get("size") or 0,
                "sha256": digest.split(":", 1)[1] if digest.startswith("sha256:") else "",
            }
    return None


def descargar(info, progreso=None):
    """Descarga el nuevo .exe a una carpeta temporal y verifica tamaño y huella. Devuelve la ruta."""
    destino = os.path.join(tempfile.mkdtemp(prefix="inv_act_"), NOMBRE_EXE)
    h = hashlib.sha256()
    total = info.get("tamano") or 0
    hecho = 0
    with _pedir(info["url"], timeout=60) as r, open(destino, "wb") as f:
        while True:
            bloque = r.read(256 * 1024)
            if not bloque:
                break
            f.write(bloque)
            h.update(bloque)
            hecho += len(bloque)
            if progreso:
                progreso(hecho, total)
    if total and hecho != total:
        raise IOError("La descarga quedó incompleta. Intenta de nuevo.")
    if info.get("sha256") and h.hexdigest().lower() != info["sha256"].lower():
        raise IOError("El archivo descargado no coincide con el publicado. Intenta de nuevo.")
    return destino


def puede_actualizarse():
    """Solo el .exe se reemplaza a sí mismo; desde el código fuente se usa git."""
    return getattr(sys, "frozen", False)


def instalar_y_reiniciar(nuevo_exe):
    """Reemplaza el .exe en uso por el descargado y lo vuelve a abrir.

    Windows no deja sobrescribir un .exe abierto, así que un pequeño script espera a que este
    programa se cierre, copia el archivo nuevo (guardando una copia del anterior) y lo inicia.
    """
    actual = os.path.abspath(sys.executable)
    script = os.path.join(os.path.dirname(nuevo_exe), "actualizar.cmd")
    # En el .exe de un solo archivo hay dos procesos: el lanzador (padre) y Python (este).
    pids = [os.getpid(), os.getppid()]
    esperas = "".join(
        f""":esperar{i}
tasklist /FI "PID eq {p}" 2>nul | find " {p} " >nul
if errorlevel 1 goto listo{i}
ping -n 2 127.0.0.1 >nul
goto esperar{i}
:listo{i}
""" for i, p in enumerate(pids))
    # Las rutas van en variables de entorno (Unicode): así funcionan carpetas con acentos o «ñ».
    # El script solo contiene texto ASCII y no usa bloques ( ) para que %intentos% se evalúe cada vez.
    contenido = f"""@echo off
setlocal
{esperas}set /a intentos=0
:copiar
copy /Y "%INV_ACTUAL%" "%INV_ACTUAL%.anterior" >nul 2>nul
copy /Y "%INV_NUEVO%" "%INV_ACTUAL%" >nul 2>nul
if not errorlevel 1 goto copiado
set /a intentos+=1
if %intentos% GEQ 15 goto abrir
ping -n 2 127.0.0.1 >nul
goto copiar
:copiado
del "%INV_NUEVO%" >nul 2>nul
:abrir
start "" "%INV_ACTUAL%"
(goto) 2>nul & del "%~f0"
"""
    with open(script, "w", encoding="ascii", newline="\r\n") as f:
        f.write(contenido)
    entorno = dict(os.environ, INV_ACTUAL=actual, INV_NUEVO=os.path.abspath(nuevo_exe))
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    try:
        # Que el script sobreviva al cierre del programa aunque Windows lo haya agrupado en un "job".
        subprocess.Popen(["cmd", "/c", script], env=entorno, close_fds=True,
                         creationflags=flags | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
    except OSError:
        subprocess.Popen(["cmd", "/c", script], env=entorno, close_fds=True, creationflags=flags)
