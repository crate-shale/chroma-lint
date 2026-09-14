"""Command-line entry point: print findings as path:line:col messages."""

import sys

from .linter import lint_text


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: chromalint FILE [FILE ...]", file=sys.stderr)
        return 2

    exit_code = 0
    for path in argv:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            print(f"{path}: {exc.strerror}", file=sys.stderr)
            exit_code = 2
            continue

        for finding in lint_text(text):
            print(f"{path}:{finding}")
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
