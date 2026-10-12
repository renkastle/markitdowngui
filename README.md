# MarkItDown GUI

Aplicación de escritorio para **macOS** y **Windows** que convierte documentos a Markdown usando
[Microsoft MarkItDown](https://github.com/microsoft/markitdown).

## Funciones

- Arrastra archivos o carpetas a la ventana (o al icono del Dock / «Abrir con…»).
- Formatos: PDF, Word, PowerPoint, Excel, HTML, CSV, JSON, XML, EPUB, Outlook `.msg`,
  Jupyter, ZIP, imágenes (metadatos/OCR vía plugins) y audio (transcripción).
- Convierte URLs: páginas web, Wikipedia, YouTube (transcripción), RSS.
- Conversión en segundo plano, en lote, con estado por archivo.
- Editor de Markdown + vista previa renderizada.
- Copiar al portapapeles, guardar un `.md` o guardar todos en una carpeta.
- Preferencias: conversión automática, plugins de MarkItDown, conservar imágenes
  incrustadas, endpoint de Azure Document Intelligence.

## Atajos

| Acción | Atajo |
| --- | --- |
| Abrir archivos | ⌘O |
| Abrir URL | ⌘L |
| Convertir selección / todo | ⌘↩ / ⇧⌘↩ |
| Copiar Markdown | ⇧⌘C |
| Guardar / Guardar todo | ⌘S / ⇧⌘S |
| Preferencias | ⌘, |

## Ejecutar desde el código

Requiere Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m markitdowngui            # abre la ventana
python -m markitdowngui archivo.pdf  # abre la ventana con ese archivo
pytest                             # tests
```

## Crear la app (.app y .dmg)

En un Mac:

```bash
./scripts/build_macos.sh
```

Genera `dist/MarkItDown GUI.app` y `dist/MarkItDownGUI-<versión>-<arquitectura>.dmg`.
El script construye para la arquitectura del Mac donde se ejecuta (Apple Silicon o Intel).

## Crear la app de Windows (.exe)

En Windows (PowerShell, Python 3.10+ y, para el instalador, [Inno Setup 6](https://jrsoftware.org/isinfo.php)):

```powershell
.\scripts\build_windows.ps1
```

Genera:

- `dist\MarkItDownGUI\MarkItDownGUI.exe` — la app (carpeta autocontenida).
- `dist\MarkItDownGUI-<versión>-windows-x64.zip` — versión portátil: descomprime y ejecuta.
- `dist\MarkItDownGUI-<versión>-windows-x64-setup.exe` — instalador (menú Inicio, acceso
  directo opcional, «Abrir con…» para los formatos soportados, desinstalador). Se instala
  por usuario sin permisos de administrador.

El `.exe` no está firmado, así que SmartScreen puede avisar la primera vez:
«Más información» → «Ejecutar de todas formas». En Windows los atajos usan Ctrl en vez de ⌘
(Salir: Ctrl+Q).

## CI y Releases

El workflow de GitHub Actions (`.github/workflows/build.yml`) ejecuta los tests en macOS y
Windows y genera los `.dmg` (Apple Silicon e Intel) y el instalador/zip de Windows en cada
push, y los publica en la Release de la versión del paquete (o del tag `v*`).

### Primera apertura

La app está firmada *ad-hoc* (sin cuenta de Apple Developer), así que macOS la bloqueará
la primera vez. Haz clic derecho sobre la app → **Abrir**, o ejecuta:

```bash
xattr -dr com.apple.quarantine "/Applications/MarkItDown GUI.app"
```

Para distribuirla sin avisos hace falta firmarla con un certificado «Developer ID» y
notarizarla (`codesign` + `xcrun notarytool`).

## Estructura

```
src/markitdowngui/
  converter.py   lógica de conversión (sin Qt, testeable)
  app.py         ventana principal (PySide6)
  __main__.py    punto de entrada; `--cli ARCHIVO…` convierte sin abrir ventana
packaging/       spec de PyInstaller (macOS y Windows) e instalador de Inno Setup
scripts/         build_macos.sh, build_windows.ps1
tests/
```

## Licencia

MIT. MarkItDown es © Microsoft, licencia MIT.
