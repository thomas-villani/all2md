"""``sanitize_attachment_filename`` logs a filename it cannot trust in escaped form.

An attachment name is untrusted input and can hold a lone surrogate (Python's
``surrogateescape`` decoding produces them from undecodable bytes). The debug
line logged it raw, and a log record that cannot be encoded as UTF-8 breaks
whatever handler writes it: under pytest-xdist it crashed the whole run.
"""

import logging

import pytest

from all2md.utils.attachments import sanitize_attachment_filename

SURROGATE = chr(0xDF86)
ESC = chr(0x1B)


@pytest.mark.unit
def test_a_surrogate_in_the_name_is_logged_escaped(caplog):
    with caplog.at_level(logging.DEBUG, logger="all2md.utils.attachments"):
        sanitize_attachment_filename(f"report{SURROGATE}.pdf")
    text = caplog.text
    text.encode("utf-8")
    assert repr(SURROGATE)[1:-1] in text  # the escape, not the character


@pytest.mark.unit
def test_a_control_character_in_the_name_is_logged_escaped(caplog):
    with caplog.at_level(logging.DEBUG, logger="all2md.utils.attachments"):
        sanitize_attachment_filename(f"report{ESC}]0;x.pdf")
    assert ESC not in caplog.text
