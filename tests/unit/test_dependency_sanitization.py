"""Unit tests for dependency sanitization functions.

Tests to verify that package names and version specifications are properly
sanitized to prevent command injection attacks.
"""

import pytest

from all2md.dependencies import _sanitize_package_name, _sanitize_version_spec, install_dependencies


class TestPackageNameSanitization:
    """Test package name sanitization."""

    def test_valid_package_names(self):
        """Test that valid package names pass sanitization."""
        valid_names = [
            "openpyxl",
            "python-docx",
            "beautifulsoup4",
            "requests_oauthlib",
            "scikit-learn",
            "Pillow",
            "PyMuPDF",
            "lxml",
            "numpy",
            "pandas",
            "matplotlib",
            "jupyter-core",
            "pkg_name.subpkg",
            "package.name",
            "a1",
            "package123",
        ]

        for name in valid_names:
            result = _sanitize_package_name(name)
            assert result == name, f"Valid package name {name} should pass unchanged"

    def test_invalid_package_names(self):
        """Test that invalid package names are rejected."""
        invalid_names = [
            "package; rm -rf /",  # Command injection
            "package && curl evil.com",  # Command chaining
            "package | tee /etc/passwd",  # Pipe redirection
            "package `whoami`",  # Command substitution
            "package$(id)",  # Command substitution
            "package{1..100}",  # Brace expansion
            "package[0-9]",  # Glob patterns
            "package\\; echo hack",  # Escaped semicolon
            "../../../etc/passwd",  # Directory traversal
            ".hidden-package",  # Hidden file
            "package name",  # Spaces
            "package\tname",  # Tabs
            "package\nname",  # Newlines
            "",  # Empty string
            "   ",  # Whitespace only
            "package()",  # Parentheses
            "package{}",  # Braces
            "package[]",  # Brackets
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match="Invalid package name"):
                _sanitize_package_name(name)

    def test_edge_cases(self):
        """Test edge cases for package name sanitization."""
        # Test single characters (excluding dot which starts with dot)
        assert _sanitize_package_name("a") == "a"
        assert _sanitize_package_name("1") == "1"
        assert _sanitize_package_name("-") == "-"
        assert _sanitize_package_name("_") == "_"

        # Test combinations
        assert _sanitize_package_name("a-b_c.d1") == "a-b_c.d1"
        assert _sanitize_package_name("pkg.subpkg") == "pkg.subpkg"

    def test_dot_patterns(self):
        """Test various dot patterns in package names."""
        # Single dot should be rejected (hidden file)
        with pytest.raises(ValueError, match="Invalid package name"):
            _sanitize_package_name(".")

        # Names starting with dot should be rejected
        with pytest.raises(ValueError, match="Invalid package name"):
            _sanitize_package_name(".hidden")

        # Double dots should be rejected (directory traversal)
        with pytest.raises(ValueError, match="Invalid package name"):
            _sanitize_package_name("pkg..name")

        # But dots in the middle are fine
        assert _sanitize_package_name("pkg.name") == "pkg.name"
        assert _sanitize_package_name("my.package.name") == "my.package.name"


class TestVersionSpecSanitization:
    """Test version specification sanitization."""

    def test_valid_version_specs(self):
        """Test that valid version specifications pass sanitization."""
        valid_specs = [
            "",  # Empty spec (no version constraint)
            "==1.0.0",
            ">=2.1",
            "<=3.0.0",
            ">1.2.3",
            "<2.0",
            "!=1.5.0",
            "~=1.4.2",
            "==1.0.0a1",  # Alpha release
            ">=2.0.0b2",  # Beta release
            "==3.0.0rc1",  # Release candidate
            ">=1.0.0.post1",  # Post release
            "==2.0.0.dev0",  # Development release
            ">=1.0+local.1",  # Local version
            "1.0.0",  # Version without operator
            "2.1",  # Short version
            "3",  # Single digit
        ]

        for spec in valid_specs:
            result = _sanitize_version_spec(spec)
            assert result == spec, f"Valid version spec {spec} should pass unchanged"

    def test_invalid_version_specs(self):
        """Test that invalid version specifications are rejected."""
        invalid_specs = [
            ">=1.0; rm -rf /",  # Command injection
            "==1.0 && curl evil.com",  # Command chaining
            ">=1.0 | tee file",  # Pipe redirection
            "==1.0`whoami`",  # Command substitution
            ">=1.0$(id)",  # Command substitution
            "==1.0{1..9}",  # Brace expansion
            ">=1.0[abc]",  # Brackets
            "==1.0()",  # Parentheses
            ">=1.0\\; echo hack",  # Escaped semicolon
            "== 1.0.0",  # Space in operator
            ">=1.0 .0",  # Space in version
            "==1.0\t0",  # Tab
            ">=1.0\n",  # Newline
            "==1.0&1.1",  # Ampersand
            ">=1.0|1.1",  # Pipe
            "==1.0$VAR",  # Variable expansion
            ">=1.0`cmd`",  # Command substitution
        ]

        for spec in invalid_specs:
            with pytest.raises(ValueError, match="Invalid version specification"):
                _sanitize_version_spec(spec)

    def test_empty_version_spec(self):
        """Test that empty version specs are handled correctly."""
        assert _sanitize_version_spec("") == ""
        assert _sanitize_version_spec(None) == None


