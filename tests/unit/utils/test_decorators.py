"""Unit tests for utils/decorators.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import all2md.utils.decorators
from all2md.exceptions import DependencyError
from all2md.utils.decorators import requires_dependencies


class TestRequiresDependencies:
    """Test the requires_dependencies decorator."""

    def test_missing_package_raises_error(self) -> None:
        """Test that a missing package raises DependencyError."""

        @requires_dependencies("test", [("nonexistent-package", "nonexistent", "")])
        def sample_function() -> str:
            return "success"

        with pytest.raises(DependencyError) as exc_info:
            sample_function()

        assert exc_info.value.converter_name == "test"
        assert ("nonexistent-package", "") in exc_info.value.missing_packages
        assert exc_info.value.original_import_error is not None

    def test_version_mismatch_raises_error(self) -> None:
        """Test that an installed package with wrong version raises DependencyError."""
        # Mock importlib to simulate package being installed
        with patch("all2md.utils.decorators.importlib.import_module"):
            # Mock check_version_requirement to return version mismatch
            with patch.object(all2md.utils.decorators, "check_version_requirement", return_value=(False, "1.0.0")):

                @requires_dependencies("test", [("test-package", "test_package", ">=2.0.0")])
                def sample_function() -> str:
                    return "success"

                with pytest.raises(DependencyError) as exc_info:
                    sample_function()

                assert exc_info.value.converter_name == "test"
                assert len(exc_info.value.missing_packages) == 0
                assert ("test-package", ">=2.0.0", "1.0.0") in exc_info.value.version_mismatches

    def test_correct_version_succeeds(self) -> None:
        """Test that an installed package with correct version allows execution."""
        # Mock importlib to simulate package being installed
        with patch("all2md.utils.decorators.importlib.import_module"):
            # Mock check_version_requirement to return success
            with patch.object(all2md.utils.decorators, "check_version_requirement", return_value=(True, "2.5.0")):

                @requires_dependencies("test", [("test-package", "test_package", ">=2.0.0")])
                def sample_function() -> str:
                    return "success"

                result = sample_function()
                assert result == "success"

    def test_no_version_spec_allows_any_version(self) -> None:
        """Test that empty version spec allows any installed version."""
        # Mock importlib to simulate package being installed
        with patch("all2md.utils.decorators.importlib.import_module"):

            @requires_dependencies("test", [("test-package", "test_package", "")])
            def sample_function() -> str:
                return "success"

            result = sample_function()
            assert result == "success"

    def test_multiple_packages_mixed_errors(self) -> None:
        """Test handling of multiple packages with both missing and version mismatch errors."""

        def mock_import(name: str) -> None:
            """Mock import that succeeds for some packages, fails for others."""
            if name == "missing_package":
                raise ImportError(f"No module named '{name}'")
            # Other packages import successfully

        # Mock check_version_requirement to return mismatch for one package
        def mock_version_check(package_name: str, version_spec: str) -> tuple[bool, str | None]:
            """Mock version check that returns mismatch for specific package."""
            if package_name == "wrong-version-package":
                return (False, "1.0.0")
            return (True, "2.0.0")

        with patch("all2md.utils.decorators.importlib.import_module", side_effect=mock_import):
            with patch.object(all2md.utils.decorators, "check_version_requirement", side_effect=mock_version_check):

                @requires_dependencies(
                    "test",
                    [
                        ("missing-package", "missing_package", ">=1.0.0"),
                        ("wrong-version-package", "wrong_version_package", ">=2.0.0"),
                        ("correct-package", "correct_package", ">=1.0.0"),
                    ],
                )
                def sample_function() -> str:
                    return "success"

                with pytest.raises(DependencyError) as exc_info:
                    sample_function()

                # Check that both missing and version mismatch are reported
                assert len(exc_info.value.missing_packages) == 1
                assert ("missing-package", ">=1.0.0") in exc_info.value.missing_packages

                assert len(exc_info.value.version_mismatches) == 1
                assert ("wrong-version-package", ">=2.0.0", "1.0.0") in exc_info.value.version_mismatches

    def test_preserves_function_metadata(self) -> None:
        """Test that decorator preserves function name and docstring."""

        @requires_dependencies("test", [])
        def sample_function() -> str:
            """Sample docstring."""
            return "success"

        assert sample_function.__name__ == "sample_function"
        assert sample_function.__doc__ == "Sample docstring."

    def test_passes_args_and_kwargs(self) -> None:
        """Test that decorator properly passes arguments to wrapped function."""
        with patch("all2md.utils.decorators.importlib.import_module"):

            @requires_dependencies("test", [("test-package", "test_package", "")])
            def sample_function(a: int, b: str, c: int = 10) -> str:
                return f"{a}-{b}-{c}"

            result = sample_function(1, "test", c=20)
            assert result == "1-test-20"

    def test_original_error_preserved(self) -> None:
        """Test that original ImportError is preserved in DependencyError."""

        @requires_dependencies("test", [("nonexistent-package", "nonexistent", "")])
        def sample_function() -> str:
            return "success"

        with pytest.raises(DependencyError) as exc_info:
            sample_function()

        assert exc_info.value.original_import_error is not None
        assert isinstance(exc_info.value.original_import_error, ImportError)
        assert "nonexistent" in str(exc_info.value.original_import_error)

    def test_empty_packages_list(self) -> None:
        """Test that decorator works with empty packages list."""

        @requires_dependencies("test", [])
        def sample_function() -> str:
            return "success"

        result = sample_function()
        assert result == "success"

    def test_version_spec_with_complex_specifiers(self) -> None:
        """Test version checking with complex version specifiers."""
        with patch("all2md.utils.decorators.importlib.import_module"):
            # Mock check_version_requirement for complex specifier
            with patch.object(all2md.utils.decorators, "check_version_requirement", return_value=(True, "1.2.5")):

                @requires_dependencies("test", [("test-package", "test_package", ">=1.2.0,<2.0.0")])
                def sample_function() -> str:
                    return "success"

                result = sample_function()
                assert result == "success"

    def test_unknown_installed_version_reported_as_unknown(self) -> None:
        """Test that when installed version cannot be determined, it's reported as 'unknown'."""
        with patch("all2md.utils.decorators.importlib.import_module"):
            # Mock check_version_requirement to return None for installed version
            with patch.object(all2md.utils.decorators, "check_version_requirement", return_value=(False, None)):

                @requires_dependencies("test", [("test-package", "test_package", ">=2.0.0")])
                def sample_function() -> str:
                    return "success"

                with pytest.raises(DependencyError) as exc_info:
                    sample_function()

                # Should report version as "unknown"
                assert ("test-package", ">=2.0.0", "unknown") in exc_info.value.version_mismatches
