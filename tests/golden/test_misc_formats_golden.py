"""Golden tests for container and communication formats (ZIP, EML, MHTML)."""

from __future__ import annotations

import base64
import datetime
import json
import sys
import types
from io import BytesIO
from pathlib import Path

import pytest
from fixtures.generators.eml_fixtures import (
    create_email_with_html_and_attachment,
    create_email_with_thread_headers,
    create_simple_email,
    email_bytes_io,
)
from fixtures.generators.mhtml_fixtures import (
    create_mhtml_with_image,
    create_simple_mhtml,
)
from fixtures.generators.outlook_fixtures import (
    create_msg_with_attachments_data,
    create_msg_with_html_data,
    create_simple_msg_data,
)
from fixtures.generators.zip_fixtures import (
    create_simple_zip,
    create_zip_with_binary_assets,
    create_zip_with_subarchives,
)

from all2md.api import to_markdown
from all2md.options.outlook import OutlookOptions


def _serialize_msg_payload(data: dict) -> dict:
    """Convert Outlook fixture data into JSON-safe payload."""
    payload: dict[str, object] = {}
    for key, value in data.items():
        if key == "attachments" and value:
            attachments = []
            for attachment in value:
                attachments.append(
                    {
                        "filename": attachment.get("filename"),
                        "content_type": attachment.get("content_type"),
                        "data": base64.b64encode(attachment.get("data", b"")).decode("ascii"),
                    }
                )
            payload[key] = attachments
        elif isinstance(value, datetime.datetime):
            payload[key] = value.isoformat()
        else:
            payload[key] = value

    payload.setdefault("attachments", [])
    if "body" not in payload and "body_text" not in payload:
        payload["body"] = ""
    return payload


def _write_msg_fixture(tmp_path: Path, name: str, data: dict) -> Path:
    """Persist serialized MSG fixture data to a faux .msg file."""
    payload = _serialize_msg_payload(data)
    msg_path = tmp_path / f"{name}.msg"
    msg_path.write_text(json.dumps(payload))
    return msg_path


def _install_extract_msg_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a lightweight extract_msg stub that reads serialized payloads."""

    class _StubAttachment:
        def __init__(self, entry: dict) -> None:
            data_b64 = entry.get("data", "")
            self.data = base64.b64decode(data_b64) if data_b64 else b""
            filename = entry.get("filename") or "attachment.bin"
            self.longFilename = filename
            self.shortFilename = filename

    class _StubMessage:
        def __init__(self, path: str | Path) -> None:
            payload = json.loads(Path(path).read_text())
            self.sender = payload.get("from")
            self.to = payload.get("to")
            self.cc = payload.get("cc")
            self.subject = payload.get("subject")
            date_value = payload.get("date")
            self.date = datetime.datetime.fromisoformat(date_value) if date_value else None
            self.body = payload.get("body") or payload.get("body_text") or ""
            self.htmlBody = payload.get("body_html")
            self.message_id = payload.get("message_id")
            attachments = payload.get("attachments") or []
            self.attachments = [_StubAttachment(item) for item in attachments]

    module = types.ModuleType("extract_msg")
    module.Message = _StubMessage
    monkeypatch.setitem(sys.modules, "extract_msg", module)


from all2md.exceptions import DependencyError


@pytest.mark.golden
@pytest.mark.unit
class TestEmlGolden:
    """Golden tests for EML conversion."""

    def test_simple_email(self, snapshot):
        stream = email_bytes_io(create_simple_email())
        result = to_markdown(stream, source_format="eml")
        assert result == snapshot

    def test_email_with_html_and_attachment(self, snapshot):
        stream = email_bytes_io(create_email_with_html_and_attachment())
        result = to_markdown(stream, source_format="eml")
        assert result == snapshot

    def test_email_with_thread_headers(self, snapshot):
        stream = email_bytes_io(create_email_with_thread_headers())
        result = to_markdown(stream, source_format="eml")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.mhtml
@pytest.mark.unit
class TestMhtmlGolden:
    """Golden tests for MHTML conversion."""

    def test_simple_mhtml(self, snapshot):
        stream = BytesIO(create_simple_mhtml())
        result = to_markdown(stream, source_format="mhtml")
        assert result == snapshot

    def test_mhtml_with_image(self, snapshot):
        stream = BytesIO(create_mhtml_with_image())
        result = to_markdown(stream, source_format="mhtml")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestZipGolden:
    """Golden tests for ZIP archive conversion."""

    def test_simple_zip(self, snapshot):
        stream = BytesIO(create_simple_zip())
        result = to_markdown(stream, source_format="zip")
        assert result == snapshot

    def test_zip_with_binary_assets(self, snapshot):
        stream = BytesIO(create_zip_with_binary_assets())
        try:
            result = to_markdown(stream, source_format="zip")
        except DependencyError as exc:
            pytest.skip(str(exc))
        assert result == snapshot

    def test_zip_with_nested_archive(self, snapshot):
        stream = BytesIO(create_zip_with_subarchives())
        try:
            result = to_markdown(stream, source_format="zip")
        except DependencyError as exc:
            pytest.skip(str(exc))
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.outlook
@pytest.mark.unit
class TestOutlookGolden:
    """Golden tests for Outlook MSG conversion."""

    def test_outlook_simple_message(self, snapshot, tmp_path, monkeypatch):
        _install_extract_msg_stub(monkeypatch)
        msg_path = _write_msg_fixture(tmp_path, "outlook-simple", create_simple_msg_data())

        result = to_markdown(str(msg_path), source_format="outlook")
        assert result == snapshot

    def test_outlook_with_attachments(self, snapshot, tmp_path, monkeypatch):
        _install_extract_msg_stub(monkeypatch)
        msg_path = _write_msg_fixture(tmp_path, "outlook-attachments", create_msg_with_attachments_data())

        result = to_markdown(str(msg_path), source_format="outlook")
        assert result == snapshot

    def test_outlook_html_body_conversion(self, snapshot, tmp_path, monkeypatch):
        _install_extract_msg_stub(monkeypatch)
        msg_path = _write_msg_fixture(tmp_path, "outlook-html", create_msg_with_html_data())

        options = OutlookOptions(convert_html_to_markdown=True)
        result = to_markdown(str(msg_path), source_format="outlook", parser_options=options)
        assert result == snapshot
