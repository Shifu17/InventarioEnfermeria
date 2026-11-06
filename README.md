<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="app/recursos/logo_horizontal_blanco.png">
  <img src="app/recursos/logo_horizontal.png" alt="Facultad de Enfermería y Nutrición · UAdeC" width="420">
</picture>

# Inventario de Enfermería

**Control del equipo de laboratorios y áreas clínicas de la Facultad de Enfermería y Nutrición (FAENUS · UAdeC).**
Fotos, estados, costos y exportación a Excel, con el inventario sincronizado en línea entre computadoras.

<br>

<a href="https://github.com/Shifu17/InventarioEnfermeria/releases/latest/download/InventarioEnfermeria.exe">
  <img src="https://img.shields.io/badge/⬇%20Descargar%20para%20Windows-InventarioEnfermeria.exe-1B4596?style=for-the-badge&logo=windows&logoColor=white" alt="Descargar para Windows" height="48">
</a>

<br><br>

[![Última versión](https://img.shields.io/github/v/release/Shifu17/InventarioEnfermeria?label=versi%C3%B3n&color=1B4596)](https://github.com/Shifu17/InventarioEnfermeria/releases/latest)
[![Descargas](https://img.shields.io/github/downloads/Shifu17/InventarioEnfermeria/total?label=descargas&color=2D5BB5)](https://github.com/Shifu17/InventarioEnfermeria/releases)
![Windows 10/11](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows&logoColor=white)

<sub>Un solo archivo · No necesita instalación · Se actualiza solo</sub>

</div>

<br>

<p align="center">
  <img src="docs/img/principal_claro.png" alt="Pantalla principal del inventario" width="900">
</p>

---

## 📥 Cómo instalarlo

1. Da clic en **[Descargar para Windows](https://github.com/Shifu17/InventarioEnfermeria/releases/latest/download/InventarioEnfermeria.exe)**.
2. Mueve el archivo `InventarioEnfermeria.exe` a una carpeta tuya, por ejemplo **Documentos** o el **Escritorio**.
3. Ábrelo con doble clic. **Listo:** el inventario se descarga solo y queda sincronizado con las demás computadoras.

> [!NOTE]
> Si Windows muestra *“Windows protegió su PC”*, da clic en **Más información → Ejecutar de todas formas**.
> Aparece porque el programa no tiene firma digital comercial; es seguro.

> [!TIP]
> **¿Ya tenías una versión anterior?** Descarga esta una vez y reemplaza tu `.exe` viejo.
> A partir de la 1.1.0 el programa **se actualiza solo**: al abrirlo te avisa si hay una versión nueva.
> Las computadoras con la versión 1.1.0 reciben la 1.2.0 automáticamente.

---

## ✨ Qué puedes hacer

| | |
|---|---|
| 🔎 **Buscar al instante** | Por nombre, folio, No. de inventario, marca o serie. Varios folios (`1,2,3`) o rangos (`1-10`). |
| 🗂️ **Organizar por áreas** | Crea áreas, cámbiales el nombre (doble clic o clic derecho) o únelas. |
| 📷 **Fotos de cada equipo** | Arrastra una imagen a la ficha; clic para verla en grande. |
| 💲 **Costos** | Costo por equipo, valor total por área y suma en el Excel. |
| 🗑️ **Equipos dados de baja** | Se mueven solos a su propia área y regresan si se reactivan. |
| ☁️ **Inventario en línea** | Todas las computadoras comparten el mismo inventario; se descarga y se actualiza solo, incluso después de trabajar sin internet. |
| 📊 **Exportar a Excel** | Una hoja por área, con fotos, costos y totales. |
| 🌙 **Modo oscuro** | Cámbialo con un botón; cada computadora recuerda su preferencia. |
| ⬆️ **Actualizaciones automáticas** | El programa avisa cuando hay una versión nueva y se actualiza con un clic. |

---

## 🖼️ Capturas

<table>
  <tr>
    <td width="50%"><img src="docs/img/ficha.png" alt="Ficha de un equipo"><p align="center"><sub>Ficha del equipo con foto, estado y costo</sub></p></td>
    <td width="50%"><img src="docs/img/principal_oscuro.png" alt="Modo oscuro"><p align="center"><sub>Modo oscuro</sub></p></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/img/tabla.png" alt="Vista de tabla"><p align="center"><sub>Vista de tabla con costos</sub></p></td>
    <td width="50%"><img src="docs/img/bajas.png" alt="Equipos dados de baja"><p align="center"><sub>Área automática de equipos dados de baja</sub></p></td>
  </tr>
</table>

<sub>Las capturas usan datos de ejemplo.</sub>

---

## ❓ Preguntas frecuentes

<details>
<summary><b>¿Cómo se comparte el inventario entre varias computadoras?</b></summary>

No hay que hacer nada: al abrir el programa en cualquier computadora con internet, descarga el inventario completo con
sus fotos. Cada cambio se sube en segundos y las demás computadoras lo reciben solas. El estado de la conexión aparece
abajo en la barra lateral; **Sincronizar ahora** lo fuerza.
</details>

<details>
<summary><b>¿Y si no hay internet?</b></summary>

Puedes seguir trabajando normalmente. Los cambios se guardan en la computadora y se suben en cuanto vuelve la conexión.
Si dos computadoras cambiaron cosas distintas se conservan las dos; si cambiaron el mismo equipo, gana el cambio más reciente.
</details>

<details>
<summary><b>¿Se pierden mis datos al actualizar?</b></summary>

No. Al actualizar solo se reemplaza el archivo `.exe`; el inventario y las fotos están en otra carpeta y no se tocan.
Además se guarda una copia del programa anterior como `InventarioEnfermeria.exe.anterior`.
</details>

<details>
<summary><b>¿Dónde están mis datos y cómo hago un respaldo?</b></summary>

El inventario está guardado en línea (con historial de cada cambio) y además cada computadora tiene una copia local.
**Abrir carpeta de datos** muestra esa copia: `inventario.db` y la carpeta `fotos`. Puedes copiarla a una memoria USB
como respaldo extra.
</details>

<details>
<summary><b>¿Dónde se guardan los datos? ¿Están en este repositorio?</b></summary>

No. Este repositorio público solo contiene el programa. El inventario y las fotos se guardan en un repositorio
**privado** aparte, al que solo accede el programa.
</details>

---

<details>
<summary><b>🛠️ Para desarrolladores</b></summary>

Hecho con Python 3.12 y PySide6 (Qt).

```bat
:: Ejecutar desde el código (crea el entorno la primera vez)
"Iniciar Inventario.bat"

:: Pruebas
.venv\Scripts\python -m pytest

:: Compilar el .exe  ->  dist\InventarioEnfermeria.exe
:: (necesita el código de acceso a los datos en token_datos.txt, que nunca se sube)
"Crear EXE.bat"
```

**Publicar una versión nueva** (los programas instalados la reciben solos):

1. Cambia `VERSION` en `app/version.py` y describe los cambios en `NOTAS_VERSION.md`.
2. `git commit -am "Versión X.Y.Z"` → `git tag vX.Y.Z` → `git push --follow-tags`
3. GitHub Actions prueba, compila y publica el `.exe` en *Releases*.
   Si Actions no está disponible, compila con `Crear EXE.bat` y publica con
   `gh release create vX.Y.Z dist/InventarioEnfermeria.exe --notes-file NOTAS_VERSION.md`.

| Carpeta | Contenido |
|---|---|
| `app/` | Interfaz (`ventana.py`, `ficha.py`), datos (`db.py`), sincronización (`sincronizacion.py`, `nube.py`), actualizador, estilos |
| `tests/` | Pruebas automáticas |
| `herramientas/` | Importación inicial desde Excel |
</details>

<div align="center">
<sub>Facultad de Enfermería y Nutrición · Universidad Autónoma de Coahuila</sub>
</div>
