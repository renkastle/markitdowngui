# MarkItDown GUI

Aplicación de escritorio para **macOS** que convierte documentos a Markdown usando
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

También hay un workflow de GitHub Actions (`.github/workflows/build-macos.yml`) que
ejecuta los tests y genera los `.dmg` para Apple Silicon e Intel en cada push; al crear
un tag `v*` los adjunta a una Release.

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
packaging/       spec de PyInstaller e Info.plist (tipos de documento)
scripts/         build_macos.sh
tests/
```

## Licencia

MIT. MarkItDown es © Microsoft, licencia MIT.
