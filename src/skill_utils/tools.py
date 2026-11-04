"""Tool definitions in the Claude Messages API format."""

import json
import uuid


def define_tool(name: str, description: str, parameters=None):
    """Build a tool definition dict for Claude's tool use.

    Args:
        name: The tool name (must be alphanumeric + underscores).
        description: What the tool does; shown to the model as context.
        parameters: Optional JSON Schema object describing arguments.

    Returns:
        A dict ready to pass in a `tools` array to Claude API calls.
    """
    return {
        "name": name,
        "description": description,
        "input_schema": parameters or {"type": "object", "properties": {}},
    }


def list_tools(tool_defs):
    """Return the names of all defined tools."""
    return [t["name"] for t in tool_defs]


def call_tool_by_name(name: str, tool_defs, **kwargs) -> dict:
    """Look up a tool definition by name and build a `tool_use` content block for it.

    Useful when you want to invoke a named skill from code rather than the model choosing it.
    Put the returned block in an assistant message's `content`, then answer it with a
    `tool_result` block whose `tool_use_id` is the block's `id`.
    """
    for t in tool_defs:
        if t["name"] == name:
            return {
                "type": "tool_use",
                "id": f"toolu_{uuid.uuid4().hex}",
                "name": name,
                "input": kwargs,
            }
    raise ValueError(f"No tool named '{name}' found")


def _field(obj, key):
    return obj[key] if isinstance(obj, dict) else getattr(obj, key)


def get_tool_uses(response):
    """Return the `tool_use` blocks from a Claude response.

    Accepts an `anthropic` SDK Message or the equivalent dict from the raw HTTP API.
    """
    return [b for b in _field(response, "content") if _field(b, "type") == "tool_use"]


def tool_result(tool_use_id: str, content, is_error: bool = False) -> dict:
    """Build a `tool_result` block answering the `tool_use` block with id `tool_use_id`.

    `content` may be a string or a list of content blocks; anything else is sent as JSON.
    Return all results for one assistant turn together in a single user message.
    """
    if not isinstance(content, (str, list)):
        content = json.dumps(content)
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        block["is_error"] = True
    return block
