"""Conversion logic, independent of the GUI so it can be tested and reused."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from markitdown import MarkItDown

# Extensions MarkItDown knows how to handle (used for the file dialog filter
# and to filter folders dropped onto the window).
SUPPORTED_EXTENSIONS = (
    ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv", ".json", ".xml",
    ".html", ".htm", ".txt", ".md", ".rss", ".atom", ".ipynb", ".epub",
    ".msg", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    ".mp3", ".wav", ".m4a", ".mp4",
)


class Status(Enum):
    PENDING = "pending"
    CONVERTING = "converting"
    DONE = "done"
    ERROR = "error"


@dataclass(frozen=True)
class ConversionOptions:
    enable_plugins: bool = False
    keep_data_uris: bool = False
    docintel_endpoint: str = ""


@dataclass
class Job:
    id: int
    source: str
    status: Status = Status.PENDING
    markdown: str = ""
    title: str | None = None
    error: str = ""
    dirty: bool = field(default=False)

    @property
    def is_url(self) -> bool:
        return is_url(self.source)

    @property
    def display_name(self) -> str:
        if self.is_url:
            return self.source
        return Path(self.source).name


def is_url(source: str) -> bool:
    return urlparse(source).scheme in ("http", "https", "file", "data")


def is_supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def expand_paths(paths: list[Path]) -> list[Path]:
    """Expand directories into the supported files they contain (recursively)."""
    result: list[Path] = []
    for path in paths:
        if path.is_dir():
            result.extend(sorted(p for p in path.rglob("*") if is_supported_file(p)))
        elif path.is_file():
            result.append(path)
    return result


class Converter:
    """Thin wrapper around MarkItDown that caches an instance per option set."""

    def __init__(self) -> None:
        self._md: MarkItDown | None = None
        self._options: ConversionOptions | None = None

    def _instance(self, options: ConversionOptions) -> MarkItDown:
        if self._md is None or self._options != options:
            kwargs = {"enable_plugins": options.enable_plugins}
            if options.docintel_endpoint:
                kwargs["docintel_endpoint"] = options.docintel_endpoint
            self._md = MarkItDown(**kwargs)
            self._options = options
        return self._md

    def convert(self, source: str, options: ConversionOptions) -> tuple[str, str | None]:
        """Convert a local path or URL. Returns (markdown, title)."""
        md = self._instance(options)
        target = source if is_url(source) else Path(source)
        result = md.convert(target, keep_data_uris=options.keep_data_uris)
        return result.markdown, result.title


def markdown_filename(source: str) -> str:
    """Suggested .md filename for a source path or URL."""
    if is_url(source):
        parsed = urlparse(source)
        stem = Path(parsed.path).stem or parsed.netloc or "documento"
    else:
        stem = Path(source).stem or "documento"
    stem = re.sub(r"[^\w\-. ]+", "_", stem).strip(" .") or "documento"
    return f"{stem}.md"


def unique_output_paths(sources: list[str], out_dir: Path) -> list[Path]:
    """Output paths in out_dir, de-duplicating names that collide between sources."""
    used: set[str] = set()
    paths: list[Path] = []
    for source in sources:
        name = markdown_filename(source)
        stem, suffix = name[:-3], ".md"
        candidate, n = name, 1
        while candidate.lower() in used:
            candidate = f"{stem}-{n}{suffix}"
            n += 1
        used.add(candidate.lower())
        paths.append(out_dir / candidate)
    return paths
