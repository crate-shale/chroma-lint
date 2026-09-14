"""Table-driven tests, keyed on the finding codes rather than exact messages.

Each case is a line of source and the list of finding codes it should
produce, in order. The awkward cases are the point: syntax that is valid but
looks wrong (hue > 360), and syntax that is invalid but looks fine at a
glance (mixed rgb() units, missing "%" on hsl() channels).
"""

import unittest

from chromalint.linter import lint_text

CASES = [
    ("valid short hex", "color: #abc;", []),
    ("valid hex with alpha", "color: #abcd;", []),
    ("valid six-digit hex", "color: #aabbcc;", []),
    ("valid eight-digit hex", "color: #aabbccdd;", []),
    ("five-digit hex is invalid", "color: #abcde;", ["hex-length"]),
    ("seven-digit hex is invalid", "color: #abcdefa;", ["hex-length"]),
    ("uppercase hex is fine", "color: #ABCDEF;", []),
    ("legacy rgb all numbers", "color: rgb(255, 0, 0);", []),
    ("legacy rgb all percentages", "color: rgb(100%, 0%, 0%);", []),
    ("rgb mixing number and percent is invalid",
     "color: rgb(50%, 100, 20);", ["rgb-mixed-units"]),
    ("rgb channel above 255", "color: rgb(300, 0, 0);", ["rgb-range"]),
    ("rgba legacy alpha as a number", "color: rgba(255, 0, 0, 0.5);", []),
    ("rgba alpha percent above 100 is invalid",
     "color: rgba(255, 0, 0, 150%);", ["alpha-range"]),
    ("rgb modern space syntax", "color: rgb(255 0 0);", []),
    ("rgb modern syntax with alpha", "color: rgb(255 0 0 / 50%);", []),
    ("rgb function name is case-insensitive", "color: RGB(255, 0, 0);", []),
    ("rgb wrong argument count", "color: rgb(255, 0);", ["arg-count"]),
    ("hsl with percent saturation and lightness",
     "color: hsl(120, 50%, 50%);", []),
    ("hsl hue above 360 is allowed, it wraps",
     "color: hsl(400, 50%, 50%);", []),
    ("hsl hue with an explicit deg unit", "color: hsl(120deg, 50%, 50%);", []),
    ("hsl saturation and lightness must be percentages",
     "color: hsl(120, 50, 50);", ["hsl-percent-required", "hsl-percent-required"]),
    ("a preprocessor variable is left alone", "color: rgb($red, 0, 0);", []),
    ("plain text with a hash but no hex digits", "# not a colour", []),
]


class LintTextTableTests(unittest.TestCase):
    def test_cases(self):
        for name, source, expected_codes in CASES:
            with self.subTest(name=name):
                codes = [f.code for f in lint_text(source)]
                self.assertEqual(codes, expected_codes)

    def test_line_numbers_are_one_indexed_per_line(self):
        text = "a {\n  color: rgb(300, 0, 0);\n}\n"
        findings = lint_text(text)
        self.assertEqual([f.line for f in findings], [2])


if __name__ == "__main__":
    unittest.main()
