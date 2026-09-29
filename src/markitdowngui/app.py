"""Main window of MarkItDown GUI (PySide6)."""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSettings, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QFont, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, __version__
from .converter import (
    SUPPORTED_EXTENSIONS,
    ConversionOptions,
    Converter,
    Job,
    Status,
    expand_paths,
    markdown_filename,
    unique_output_paths,
)

STATUS_ICONS = {
    Status.PENDING: "○",
    Status.CONVERTING: "◌",
    Status.DONE: "●",
    Status.ERROR: "✕",
}
JOB_ROLE = Qt.UserRole + 1


class ConversionWorker(QObject):
    """Runs conversions sequentially on a background thread."""

    started = Signal(int)
    finished = Signal(int, str, object)  # job id, markdown, title
    failed = Signal(int, str)

    def __init__(self) -> None:
        super().__init__()
        self._converter = Converter()

    @Slot(int, str, object)
    def convert(self, job_id: int, source: str, options: ConversionOptions) -> None:
        self.started.emit(job_id)
        try:
            markdown, title = self._converter.convert(source, options)
        except Exception as exc:  # MarkItDown raises many different exception types
            self.failed.emit(job_id, f"{type(exc).__name__}: {exc}")
        else:
            self.finished.emit(job_id, markdown, title)


class DropArea(QLabel):
    """Placeholder shown when the file list is empty."""

    def __init__(self) -> None:
        super().__init__(
            "Arrastra archivos o carpetas aquí\n\n"
            "PDF · Word · PowerPoint · Excel · HTML · CSV · JSON\n"
            "imágenes · audio · EPUB · ZIP · URLs"
        )
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setStyleSheet(
            "QLabel { border: 2px dashed palette(mid); border-radius: 12px;"
            " color: palette(placeholder-text); padding: 24px; }"
        )


class PreferencesDialog(QDialog):
    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferencias")
        self._settings = settings

        self.auto_convert = QCheckBox("Convertir automáticamente al añadir archivos")
        self.auto_convert.setChecked(settings.value("auto_convert", True, type=bool))
        self.enable_plugins = QCheckBox("Habilitar plugins de MarkItDown instalados")
        self.enable_plugins.setChecked(settings.value("enable_plugins", False, type=bool))
        self.keep_data_uris = QCheckBox("Conservar imágenes incrustadas (data URIs)")
        self.keep_data_uris.setChecked(settings.value("keep_data_uris", False, type=bool))
        self.docintel = QLineEdit(settings.value("docintel_endpoint", "", type=str))
        self.docintel.setPlaceholderText("https://<recurso>.cognitiveservices.azure.com/")

        form = QFormLayout()
        form.addRow(self.auto_convert)
        form.addRow(self.enable_plugins)
        form.addRow(self.keep_data_uris)
        form.addRow("Azure Document Intelligence:", self.docintel)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self._settings.setValue("auto_convert", self.auto_convert.isChecked())
        self._settings.setValue("enable_plugins", self.enable_plugins.isChecked())
        self._settings.setValue("keep_data_uris", self.keep_data_uris.isChecked())
        self._settings.setValue("docintel_endpoint", self.docintel.text().strip())
        super().accept()


