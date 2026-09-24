"""Regex-based checks for colour literals: hex codes, rgb()/rgba(), hsl()/hsla(),
lab()/lch()/oklab()/oklch().

This is a line scanner, not a CSS parser. It finds things that look like
colour literals wherever they appear in a line and validates them against the
CSS Color spec rules that are easy to get wrong by hand: mixing percentages
and numbers in the same rgb(), forgetting the "%" on hsl() saturation and
lightness, channel or alpha values outside their legal range, and hex codes
with the wrong number of digits. Tokens it cannot make sense of (custom
properties, Sass variables, etc.) are left alone rather than flagged. Matches
inside /* */ comments and quoted strings are also left alone, since those
aren't colours a browser will ever render.
"""

from dataclasses import dataclass
import re

HEX_RE = re.compile(r"#([0-9a-fA-F]+)\b")
FUNC_RE = re.compile(
    r"\b(rgba?|hsla?|(?:ok)?lab|(?:ok)?lch)\(\s*([^)]*?)\s*\)", re.IGNORECASE
)

VALID_HEX_LENGTHS = {3, 4, 6, 8}

NUMBER_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)$")
PERCENT_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)%$")
ANGLE_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:deg|grad|rad|turn)?$", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    line: int
    column: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.line}:{self.column}: {self.message} [{self.code}]"


def lint_text(text: str) -> list[Finding]:
    findings: list[Finding] = []
    in_comment = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        masked, in_comment = _mask_comments_and_strings(line, in_comment)
        findings.extend(_check_hex(masked, lineno))
        findings.extend(_check_functional(masked, lineno))
    return findings


def lint_file(path: str) -> list[Finding]:
    with open(path, encoding="utf-8") as f:
        return lint_text(f.read())


