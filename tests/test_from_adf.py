"""Tests for ADF -> Markdown conversion."""

from adflip.from_adf import adf_to_markdown


def _doc(*content):
    return {"type": "doc", "version": 1, "content": list(content)}


def _p(*inline):
    return {"type": "paragraph", "content": list(inline)}


def _text(t, marks=None):
    node = {"type": "text", "text": t}
    if marks:
        node["marks"] = marks
    return node


def _heading(level, *inline):
    return {"type": "heading", "attrs": {"level": level}, "content": list(inline)}


class TestBasicNodes:
    def test_paragraph(self):
        adf = _doc(_p(_text("Hello world")))
        assert adf_to_markdown(adf) == "Hello world"

    def test_multiple_paragraphs(self):
        adf = _doc(_p(_text("First")), _p(_text("Second")))
        assert adf_to_markdown(adf) == "First\n\nSecond"

    def test_heading(self):
        adf = _doc(_heading(1, _text("Title")))
        assert adf_to_markdown(adf) == "# Title"

    def test_heading_levels(self):
        adf = _doc(_heading(2, _text("H2")), _heading(3, _text("H3")))
        result = adf_to_markdown(adf)
        assert "## H2" in result
        assert "### H3" in result

    def test_horizontal_rule(self):
        adf = _doc(_p(_text("Before")), {"type": "rule"}, _p(_text("After")))
        result = adf_to_markdown(adf)
        assert "---" in result

    def test_code_block(self):
        adf = _doc({
            "type": "codeBlock",
            "attrs": {"language": "python"},
            "content": [_text("x = 42")],
        })
        result = adf_to_markdown(adf)
        assert "```python" in result
        assert "x = 42" in result

    def test_code_block_no_language(self):
        adf = _doc({
            "type": "codeBlock",
            "content": [_text("some code")],
        })
        result = adf_to_markdown(adf)
        assert "```\n" in result
        assert "some code" in result

    def test_blockquote(self):
        adf = _doc({"type": "blockquote", "content": [_p(_text("Quoted text"))]})
        result = adf_to_markdown(adf)
        assert "> Quoted text" in result


class TestInlineMarks:
    def test_bold(self):
        adf = _doc(_p(_text("bold", marks=[{"type": "strong"}])))
        assert "**bold**" in adf_to_markdown(adf)

    def test_italic(self):
        adf = _doc(_p(_text("italic", marks=[{"type": "em"}])))
        assert "*italic*" in adf_to_markdown(adf)

    def test_strikethrough(self):
        adf = _doc(_p(_text("struck", marks=[{"type": "strike"}])))
        assert "~~struck~~" in adf_to_markdown(adf)

    def test_inline_code(self):
        adf = _doc(_p(_text("code", marks=[{"type": "code"}])))
        assert "`code`" in adf_to_markdown(adf)

    def test_link(self):
        adf = _doc(_p(_text("click", marks=[{
            "type": "link",
            "attrs": {"href": "https://example.com"},
        }])))
        result = adf_to_markdown(adf)
        assert "[click](https://example.com)" in result

    def test_underline(self):
        adf = _doc(_p(_text("underlined", marks=[{"type": "underline"}])))
        assert "<u>underlined</u>" in adf_to_markdown(adf)


class TestLists:
    def test_bullet_list(self):
        adf = _doc({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [_p(_text("Item 1"))]},
                {"type": "listItem", "content": [_p(_text("Item 2"))]},
            ],
        })
        result = adf_to_markdown(adf)
        assert "- Item 1" in result
        assert "- Item 2" in result

    def test_ordered_list(self):
        adf = _doc({
            "type": "orderedList",
            "content": [
                {"type": "listItem", "content": [_p(_text("First"))]},
                {"type": "listItem", "content": [_p(_text("Second"))]},
            ],
        })
        result = adf_to_markdown(adf)
        assert "1. First" in result
        assert "2. Second" in result

    def test_task_list(self):
        adf = _doc({
            "type": "taskList",
            "content": [
                {"type": "taskItem", "attrs": {"state": "TODO"}, "content": [_p(_text("Todo"))]},
                {"type": "taskItem", "attrs": {"state": "DONE"}, "content": [_p(_text("Done"))]},
            ],
        })
        result = adf_to_markdown(adf)
        assert "- [ ] Todo" in result
        assert "- [x] Done" in result


