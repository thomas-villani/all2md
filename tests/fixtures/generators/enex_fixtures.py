"""Generate sample ENEX (Evernote Export) test fixtures.

This module provides utilities to generate synthetic ENEX files for testing
the ENEX parser.
"""

import base64
import hashlib
from pathlib import Path


def generate_simple_note_enex(tmp_path: Path) -> Path:
    """Generate a simple ENEX file with one note.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory to create the file in

    Returns
    -------
    Path
        Path to the generated ENEX file

    """
    content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export export-date="20250128T120000Z" application="Evernote" version="10.0">
<note>
  <title>Test Note</title>
  <content><![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
  <div>This is a test note with <b>bold</b> and <i>italic</i> text.</div>
  <div><br/></div>
  <div>A paragraph with a <a href="https://example.com">link</a>.</div>
</en-note>
]]></content>
  <created>20250115T100000Z</created>
  <updated>20250120T150000Z</updated>
  <tag>test</tag>
  <tag>example</tag>
  <note-attributes>
    <source-url>https://example.com/source</source-url>
    <source>web.clip</source>
  </note-attributes>
</note>
</en-export>"""

    enex_path = tmp_path / "simple_note.enex"
    enex_path.write_text(content, encoding="utf-8")
    return enex_path


def generate_note_with_image_enex(tmp_path: Path) -> Path:
    """Generate an ENEX file with a note containing an embedded image.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory to create the file in

    Returns
    -------
    Path
        Path to the generated ENEX file

    """
    # Create a minimal 1x1 PNG image
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    png_base64 = base64.b64encode(png_data).decode("ascii")
    png_hash = hashlib.md5(png_data).hexdigest()

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export export-date="20250128T120000Z" application="Evernote" version="10.0">
<note>
  <title>Note with Image</title>
  <content><![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
  <div>This note has an embedded image:</div>
  <div><en-media type="image/png" hash="{png_hash}"/></div>
  <div>Image caption text.</div>
</en-note>
]]></content>
  <created>20250115T100000Z</created>
  <updated>20250120T150000Z</updated>
  <resource>
    <data encoding="base64">{png_base64}</data>
    <mime>image/png</mime>
    <resource-attributes>
      <file-name>test-image.png</file-name>
    </resource-attributes>
  </resource>
</note>
</en-export>"""

    enex_path = tmp_path / "note_with_image.enex"
    enex_path.write_text(content, encoding="utf-8")
    return enex_path


def generate_multiple_notes_enex(tmp_path: Path) -> Path:
    """Generate an ENEX file with multiple notes.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory to create the file in

    Returns
    -------
    Path
        Path to the generated ENEX file

    """
    content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export export-date="20250128T120000Z" application="Evernote" version="10.0">
<note>
  <title>First Note</title>
  <content><![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
  <div>Content of the first note.</div>
</en-note>
]]></content>
  <created>20250115T100000Z</created>
  <updated>20250120T150000Z</updated>
  <tag>first</tag>
  <notebook>Work</notebook>
</note>
<note>
  <title>Second Note</title>
  <content><![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
  <div>Content of the second note.</div>
</en-note>
]]></content>
  <created>20250116T110000Z</created>
  <updated>20250121T160000Z</updated>
  <tag>second</tag>
  <notebook>Personal</notebook>
</note>
<note>
  <title>Third Note</title>
  <content><![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
  <div>Content of the third note with a <a href="https://example.com">link</a>.</div>
</en-note>
]]></content>
  <created>20250117T120000Z</created>
  <updated>20250122T170000Z</updated>
  <tag>third</tag>
  <notebook>Work</notebook>
</note>
</en-export>"""

    enex_path = tmp_path / "multiple_notes.enex"
    enex_path.write_text(content, encoding="utf-8")
    return enex_path


def generate_empty_note_enex(tmp_path: Path) -> Path:
    """Generate an ENEX file with an empty note (no content).

    Parameters
    ----------
    tmp_path : Path
        Temporary directory to create the file in

    Returns
    -------
    Path
        Path to the generated ENEX file

    """
    content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export export-date="20250128T120000Z" application="Evernote" version="10.0">
<note>
  <title>Empty Note</title>
  <content><![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
</en-note>
]]></content>
  <created>20250115T100000Z</created>
</note>
</en-export>"""

    enex_path = tmp_path / "empty_note.enex"
    enex_path.write_text(content, encoding="utf-8")
    return enex_path


def generate_note_with_table_enex(tmp_path: Path) -> Path:
    """Generate an ENEX file with a note containing a table.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory to create the file in

    Returns
    -------
    Path
        Path to the generated ENEX file

    """
    content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export export-date="20250128T120000Z" application="Evernote" version="10.0">
<note>
  <title>Note with Table</title>
  <content><![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
  <div>This note has a table:</div>
  <table>
    <tr>
      <th>Header 1</th>
      <th>Header 2</th>
    </tr>
    <tr>
      <td>Cell 1</td>
      <td>Cell 2</td>
    </tr>
    <tr>
      <td>Cell 3</td>
      <td>Cell 4</td>
    </tr>
  </table>
</en-note>
]]></content>
  <created>20250115T100000Z</created>
  <updated>20250120T150000Z</updated>
  <tag>table</tag>
</note>
</en-export>"""

    enex_path = tmp_path / "note_with_table.enex"
    enex_path.write_text(content, encoding="utf-8")
    return enex_path
