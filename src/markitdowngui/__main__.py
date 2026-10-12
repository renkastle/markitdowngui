"""Entry point: `python -m markitdowngui` or the bundled app.

`--cli FILE...` converts files and prints Markdown to stdout without opening
the window (handy for checking that a frozen bundle includes every converter).
`--cli --output OUT.md FILE...` writes to a file instead, which also works from
the windowed Windows .exe, where there is no stdout.
"""

import sys


def _console_stdout():
    """stdout for --cli; a windowed Windows .exe has none, so borrow the parent console."""
    if sys.stdout is None and sys.platform == "win32":
        import ctypes

        if ctypes.windll.kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
            sys.stdout = open("CONOUT$", "w", encoding="utf-8")
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    return sys.stdout


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--cli"]:
        from .converter import ConversionOptions, Converter

        sources, output = args[1:], None
        if sources[:1] == ["--output"] and len(sources) > 1:
            output, sources = sources[1], sources[2:]
        converter, options = Converter(), ConversionOptions()
        markdown = "\n".join(converter.convert(s, options)[0] + "\n" for s in sources)
        if output:
            with open(output, "w", encoding="utf-8") as fh:
                fh.write(markdown)
        else:
            out = _console_stdout()
            if out is None:
                return 1
            out.write(markdown)
            out.flush()
        return 0

    from .app import run

    return run([sys.argv[0], *args])


if __name__ == "__main__":
    sys.exit(main())
