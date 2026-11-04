"""Prompt template utilities for Claude skills."""

import html
import re

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def format_prompt(template: str, **kwargs) -> str:
    """Interpolate variables into a prompt template.

    Replaces `{name}` placeholders that have a matching keyword argument and leaves every
    other brace untouched, so JSON or code examples in the template need no escaping.
    Placeholders without a matching argument are left as-is. Example:
        format_prompt("Hello {name}, you are a {role}.", name="Alice", role="doctor")
    """
    return _PLACEHOLDER.sub(
        lambda m: str(kwargs[m.group(1)]) if m.group(1) in kwargs else m.group(0), template
    )


def wrap_tag(name: str, content: str, **attrs) -> str:
    """Wrap content in an XML tag, e.g. `<document source="a.md">...</document>`.

    Attribute values are escaped; content is inserted verbatim.
    """
    attr_text = "".join(f' {k}="{html.escape(str(v), quote=True)}"' for k, v in attrs.items())
    body = content.strip("\n")
    return f"<{name}{attr_text}>\n{body}\n</{name}>"


def build_system_message(role, instructions=None):
    """Create a system prompt text block; pass it as `system=[...]` to Claude API calls."""
    msg = {"type": "text", "text": f"You are {role}."}
    if instructions:
        msg["text"] += "\n\n" + instructions.strip()
    return msg