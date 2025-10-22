"""Property-based fuzzing tests for filename sanitization.

This test module uses Hypothesis to generate random filenames and validate
that the filename sanitization logic produces safe, filesystem-compatible
names across a wide range of inputs.

Test Coverage:
- Random Unicode strings
- Control characters and special characters
- Path traversal patterns
- Windows reserved names
- Property: Sanitized names are always safe for filesystem
- Property: No path traversal in output
"""

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from all2md.utils.attachments import sanitize_attachment_filename


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.security
class TestFilenameSanitizationFuzzing:
    """Property-based tests for filename sanitization using Hypothesis."""

    @given(st.text(min_size=0, max_size=300))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_arbitrary_strings_produce_safe_filenames(self, random_string):
        """Property: Any input string produces a safe filename (or 'attachment')."""
        result = sanitize_attachment_filename(random_string)

        # Result should always be a string
        assert isinstance(result, str)

        # Result should not be empty (defaults to 'attachment' if needed)
        assert len(result) > 0

        # Result should not contain path separators
        assert "/" not in result
        assert "\\" not in result

        # Result should not contain null bytes
        assert "\x00" not in result

        # Result should not be dangerous Windows reserved names
        dangerous_names = [
            "con",
            "prn",
            "aux",
            "nul",
            "com1",
            "com2",
            "com3",
            "com4",
            "com5",
            "com6",
            "com7",
            "com8",
            "com9",
            "lpt1",
            "lpt2",
            "lpt3",
            "lpt4",
            "lpt5",
            "lpt6",
            "lpt7",
            "lpt8",
            "lpt9",
        ]
        name_without_ext = Path(result).stem.lower()
        if name_without_ext in dangerous_names:
            # Should be prefixed with 'file_'
            assert result.lower().startswith("file_")

    @given(st.text(alphabet=st.characters(blacklist_categories=["C"], min_codepoint=1), min_size=1, max_size=100))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_control_characters_in_output(self, text):
        """Property: Output should never contain control characters."""
        result = sanitize_attachment_filename(text)

        # Check for control characters (C0 and C1 control codes)
        for char in result:
            # ord values 0-31 and 127-159 are control characters
            char_code = ord(char)
            assert not (
                0 <= char_code < 32 or 127 <= char_code < 160
            ), f"Control character found in output: {char!r} (code {char_code})"

    @given(
        st.text(alphabet=st.characters(whitelist_categories=["L", "N"]), min_size=1, max_size=50),
        st.sampled_from([".txt", ".pdf", ".png", ".docx", ".jpg", ""]),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_extension_preservation(self, basename, extension):
        """Property: Valid file extensions should be preserved."""
        filename = basename + extension
        result = sanitize_attachment_filename(filename)

        if extension and len(basename) > 0:
            # Extension should be preserved (in lowercase)
            assert result.endswith(extension.lower())

    @given(st.text(min_size=0, max_size=100))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_length_limit_enforced(self, text):
        """Property: Output length should never exceed max_length."""
        max_length = 255
        result = sanitize_attachment_filename(text, max_length=max_length)

        assert len(result) <= max_length

    @given(st.text(min_size=1, max_size=1000))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_path_traversal_in_output(self, text):
        """Property: Output should never contain path traversal sequences."""
        result = sanitize_attachment_filename(text)

        # Should not contain ..
        assert ".." not in result

        # Should not start with /
        assert not result.startswith("/")

        # Should not contain \\ (Windows path separator)
        assert "\\" not in result

    @given(
        st.integers(min_value=0, max_value=10),
        st.text(alphabet="._-/", min_size=0, max_size=50),
        st.integers(min_value=0, max_value=10),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_path_traversal_patterns(self, leading_dots, middle, trailing_dots):
        """Test various path traversal patterns are neutralized."""
        # Create pattern like: ../../path/../../
        pattern = "." * leading_dots + middle + "." * trailing_dots
        result = sanitize_attachment_filename(pattern)

        # Should not create valid path traversal
        # Either becomes empty (-> 'attachment') or safe string
        if result != "attachment":
            # Should not have .. sequences
            assert ".." not in result
            # Should not have path separators
            assert "/" not in result
            assert "\\" not in result


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.security
class TestWindowsReservedNamesFuzzing:
    """Fuzz test Windows reserved name handling."""

    @given(
        st.sampled_from(
            [
                "CON",
                "PRN",
                "AUX",
                "NUL",
                "COM1",
                "COM2",
                "COM3",
                "COM4",
                "COM5",
                "COM6",
                "COM7",
                "COM8",
                "COM9",
                "LPT1",
                "LPT2",
                "LPT3",
                "LPT4",
                "LPT5",
                "LPT6",
                "LPT7",
                "LPT8",
                "LPT9",
            ]
        ),
        st.sampled_from(["", ".txt", ".exe", ".dat", ".log"]),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_windows_reserved_names_prefixed(self, reserved_name, extension):
        """Property: Windows reserved names should be prefixed with 'file_'."""
        filename = reserved_name + extension
        result = sanitize_attachment_filename(filename)

        # Should start with 'file_'
        assert result.lower().startswith("file_")

        # Should preserve extension
        if extension:
            assert result.lower().endswith(extension.lower())

    @given(
        st.sampled_from(["con", "prn", "aux", "nul"]),  # lowercase
        st.sampled_from(["", ".txt", ".exe", ".dat"]),  # Extension only
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_case_insensitive_reserved_name_detection(self, reserved_name, extension):
        """Property: Reserved name detection should be case-insensitive."""
        # Mix cases - e.g., 'CoN', 'pRn', etc
        mixed_case = "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(reserved_name))
        filename = mixed_case + extension

        result = sanitize_attachment_filename(filename)

        # Should detect and handle the reserved name regardless of case
        # Result should start with 'file_' prefix
        assert result.lower().startswith("file_")


@pytest.mark.unit
@pytest.mark.fuzzing
class TestUnicodeFuzzing:
    """Fuzz test Unicode handling in filename sanitization."""

    @given(st.text(alphabet=st.characters(min_codepoint=128, max_codepoint=0x10FFFF), min_size=1, max_size=50))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100)
    def test_unicode_normalization(self, unicode_text):
        """Property: Unicode should be normalized (NFC or safe ASCII)."""
        result = sanitize_attachment_filename(unicode_text)

        # Result should be valid UTF-8
        result.encode("utf-8")

        # Should not crash on any Unicode input
        assert isinstance(result, str)

    @given(
        st.text(alphabet=st.characters(whitelist_categories=["L"]), min_size=1, max_size=20),
        st.sampled_from(["\u0301", "\u0302", "\u0303", "\u0308"]),  # Combining diacritics
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_combining_characters_normalized(self, base_text, combining_char):
        """Property: Combining characters should be normalized or removed."""
        filename = base_text + combining_char + ".txt"
        result = sanitize_attachment_filename(filename)

        # Should produce valid filename
        assert len(result) > 0

        # Should preserve .txt extension
        assert result.endswith(".txt")

    @given(st.text(alphabet=st.sampled_from(["ﬁ", "ﬂ", "ﬀ", "ﬃ", "ﬄ"]), min_size=1, max_size=10))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_ligatures_normalized(self, ligature_text):
        """Property: Ligatures should be decomposed to normal characters."""
        filename = ligature_text + ".txt"
        result = sanitize_attachment_filename(filename)

        # Should not contain ligatures (or be normalized to 'attachment')
        # Ligatures U+FB00 to U+FB04
        for char in result:
            assert not ("\ufb00" <= char <= "\ufb04"), f"Ligature found: {char!r}"


@pytest.mark.unit
@pytest.mark.fuzzing
class TestSpecialCharacterFuzzing:
    """Fuzz test special character handling."""

    @given(
        st.text(alphabet='<>:|?*"', min_size=1, max_size=20),
        st.text(alphabet=st.characters(whitelist_categories=["L"]), min_size=1, max_size=20),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_dangerous_characters_removed(self, dangerous_chars, safe_text):
        """Property: Dangerous filesystem characters should be removed."""
        filename = safe_text + dangerous_chars + ".txt"
        result = sanitize_attachment_filename(filename)

        # Dangerous characters should be removed
        for char in '<>:|?*"':
            assert char not in result, f"Dangerous character '{char}' found in result"

    @given(st.text(alphabet=" \t\n\r", min_size=1, max_size=20))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_whitespace_only_becomes_attachment(self, whitespace):
        """Property: Whitespace-only input should become 'attachment'."""
        result = sanitize_attachment_filename(whitespace)

        # Should default to 'attachment' for whitespace-only input
        assert result == "attachment"

    @given(st.text(alphabet=".", min_size=1, max_size=20))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_dots_only_becomes_attachment(self, dots):
        """Property: Dot-only input should become 'attachment'."""
        result = sanitize_attachment_filename(dots)

        # Should default to 'attachment' for dot-only input
        assert result == "attachment"


@pytest.mark.unit
@pytest.mark.fuzzing
class TestEdgeCasesFuzzing:
    """Fuzz test edge cases and boundary conditions."""

    @given(st.integers(min_value=1, max_value=1000))  # At least 1 character
    @settings(max_examples=50)
    def test_very_long_filenames(self, length):
        """Property: Very long filenames should be truncated to max_length."""
        filename = "a" * length + ".txt"
        max_length = 255

        result = sanitize_attachment_filename(filename, max_length=max_length)

        # Should not exceed max length
        assert len(result) <= max_length

        # Should preserve extension if possible (when there's room)
        if length < max_length - 4:  # Room for extension (.txt = 4 chars)
            assert result.endswith(".txt")
        elif length > 0:  # At least some content
            # Very long names might lose extension due to truncation
            assert len(result) > 0

    @given(
        st.text(alphabet=st.characters(whitelist_categories=["L"]), min_size=1, max_size=50),
        st.integers(min_value=1, max_value=10),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multiple_dots_in_filename(self, basename, num_dots):
        """Test filenames with multiple dots are handled correctly."""
        filename = basename + "." * num_dots + "tar.gz"
        result = sanitize_attachment_filename(filename)

        # Should not have consecutive dots
        assert ".." not in result

        # Should produce valid filename
        assert len(result) > 0

    @given(st.text(alphabet="_", min_size=1, max_size=50))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_underscores_only(self, underscores):
        """Property: Underscore-only input should become 'attachment'."""
        result = sanitize_attachment_filename(underscores)

        # Should default to 'attachment'
        assert result == "attachment"


@pytest.mark.unit
@pytest.mark.fuzzing
class TestIdempotenceFuzzing:
    """Test that sanitization is idempotent."""

    @given(st.text(min_size=1, max_size=100))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_sanitization_is_idempotent(self, text):
        """Property: Sanitizing twice should produce same result as sanitizing once."""
        first_pass = sanitize_attachment_filename(text)
        second_pass = sanitize_attachment_filename(first_pass)

        # Should be idempotent
        assert first_pass == second_pass, f"Not idempotent: '{text}' -> '{first_pass}' -> '{second_pass}'"
