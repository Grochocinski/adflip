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
