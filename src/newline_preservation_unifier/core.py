"""Collapse mixed CR, LF, and CRLF line endings to a consistent style.

The library unifies line endings in a single document while preserving a map
from each normalized line break back to the byte offsets of the original line
endings. That offset record lets tooling translate positions in the unified
text to positions in the original document even after the ending style has been
flattened.

Decision on ambiguous cases (documented in the README):
  * A lone CR is always treated as a line ending. We never try to decide
    whether a CR is a "legacy Mac newline" versus a stray control character;
    if it sits where a line break could be, it is one.
  * Offsets are measured in *Python string indices* (code points), not bytes.
    Mixing byte and code-point offsets in one API is a bug farm; pick one.
  * Trailing content with no line ending produces no offset entry. An offset
    is emitted only where a line ending actually existed in the source.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import List, Optional, Tuple


class LineEnding(enum.Enum):
    """The three line-ending styles this library recognizes.

    ``LF`` and ``CRLF`` are self-explanatory. ``CR`` exists for legacy Mac
    content and for the rare-but-real case of a CR creeping in as a stripped
    carriage return; the unifier treats both the same way because distinguishing
    them reliably from a blob of text is not possible.
    """

    LF = "\n"
    CRLF = "\r\n"
    CR = "\r"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class LineEndingOffset:
    """One original line ending and its location in the source text.

    ``start`` is the index of the first character of the ending in the original
    document; ``end`` is the index just past the last character, so
    ``original[start:end]`` reproduces the exact ending sequence that was
    replaced. Keeping both bounds avoids recomputing lengths and makes the
    span directly sliceable.
    """

    start: int
    end: int
    ending: LineEnding


@dataclass(frozen=True)
class UnificationResult:
    """Output of :meth:`NewlineUnifier.unify`.

    ``unified`` is the document with every line ending converted to
    ``target_ending``. ``offsets`` records, in source order, each original
    line ending that was replaced. The offsets describe the *original* text,
    not the unified text; mapping a unified position back to the original is a
    separate concern the caller can build on top of this record.
    """

    unified: str
    offsets: List[LineEndingOffset]
    target_ending: LineEnding


class NewlineUnifier:
    """Detect and replace mixed line endings in a single document.

    The class is stateless across calls; constructing one per target style is
    cheap and makes call sites explicit about which style they want.
    """

    def __init__(self, target_ending: LineEnding = LineEnding.LF) -> None:
        if not isinstance(target_ending, LineEnding):
            raise TypeError(
                "target_ending must be a LineEnding, got %r" % (type(target_ending).__name__,)
            )
        self._target = target_ending

    @property
    def target_ending(self) -> LineEnding:
        """The line ending this unifier converts to."""
        return self._target

    @staticmethod
    def detect_endings(text: str) -> List[LineEndingOffset]:
        """Return every line ending in ``text`` with its source span.

        Scanning is a single forward pass that special-cases CRLF so that a
        CR immediately followed by an LF is recorded as one ending, not two.
        Everything else (LF alone, CR alone) is recorded as its own ending.
        The function does not skip or merge adjacent endings of the same kind:
        ``"\n\n"`` is two LF endings, which is the behavior callers will want
        when they need to map every original line break.
        """
        offsets: List[LineEndingOffset] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\r":
                if i + 1 < n and text[i + 1] == "\n":
                    offsets.append(LineEndingOffset(i, i + 2, LineEnding.CRLF))
                    i += 2
                    continue
                offsets.append(LineEndingOffset(i, i + 1, LineEnding.CR))
                i += 1
            elif ch == "\n":
                offsets.append(LineEndingOffset(i, i + 1, LineEnding.LF))
                i += 1
            else:
                i += 1
        return offsets

    def unify(self, text: str) -> UnificationResult:
        """Replace every line ending in ``text`` with the target style.

        Returns an :class:`UnificationResult` whose ``offsets`` describe the
        original endings. If ``text`` contains no line endings at all, the
        unified text equals the input and ``offsets`` is empty.
        """
        if not isinstance(text, str):
            raise TypeError("text must be str, got %r" % (type(text).__name__,))

        offsets = self.detect_endings(text)
        if not offsets:
            return UnificationResult(unified=text, offsets=[], target_ending=self._target)

        # Build the unified string by copying the gaps between original endings
        # and appending the target ending where each original ending sat. This
        # avoids a chain of ``str.replace`` calls that would mishandle cases
        # where the target style happens to be a substring of an original style
        # (e.g. normalizing CRLF -> LF must not then re-detect the new LFs).
        replacement = self._target.value
        parts: List[str] = []
        cursor = 0
        for off in offsets:
            parts.append(text[cursor:off.start])
            parts.append(replacement)
            cursor = off.end
        parts.append(text[cursor:])
        unified = "".join(parts)
        return UnificationResult(
            unified=unified, offsets=offsets, target_ending=self._target
        )

    def original_span_for(self, offset: LineEndingOffset) -> Tuple[int, int]:
        """Return the ``(start, end)`` source span of ``offset``.

        Convenience accessor so callers do not need to reach into the dataclass
        fields directly. The returned tuple matches what
        ``original[start:end]`` would slice.
        """
        return offset.start, offset.end