class TestTable:
    def test_simple_table(self):
        adf = _doc({
            "type": "table",
            "content": [
                {"type": "tableRow", "content": [
                    {"type": "tableHeader", "content": [_p(_text("A"))]},
                    {"type": "tableHeader", "content": [_p(_text("B"))]},
                ]},
                {"type": "tableRow", "content": [
                    {"type": "tableCell", "content": [_p(_text("1"))]},
                    {"type": "tableCell", "content": [_p(_text("2"))]},
                ]},
            ],
        })
        result = adf_to_markdown(adf)
        assert "| A | B |" in result
        assert "| --- | --- |" in result
        assert "| 1 | 2 |" in result


class TestConfluenceDirectives:
    def test_panel(self):
        adf = _doc({
            "type": "panel",
            "attrs": {"panelType": "info"},
            "content": [_p(_text("Panel content"))],
        })
        result = adf_to_markdown(adf)
        assert '<!-- confluence:panel type="info" -->' in result
        assert "Panel content" in result
        assert "<!-- /confluence:panel -->" in result

    def test_expand(self):
        adf = _doc({
            "type": "expand",
            "attrs": {"title": "Details"},
            "content": [_p(_text("Hidden"))],
        })
        result = adf_to_markdown(adf)
        assert '<!-- confluence:expand title="Details" -->' in result
        assert "Hidden" in result
        assert "<!-- /confluence:expand -->" in result

    def test_status_inline(self):
        adf = _doc(_p(
            _text("Status: "),
            {"type": "status", "attrs": {"text": "Done", "color": "green"}},
        ))
        result = adf_to_markdown(adf)
        assert '<!-- confluence:status text="Done" color="green" -->' in result

    def test_mention_inline(self):
        adf = _doc(_p(
            _text("Assigned to "),
            {"type": "mention", "attrs": {"id": "abc123", "text": "@Alice"}},
        ))
        result = adf_to_markdown(adf)
        assert '<!-- confluence:mention id="abc123" text="@Alice" -->' in result

    def test_extension_self_closing(self):
        adf = _doc({
            "type": "extension",
            "attrs": {"extensionType": "com.atlassian.jira", "extensionKey": "issue"},
        })
        result = adf_to_markdown(adf)
        assert "confluence:extension" in result

    def test_bodied_extension(self):
        adf = _doc({
            "type": "bodiedExtension",
            "attrs": {"extensionType": "com.atlassian.macro", "extensionKey": "code"},
            "content": [_p(_text("Macro body"))],
        })
        result = adf_to_markdown(adf)
        assert "<!-- confluence:extension" in result
        assert "Macro body" in result
        assert "<!-- /confluence:extension -->" in result

    def test_unknown_node_preserved(self):
        adf = _doc({"type": "someFutureNode", "attrs": {"foo": "bar"}, "content": []})
        result = adf_to_markdown(adf)
        assert "confluence:adf" in result
        assert "someFutureNode" in result

    def test_external_media(self):
        adf = _doc({
            "type": "mediaSingle",
            "content": [{
                "type": "media",
                "attrs": {"url": "https://example.com/img.png", "type": "external"},
            }],
        })
        result = adf_to_markdown(adf)
        assert "![](https://example.com/img.png)" in result

    def test_confluence_hosted_media(self):
        adf = _doc({
            "type": "mediaSingle",
            "content": [{
                "type": "media",
                "attrs": {"id": "abc-123", "type": "file", "collection": "coll"},
            }],
        })
        result = adf_to_markdown(adf)
        assert "confluence:media" in result
        assert "abc-123" in result