class MainWindow(QMainWindow):
    request_conversion = Signal(int, str, object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 720)
        self.setAcceptDrops(True)

        self.settings = QSettings()
        self.jobs: dict[int, Job] = {}
        self._ids = itertools.count(1)
        self._updating_editor = False

        self._build_ui()
        self._build_actions()
        self._start_worker()
        self._refresh_state()

    # ----- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list.currentItemChanged.connect(self._on_current_changed)
        self.file_list.itemSelectionChanged.connect(self._refresh_state)

        self.list_stack = QStackedWidget()
        self.list_stack.addWidget(DropArea())
        self.list_stack.addWidget(self.file_list)

        add_btn = QPushButton("Añadir…")
        add_btn.clicked.connect(self.add_files_dialog)
        url_btn = QPushButton("URL…")
        url_btn.clicked.connect(self.add_url_dialog)
        self.remove_btn = QPushButton("Quitar")
        self.remove_btn.clicked.connect(self.remove_selected)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(url_btn)
        buttons.addStretch()
        buttons.addWidget(self.remove_btn)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)
        left_layout.addWidget(self.list_stack)
        left_layout.addLayout(buttons)

        mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        mono.setPointSize(max(mono.pointSize(), 12))
        self.editor = QPlainTextEdit()
        self.editor.setFont(mono)
        self.editor.setPlaceholderText("El Markdown convertido aparecerá aquí.")
        self.editor.textChanged.connect(self._on_editor_changed)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.editor, "Markdown")
        self.tabs.addTab(self.preview, "Vista previa")
        self.tabs.currentChanged.connect(lambda _: self._update_preview())

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.error_label.setStyleSheet("color: #d0342c; padding: 6px;")
        self.error_label.hide()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)
        right_layout.addWidget(self.error_label)
        right_layout.addWidget(self.tabs)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 800])
        self.setCentralWidget(splitter)
        self.statusBar()

    def _build_actions(self) -> None:
        def action(text, slot, shortcut=None):
            act = QAction(text, self)
            act.triggered.connect(slot)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            return act

        self.act_open = action("Abrir archivos…", self.add_files_dialog, QKeySequence.Open)
        self.act_url = action("Abrir URL…", self.add_url_dialog, "Ctrl+L")
        self.act_convert = action("Convertir", self.convert_selected, "Ctrl+Return")
        self.act_convert_all = action("Convertir todo", self.convert_all, "Ctrl+Shift+Return")
        self.act_copy = action("Copiar Markdown", self.copy_markdown, "Ctrl+Shift+C")
        self.act_save = action("Guardar Markdown…", self.save_current, QKeySequence.Save)
        self.act_save_all = action("Guardar todo en carpeta…", self.save_all, "Ctrl+Shift+S")
        self.act_remove = action("Quitar de la lista", self.remove_selected, QKeySequence.Delete)
        self.act_clear = action("Vaciar lista", self.clear_all)
        self.act_prefs = action("Preferencias…", self.show_preferences, QKeySequence.Preferences)
        self.act_prefs.setMenuRole(QAction.PreferencesRole)
        self.act_about = action(f"Acerca de {APP_NAME}", self.show_about)
        self.act_about.setMenuRole(QAction.AboutRole)
        self.act_quit = action("Salir", self.close, QKeySequence.Quit)
        self.act_quit.setMenuRole(QAction.QuitRole)
        self.act_help = action(
            "Proyecto MarkItDown en GitHub",
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/microsoft/markitdown")),
        )

        menu = self.menuBar()
        file_menu = menu.addMenu("Archivo")
        for act in (self.act_open, self.act_url, None, self.act_save, self.act_save_all,
                    None, self.act_prefs, self.act_quit):
            file_menu.addSeparator() if act is None else file_menu.addAction(act)
        edit_menu = menu.addMenu("Edición")
        for act in (self.act_copy, None, self.act_remove, self.act_clear):
            edit_menu.addSeparator() if act is None else edit_menu.addAction(act)
        convert_menu = menu.addMenu("Conversión")
        convert_menu.addAction(self.act_convert)
        convert_menu.addAction(self.act_convert_all)
        help_menu = menu.addMenu("Ayuda")
        help_menu.addAction(self.act_help)
        help_menu.addAction(self.act_about)

        toolbar = QToolBar("Principal")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        for act in (self.act_open, self.act_url, None, self.act_convert, self.act_convert_all,
                    None, self.act_copy, self.act_save, self.act_save_all):
            toolbar.addSeparator() if act is None else toolbar.addAction(act)
        self.addToolBar(toolbar)
        self.setUnifiedTitleAndToolBarOnMac(True)

    def _start_worker(self) -> None:
        self._thread = QThread(self)
        self._worker = ConversionWorker()
        self._worker.moveToThread(self._thread)
        self.request_conversion.connect(self._worker.convert)
        self._worker.started.connect(self._on_job_started)
        self._worker.finished.connect(self._on_job_finished)
        self._worker.failed.connect(self._on_job_failed)
        self._thread.start()

    def closeEvent(self, event) -> None:
        unsaved = [j for j in self.jobs.values() if j.dirty]
        if unsaved:
            answer = QMessageBox.question(
                self,
                APP_NAME,
                f"Hay {len(unsaved)} documento(s) editado(s) sin guardar. ¿Salir de todos modos?",
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self._thread.quit()
        self._thread.wait(3000)
        super().closeEvent(event)

    # ----- Adding sources --------------------------------------------------

    def add_sources(self, sources: list[str]) -> None:
        existing = {job.source for job in self.jobs.values()}
        new_jobs = []
        for source in sources:
            if source in existing:
                continue
            job = Job(id=next(self._ids), source=source)
            self.jobs[job.id] = job
            existing.add(source)
            item = QListWidgetItem()
            item.setData(JOB_ROLE, job.id)
            item.setToolTip(source)
            self.file_list.addItem(item)
            self._render_item(job)
            new_jobs.append(job)

        if new_jobs:
            self.file_list.setCurrentItem(self._item_for(new_jobs[0].id))
            if self.settings.value("auto_convert", True, type=bool):
                for job in new_jobs:
                    self._enqueue(job)
        self._refresh_state()

    def add_paths(self, paths: list[Path]) -> None:
        self.add_sources([str(p.resolve()) for p in expand_paths(paths)])

    def add_files_dialog(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleccionar documentos",
            self.settings.value("last_open_dir", str(Path.home()), type=str),
            f"Documentos compatibles ({patterns});;Todos los archivos (*)",
        )
        if files:
            self.settings.setValue("last_open_dir", str(Path(files[0]).parent))
            self.add_paths([Path(f) for f in files])

    def add_url_dialog(self) -> None:
        url, ok = QInputDialog.getText(
            self, "Convertir URL", "URL (página web, YouTube, Wikipedia, RSS…):"
        )
        url = url.strip()
        if ok and url:
            if "://" not in url:
                url = "https://" + url
            self.add_sources([url])

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths, urls = [], []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(Path(url.toLocalFile()))
            elif url.scheme() in ("http", "https"):
                urls.append(url.toString())
        self.add_paths(paths)
        self.add_sources(urls)
        event.acceptProposedAction()

    # ----- Conversion ------------------------------------------------------

    def _options(self) -> ConversionOptions:
        return ConversionOptions(
            enable_plugins=self.settings.value("enable_plugins", False, type=bool),
            keep_data_uris=self.settings.value("keep_data_uris", False, type=bool),
            docintel_endpoint=self.settings.value("docintel_endpoint", "", type=str),
        )

    def _enqueue(self, job: Job) -> None:
        if job.status == Status.CONVERTING:
            return
        if job.dirty and QMessageBox.question(
            self, APP_NAME, f"«{job.display_name}» tiene cambios sin guardar. ¿Reconvertir?"
        ) != QMessageBox.Yes:
            return
        job.status = Status.CONVERTING
        job.error = ""
        self._render_item(job)
        self.request_conversion.emit(job.id, job.source, self._options())

    def convert_selected(self) -> None:
        for job in self._selected_jobs():
            self._enqueue(job)

    def convert_all(self) -> None:
        for job in self.jobs.values():
            if job.status != Status.DONE or not job.dirty:
                self._enqueue(job)

    @Slot(int)
    def _on_job_started(self, job_id: int) -> None:
        if job := self.jobs.get(job_id):
            self.statusBar().showMessage(f"Convirtiendo {job.display_name}…")

    @Slot(int, str, object)
    def _on_job_finished(self, job_id: int, markdown: str, title) -> None:
        job = self.jobs.get(job_id)
        if job is None:  # removed while converting
            return
        job.status, job.markdown, job.title, job.dirty = Status.DONE, markdown, title, False
        self._render_item(job)
        self.statusBar().showMessage(f"{job.display_name}: {len(markdown):,} caracteres", 5000)
        if job is self._current_job():
            self._show_job(job)
        self._refresh_state()

    @Slot(int, str)
    def _on_job_failed(self, job_id: int, error: str) -> None:
        job = self.jobs.get(job_id)
        if job is None:
            return
        job.status, job.error = Status.ERROR, error
        self._render_item(job)
        self.statusBar().showMessage(f"Error al convertir {job.display_name}", 5000)
        if job is self._current_job():
            self._show_job(job)
        self._refresh_state()

    # ----- Output ----------------------------------------------------------

    def copy_markdown(self) -> None:
        if (job := self._current_job()) and job.status == Status.DONE:
            QApplication.clipboard().setText(job.markdown)
            self.statusBar().showMessage("Markdown copiado al portapapeles", 3000)

    def save_current(self) -> None:
        job = self._current_job()
        if not job or job.status != Status.DONE:
            return
        default_dir = self.settings.value("last_save_dir", "", type=str)
        if not default_dir:
            default_dir = str(Path.home()) if job.is_url else str(Path(job.source).parent)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Markdown",
            str(Path(default_dir) / markdown_filename(job.source)),
            "Markdown (*.md);;Todos los archivos (*)",
        )
        if path:
            self._write(job, Path(path))
            self.settings.setValue("last_save_dir", str(Path(path).parent))

    def save_all(self) -> None:
        done = [j for j in self.jobs.values() if j.status == Status.DONE]
        if not done:
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Guardar todos en…", self.settings.value("last_save_dir", str(Path.home()), type=str)
        )
        if not folder:
            return
        self.settings.setValue("last_save_dir", folder)
        targets = unique_output_paths([j.source for j in done], Path(folder))
        existing = [p for p in targets if p.exists()]
        if existing and QMessageBox.question(
            self, APP_NAME, f"{len(existing)} archivo(s) ya existen en la carpeta. ¿Sobrescribir?"
        ) != QMessageBox.Yes:
            return
        written = sum(self._write(job, path) for job, path in zip(done, targets))
        self.statusBar().showMessage(f"{written} archivo(s) guardados en {folder}", 5000)

    def _write(self, job: Job, path: Path) -> bool:
        try:
            path.write_text(job.markdown, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, APP_NAME, f"No se pudo guardar {path}:\n{exc}")
            return False
        job.dirty = False
        self._render_item(job)
        self.statusBar().showMessage(f"Guardado {path}", 5000)
        return True

    # ----- List management -------------------------------------------------

    def remove_selected(self) -> None:
        for item in self.file_list.selectedItems():
            self.jobs.pop(item.data(JOB_ROLE), None)
            self.file_list.takeItem(self.file_list.row(item))
        self._show_job(self._current_job())
        self._refresh_state()

    def clear_all(self) -> None:
        self.file_list.clear()
        self.jobs.clear()
        self._show_job(None)
        self._refresh_state()

    def _item_for(self, job_id: int) -> QListWidgetItem | None:
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            if item.data(JOB_ROLE) == job_id:
                return item
        return None

    def _render_item(self, job: Job) -> None:
        if item := self._item_for(job.id):
            dirty = " — editado" if job.dirty else ""
            item.setText(f"{STATUS_ICONS[job.status]}  {job.display_name}{dirty}")

    def _current_job(self) -> Job | None:
        item = self.file_list.currentItem()
        return self.jobs.get(item.data(JOB_ROLE)) if item else None

    def _selected_jobs(self) -> list[Job]:
        items = self.file_list.selectedItems() or ([self.file_list.currentItem()] if self.file_list.currentItem() else [])
        return [self.jobs[i.data(JOB_ROLE)] for i in items if i.data(JOB_ROLE) in self.jobs]

    # ----- Editor / preview ------------------------------------------------

    def _on_current_changed(self, *_):
        self._show_job(self._current_job())
        self._refresh_state()

    def _show_job(self, job: Job | None) -> None:
        self._updating_editor = True
        self.editor.setPlaceholderText("El Markdown convertido aparecerá aquí.")
        try:
            if job is None:
                self.editor.setPlainText("")
                self.editor.setReadOnly(True)
                self.error_label.hide()
            elif job.status == Status.ERROR:
                self.editor.setPlainText("")
                self.editor.setReadOnly(True)
                self.error_label.setText(f"No se pudo convertir «{job.display_name}».\n{job.error}")
                self.error_label.show()
            elif job.status == Status.DONE:
                self.editor.setPlainText(job.markdown)
                self.editor.setReadOnly(False)
                self.error_label.hide()
            else:
                self.editor.setPlainText("")
                self.editor.setReadOnly(True)
                self.error_label.hide()
                self.editor.setPlaceholderText(
                    "Convirtiendo…" if job.status == Status.CONVERTING
                    else "Pendiente. Pulsa «Convertir» (⌘↩)."
                )
        finally:
            self._updating_editor = False
        self._update_preview()

    def _on_editor_changed(self) -> None:
        if self._updating_editor:
            return
        job = self._current_job()
        if job and job.status == Status.DONE:
            job.markdown = self.editor.toPlainText()
            if not job.dirty:
                job.dirty = True
                self._render_item(job)
            self._refresh_state()

    def _update_preview(self) -> None:
        if self.tabs.currentWidget() is self.preview:
            job = self._current_job()
            self.preview.setMarkdown(job.markdown if job and job.status == Status.DONE else "")

    def _refresh_state(self) -> None:
        has_jobs = bool(self.jobs)
        self.list_stack.setCurrentIndex(1 if has_jobs else 0)
        job = self._current_job()
        done = bool(job and job.status == Status.DONE)
        self.act_copy.setEnabled(done)
        self.act_save.setEnabled(done)
        self.act_save_all.setEnabled(any(j.status == Status.DONE for j in self.jobs.values()))
        self.act_convert.setEnabled(job is not None)
        self.act_convert_all.setEnabled(has_jobs)
        self.act_remove.setEnabled(bool(self.file_list.selectedItems()))
        self.remove_btn.setEnabled(bool(self.file_list.selectedItems()))
        self.act_clear.setEnabled(has_jobs)
        title = APP_NAME
        if job:
            title = f"{job.display_name}{' •' if job.dirty else ''} — {APP_NAME}"
        self.setWindowTitle(title)

    # ----- Dialogs ---------------------------------------------------------

    def show_preferences(self) -> None:
        PreferencesDialog(self.settings, self).exec()

    def show_about(self) -> None:
        import markitdown

        QMessageBox.about(
            self,
            f"Acerca de {APP_NAME}",
            f"<b>{APP_NAME}</b> {__version__}<br>"
            f"Interfaz para <a href='https://github.com/microsoft/markitdown'>Microsoft MarkItDown</a> "
            f"{getattr(markitdown, '__version__', '')}.",
        )


