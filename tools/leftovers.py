"""Показывает строковые литералы, ещё не переведённые на t("...")."""

import io
import re
import sys

SKIP_PREFIX = ("pygame.", "self.", "Menu", "os.", "C.", "Level", "Item",
                "Actor", "Player", "KEYMAP", "TITLE", "http", "%", "#", "/")


def main(paths):
    pat = re.compile(r"""(?<![\w.])(["'])([A-Za-z][^"'\\\n]{4,}?)\1""")
    for path in paths:
        src = io.open(path, encoding="utf-8").read()
        print("=" * 60)
        print(path)
        seen = set()
        for i, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"') and stripped.endswith('"'):
                continue
            for m in pat.finditer(line):
                val = m.group(2)
                if val.startswith(SKIP_PREFIX):
                    continue
                if any(val in x for x in ("def ", "import ")):
                    continue
                if val in seen:
                    continue
                seen.add(val)
                print(f"  {i:5d}: {val}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["game/app.py"])
