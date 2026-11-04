"""Parse and extract structured data from Claude's text responses."""

import json


def parse_json_response(text):
    """Parse JSON out of a model response.

    Tries, in order: the whole text, each ```json or untagged code block, and the
    first JSON object or array embedded in prose. Raises ValueError if none parse.
    """
    if not isinstance(text, str):
        raise ValueError(f"Failed to parse JSON response: expected str, got {type(text).__name__}")

    blocks = [b["code"] for b in extract_code_blocks(text) if b["lang"] in ("json", "text")]
    for candidate in (text, *blocks):
        try:
            return json.loads(candidate.strip())
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                return decoder.raw_decode(text, i)[0]
            except json.JSONDecodeError:
                continue
    raise ValueError("Failed to parse JSON response: no valid JSON found")


def extract_code_blocks(text):
    """Extract all ```code``` blocks from markdown text.

    Returns a list of dicts with 'lang' and 'code'.
    Useful when Claude returns code snippets inside prose.
    """
    import re
    pattern = r"```([^\s`]*)[^\n`]*\n(.*?)```"
    matches = re.findall(pattern, text, flags=re.DOTALL)
    return [{"lang": lang or "text", "code": code.strip()} for lang, code in matches]


def clean_text(text):
    """Strip excessive whitespace from model output."""
    import re
    lines = [l.rstrip() for l in text.split("\n")]
    result = "\n".join(lines).strip()
    # Collapse multiple blank lines into one
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result