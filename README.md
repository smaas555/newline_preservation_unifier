# Newline Preservation Unifier

Collapses mixed CR, LF, and CRLF line endings in a single document to one consistent style and records the source position of every original line ending so you can map positions back.

## Usage

```python
from newline_preservation_unifier import NewlineUnifier, LineEnding

unifier = NewlineUnifier(LineEnding.LF)
result = unifier.unify("a\r\nb\r\nc\nd")

print(repr(result.unified))      # 'a\nb\nc\nd'
print(result.target_ending)       # LineEnding.LF
for off in result.offsets:
    print(off.start, off.end, off.ending)
    # 1 3 LineEnding.CRLF
    # 4 5 LineEnding.CR
    # 6 7 LineEnding.LF
```

`NewlineUnifier(target_ending)` takes a `LineEnding` (`LF`, `CRLF`, or `CR`). `unify(text)` returns an `UnificationResult` with three fields: `unified` (the rewritten text), `offsets` (a list of `LineEndingOffset` describing each original line ending), and `target_ending`. Each `LineEndingOffset` has `start`, `end`, and `ending`; `original[start:end]` reproduces the exact original ending sequence.

## Why

The problem is straightforward in isolation — find line endings, replace them — but doing it while keeping a faithful record of where the originals sat is what this library is for. Positions in error messages, source maps, and diagnostics are only useful if you can translate a column in the unified text back to the column in the file on disk. `str.replace` gets you a clean string and loses the mapping; a regex gets you a mapping and mishandles CRLF-into-LF collapses because the replacement text can be re-seen by a second pass.

The unifier scans once, special-cases CRLF so a CR immediately followed by LF is one ending rather than two, and builds the unified string by stitching the gaps between original endings together with the target ending. Offsets always describe the original text, never the unified text, so the unified string can be shorter or longer than the source without any offset referring to a position that no longer exists.

## Decisions and edges

- **A lone CR is always a line ending.** The library does not try to distinguish a legacy Mac newline from a stray carriage return; if a CR sits where a line break could be, it is treated as one. If you have binary-ish content with meaningful lone CRs, do not run this over it.
- **Offsets are Python string indices (code points), not bytes.** Mixing byte and code-point positions in one API is a common source of off-by-one bugs when non-ASCII characters appear. Everything here is in the same unit `str` uses.
- **Trailing content with no line ending produces no offset.** An offset is emitted only where a line ending actually existed. If the input is `"abc"`, the result has zero offsets; if it is `"abc\n"`, it has one.
- **The same ending appearing twice in a row is two offsets.** `"\n\n"` yields two LF offsets. The library records every original break; it does not coalesce.

## Layout

- `src/newline_preservation_unifier/__init__.py` re-exports `NewlineUnifier`, `LineEnding`, `UnificationResult`.
- `src/newline_preservation_unifier/core.py` holds the implementation. `LineEndingOffset` is also exported from `core` for callers who need the type for annotations.

Run the tests with `PYTHONPATH=src python -m unittest discover -s tests`.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

