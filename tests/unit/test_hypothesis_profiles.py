"""Guards on the Hypothesis profiles registered in ``tests/conftest.py``.

Why this file exists
--------------------

Hypothesis ships a built-in profile named ``ci`` and auto-loads it when it
detects a CI environment (``CI=true``, which GitHub Actions always sets).
``tests/conftest.py`` registers a profile under that same name -- and
``settings.register_profile`` re-loads a profile if it is the one currently
active. So in CI, and *only* in CI, our registration lands on the live profile,
and every profile registered after it inherits whatever we put there. ``dev`` is
registered after ``ci`` and is what actually runs, so a setting meant for the
``ci`` profile silently became the setting for every test.

That is not hypothetical: a ``verbosity=Verbosity.verbose`` on the ``ci``
profile made CI pretty-print every generated example. That printer calls
``ast.parse``/``inspect.getsource`` per example, which cost ~35s on a
structurally complex document and turned the ~40s generative fuzz run into 68
minutes. It survived weeks of investigation because it cannot reproduce locally
-- off CI the active profile is ``default``, the re-registration does not
re-load, and ``dev`` inherits nothing.

These tests are cheap insurance against the same shape of mistake.
"""

import os

import pytest
from hypothesis import Verbosity, settings


@pytest.mark.unit
def test_the_ci_profile_does_not_request_verbose_output() -> None:
    """Verbose output in CI is not free -- it is a ~100x runtime multiplier.

    Anyone who wants a noisy run has ``--hypothesis-verbosity=verbose`` for a
    single invocation, which costs nothing when it is not passed.
    """
    assert settings.get_profile("ci").verbosity < Verbosity.verbose


@pytest.mark.unit
def test_the_active_profile_is_not_verbose() -> None:
    """The profile that actually runs must not be verbose unless asked for.

    This is the assertion that would have caught the original defect. It passes
    trivially off CI, where nothing re-loads the active profile; it fails in CI
    the moment a profile registered before ``dev`` sets verbosity. ``debug`` is
    exempt because being verbose is the entire point of asking for it.
    """
    if os.getenv("HYPOTHESIS_PROFILE") == "debug":
        pytest.skip("the debug profile is verbose on purpose")
    assert settings.default.verbosity < Verbosity.verbose
