"""Round-trip tests: ADF -> Markdown -> ADF should preserve structure."""

from adflip.from_adf import adf_to_markdown
from adflip.to_adf import markdown_to_adf


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


def _find_nodes(adf, node_type):
    results = []
    if isinstance(adf, dict):
        if adf.get("type") == node_type:
            results.append(adf)
        for v in adf.values():
            results.extend(_find_nodes(v, node_type))
    elif isinstance(adf, list):
        for item in adf:
            results.extend(_find_nodes(item, node_type))
    return results


def _find_text(adf):
    if isinstance(adf, dict):
        if adf.get("type") == "text":
            return adf.get("text", "")
        return "".join(_find_text(v) for v in adf.values())
    elif isinstance(adf, list):
        return "".join(_find_text(item) for item in adf)
    return ""


class TestRoundTrip:
    """ADF -> Markdown -> ADF should preserve the semantic content."""

    def test_paragraph_roundtrip(self):
        original = _doc(_p(_text("Hello world")))
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        assert result["type"] == "doc"
        assert "Hello world" in _find_text(result)

    def test_heading_roundtrip(self):
        original = _doc(_heading(2, _text("My Heading")))
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        headings = _find_nodes(result, "heading")
        assert len(headings) >= 1
        assert headings[0]["attrs"]["level"] == 2
        assert "My Heading" in _find_text(headings[0])

    def test_bold_roundtrip(self):
        original = _doc(_p(_text("bold", marks=[{"type": "strong"}])))
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        text_nodes = _find_nodes(result, "text")
        bold_nodes = [n for n in text_nodes if any(
            m.get("type") == "strong" for m in n.get("marks", [])
        )]
        assert len(bold_nodes) >= 1

    def test_panel_roundtrip(self):
        original = _doc({
            "type": "panel",
            "attrs": {"panelType": "info"},
            "content": [_p(_text("Panel text"))],
        })
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        panels = _find_nodes(result, "panel")
        assert len(panels) == 1
        assert panels[0]["attrs"]["panelType"] == "info"
        assert "Panel text" in _find_text(panels[0])

    def test_expand_roundtrip(self):
        original = _doc({
            "type": "expand",
            "attrs": {"title": "Click me"},
            "content": [_p(_text("Expanded content"))],
        })
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        expands = _find_nodes(result, "expand")
        assert len(expands) == 1
        assert expands[0]["attrs"]["title"] == "Click me"
        assert "Expanded content" in _find_text(expands[0])

    def test_status_roundtrip(self):
        original = _doc(_p(
            _text("Status: "),
            {"type": "status", "attrs": {"text": "In Progress", "color": "blue"}},
        ))
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        statuses = _find_nodes(result, "status")
        assert len(statuses) >= 1
        assert statuses[0]["attrs"]["text"] == "In Progress"
        assert statuses[0]["attrs"]["color"] == "blue"

    def test_code_block_roundtrip(self):
        original = _doc({
            "type": "codeBlock",
            "attrs": {"language": "python"},
            "content": [_text("x = 1")],
        })
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        blocks = _find_nodes(result, "codeBlock")
        assert len(blocks) >= 1
        assert "x = 1" in _find_text(blocks[0])

    def test_mixed_content_roundtrip(self):
        """A realistic page with headings, text, a panel, and a code block."""
        original = _doc(
            _heading(1, _text("Setup Guide")),
            _p(_text("Follow these steps to get started.")),
            {
                "type": "panel",
                "attrs": {"panelType": "warning"},
                "content": [_p(_text("Make sure you have Python 3.10+"))],
            },
            {
                "type": "codeBlock",
                "attrs": {"language": "bash"},
                "content": [_text("pip install adflip")],
            },
        )
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        assert "Setup Guide" in _find_text(result)
        assert "Follow these steps" in _find_text(result)
        panels = _find_nodes(result, "panel")
        assert len(panels) == 1
        assert panels[0]["attrs"]["panelType"] == "warning"
        blocks = _find_nodes(result, "codeBlock")
        assert len(blocks) >= 1

    def test_text_color_roundtrip(self):
        """textColor mark should preserve the color value through round-trip."""
        original = _doc(_p(
            _text("red text", marks=[{"type": "textColor", "attrs": {"color": "#ff0000"}}]),
        ))
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        text_nodes = _find_nodes(result, "text")
        colored = [
            n for n in text_nodes
            if any(m.get("type") == "textColor" for m in n.get("marks", []))
        ]
        assert len(colored) >= 1, f"No textColor nodes found in: {result}"
        color_mark = next(
            m for m in colored[0]["marks"] if m["type"] == "textColor"
        )
        assert color_mark["attrs"]["color"] == "#ff0000"

    def test_unknown_node_roundtrip(self):
        """Unknown ADF nodes preserved via confluence:adf should survive round-trip."""
        original = _doc({
            "type": "someFutureNode",
            "attrs": {"key": "value"},
            "content": [],
        })
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        all_types = [n.get("type") for n in result.get("content", [])]
        assert "someFutureNode" in all_types, (
            f"Expected someFutureNode in top-level types, got: {all_types}"
        )

    def test_confluence_hosted_media_roundtrip(self):
        """Confluence-hosted media (non-external) should survive round-trip."""
        original = _doc({
            "type": "mediaSingle",
            "content": [{
                "type": "media",
                "attrs": {"id": "abc-123", "type": "file", "collection": "coll"},
            }],
        })
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        media_nodes = _find_nodes(result, "media")
        assert len(media_nodes) >= 1, f"No media nodes found in: {result}"
        assert media_nodes[0]["attrs"]["id"] == "abc-123"
        assert media_nodes[0]["attrs"]["type"] == "file"

    def test_table_roundtrip(self):
        """Tables should preserve structure through round-trip."""
        original = _doc({
            "type": "table",
            "content": [
                {"type": "tableRow", "content": [
                    {"type": "tableHeader", "content": [_p(_text("Name"))]},
                    {"type": "tableHeader", "content": [_p(_text("Value"))]},
                ]},
                {"type": "tableRow", "content": [
                    {"type": "tableCell", "content": [_p(_text("foo"))]},
                    {"type": "tableCell", "content": [_p(_text("bar"))]},
                ]},
            ],
        })
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        tables = _find_nodes(result, "table")
        assert len(tables) >= 1, f"No table nodes found in: {result}"
        assert "Name" in _find_text(tables[0])
        assert "foo" in _find_text(tables[0])

    def test_horizontal_rule_roundtrip(self):
        """Horizontal rules should survive round-trip."""
        original = _doc(
            _p(_text("Before")),
            {"type": "rule"},
            _p(_text("After")),
        )
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        rules = _find_nodes(result, "rule")
        assert len(rules) >= 1
        assert "Before" in _find_text(result)
        assert "After" in _find_text(result)

    def test_bullet_list_roundtrip(self):
        """Bullet lists should survive round-trip."""
        original = _doc({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [_p(_text("Alpha"))]},
                {"type": "listItem", "content": [_p(_text("Bravo"))]},
            ],
        })
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        lists = _find_nodes(result, "bulletList")
        assert len(lists) >= 1
        items = _find_nodes(lists[0], "listItem")
        assert len(items) == 2

    def test_ordered_list_roundtrip(self):
        """Ordered lists should survive round-trip."""
        original = _doc({
            "type": "orderedList",
            "content": [
                {"type": "listItem", "content": [_p(_text("First"))]},
                {"type": "listItem", "content": [_p(_text("Second"))]},
            ],
        })
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        lists = _find_nodes(result, "orderedList")
        assert len(lists) >= 1
        items = _find_nodes(lists[0], "listItem")
        assert len(items) == 2

    def test_blockquote_roundtrip(self):
        """Blockquotes should survive round-trip."""
        original = _doc({"type": "blockquote", "content": [_p(_text("Wise words"))]})
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        quotes = _find_nodes(result, "blockquote")
        assert len(quotes) >= 1
        assert "Wise words" in _find_text(quotes[0])

    def test_extension_self_closing_roundtrip(self):
        """Self-closing extensions should survive round-trip."""
        original = _doc({
            "type": "extension",
            "attrs": {
                "extensionType": "com.atlassian.confluence.macro.core",
                "extensionKey": "status",
            },
        })
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        extensions = _find_nodes(result, "extension")
        assert len(extensions) >= 1, f"No extension nodes found in: {result}"
        assert extensions[0]["attrs"]["extensionType"] == "com.atlassian.confluence.macro.core"

    def test_bodied_extension_roundtrip(self):
        """Bodied extensions should survive round-trip."""
        original = _doc({
            "type": "bodiedExtension",
            "attrs": {
                "extensionType": "com.atlassian.macro",
                "extensionKey": "code",
            },
            "content": [_p(_text("Macro body text"))],
        })
        md = adf_to_markdown(original)
        result = markdown_to_adf(md)

        bodied = _find_nodes(result, "bodiedExtension")
        assert len(bodied) >= 1, f"No bodiedExtension nodes found in: {result}"
        assert "Macro body text" in _find_text(bodied[0])
