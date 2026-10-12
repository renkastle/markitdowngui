# PyInstaller spec for MarkItDown GUI.
# Build with:  pyinstaller --noconfirm packaging/MarkItDownGUI.spec
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "src"))
from markitdowngui import APP_NAME, __version__  # noqa: E402

datas, binaries, hiddenimports = [], [], []
# markitdown loads converters lazily and magika ships its ONNX model as data.
for package in ("markitdown", "magika", "pdfminer", "mammoth", "pptx", "openpyxl",
                "xlrd", "olefile", "youtube_transcript_api", "speech_recognition", "pydub"):
    try:
        d, b, h = collect_all(package)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h
for dist in ("markitdown", "magika"):
    datas += copy_metadata(dist)

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"
icon = ROOT / "packaging" / ("AppIcon.icns" if IS_MAC else "AppIcon.ico")
icon = str(icon) if icon.exists() else None

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore", "PySide6.QtQuick"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if IS_WIN:
    # Windows file properties (Explorer → Properties → Details).
    parts = (tuple(int(p) for p in __version__.split(".")[:3]) + (0, 0, 0, 0))[:4]
    Path(workpath).mkdir(parents=True, exist_ok=True)
    (Path(workpath) / "version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={parts}, prodvers={parts}),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'markitdowngui'),
      StringStruct('FileDescription', '{APP_NAME}'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'MarkItDownGUI'),
      StringStruct('OriginalFilename', 'MarkItDownGUI.exe'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MarkItDownGUI",
    console=False,
    argv_emulation=False,
    icon=icon,
    version=None if not IS_WIN else str(Path(workpath) / "version_info.txt"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="MarkItDownGUI")

DOCUMENT_TYPES = [
    ("Documentos", ["pdf", "docx", "pptx", "xlsx", "xls", "epub", "msg"]),
    ("Texto y datos", ["html", "htm", "csv", "json", "xml", "txt", "md", "ipynb", "rss", "atom"]),
    ("Imágenes", ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"]),
    ("Audio", ["mp3", "wav", "m4a", "mp4"]),
    ("Archivos ZIP", ["zip"]),
]

if IS_MAC:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon,
        bundle_identifier="io.github.markitdowngui",
        version=__version__,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.productivity",
            "CFBundleDocumentTypes": [
                {"CFBundleTypeName": name, "CFBundleTypeRole": "Viewer",
                 "LSHandlerRank": "Alternate", "CFBundleTypeExtensions": exts}
                for name, exts in DOCUMENT_TYPES
            ],
        },
    )
