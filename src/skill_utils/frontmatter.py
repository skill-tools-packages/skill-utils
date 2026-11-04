"""Parse the frontmatter of SKILL.md files."""

import re


def parse_frontmatter(text):
    """Return (frontmatter dict, body). Only top-level `key: value` scalars.

    Hand-rolled rather than via PyYAML to avoid a dependency; skill frontmatter
    is flat in practice. A block that fails to parse yields {}.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return {}, text
    head = parts[0][3:]
    # Drop the rest of the closing delimiter line (e.g. a fourth dash), then leading blank lines.
    body = parts[1].partition("\n")[2].lstrip("\n")
    fm = {}
    for line in head.splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip("'\"")
    return fm, body