class Application(QApplication):
    """QApplication that forwards macOS "Open With…" / Dock drops to the window.

    FileOpen events can arrive before the window exists (when the app is
    launched by opening a document), so they are buffered until a handler
    is attached.
    """

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self._pending: list[str] = []
        self._handler = None

    def set_file_handler(self, handler) -> None:
        self._handler = handler
        pending, self._pending = self._pending, []
        if pending:
            handler(pending)

    def event(self, event) -> bool:
        if event.type() == QEvent.FileOpen:
            source = event.file() or event.url().toString()
            if self._handler:
                self._handler([source])
            else:
                self._pending.append(source)
            return True
        return super().event(event)


def run(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = Application(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("markitdowngui")
    app.setOrganizationDomain("markitdowngui.local")
    app.setApplicationVersion(__version__)
    app.setFont(QFont(app.font().family(), max(app.font().pointSize(), 13)))

    window = MainWindow()

    def open_sources(sources: list[str]) -> None:
        window.add_paths([Path(s) for s in sources if "://" not in s])
        window.add_sources([s for s in sources if "://" in s])
        window.raise_()
        window.activateWindow()

    app.set_file_handler(open_sources)
    cli_sources = [a for a in argv[1:] if not a.startswith("-")]
    if cli_sources:
        open_sources(cli_sources)
    window.show()
    return app.exec()
