import datetime
from io import StringIO

import pytest

from all2md import MdparseInputError
from all2md.emlfile import format_email_chain_as_markdown, parse_email_chain


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
    msgs = parse_email_chain(f)
    assert isinstance(msgs, list) and len(msgs) == 1
    m = msgs[0]
    assert m["from"] == "A <a@example.com>"
    assert m["to"] == "B <b@example.com>"
    assert m["subject"] == "Test Email"
    assert m["date"].year == 2023 and m["date"].hour == 10 and m["date"].tzinfo is not None
    assert m["content"].strip() == "Hello world"
    assert m["message_id"] == "<msg1@example.com>"
    assert m["in_reply_to"] == "<prev@example.com>"
    assert m["references"] == "<ref1@example.com>"


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
    msgs = parse_email_chain(str(p))
    assert len(msgs) == 1
    m = msgs[0]
    assert m["subject"] == "File Path Test"
    assert "File content here" in m["content"]


def test_parse_email_chain_invalid_type():
    with pytest.raises(MdparseInputError):
        parse_email_chain(123)


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
    msgs = parse_email_chain(f)
    assert len(msgs) == 1
    m = msgs[0]
    assert "<p>This is <b>HTML</b> content.</p>" in m["content"]


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
    msgs = parse_email_chain(f)
    assert len(msgs) == 2
    m0, m1 = msgs
    # original message from chain should be first (older)
    assert m0["from"] == "Original <orig@example.com>"
    assert m0["to"] == "Respond <resp@example.com>"
    assert m0["subject"] == "Re: Chain Example"
    assert m0["date"].year == 2023 and m0["date"].month == 1 and m0["date"].day == 2
    assert "This is quoted" in m0["content"]
    assert "Original content line 1" in m0["content"]
    assert "<https://urldefense.com" not in m0["content"]
    assert m0.get("cc") == "CC <cc@example.com>"
    # top message should be second (newer)
    assert m1["from"] == "Top <top@example.com>"
    assert m1["to"] == "Bot <bot@example.com>"
    assert m1["subject"] == "Chain Example"
    assert "Here is my message" in m1["content"]
    assert m1.get("cc") is None


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
    md = parse_email_chain(f, as_markdown=True)
    # Older message first
    assert md.startswith("From: Original <orig@example.com>")
    # cc line only in first block
    assert md.count("cc: CC <cc@example.com>") == 1
    assert "From: Top <top@example.com>" in md
    assert "Quoted content" in md
    assert "Hello Top" in md
    assert "<https://urldefense.com" not in md
