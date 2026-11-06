"""Cliente mínimo de la API de GitHub para guardar el inventario en un repositorio privado.

Usa la "Git Data API": cada sincronización sube un solo commit con el inventario (inventario.json)
y las fotos nuevas. Si otra computadora subió algo en el mismo momento, GitHub rechaza el commit
(no es "fast-forward") y el sincronizador vuelve a combinar y reintenta.
"""
import base64
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .version import VERSION

API = "https://api.github.com"
ARCHIVO_DOC = "inventario.json"
CARPETA_FOTOS = "fotos/"


class SinConexion(Exception):
    """No hay internet o GitHub no respondió."""


class AccesoDenegado(Exception):
    """El código de acceso no es válido o no tiene permiso sobre el repositorio de datos."""


class Conflicto(Exception):
    """Otra computadora subió cambios al mismo tiempo."""


class Nube:
    def __init__(self, repo, token, rama="main", timeout=30):
        self.repo = repo
        self.token = token
        self.rama = rama
        self.timeout = timeout
        self._etag = None
        self._head = None

    # ---------- HTTP
    def _pedir(self, metodo, ruta, cuerpo=None, crudo=False, etag=None):
        url = ruta if ruta.startswith("http") else f"{API}/repos/{self.repo}/{ruta}"
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(url, data=datos, method=metodo)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("User-Agent", f"InventarioEnfermeria/{VERSION}")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("Accept", "application/vnd.github.raw" if crudo else "application/vnd.github+json")
        if datos is not None:
            req.add_header("Content-Type", "application/json")
        if etag:
            req.add_header("If-None-Match", etag)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                contenido = r.read()
                return r.status, (contenido if crudo else json.loads(contenido or b"null")), r.headers
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return 304, None, e.headers
            texto = e.read().decode("utf-8", "replace")[:300]
            if e.code in (401, 403) and "rate limit" not in texto.lower():
                raise AccesoDenegado(f"GitHub respondió {e.code}: {texto}") from None
            if e.code == 404 and "/git/refs/" not in url and "/git/ref/" not in url:
                raise AccesoDenegado("No se encontró el repositorio de datos o el código no tiene acceso.") from None
            if e.code in (409, 422) and metodo == "PATCH":
                raise Conflicto(texto) from None
            if e.code in (404, 409):
                return e.code, None, e.headers
            raise SinConexion(f"GitHub respondió {e.code}: {texto}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise SinConexion(str(getattr(e, "reason", e))) from None

    # ---------- lectura
    def cabeza(self):
        """SHA del último commit de la rama (None si el repositorio está vacío).

        Usa ETag: si nada cambió, GitHub contesta 304 y no cuenta contra el límite de consultas.
        """
        st, datos, h = self._pedir("GET", f"git/ref/heads/{self.rama}", etag=self._etag)
        if st == 304:
            return self._head
        if st in (404, 409):
            self._etag, self._head = None, None
            return None
        self._etag = h.get("ETag")
        self._head = datos["object"]["sha"]
        return self._head

    def arbol(self, commit_sha):
        """(sha_del_árbol, {ruta: sha_blob}) de un commit."""
        _, commit, _ = self._pedir("GET", f"git/commits/{commit_sha}")
        tree_sha = commit["tree"]["sha"]
        _, arbol, _ = self._pedir("GET", f"git/trees/{tree_sha}?recursive=1")
        if arbol.get("truncated"):
            raise SinConexion("El repositorio de datos es demasiado grande para leerlo de una vez.")
        return tree_sha, {e["path"]: e["sha"] for e in arbol["tree"] if e["type"] == "blob"}

    def blob(self, sha):
        _, contenido, _ = self._pedir("GET", f"git/blobs/{sha}", crudo=True)
        return contenido

    # ---------- escritura
    def subir(self, padre, arbol_base, archivos, mensaje):
        """Crea un commit con `archivos` ({ruta: bytes}) encima de `padre`. Devuelve el SHA nuevo."""
        def crear_blob(item):
            ruta, contenido = item
            _, b, _ = self._pedir("POST", "git/blobs", {"content": base64.b64encode(contenido).decode(),
                                                        "encoding": "base64"})
            return {"path": ruta, "mode": "100644", "type": "blob", "sha": b["sha"]}

        with ThreadPoolExecutor(max_workers=6) as ex:
            entradas = list(ex.map(crear_blob, archivos.items()))
        cuerpo = {"tree": entradas}
        if arbol_base:
            cuerpo["base_tree"] = arbol_base
        _, arbol, _ = self._pedir("POST", "git/trees", cuerpo)
        _, commit, _ = self._pedir("POST", "git/commits", {"message": mensaje, "tree": arbol["sha"],
                                                           "parents": [padre] if padre else []})
        if padre:
            self._pedir("PATCH", f"git/refs/heads/{self.rama}", {"sha": commit["sha"], "force": False})
        else:
            st, _, _ = self._pedir("POST", "git/refs", {"ref": f"refs/heads/{self.rama}", "sha": commit["sha"]})
            if st in (409, 422):
                raise Conflicto("La rama ya existe")
        self._etag, self._head = None, commit["sha"]
        return commit["sha"]
