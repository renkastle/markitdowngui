"""Entry point: `python -m markitdowngui` or the bundled .app.

`--cli FILE...` converts files and prints Markdown to stdout without opening
the window (handy for checking that a frozen bundle includes every converter).
"""

import sys


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--cli"]:
        from .converter import ConversionOptions, Converter

        converter, options = Converter(), ConversionOptions()
        for source in args[1:]:
            markdown, _ = converter.convert(source, options)
            sys.stdout.write(markdown + "\n")
        return 0

    from .app import run

    return run([sys.argv[0], *args])


if __name__ == "__main__":
    sys.exit(main())
