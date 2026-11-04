from skill_utils import build_system_message, format_prompt, wrap_tag


def test_format_prompt_interpolates():
    assert format_prompt("Hello {name}, a {role}.", name="Alice", role="doctor") == "Hello Alice, a doctor."


def test_format_prompt_leaves_unknown_placeholders():
    assert format_prompt("Hello {name}") == "Hello {name}"


def test_format_prompt_json_example_needs_no_escaping():
    template = 'Reply as {"answer": "..."} about {topic}.'

    assert format_prompt(template, topic="cats") == 'Reply as {"answer": "..."} about cats.'


def test_format_prompt_non_string_values():
    assert format_prompt("{n} items", n=3) == "3 items"


def test_format_prompt_values_not_reinterpolated():
    assert format_prompt("{a}", a="{b}", b="x") == "{b}"


def test_system_message_role_only():
    assert build_system_message("a helpful assistant") == {"type": "text", "text": "You are a helpful assistant."}


def test_system_message_appends_stripped_instructions():
    msg = build_system_message("a reviewer", "  Be terse.\n")

    assert msg["text"] == "You are a reviewer.\n\nBe terse."


def test_system_message_empty_instructions_ignored():
    assert build_system_message("x", "")["text"] == "You are x."


def test_wrap_tag():
    assert wrap_tag("document", "\nBody text\n") == "<document>\nBody text\n</document>"


def test_wrap_tag_attributes_escaped():
    out = wrap_tag("document", "x", source='a "b" & <c>.md', index=1)

    assert out.startswith('<document source="a &quot;b&quot; &amp; &lt;c&gt;.md" index="1">\n')


def test_wrap_tag_content_verbatim():
    assert wrap_tag("code", "  if a < b:\n    pass") == "<code>\n  if a < b:\n    pass\n</code>"
