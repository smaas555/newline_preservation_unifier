import unittest

from newline_preservation_unifier import NewlineUnifier, LineEnding, UnificationResult
from newline_preservation_unifier.core import LineEndingOffset


class TestDetectEndings(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(NewlineUnifier.detect_endings(""), [])

    def test_no_line_endings(self):
        self.assertEqual(NewlineUnifier.detect_endings("hello world"), [])

    def test_single_lf(self):
        offsets = NewlineUnifier.detect_endings("a\nb")
        self.assertEqual(len(offsets), 1)
        self.assertEqual(offsets[0].start, 1)
        self.assertEqual(offsets[0].end, 2)
        self.assertIs(offsets[0].ending, LineEnding.LF)

    def test_single_crlf(self):
        offsets = NewlineUnifier.detect_endings("a\r\nb")
        self.assertEqual(len(offsets), 1)
        self.assertEqual(offsets[0].start, 1)
        self.assertEqual(offsets[0].end, 3)
        self.assertIs(offsets[0].ending, LineEnding.CRLF)

    def test_single_cr(self):
        offsets = NewlineUnifier.detect_endings("a\rb")
        self.assertEqual(len(offsets), 1)
        self.assertEqual(offsets[0].start, 1)
        self.assertEqual(offsets[0].end, 2)
        self.assertIs(offsets[0].ending, LineEnding.CR)

    def test_crlf_does_not_become_two_endings(self):
        offsets = NewlineUnifier.detect_endings("\r\n")
        self.assertEqual(len(offsets), 1)
        self.assertIs(offsets[0].ending, LineEnding.CRLF)

    def test_mixed_endings_in_order(self):
        # CRLF, then LF, then CR. The scanner must keep source order and
        # advance past each ending correctly so the next one starts after it.
        text = "1\r\n2\n3\r4"
        offsets = NewlineUnifier.detect_endings(text)
        self.assertEqual(
            [(o.start, o.end, o.ending) for o in offsets],
            [
                (1, 3, LineEnding.CRLF),
                (4, 5, LineEnding.LF),
                (6, 7, LineEnding.CR),
            ],
        )

    def test_adjacent_lf_lf(self):
        offsets = NewlineUnifier.detect_endings("\n\n")
        self.assertEqual(len(offsets), 2)
        self.assertEqual(offsets[0].start, 0)
        self.assertEqual(offsets[1].start, 1)

    def test_trailing_text_produces_no_extra_offset(self):
        offsets = NewlineUnifier.detect_endings("a\nb")
        self.assertEqual(len(offsets), 1)
        self.assertEqual(text := "a\nb", "a\nb")  # sanity on the fixture


class TestUnify(unittest.TestCase):
    def test_already_target_is_unchanged_in_content(self):
        u = NewlineUnifier(LineEnding.LF)
        result = u.unify("a\nb\n")
        self.assertEqual(result.unified, "a\nb\n")
        self.assertEqual(len(result.offsets), 2)

    def test_crlf_to_lf(self):
        u = NewlineUnifier(LineEnding.LF)
        result = u.unify("a\r\nb\r\n")
        self.assertEqual(result.unified, "a\nb\n")
        self.assertEqual(result.target_ending, LineEnding.LF)
        self.assertEqual(len(result.offsets), 2)
        self.assertIs(result.offsets[0].ending, LineEnding.CRLF)

    def test_lf_to_crlf(self):
        u = NewlineUnifier(LineEnding.CRLF)
        result = u.unify("a\nb\n")
        self.assertEqual(result.unified, "a\r\nb\r\n")
        self.assertEqual(len(result.offsets), 2)
        self.assertIs(result.offsets[0].ending, LineEnding.LF)

    def test_cr_to_lf(self):
        u = NewlineUnifier(LineEnding.LF)
        result = u.unify("a\rb\r")
        self.assertEqual(result.unified, "a\nb\n")
        self.assertEqual(len(result.offsets), 2)
        self.assertIs(result.offsets[0].ending, LineEnding.CR)

    def test_mixed_to_lf(self):
        u = NewlineUnifier(LineEnding.LF)
        result = u.unify("1\r\n2\n3\r4")
        self.assertEqual(result.unified, "1\n2\n3\n4")
        self.assertEqual(len(result.offsets), 3)
        self.assertEqual(
            [(o.ending) for o in result.offsets],
            [LineEnding.CRLF, LineEnding.LF, LineEnding.CR],
        )

    def test_no_endings_returns_input_unchanged(self):
        u = NewlineUnifier(LineEnding.LF)
        result = u.unify("no newlines here")
        self.assertEqual(result.unified, "no newlines here")
        self.assertEqual(result.offsets, [])

    def test_empty_string_unified(self):
        u = NewlineUnifier(LineEnding.LF)
        result = u.unify("")
        self.assertEqual(result.unified, "")
        self.assertEqual(result.offsets, [])

    def test_only_line_endings(self):
        u = NewlineUnifier(LineEnding.LF)
        result = u.unify("\r\n\r\n")
        self.assertEqual(result.unified, "\n\n")
        self.assertEqual(len(result.offsets), 2)

    def test_offsets_describe_original_not_unified(self):
        # Offsets must point into the ORIGINAL text so the caller can slice
        # the original ending back out. After CRLF->LF the unified text is
        # shorter, but the recorded span must still cover 2 chars.
        original = "x\r\ny"
        u = NewlineUnifier(LineEnding.LF)
        result = u.unify(original)
        off = result.offsets[0]
        self.assertEqual(original[off.start:off.end], "\r\n")
        self.assertEqual(result.unified[off.start:off.start + 1], "\n")

    def test_trailing_newline_only(self):
        u = NewlineUnifier(LineEnding.CRLF)
        result = u.unify("text\n")
        self.assertEqual(result.unified, "text\r\n")
        self.assertEqual(len(result.offsets), 1)
        self.assertEqual(result.offsets[0].start, 4)
        self.assertEqual(result.offsets[0].end, 5)

    def test_result_type(self):
        u = NewlineUnifier(LineEnding.LF)
        result = u.unify("a\nb")
        self.assertIsInstance(result, UnificationResult)
        self.assertIsInstance(result.offsets, list)
        self.assertTrue(all(isinstance(o, LineEndingOffset) for o in result.offsets))

    def test_target_ending_property(self):
        u = NewlineUnifier(LineEnding.CRLF)
        self.assertIs(u.target_ending, LineEnding.CRLF)

    def test_invalid_target_raises(self):
        with self.assertRaises(TypeError):
            NewlineUnifier("\n")  # type: ignore[arg-type]

    def test_invalid_text_raises(self):
        u = NewlineUnifier(LineEnding.LF)
        with self.assertRaises(TypeError):
            u.unify(b"not a string")  # type: ignore[arg-type]

    def test_original_span_for_accessor(self):
        u = NewlineUnifier(LineEnding.LF)
        result = u.unify("a\r\nb")
        off = result.offsets[0]
        self.assertEqual(u.original_span_for(off), (1, 3))


class TestLineEnding(unittest.TestCase):
    def test_str_value(self):
        self.assertEqual(str(LineEnding.LF), "\n")
        self.assertEqual(str(LineEnding.CRLF), "\r\n")
        self.assertEqual(str(LineEnding.CR), "\r")

    def test_members(self):
        # Ensure the public enum has exactly these three members and no more,
        # so downstream code relying on the set of styles does not break quietly.
        self.assertEqual(
            {m.name for m in LineEnding},
            {"LF", "CRLF", "CR"},
        )


if __name__ == "__main__":
    unittest.main()
