import datetime
from io import StringIO

import pytest

from all2md import InputError
from all2md.parsers.eml2markdown import eml_to_markdown



@pytest.mark.unit
def test_parse_email_chain_stringio_simple():
    eml = """From: A <a@example.com>
Sent: Mon, 1 Jan 2023 10:00:00 -0500
To: B <b@example.com>
Subject: Test Email
Message-ID: <msg1@example.com>
In-Reply-To: <prev@example.com>
References: <ref1@example.com>

Hello world
"""
    f = StringIO(eml)
    md = eml_to_markdown(f)
    assert isinstance(md, str)
    assert "From: A <a@example.com>" in md
    assert "To: B <b@example.com>" in md
    # Subject is now shown as H1 heading by default (subject_as_h1=True)
    assert "# Test Email" in md
    assert "Hello world" in md


@pytest.mark.unit
def test_parse_email_chain_file_path(tmp_path):
    eml = """From: C <c@example.com>
Sent: Tue, 2 Jan 2023 15:30:00 +0000
To: D <d@example.com>
Subject: File Path Test
Message-ID: <msg2@example.com>

File content here
"""
    p = tmp_path / "test.eml"
    p.write_text(eml, encoding="utf-8")
    md = eml_to_markdown(str(p))
    assert isinstance(md, str)
    # Subject is now shown as H1 heading by default (subject_as_h1=True)
    assert "# File Path Test" in md
    assert "File content here" in md


@pytest.mark.unit
def test_parse_email_chain_invalid_type():
    with pytest.raises(InputError):
        eml_to_markdown(123)


@pytest.mark.unit
def test_parse_email_chain_html_only():
    eml = """From: HTML <html@example.com>
To: Dest <dest@example.com>
Sent: Thu, 5 Jan 2023 08:00:00 +0000
Subject: HTML Only
Message-ID: <htmlmsg@example.com>
Content-Type: text/html; charset="utf-8"

<html>
<body>
<p>This is <b>HTML</b> content.</p>
</body>
</html>
"""
    f = StringIO(eml)
    md = eml_to_markdown(f)
    assert isinstance(md, str)
    # Subject is now shown as H1 heading by default (subject_as_h1=True)
    assert "# HTML Only" in md
    assert "<p>This is <b>HTML</b> content.</p>" in md


# def test_parse_email_chain_missing_optional_headers():
#     eml = """From: NoOpt <noopt@example.com>
# To: Someone <someone@example.com>
# Subject: No Optional
#
# Body text here
# """
#     f = StringIO(eml)
#     msgs = parse_email_chain(f)
#     assert len(msgs) == 1
#     m = msgs[0]
#     assert m['in_reply_to'] is None
#     assert m['references'] is None
#     assert m['message_id'] is None
#     assert m['date'] is None


@pytest.mark.unit
def test_parse_email_chain_chain_cleaning_and_sorting():
    eml = """From: Top <top@example.com>
To: Bot <bot@example.com>
Date: Wed, 4 Jan 2023 12:00:00 +0000
Subject: Chain Example
Message-ID: <topid@example.com>

Here is my message
Check this out
<https://urldefense.com/some>

From: Original <orig@example.com>
Sent: Tue, 2 Jan 2023 09:00:00 -0500
To: Respond <resp@example.com>
Cc: CC <cc@example.com>
Subject: Re: Chain Example

> This is quoted
>
Original content line 1
Original content line 2

<https://urldefense.com/remove>This link
"""
    f = StringIO(eml)
    md = eml_to_markdown(f)
    assert isinstance(md, str)
    # Should contain both messages in chronological order (older first)
    assert "From: Original <orig@example.com>" in md
    assert "From: Top <top@example.com>" in md
    # Subjects are now shown as H1 headings by default (subject_as_h1=True)
    assert "# Re: Chain Example" in md
    assert "# Chain Example" in md
    assert "This is quoted" in md
    assert "Original content line 1" in md
    assert "Here is my message" in md
    # URL defense links should be cleaned
    assert "<https://urldefense.com" not in md
    # CC should appear
    assert "cc: CC <cc@example.com>" in md


@pytest.mark.unit
def test_parse_email_chain_as_markdown_chain():
    eml = """From: Top <top@example.com>
To: Bot <bot@example.com>
Date: Wed, 4 Jan 2023 12:00:00 +0000
Subject: Chain Example

Hello Top

From: Original <orig@example.com>
Sent: Tue, 2 Jan 2023 09:00:00 -0500
To: Respond <resp@example.com>
Cc: CC <cc@example.com>
Subject: Re: Chain Example

Quoted content
"""
    f = StringIO(eml)
    md = eml_to_markdown(f)
    # Subject heading comes first now (subject_as_h1=True by default)
    assert md.startswith("# Re: Chain Example")
    # cc line only in first block
    assert md.count("cc: CC <cc@example.com>") == 1
    assert "From: Top <top@example.com>" in md
    assert "Quoted content" in md
    assert "Hello Top" in md
    assert "<https://urldefense.com" not in md
