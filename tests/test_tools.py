import pytest

from types import SimpleNamespace as NS

from skill_utils import call_tool_by_name, define_tool, get_tool_uses, list_tools, tool_result


def test_define_tool_defaults_to_empty_parameters():
    tool = define_tool("get_weather", "Look up weather")

    assert tool == {
        "name": "get_weather",
        "description": "Look up weather",
        "input_schema": {"type": "object", "properties": {}},
    }


def test_define_tool_uses_given_schema():
    schema = {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}

    assert define_tool("t", "d", schema)["input_schema"] is schema


def test_default_parameters_not_shared_between_tools():
    a, b = define_tool("a", "d"), define_tool("b", "d")
    a["input_schema"]["properties"]["x"] = {}

    assert b["input_schema"]["properties"] == {}


def test_list_tools_preserves_order():
    assert list_tools([define_tool("b", ""), define_tool("a", "")]) == ["b", "a"]
    assert list_tools([]) == []


def test_call_tool_by_name_builds_tool_use_block():
    tools = [define_tool("a", ""), define_tool("search", "")]
    call = call_tool_by_name("search", tools, query="cats", limit=3)

    assert call["type"] == "tool_use"
    assert call["name"] == "search"
    assert call["input"] == {"query": "cats", "limit": 3}
    assert call["id"].startswith("toolu_")


def test_call_tool_by_name_ids_are_unique():
    tools = [define_tool("a", "")]

    assert call_tool_by_name("a", tools)["id"] != call_tool_by_name("a", tools)["id"]


def test_call_tool_by_name_unknown_tool():
    with pytest.raises(ValueError, match="No tool named 'nope'"):
        call_tool_by_name("nope", [define_tool("a", "")])


class TestGetToolUses:
    def test_dict_response(self):
        use = {"type": "tool_use", "id": "toolu_1", "name": "a", "input": {}}
        response = {"content": [{"type": "text", "text": "hi"}, use]}

        assert get_tool_uses(response) == [use]

    def test_sdk_style_response(self):
        use = NS(type="tool_use", id="toolu_1", name="a", input={})
        response = NS(content=[NS(type="thinking", thinking=""), use, NS(type="text", text="x")])

        assert get_tool_uses(response) == [use]

    def test_no_tool_uses(self):
        assert get_tool_uses({"content": [{"type": "text", "text": "done"}]}) == []

    def test_round_trip_with_call_tool_by_name(self):
        use = call_tool_by_name("a", [define_tool("a", "")], x=1)

        assert get_tool_uses({"content": [use]}) == [use]


class TestToolResult:
    def test_string_content(self):
        assert tool_result("toolu_1", "42") == {"type": "tool_result", "tool_use_id": "toolu_1", "content": "42"}

    def test_block_list_passed_through(self):
        blocks = [{"type": "text", "text": "42"}]

        assert tool_result("toolu_1", blocks)["content"] is blocks

    def test_other_values_sent_as_json(self):
        assert tool_result("toolu_1", {"temp": 21})["content"] == '{"temp": 21}'
        assert tool_result("toolu_1", 7)["content"] == "7"

    def test_error_flag(self):
        assert tool_result("toolu_1", "boom", is_error=True)["is_error"] is True
        assert "is_error" not in tool_result("toolu_1", "ok")
