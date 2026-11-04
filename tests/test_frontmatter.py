from skill_utils import parse_frontmatter


class TestParseFrontmatter:
    def test_flat_scalars(self):
        fm, body = parse_frontmatter("---\nname: a\ndescription: Does b\n---\nBody\n")

        assert fm == {"name": "a", "description": "Does b"}
        assert body == "Body\n"

    def test_quotes_stripped(self):
        fm, _ = parse_frontmatter("---\nname: 'a'\ndescription: \"b\"\n---\n")

        assert fm == {"name": "a", "description": "b"}

    def test_no_frontmatter(self):
        assert parse_frontmatter("Just body") == ({}, "Just body")

    def test_unclosed_frontmatter(self):
        assert parse_frontmatter("---\nname: a\n") == ({}, "---\nname: a\n")

    def test_nested_lines_ignored(self):
        fm, _ = parse_frontmatter("---\nname: a\nmetadata:\n  type: x\n---\nBody")

        assert fm == {"name": "a", "metadata": ""}

    def test_body_keeps_horizontal_rules(self):
        _, body = parse_frontmatter("---\nname: a\n---\nPart one\n\n---\n\nPart two\n")

        assert body == "Part one\n\n---\n\nPart two\n"

    def test_body_starting_with_bullet_keeps_dash(self):
        _, body = parse_frontmatter("---\nname: a\n---\n- first\n- second\n")

        assert body == "- first\n- second\n"

    def test_leading_blank_lines_and_long_delimiter(self):
        _, body = parse_frontmatter("---\nname: a\n----\n\n\nBody\n")

        assert body == "Body\n"

    def test_frontmatter_only(self):
        assert parse_frontmatter("---\nname: a\n---") == ({"name": "a"}, "")
