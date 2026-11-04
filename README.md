# skill-utils

A collection of helpful tools and functions for use with Claude skills

```
pip install --index-url https://dl.cloudsmith.io/public/skill-tools/python/python/simple/ skill-utils
```

## Markdown

Read, write, parse, format, and validate markdown (CommonMark plus GFM tables and strikethrough).

```python
from skill_utils import (
    parse_markdown, validate_markdown, format_markdown,
    read_markdown, write_markdown, MarkdownValidationError,
)

doc = parse_markdown(text)
doc.frontmatter                     # {"name": "...", ...}
doc.headings[0]                     # Heading(level=1, text="Title", line=6)
# also: doc.body, code_blocks, links, images, lists, tables (each element has a 1-based line)

valid, errors = validate_markdown(text)
for e in errors:
    print(e.line, e.rule, e.message)

pretty = format_markdown(text)      # mdformat; frontmatter is preserved verbatim

text = read_markdown("SKILL.md")    # raises MarkdownValidationError if invalid
write_markdown("SKILL.md", text, format=True)  # validates, optionally formats, then writes
```

`MarkdownValidationError` is a `ValueError`; its `.errors` attribute holds the list of failures.

### Validation rules

| Rule | Fails when |
| --- | --- |
| `frontmatter` | Frontmatter opens with `---` but never closes, or a top-level line isn't `key: value` (indented lines and `- item` lists are allowed) |
| `unclosed-fence` | A ```` ``` ```` or `~~~` code fence has no closing fence |
| `unresolved-reference` | `[text][ref]` or `[ref][]` has no `[ref]: url` definition |
| `heading-skip` | A heading jumps more than one level deeper (e.g. `#` then `###`) |
| `empty-heading` | A heading has no text |
| `empty-link` / `empty-image` | A link or image has an empty URL |
| `table-columns` | A table row has a different number of cells than the header |

Not checked: bare shortcut references like `[ref]`, since task lists and literal brackets would false-positive. Link and image line numbers point to the start of their containing paragraph.

`write_markdown` validates *before* formatting, because mdformat would otherwise silently close unclosed fences and drop extra table cells.