class TestInstallDependenciesSecurity:
    """Test security aspects of install_dependencies function."""

    def test_malicious_package_names_rejected(self):
        """Test that malicious package names are rejected by install_dependencies."""
        malicious_packages = [
            ("package; rm -rf /", ""),
            ("package && curl evil.com", ">=1.0"),
            ("package`whoami`", "==2.0"),
        ]

        for package_name, version_spec in malicious_packages:
            success, message = install_dependencies([(package_name, version_spec)])
            assert not success, f"Malicious package {package_name} should be rejected"
            assert "Package validation failed" in message
            assert "Invalid package name" in message

    def test_malicious_version_specs_rejected(self):
        """Test that malicious version specifications are rejected."""
        malicious_packages = [
            ("openpyxl", ">=1.0; rm -rf /"),
            ("requests", "==2.0 && curl evil.com"),
            ("lxml", ">=4.0`whoami`"),
        ]

        for package_name, version_spec in malicious_packages:
            success, message = install_dependencies([(package_name, version_spec)])
            assert not success, f"Malicious version spec {version_spec} should be rejected"
            assert "Package validation failed" in message
            assert "Invalid version specification" in message

    def test_valid_packages_pass_validation(self):
        """Test that valid packages pass validation (but may fail installation due to network/environment)."""
        valid_packages = [
            ("openpyxl", ">=3.0.0"),
            ("requests", ""),
            ("lxml", "~=4.6.0"),
        ]

        # Note: We're only testing that validation passes, not actual installation
        # The function may still return False due to network issues, missing pip, etc.
        # But it should NOT fail due to validation errors
        for package_name, version_spec in valid_packages:
            success, message = install_dependencies([(package_name, version_spec)])
            # If it fails, it should NOT be due to validation
            if not success:
                assert "Package validation failed" not in message
                assert "Invalid package name" not in message
                assert "Invalid version specification" not in message

    def test_empty_package_list(self):
        """Test that empty package list is handled correctly."""
        success, message = install_dependencies([])
        assert success
        assert message == "No packages to install"


class TestSecurityPatterns:
    """Test various security attack patterns."""

    def test_shell_injection_patterns(self):
        """Test various shell injection patterns are blocked."""
        injection_patterns = [
            # Command separators
            "pkg;cmd", "pkg&&cmd", "pkg||cmd", "pkg|cmd",
            # Command substitution
            "pkg$(cmd)", "pkg`cmd`",
            # Redirection
            "pkg>file", "pkg<file", "pkg>>file",
            # Background execution
            "pkg&cmd",
            # Globbing
            "pkg*", "pkg?", "pkg[abc]",
            # Variable expansion
            "pkg$VAR", "pkg${VAR}",
            # Path traversal
            "../pkg", "./pkg", "/etc/passwd",
            # Whitespace injection
            "pkg cmd", "pkg\tcmd", "pkg\ncmd",
        ]

        for pattern in injection_patterns:
            with pytest.raises(ValueError):
                _sanitize_package_name(pattern)

    def test_version_injection_patterns(self):
        """Test various version spec injection patterns are blocked."""
        injection_patterns = [
            # Command separators
            "1.0;cmd", "1.0&&cmd", "1.0||cmd", "1.0|cmd",
            # Command substitution
            "1.0$(cmd)", "1.0`cmd`",
            # Redirection
            "1.0>file", "1.0<file",
            # Background execution
            "1.0&cmd",
            # Globbing
            "1.0*", "1.0?", "1.0[abc]",
            # Variable expansion
            "1.0$VAR", "1.0${VAR}",
            # Whitespace injection
            "1.0 cmd", "1.0\tcmd", "1.0\ncmd",
        ]

        for pattern in injection_patterns:
            with pytest.raises(ValueError):
                _sanitize_version_spec(pattern)
