import datetime
from io import StringIO

import pytest

from all2md import InputError
from all2md.converters.eml2markdown import format_email_chain_as_markdown, eml_to_markdown


@pytest.mark.unit
def test_format_email_chain_as_markdown_basic():
    items = [
        {
            "from": "a@example.com",
            "to": "b@example.com",
            "date": datetime.datetime(2023, 1, 1, 10, 0, tzinfo=datetime.UTC),
            "subject": "Subj1",
            "content": "Hello",
            "cc": "c@example.com",
        },
        {
            "from": "x@example.com",
            "to": "y@example.com",
            "date": datetime.datetime(2023, 1, 2, 11, 30, tzinfo=datetime.UTC),
            "subject": "Subj2",
            "content": "World",
        },
    ]
    expected = ""
    expected += "From: a@example.com\n"
    expected += "To: b@example.com\n"
    expected += "cc: c@example.com\n"
    expected += "Date: 01/01/23 10:00\n"
    expected += "Subject: Subj1\n"
    expected += "Hello\n"
    expected += "---\n"
    expected += "From: x@example.com\n"
    expected += "To: y@example.com\n"
    expected += "Date: 01/02/23 11:30\n"
    expected += "Subject: Subj2\n"
    expected += "World\n"
    expected += "---\n"
    assert format_email_chain_as_markdown(items) == expected


@pytest.mark.unit
def test_format_email_chain_as_markdown_no_cc():
    items = [
        {
            "from": "foo",
            "to": "bar",
            "date": datetime.datetime(2022, 12, 31, 23, 59, tzinfo=datetime.UTC),
            "subject": "Year End",
            "content": "Bye",
        },
    ]
    result = format_email_chain_as_markdown(items)
    assert "cc:" not in result


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
    assert "Subject: Test Email" in md
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
    assert "Subject: File Path Test" in md
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
    assert "Subject: HTML Only" in md
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
    assert "Subject: Re: Chain Example" in md
    assert "Subject: Chain Example" in md
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
    # Older message first
    assert md.startswith("From: Original <orig@example.com>")
    # cc line only in first block
    assert md.count("cc: CC <cc@example.com>") == 1
    assert "From: Top <top@example.com>" in md
    assert "Quoted content" in md
    assert "Hello Top" in md
    assert "<https://urldefense.com" not in md
