import pytest

from skill_utils import (
    MarkdownValidationError,
    format_markdown,
    parse_markdown,
    read_markdown,
    validate_markdown,
    write_markdown,
)

DOC = """---
name: demo
description: A demo
---

# Title

See [docs](https://a.com "Docs") and ![logo](logo.png) and [ref][r].

[r]: https://r.com

## Usage

- one
  - nested
- two

1. first

| a | b |
|---|---|
| 1 | 2 |

```python
print(1)
```
"""


def rules(text):
    return [e.rule for e in validate_markdown(text)[1]]


class TestParseMarkdown:
    def test_frontmatter_and_body(self):
        doc = parse_markdown(DOC)

        assert doc.frontmatter == {"name": "demo", "description": "A demo"}
        assert doc.body.startswith("# Title")

    def test_headings_with_lines_relative_to_full_text(self):
        doc = parse_markdown(DOC)

        assert [(h.level, h.text, h.line) for h in doc.headings] == [(1, "Title", 6), (2, "Usage", 12)]

    def test_links_include_resolved_references(self):
        doc = parse_markdown(DOC)

        assert [(l.text, l.url, l.title, l.line) for l in doc.links] == [
            ("docs", "https://a.com", "Docs", 8),
            ("ref", "https://r.com", "", 8),
        ]

    def test_link_text_keeps_escaped_characters(self):
        assert parse_markdown(r"[a\*b](u)").links[0].text == "a*b"

    def test_images(self):
        img = parse_markdown(DOC).images[0]

        assert (img.alt, img.src, img.title) == ("logo", "logo.png", "")

    def test_lists_nested_lists_are_separate(self):
        doc = parse_markdown(DOC)

        assert [(l.ordered, l.items) for l in doc.lists] == [
            (False, ["one", "two"]),
            (False, ["nested"]),
            (True, ["first"]),
        ]

    def test_tables(self):
        table = parse_markdown(DOC).tables[0]

        assert (table.header, table.rows, table.line) == (["a", "b"], [["1", "2"]], 20)

    def test_code_blocks_fenced_and_indented(self):
        doc = parse_markdown("```python extra\nx = 1\n```\n\n    indented\n")

        assert [(c.lang, c.code) for c in doc.code_blocks] == [("python", "x = 1\n"), ("", "indented\n")]

    def test_no_frontmatter(self):
        doc = parse_markdown("# Hi\n")

        assert doc.frontmatter == {}
        assert doc.headings[0].line == 1


class TestValidateMarkdown:
    def test_valid_document(self):
        assert validate_markdown(DOC) == (True, [])

    def test_empty_document_is_valid(self):
        assert validate_markdown("") == (True, [])

    def test_unclosed_frontmatter(self):
        valid, errors = validate_markdown("---\nname: a\n# Body\n")

        assert not valid
        assert (errors[0].rule, errors[0].line) == ("frontmatter", 1)

    def test_frontmatter_line_without_key(self):
        _, errors = validate_markdown("---\nname: a\nno colon here\n---\nBody\n")

        assert [(e.rule, e.line) for e in errors] == [("frontmatter", 3)]

    def test_frontmatter_allows_nested_values_comments_and_blanks(self):
        assert rules("---\nmetadata:\n  type: x\ntags:\n- a\n# comment\n\nname: a\n---\nBody\n") == []

    def test_unclosed_fence(self):
        _, errors = validate_markdown("Text\n\n```python\nprint(1)\n")

        assert [(e.rule, e.line) for e in errors] == [("unclosed-fence", 3)]

    def test_unclosed_fence_in_blockquote(self):
        assert rules("> ```\n> code\n\nafter\n") == ["unclosed-fence"]

    def test_closed_fences(self):
        assert rules("~~~~\ncode\n~~~~~\n\n> ```\n> x\n> ```\n") == []

    def test_unresolved_references(self):
        assert rules("[a][missing] and [b][]\n") == ["unresolved-reference", "unresolved-reference"]

    @pytest.mark.parametrize("text", [
        "[a][r]\n\n[r]: https://x.com\n",
        "`[a][b]`\n",
        r"\[a\]\[b\]" + "\n",
        "- [ ] task\n- [x] done\n",
    ])
    def test_no_false_unresolved_references(self, text):
        assert rules(text) == []

    def test_heading_skip(self):
        _, errors = validate_markdown("# A\n\n### C\n")

        assert [(e.rule, e.line) for e in errors] == [("heading-skip", 3)]

    def test_heading_going_back_up_is_fine(self):
        assert rules("## A\n\n### B\n\n# C\n\n## D\n") == []

    def test_empty_heading(self):
        assert rules("#\n") == ["empty-heading"]

    def test_empty_link_and_image(self):
        assert rules("[a]() ![b]()\n") == ["empty-link", "empty-image"]

    def test_table_column_mismatch(self):
        _, errors = validate_markdown("| a | b |\n|---|---|\n| 1 |\n| 1 | 2 | 3 |\n")

        assert [(e.rule, e.line) for e in errors] == [("table-columns", 3), ("table-columns", 4)]

    def test_table_escaped_pipe_and_no_outer_pipes(self):
        assert rules("a | b\n--|--\n`x\\|y` | 2\n") == []

    def test_error_lines_account_for_frontmatter(self):
        _, errors = validate_markdown("---\nname: a\n---\n\n# A\n### B\n")

        assert errors[0].line == 6


class TestFormatMarkdown:
    def test_reformats_body(self):
        assert format_markdown("* a\n* b\n\n\n\nText\n") == "- a\n- b\n\nText\n"

    def test_preserves_frontmatter_verbatim(self):
        text = "---\nname: 'a'\nmetadata:\n  k: v\n---\n\n* item\n"

        assert format_markdown(text) == "---\nname: 'a'\nmetadata:\n  k: v\n---\n\n- item\n"

    def test_aligns_tables(self):
        assert format_markdown("|a|b|\n|-|-|\n|1|2|\n") == "| a   | b   |\n| --- | --- |\n| 1   | 2   |\n"

    def test_idempotent(self):
        once = format_markdown(DOC)

        assert format_markdown(once) == once


class TestReadWriteMarkdown:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "doc.md"

        write_markdown(path, DOC)

        assert read_markdown(path) == DOC

    def test_write_with_format(self, tmp_path):
        path = tmp_path / "doc.md"

        write_markdown(path, "* a\n", format=True)

        assert path.read_text() == "- a\n"

    def test_write_invalid_raises_and_writes_nothing(self, tmp_path):
        path = tmp_path / "doc.md"

        with pytest.raises(MarkdownValidationError) as exc:
            write_markdown(path, "```\nunclosed\n")

        assert [e.rule for e in exc.value.errors] == ["unclosed-fence"]
        assert not path.exists()

    def test_validates_before_formatting(self, tmp_path):
        # mdformat would drop the extra cell; validation must catch it first.
        with pytest.raises(MarkdownValidationError):
            write_markdown(tmp_path / "doc.md", "|a|\n|-|\n|1|2|\n", format=True)

    def test_read_invalid_raises(self, tmp_path):
        path = tmp_path / "doc.md"
        path.write_text("# A\n\n### B\n")

        with pytest.raises(MarkdownValidationError, match=r"line 3: \[heading-skip\]"):
            read_markdown(path)

    def test_error_is_value_error(self):
        assert issubclass(MarkdownValidationError, ValueError)
