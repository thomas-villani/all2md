"""Dump / grep parts of a .docx.

    uv run python dumpx.py FILE.docx [part] [--grep PATTERN] [--ctx N] [--pretty]

part defaults to word/document.xml. --grep prints matching windows.
No args after file: lists the zip members.
"""

import re
import sys
import zipfile


def main() -> int:
    path = sys.argv[1]
    args = sys.argv[2:]
    z = zipfile.ZipFile(path)
    if not args:
        for n in z.namelist():
            print(n)
        return 0
    part = args[0]
    rest = args[1:]
    data = z.read(part).decode("utf-8")
    pretty = "--pretty" in rest
    if pretty:
        data = re.sub(r"><", ">\n<", data)
        rest = [r for r in rest if r != "--pretty"]
    if rest and rest[0] == "--grep":
        pat = rest[1]
        ctx = int(rest[3]) if len(rest) > 3 and rest[2] == "--ctx" else 200
        hits = list(re.finditer(pat, data))
        print(f"# {len(hits)} match(es) for {pat!r} in {part}")
        for m in hits[:40]:
            s = max(0, m.start() - ctx)
            e = min(len(data), m.end() + ctx)
            print("---")
            print(data[s:e])
    else:
        print(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
