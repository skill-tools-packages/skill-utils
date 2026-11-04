import pytest

from skill_utils import clean_text, extract_code_blocks, parse_json_response


class TestParseJsonResponse:
    def test_parses_with_surrounding_whitespace(self):
        assert parse_json_response('  \n{"a": [1, 2]}\n ') == {"a": [1, 2]}

    def test_scalars_and_arrays(self):
        assert parse_json_response("[1]") == [1]
        assert parse_json_response("null") is None

    def test_json_code_block(self):
        assert parse_json_response('Here you go:\n```json\n{"a": 1}\n```\nThanks') == {"a": 1}

    def test_untagged_code_block(self):
        assert parse_json_response("```\n[1, 2]\n```") == [1, 2]

    def test_skips_non_json_blocks(self):
        text = "```python\nx = {1: 2}\n```\n```json\n{\"ok\": true}\n```"

        assert parse_json_response(text) == {"ok": True}

    def test_embedded_in_prose(self):
        assert parse_json_response('The result is {"a": [1, 2]} as requested.') == {"a": [1, 2]}

    def test_skips_brackets_that_are_not_json(self):
        assert parse_json_response('Use [brackets] here: {"a": 1}') == {"a": 1}

    @pytest.mark.parametrize("bad", ["not json", "", '{"a": 1', None, "```json\n{bad}\n```"])
    def test_invalid_raises_value_error(self, bad):
        with pytest.raises(ValueError, match="Failed to parse JSON response"):
            parse_json_response(bad)


class TestExtractCodeBlocks:
    def test_extracts_language_and_code(self):
        text = "Intro\n```python\nprint('hi')\n```\nmid\n```\nplain\n```\n"

        assert extract_code_blocks(text) == [
            {"lang": "python", "code": "print('hi')"},
            {"lang": "text", "code": "plain"},
        ]

    def test_no_blocks(self):
        assert extract_code_blocks("no code here") == []

    def test_multiline_code_stripped(self):
        [block] = extract_code_blocks("```js\n\n  a();\n  b();\n\n```")

        assert block["code"] == "a();\n  b();"

    @pytest.mark.parametrize("lang", ["c++", "objective-c", "c#"])
    def test_language_with_symbols(self, lang):
        assert extract_code_blocks(f"```{lang}\nint x;\n```") == [{"lang": lang, "code": "int x;"}]

    def test_info_string_after_language_ignored(self):
        assert extract_code_blocks('```python title="a.py"\nx = 1\n```') == [{"lang": "python", "code": "x = 1"}]

    def test_inline_triple_backticks_not_a_block(self):
        assert extract_code_blocks("use ```x``` inline\nmore") == []


class TestCleanText:
    def test_strips_trailing_whitespace_per_line(self):
        assert clean_text("a   \nb\t\n") == "a\nb"

    def test_collapses_blank_lines(self):
        assert clean_text("a\n\n\n\n\nb") == "a\n\nb"

    def test_keeps_single_blank_line(self):
        assert clean_text("a\n\nb") == "a\n\nb"

    def test_strips_outer_whitespace_keeps_indentation(self):
        assert clean_text("\n\n  a\n    b\n\n") == "a\n    b"

    def test_whitespace_only_lines_count_as_blank(self):
        assert clean_text("a\n  \n \t\n  \nb") == "a\n\nb"
