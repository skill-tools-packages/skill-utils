"""Read, write, parse, format, and validate markdown (CommonMark + GFM tables/strikethrough)."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import mdformat
from markdown_it import MarkdownIt

from .frontmatter import parse_frontmatter

# text_join off keeps backslash escapes as separate `text_special` tokens, so `\[a\]\[b\]` isn't
# mistaken for an unresolved reference.
_md = MarkdownIt("commonmark").enable(["table", "strikethrough"]).disable("text_join")

# Full `[text][ref]` and collapsed `[ref][]` forms. Shortcut `[ref]` is skipped: too many false
# positives (task-list boxes, literal brackets in prose).
_UNRESOLVED_REF = re.compile(r"!?\[([^\[\]]+)\]\[([^\[\]]*)\]")
_CONTAINER_PREFIX = re.compile(r"^[\s>]*")


@dataclass
class Heading:
    level: int
    text: str
    line: int


@dataclass
class CodeBlock:
    lang: str  # "" for untagged or indented blocks
    code: str
    line: int


@dataclass
class Link:
    text: str
    url: str
    title: str
    line: int


@dataclass
class Image:
    alt: str
    src: str
    title: str
    line: int


@dataclass
class ListBlock:
    ordered: bool
    items: list  # text of each item's first paragraph; nested lists are their own ListBlock
    line: int


@dataclass
class Table:
    header: list
    rows: list
    line: int


@dataclass
class MarkdownDocument:
    frontmatter: dict
    body: str
    headings: list = field(default_factory=list)
    code_blocks: list = field(default_factory=list)
    links: list = field(default_factory=list)
    images: list = field(default_factory=list)
    lists: list = field(default_factory=list)
    tables: list = field(default_factory=list)


@dataclass
class ValidationError:
    rule: str
    line: int
    message: str


class MarkdownValidationError(ValueError):
    """Raised by read/write when content fails validation; `.errors` holds the details."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("Invalid markdown:\n" + "\n".join(f"  line {e.line}: [{e.rule}] {e.message}" for e in errors))


def _split(text):
    """Return (frontmatter dict, raw frontmatter block, body, line offset of body)."""
    fm, body = parse_frontmatter(text)
    head = text[: len(text) - len(body)]
    return fm, head, body, head.count("\n")


def _inline_text(children):
    return "".join(c.content for c in children if c.type in ("text", "text_special", "code_inline", "softbreak"))


def parse_markdown(text):
    """Parse markdown into a MarkdownDocument. Line numbers are 1-based in `text`.

    Links and images report the line their containing block starts on.
    """
    fm, _, body, offset = _split(text)
    doc = MarkdownDocument(frontmatter=fm, body=body)
    tokens = _md.parse(body)
    list_stack, table, row = [], None, None

    for i, tok in enumerate(tokens):
        line = tok.map[0] + offset + 1 if tok.map else None
        if tok.type == "heading_open":
            doc.headings.append(Heading(int(tok.tag[1]), tokens[i + 1].content.strip(), line))
        elif tok.type in ("fence", "code_block"):
            doc.code_blocks.append(CodeBlock(tok.info.strip().split(" ")[0], tok.content, line))
        elif tok.type in ("bullet_list_open", "ordered_list_open"):
            list_stack.append(ListBlock(tok.type == "ordered_list_open", [], line))
            doc.lists.append(list_stack[-1])
        elif tok.type in ("bullet_list_close", "ordered_list_close"):
            list_stack.pop()
        elif tok.type == "list_item_open":
            list_stack[-1].items.append("")
        elif tok.type == "table_open":
            table = Table([], [], line)
            doc.tables.append(table)
        elif tok.type == "tr_open":
            row = []
        elif tok.type == "tr_close":
            if table.header:
                table.rows.append(row)
            else:
                table.header = row
        elif tok.type == "inline":
            if tokens[i - 1].type in ("th_open", "td_open"):
                row.append(tok.content.strip())
            elif list_stack and tokens[i - 2].type == "list_item_open":
                list_stack[-1].items[-1] = tok.content.strip()
            _collect_links(tok, line, doc)
    return doc


def _collect_links(inline, line, doc):
    children = inline.children or []
    for j, c in enumerate(children):
        if c.type == "image":
            doc.images.append(Image(c.content, c.attrGet("src") or "", c.attrGet("title") or "", line))
        elif c.type == "link_open":
            end = next(k for k in range(j, len(children)) if children[k].type == "link_close")
            doc.links.append(Link(_inline_text(children[j + 1 : end]), c.attrGet("href") or "", c.attrGet("title") or "", line))