def _mask_comments_and_strings(line: str, in_comment: bool) -> tuple[str, bool]:
    # Blank out comment and string contents with spaces rather than deleting
    # them, so every match's column still lines up with the original line.
    # /* */ comments can span lines, so `in_comment` carries over between
    # calls; quoted strings are assumed to close on the line they open, which
    # covers real CSS (a raw newline inside a string is invalid there).
    chars = list(line)
    i = 0
    n = len(line)
    while i < n:
        if in_comment:
            end = line.find("*/", i)
            stop = n if end == -1 else end + 2
            for j in range(i, stop):
                chars[j] = " "
            in_comment = end == -1
            i = stop
            continue

        ch = line[i]
        if ch == "/" and i + 1 < n and line[i + 1] == "*":
            in_comment = True
            chars[i] = chars[i + 1] = " "
            i += 2
            continue

        if ch in ("'", '"'):
            j = i + 1
            while j < n:
                if line[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if line[j] == ch:
                    j += 1
                    break
                j += 1
            for k in range(i, j):
                chars[k] = " "
            i = j
            continue

        i += 1

    return "".join(chars), in_comment


def _check_hex(line: str, lineno: int) -> list[Finding]:
    findings = []
    for m in HEX_RE.finditer(line):
        digits = m.group(1)
        if len(digits) not in VALID_HEX_LENGTHS:
            findings.append(Finding(
                lineno, m.start() + 1, "hex-length",
                f"#{digits} has {len(digits)} hex digits; valid lengths are 3, 4, 6, or 8",
            ))
    return findings


def _check_functional(line: str, lineno: int) -> list[Finding]:
    findings = []
    for m in FUNC_RE.finditer(line):
        func = m.group(1).lower()
        args = m.group(2)
        col = m.start() + 1
        if func.startswith("rgb"):
            findings.extend(_check_rgb(func, args, lineno, col))
        elif func.startswith("hsl"):
            findings.extend(_check_hsl(func, args, lineno, col))
        elif func.endswith("lab"):
            findings.extend(_check_lab(func, args, lineno, col))
        else:
            findings.extend(_check_lch(func, args, lineno, col))
    return findings


def _classify(token: str) -> tuple[str | None, float | None]:
    token = token.strip()
    if PERCENT_RE.match(token):
        return "percent", float(token[:-1])
    if NUMBER_RE.match(token):
        return "number", float(token)
    return None, None


def _split_alpha(args: str) -> tuple[str, str | None]:
    if "/" in args:
        main, _, alpha = args.partition("/")
        return main.strip(), alpha.strip()
    return args.strip(), None


def _split_parts(main: str) -> list[str]:
    if "," in main:
        return [p.strip() for p in main.split(",") if p.strip()]
    return main.split()


def _check_rgb(func: str, args: str, lineno: int, col: int) -> list[Finding]:
    main, alpha = _split_alpha(args)
    parts = _split_parts(main)

    # Legacy comma syntax folds alpha in as a 4th value: rgba(255, 0, 0, .5)
    if len(parts) == 4 and alpha is None:
        alpha = parts.pop()

    if len(parts) != 3:
        return [Finding(
            lineno, col, "arg-count",
            f"{func}() takes 3 channel values plus optional alpha, got {len(parts)}",
        )]

    classified = [_classify(p) for p in parts]
    if any(kind is None for kind, _ in classified):
        return []  # not a literal we can parse, e.g. a custom property

    kinds = {kind for kind, _ in classified}
    if len(kinds) > 1:
        return [Finding(
            lineno, col, "rgb-mixed-units",
            f"{func}() mixes percentages and numbers: {main}",
        )]

    findings = []
    kind = kinds.pop()
    limit = 100 if kind == "percent" else 255
    for token, (_, value) in zip(parts, classified):
        if not 0 <= value <= limit:
            unit = "%" if kind == "percent" else ""
            findings.append(Finding(
                lineno, col, "rgb-range",
                f"{func}() channel {token} is outside 0-{limit}{unit}",
            ))

    if alpha is not None:
        findings.extend(_check_alpha(func, alpha, lineno, col))

    return findings


def _check_hsl(func: str, args: str, lineno: int, col: int) -> list[Finding]:
    main, alpha = _split_alpha(args)
    parts = _split_parts(main)

    if len(parts) == 4 and alpha is None:
        alpha = parts.pop()

    if len(parts) != 3:
        return [Finding(
            lineno, col, "arg-count",
            f"{func}() takes 3 channel values plus optional alpha, got {len(parts)}",
        )]

    hue, saturation, lightness = parts

    # Hue can be any number of degrees, including outside 0-360 (it wraps),
    # so we only check that it parses as an angle, not its range.
    if not ANGLE_RE.match(hue):
        return []  # not a literal we can parse

    findings = []
    for label, token in (("saturation", saturation), ("lightness", lightness)):
        kind, value = _classify(token)
        if kind is None:
            continue
        if kind != "percent":
            findings.append(Finding(
                lineno, col, "hsl-percent-required",
                f"{func}() {label} must be a percentage, got '{token}'",
            ))
        elif not 0 <= value <= 100:
            findings.append(Finding(
                lineno, col, "hsl-range",
                f"{func}() {label} {token} is outside 0%-100%",
            ))

    if alpha is not None:
        findings.extend(_check_alpha(func, alpha, lineno, col))

    return findings


def _lightness_finding(func: str, token: str, lineno: int, col: int) -> Finding | None:
    # lab()/lch() lightness is 0-100 either way; ok*() numbers are 0-1 instead,
    # but a percentage always means 0%-100% regardless of function.
    kind, value = _classify(token)
    if kind is None:
        return None
    limit = 100 if kind == "percent" else (1 if func.startswith("ok") else 100)
    if 0 <= value <= limit:
        return None
    unit = "%" if kind == "percent" else ""
    return Finding(
        lineno, col, "lab-lightness-range",
        f"{func}() lightness {token} is outside 0-{limit}{unit}",
    )


def _check_lab(func: str, args: str, lineno: int, col: int) -> list[Finding]:
    main, alpha = _split_alpha(args)
    parts = _split_parts(main)

    if len(parts) != 3:
        return [Finding(
            lineno, col, "arg-count",
            f"{func}() takes 3 channel values plus optional alpha, got {len(parts)}",
        )]

    lightness, _a, _b = parts
    findings = []

    finding = _lightness_finding(func, lightness, lineno, col)
    if finding is not None:
        findings.append(finding)

    if alpha is not None:
        findings.extend(_check_alpha(func, alpha, lineno, col))

    return findings


def _check_lch(func: str, args: str, lineno: int, col: int) -> list[Finding]:
    main, alpha = _split_alpha(args)
    parts = _split_parts(main)

    if len(parts) != 3:
        return [Finding(
            lineno, col, "arg-count",
            f"{func}() takes 3 channel values plus optional alpha, got {len(parts)}",
        )]

    lightness, chroma, hue = parts

    # Hue wraps like it does in hsl(), so only its shape is checked, not its range.
    if not ANGLE_RE.match(hue):
        return []  # not a literal we can parse

    findings = []

    finding = _lightness_finding(func, lightness, lineno, col)
    if finding is not None:
        findings.append(finding)

    kind, value = _classify(chroma)
    if kind is not None and value < 0:
        findings.append(Finding(
            lineno, col, "lch-chroma-negative",
            f"{func}() chroma {chroma} cannot be negative",
        ))

    if alpha is not None:
        findings.extend(_check_alpha(func, alpha, lineno, col))

    return findings


def _check_alpha(func: str, token: str, lineno: int, col: int) -> list[Finding]:
    kind, value = _classify(token)
    if kind is None:
        return []
    limit = 100 if kind == "percent" else 1
    if not 0 <= value <= limit:
        unit = "%" if kind == "percent" else ""
        return [Finding(
            lineno, col, "alpha-range",
            f"{func}() alpha {token} is outside 0-{limit}{unit}",
        )]
    return []
