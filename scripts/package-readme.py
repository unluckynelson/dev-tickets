#!/usr/bin/env python3
"""Write the root README into a package folder for PyPI / npm, with absolute links.

The root README is the one the packages should show, but it links its screenshots and
docs relatively (docs/screenshots/board.png), which PyPI and npmjs cannot resolve: they
render the README away from the repository. Run by the release workflow just before
building, never committed.

    python3 scripts/package-readme.py python v1.4.2
    python3 scripts/package-readme.py nuxt v1.4.2
"""

import re
import sys
from pathlib import Path

REPO = "unluckynelson/dev-tickets"
ROOT = Path(__file__).resolve().parent.parent


def absolute(markdown: str, ref: str) -> str:
    raw = f"https://raw.githubusercontent.com/{REPO}/{ref}/"
    blob = f"https://github.com/{REPO}/blob/{ref}/"

    def fix(url: str) -> str:
        if re.match(r"^([a-z]+:|#|/)", url):
            return url  # absolute, an anchor, or site-rooted
        is_image = re.search(r"\.(png|jpe?g|gif|svg|webp)$", url, re.I)
        return (raw if is_image else blob) + url

    markdown = re.sub(r"(\]\()([^)\s]+)", lambda m: m.group(1) + fix(m.group(2)), markdown)
    markdown = re.sub(r'(src=")([^"]+)', lambda m: m.group(1) + fix(m.group(2)), markdown)
    return markdown


def main() -> None:
    package, ref = sys.argv[1], sys.argv[2]
    text = absolute((ROOT / "README.md").read_text(encoding="utf-8"), ref)
    (ROOT / package / "README.md").write_text(text, encoding="utf-8")
    print(f"wrote {package}/README.md with links pinned to {ref}")


if __name__ == "__main__":
    main()