def validate_markdown(text):
    """Check markdown for structural problems. Returns (is_valid, list of ValidationError).

    Checks: frontmatter is closed and its top-level lines are `key: value`; code fences are
    closed; `[text][ref]` links resolve; heading levels don't skip; headings, link URLs and image
    sources aren't empty; table rows have as many cells as the header.
    """
    errors = []
    fm, head, body, offset = _split(text)

    if text.startswith("---") and not head:
        errors.append(ValidationError("frontmatter", 1, "Frontmatter opened with --- but never closed"))
    for n, ln in enumerate(head.split("\n---", 1)[0].splitlines()[1:], start=2):
        # Indented lines and `- item` lines are nested YAML values (mappings, block sequences).
        if ln.strip() and not ln[0].isspace() and not ln.startswith(("#", "-")) and not re.match(r"^[A-Za-z0-9_-]+:", ln):
            errors.append(ValidationError("frontmatter", n, f"Expected `key: value`, got {ln!r}"))

    lines = body.splitlines()
    tokens = _md.parse(body)
    prev_level = None
    for i, tok in enumerate(tokens):
        line = tok.map[0] + offset + 1 if tok.map else None
        if tok.type == "fence" and not _fence_closed(tok, lines):
            errors.append(ValidationError("unclosed-fence", line, f"Code fence {tok.markup} is never closed"))
        elif tok.type == "heading_open":
            level = int(tok.tag[1])
            if prev_level and level > prev_level + 1:
                errors.append(ValidationError("heading-skip", line, f"Heading jumps from h{prev_level} to h{level}"))
            if not tokens[i + 1].content.strip():
                errors.append(ValidationError("empty-heading", line, "Heading has no text"))
            prev_level = level
        elif tok.type == "table_open":
            errors.extend(_check_table(lines[tok.map[0] : tok.map[1]], line))
        elif tok.type == "inline":
            errors.extend(_check_inline(tok, line))
    return not errors, errors


def _fence_closed(tok, lines):
    start, end = tok.map
    if end - start < 2:
        return False
    last = _CONTAINER_PREFIX.sub("", lines[end - 1]).rstrip()
    ch = tok.markup[0]
    return bool(re.fullmatch(re.escape(ch) + "{%d,}" % len(tok.markup), last))


def _cell_count(row):
    row = _CONTAINER_PREFIX.sub("", row).strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
    return len(re.split(r"(?<!\\)\|", row))


def _check_table(rows, line):
    expected = _cell_count(rows[0])
    return [
        ValidationError("table-columns", line + n, f"Row has {count} cells, header has {expected}")
        for n, row in enumerate(rows)
        if n != 1 and (count := _cell_count(row)) != expected
    ]


def _check_inline(inline, line):
    errors = []
    # Join text runs only, so code spans and real links can't produce false matches.
    text = "\x00".join(c.content if c.type == "text" else "" for c in inline.children or [])
    for m in _UNRESOLVED_REF.finditer(text):
        errors.append(ValidationError("unresolved-reference", line, f"Reference {m.group(0)!r} has no definition"))
    for c in inline.children or []:
        if c.type == "link_open" and not c.attrGet("href"):
            errors.append(ValidationError("empty-link", line, "Link has an empty URL"))
        elif c.type == "image" and not c.attrGet("src"):
            errors.append(ValidationError("empty-image", line, "Image has an empty source"))
    return errors


def format_markdown(text):
    """Reformat markdown with mdformat. Frontmatter is preserved verbatim."""
    _, head, body, _ = _split(text)
    return head + mdformat.text(body, extensions={"gfm"})


def read_markdown(path):
    """Read a markdown file, raising MarkdownValidationError if it fails validation."""
    text = Path(path).read_text(encoding="utf-8")
    valid, errors = validate_markdown(text)
    if not valid:
        raise MarkdownValidationError(errors)
    return text


def write_markdown(path, text, format=False):
    """Validate (and optionally format) markdown, then write it to `path`.

    Validation runs on the input before formatting, because mdformat would otherwise silently
    close unclosed fences and drop extra table cells.
    """
    valid, errors = validate_markdown(text)
    if not valid:
        raise MarkdownValidationError(errors)
    if format:
        text = format_markdown(text)
    Path(path).write_text(text, encoding="utf-8")
