# chromalint

A linter for colour literals in CSS (and anything else that embeds CSS-style
colours: templates, Sass, JS-in-CSS). It checks hex codes and the `rgb()` /
`rgba()` / `hsl()` / `hsla()` / `lab()` / `lch()` / `oklab()` / `oklch()`
functions for the kind of mistake that's easy to type by hand and easy to
miss in review, because the file still parses fine and the browser just
clamps or ignores the bad value:

- hex codes with the wrong number of digits (`#12345` isn't 3, 4, 6, or 8)
- `rgb()` calls that mix percentages and numbers across channels, e.g.
  `rgb(50%, 100, 20)` — the spec requires one or the other, not both
- channel or alpha values outside their legal range, e.g. `rgb(300, 0, 0)`
  or `rgba(0, 0, 0, 150%)`
- `hsl()` saturation or lightness written without a `%`, e.g.
  `hsl(120, 50, 50)` — those two channels are always percentages, only the
  hue is a bare number (or an angle with `deg`/`grad`/`rad`/`turn`)
- `lab()` / `lch()` lightness outside its legal range, e.g. `lab(150 40 60)`
  — a plain number tops out at 100, or at 1 for `oklab()`/`oklch()`, and a
  percentage always means 0%-100% regardless of which function it's in
- `lch()` / `oklch()` chroma written as a negative number, e.g.
  `lch(50% -40 200)` — chroma has no sign, unlike the hue that follows it

It does not flag a hue outside 0-360, because CSS defines that as wrapping,
not an error. That's the kind of distinction a plain regex-for-any-hex-string
check gets wrong, which is the reason this exists instead of a one-line grep.

## Usage

As a script, given a stylesheet:

```css
/* style.css */
a {
  color: #abcde;
  background: rgb(50%, 100, 20);
  border-color: hsl(200, 50, 40%);
}
```

```
$ python -m chromalint.cli style.css
style.css:3:10: #abcde has 5 hex digits; valid lengths are 3, 4, 6, or 8 [hex-length]
style.css:4:15: rgb() mixes percentages and numbers: 50%, 100, 20 [rgb-mixed-units]
style.css:5:17: hsl() saturation must be a percentage, got '50' [hsl-percent-required]
```

The exit code is 1 if any findings were reported, 2 on a usage or I/O error,
0 otherwise, which is enough to wire into a pre-commit hook or CI step.

As a library:

```python
from chromalint import lint_text

findings = lint_text(open("style.css").read())
for f in findings:
    print(f)  # "3:10: #abcde has 5 hex digits ... [hex-length]"
```

## How it works, and where that falls short

`chromalint` scans text line by line with regular expressions; it does not
parse CSS. That keeps it dependency-free and usable on anything that embeds
colour literals. It skips matches inside `/* */` comments (including ones
spanning several lines) and inside `'...'`/`"..."` strings. A colour
function whose arguments are split across multiple lines is still checked —
`rgb(50%,\n  100, 20)` is reported at the line and column where `rgb(`
starts — but if the closing `)` is never found before the end of the file,
the call is silently skipped rather than guessed at. Tokens it can't make
sense of — Sass variables, custom properties, `calc()` — are left alone
rather than guessed at.

## Status

Early. `lab()`/`lch()`/`oklab()`/`oklch()` are checked for lightness range
and (for `lch()`/`oklch()`) negative chroma, but not the `a`/`b` axes in
`lab()`/`oklab()` — CSS Color 4 doesn't define a hard range for those, so
there's nothing obviously wrong to flag. See the tests for the exact set of
cases currently covered.

## License

MIT, see [LICENSE](LICENSE).
